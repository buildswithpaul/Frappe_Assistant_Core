# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

import unittest
from unittest.mock import patch

import frappe
from frappe.utils import add_to_date, now_datetime

from frappe_assistant_core.chat import home_signals
from frappe_assistant_core.chat.home_signals import approvals_for_user
from frappe_assistant_core.plugins.core.tools import get_pending_approvals as approvals_tool
from frappe_assistant_core.plugins.core.tools.get_pending_approvals import (
    GetPendingApprovals,
    actionable_states,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest

APPROVER_ROLE = "System Manager"


class ApprovalTestCase(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("approver", roles=(APPROVER_ROLE,))

    def _todo(self, role: str | None = None) -> str:
        # Production path: a user assigns a ToDo to themselves.
        return (
            frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "description": "approval signal test",
                    "allocated_to": self.user,
                    "assigned_by": self.user,
                    "role": role,
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def _open_action(
        self, todo: str, role: str | None = APPROVER_ROLE, user: str | None = None, state: str = "Pending"
    ) -> str:
        # Manufactured: production creates these rows when a document enters a workflow state.
        # A Workflow is not created here: inserting one adds a Custom Field by DDL, which commits.
        action = frappe.get_doc(
            {
                "doctype": "Workflow Action",
                "status": "Open",
                "reference_doctype": "ToDo",
                "reference_name": todo,
                "workflow_state": state,
                "user": user,
                "permitted_roles": [{"role": role}] if role else [],
            }
        )
        return action.insert(ignore_permissions=True).name

    def _waiting(self) -> list[str]:
        return approvals_for_user(self.user).get("ToDo", [])

    def _run_tool_as_user(self, **arguments) -> dict:
        previous = frappe.session.user
        self.addCleanup(frappe.set_user, previous)
        frappe.set_user(self.user)
        return GetPendingApprovals().execute({"doctype": "ToDo", "include_actions": False, **arguments})


class TestHomeSignalApprovals(ApprovalTestCase):
    def test_u1_counts_actions_for_users_role(self):
        before = len(self._waiting())
        todo = self._todo()
        self._open_action(todo)
        self.assertIn(todo, self._waiting())
        result = home_signals._approvals_waiting(self.user, None)
        self.assertEqual(result.count, before + 1)
        self.assertEqual(result.title, "approval waiting for you")
        self.assertEqual(result.source, "Workflow · ToDo")

    def test_u1_ignores_actions_for_other_roles(self):
        todo = self._todo()
        self._open_action(todo, role="Accounts Manager")
        self.assertNotIn(todo, self._waiting())

    def test_u1_excludes_documents_hidden_by_user_permission(self):
        todo = self._todo(role="Sales User")
        self._open_action(todo)
        self.assertIn(todo, self._waiting())
        count = home_signals._approvals_waiting(self.user, None).count
        # Manufactured: production reaches this when an administrator restricts the user to
        # one Role value through a User Permission; ToDo.role is a Link to Role that
        # enforces User Permissions (allocated_to ignores them).
        frappe.get_doc(
            {"doctype": "User Permission", "user": self.user, "allow": "Role", "for_value": "Accounts User"}
        ).insert(ignore_permissions=True)
        frappe.clear_cache(user=self.user)

        self.assertNotIn(todo, self._waiting())
        hidden = home_signals._approvals_waiting(self.user, None)
        self.assertEqual(hidden.count if hidden else 0, count - 1)

    def test_u1_respects_limit(self):
        for _i in range(3):
            self._open_action(self._todo())
        self.assertEqual(len(approvals_for_user(self.user, limit=1)["ToDo"]), 1)

    def test_u1_is_first_in_catalogue(self):
        self.assertEqual(home_signals.CATALOGUE[0].id, "approvals")

    def test_pending_approvals_tool_output_unchanged(self):
        todo = self._todo()
        self._open_action(todo, role=None, user=self.user)
        previous = frappe.session.user
        self.addCleanup(frappe.set_user, previous)
        frappe.set_user(self.user)

        result = GetPendingApprovals().execute({"doctype": "ToDo", "include_actions": False})

        self.assertEqual(
            set(result),
            {"success", "total_pending", "doctypes_with_pending", "pending_approvals", "message"},
        )
        entries = {e["document_name"]: e for e in result["pending_approvals"]["ToDo"]}
        self.assertEqual(result["total_pending"], len(entries))
        self.assertEqual(result["doctypes_with_pending"], ["ToDo"])
        self.assertEqual(
            set(entries[todo]), {"document_name", "workflow_state", "permitted_roles", "creation"}
        )

    def test_pending_approvals_tool_hides_documents_blocked_by_user_permission(self):
        hidden = self._todo(role="Sales User")
        visible = self._todo(role="Accounts User")
        self._open_action(hidden, role=None, user=self.user)
        self._open_action(visible, role=None, user=self.user)
        # Manufactured: production reaches this when an administrator restricts the user to
        # one Role value through a User Permission; ToDo.role is a Link to Role that
        # enforces User Permissions (allocated_to ignores them).
        frappe.get_doc(
            {"doctype": "User Permission", "user": self.user, "allow": "Role", "for_value": "Accounts User"}
        ).insert(ignore_permissions=True)
        frappe.clear_cache(user=self.user)

        result = self._run_tool_as_user()

        names = {e["document_name"] for e in result["pending_approvals"].get("ToDo", [])}
        self.assertNotIn(hidden, names)
        self.assertIn(visible, names)
        self.assertEqual(result["total_pending"], len(names))
        self.assertEqual(
            set(result),
            {"success", "total_pending", "doctypes_with_pending", "pending_approvals", "message"},
        )

    def test_pending_approvals_tool_fills_the_limit_past_hidden_rows(self):
        readable = self._todo(role="Accounts User")
        self._open_action(readable, role=None, user=self.user)
        # Manufactured: production reaches this when newer approvals are hidden from the user;
        # the readable action is aged so the hidden ones sort ahead of it.
        frappe.db.set_value(
            "Workflow Action",
            {"reference_name": readable},
            "creation",
            add_to_date(now_datetime(), days=-2),
            update_modified=False,
        )
        for _i in range(4):
            self._open_action(self._todo(role="Sales User"), role=None, user=self.user)
        # Manufactured: production reaches this when an administrator restricts the user to
        # one Role value through a User Permission (ToDo.role enforces it).
        frappe.get_doc(
            {"doctype": "User Permission", "user": self.user, "allow": "Role", "for_value": "Accounts User"}
        ).insert(ignore_permissions=True)
        frappe.clear_cache(user=self.user)

        # A small page forces the scan past the hidden rows; production pages are 100+ rows.
        with patch.object(approvals_tool, "MIN_PAGE_SIZE", 3):
            result = self._run_tool_as_user(limit=1)

        self.assertEqual(result["total_pending"], 1)
        self.assertEqual([e["document_name"] for e in result["pending_approvals"]["ToDo"]], [readable])

    def test_pending_approvals_tool_skips_a_doctype_the_user_cannot_read(self):
        outsider = self.make_throwaway_user("outsider")
        log = frappe.get_doc({"doctype": "Error Log", "method": "approval test", "error": "x"}).insert(
            ignore_permissions=True
        )
        # Manufactured: production creates these rows when a document enters a workflow state;
        # a user holding no role on Error Log can still be named as the action's user.
        frappe.get_doc(
            {
                "doctype": "Workflow Action",
                "status": "Open",
                "reference_doctype": "Error Log",
                "reference_name": log.name,
                "workflow_state": "Pending",
                "user": outsider,
            }
        ).insert(ignore_permissions=True)
        previous = frappe.session.user
        self.addCleanup(frappe.set_user, previous)
        frappe.set_user(outsider)

        result = GetPendingApprovals().execute({"doctype": "Error Log", "include_actions": False})

        self.assertTrue(result["success"])
        self.assertEqual(result["total_pending"], 0)
        self.assertEqual(result["pending_approvals"], {})


def _purchase_order_workflow() -> "frappe.model.document.Document":
    """The shape of a common approval workflow: once approved, the only step left is Cancel."""
    return frappe.get_doc(
        {
            "doctype": "Workflow",
            "workflow_name": "Approval test",
            "document_type": "ToDo",
            "workflow_state_field": "workflow_state",
            "states": [
                {"state": "Draft", "doc_status": "0", "allow_edit": APPROVER_ROLE},
                {"state": "Pending", "doc_status": "0", "allow_edit": APPROVER_ROLE},
                {"state": "Approved", "doc_status": "1", "allow_edit": APPROVER_ROLE},
                {"state": "Rejected", "doc_status": "0", "allow_edit": APPROVER_ROLE},
                {"state": "Cancelled", "doc_status": "2", "allow_edit": APPROVER_ROLE},
                {"state": "Archived", "doc_status": "0", "allow_edit": APPROVER_ROLE, "is_optional_state": 1},
            ],
            "transitions": [
                {"state": "Draft", "action": "Archive", "next_state": "Archived", "allowed": APPROVER_ROLE},
                {"state": "Pending", "action": "Approve", "next_state": "Approved", "allowed": APPROVER_ROLE},
                {"state": "Pending", "action": "Reject", "next_state": "Rejected", "allowed": APPROVER_ROLE},
                {
                    "state": "Approved",
                    "action": "Cancel",
                    "next_state": "Cancelled",
                    "allowed": APPROVER_ROLE,
                },
            ],
        }
    )


class TestCancelOnlyApprovals(ApprovalTestCase):
    """Redmine #34441: a document whose only step left is Cancel is not waiting for approval."""

    def test_actionable_states_drop_cancel_only_and_optional_only_states(self):
        self.assertEqual(actionable_states(_purchase_order_workflow()), {"Pending"})

    def _with_workflow(self):
        # Manufactured: production reaches this when an active Workflow exists for the doctype.
        # Inserting one adds a Custom Field by DDL, which commits, so the lookup is patched instead.
        patcher = patch.object(
            approvals_tool, "active_workflow", autospec=True, return_value=_purchase_order_workflow()
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _action_in_state(self, state: str) -> str:
        todo = self._todo()
        self._open_action(todo, state=state)
        return todo

    def test_card_skips_document_whose_only_step_is_cancel(self):
        self._with_workflow()
        approved = self._action_in_state("Approved")
        pending = self._action_in_state("Pending")

        waiting = self._waiting()

        self.assertNotIn(approved, waiting)
        self.assertIn(pending, waiting)

    def test_tool_skips_document_whose_only_step_is_cancel(self):
        self._with_workflow()
        approved = self._action_in_state("Approved")
        pending = self._action_in_state("Pending")

        result = self._run_tool_as_user()

        names = {e["document_name"] for e in result["pending_approvals"].get("ToDo", [])}
        self.assertNotIn(approved, names)
        self.assertIn(pending, names)

    def test_doctype_without_an_active_workflow_is_still_counted(self):
        todo = self._todo()
        self._open_action(todo)
        self.assertIn(todo, self._waiting())


class TestApprovalTotals(ApprovalTestCase):
    """Redmine #34441: the answer reports the same total the card shows, even when it lists fewer."""

    def test_tool_total_counts_past_its_listing_limit(self):
        todos = [self._todo() for _i in range(3)]
        for todo in todos:
            self._open_action(todo, role=None, user=self.user)
        card = len(self._waiting())

        result = self._run_tool_as_user(limit=1)

        self.assertEqual(result["total_pending"], card)
        self.assertEqual(result["listed"], 1)
        self.assertEqual(len(result["pending_approvals"]["ToDo"]), 1)

    def test_tool_lists_each_document_once(self):
        todo = self._todo()
        self._open_action(todo, role=None, user=self.user)
        self._open_action(todo, role=None, user=self.user)

        result = self._run_tool_as_user()

        names = [e["document_name"] for e in result["pending_approvals"]["ToDo"]]
        self.assertEqual(names.count(todo), 1)
        self.assertEqual(result["total_pending"], len(names))


class TestWaitedDetail(unittest.TestCase):
    def test_today_singular_and_plural_are_whole_sentences(self):
        self.assertEqual(home_signals._waited_detail("ToDo", 0), "Mostly ToDo; the oldest arrived today.")
        self.assertEqual(home_signals._waited_detail("ToDo", 1), "Mostly ToDo; the oldest has waited 1 day.")
        self.assertEqual(home_signals._waited_detail("ToDo", 5), "Mostly ToDo; the oldest has waited 5 days.")
