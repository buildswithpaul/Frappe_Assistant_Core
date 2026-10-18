# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

import unittest

import frappe

from frappe_assistant_core.chat import home_signals
from frappe_assistant_core.chat.home_signals import approvals_for_user
from frappe_assistant_core.plugins.core.tools.get_pending_approvals import GetPendingApprovals
from frappe_assistant_core.tests.base_test import BaseAssistantTest

APPROVER_ROLE = "System Manager"


class TestHomeSignalApprovals(BaseAssistantTest):
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

    def _open_action(self, todo: str, role: str | None = APPROVER_ROLE, user: str | None = None) -> str:
        # Manufactured: production creates these rows when a document enters a workflow state.
        # A Workflow is not created here: inserting one adds a Custom Field by DDL, which commits.
        action = frappe.get_doc(
            {
                "doctype": "Workflow Action",
                "status": "Open",
                "reference_doctype": "ToDo",
                "reference_name": todo,
                "workflow_state": "Pending",
                "user": user,
                "permitted_roles": [{"role": role}] if role else [],
            }
        )
        return action.insert(ignore_permissions=True).name

    def _waiting(self) -> list[str]:
        return approvals_for_user(self.user).get("ToDo", [])

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

    def _run_tool_as_user(self, **arguments) -> dict:
        previous = frappe.session.user
        self.addCleanup(frappe.set_user, previous)
        frappe.set_user(self.user)
        return GetPendingApprovals().execute({"doctype": "ToDo", "include_actions": False, **arguments})

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


class TestWaitedDetail(unittest.TestCase):
    def test_today_singular_and_plural_are_whole_sentences(self):
        self.assertEqual(home_signals._waited_detail("ToDo", 0), "Mostly ToDo; the oldest arrived today.")
        self.assertEqual(home_signals._waited_detail("ToDo", 1), "Mostly ToDo; the oldest has waited 1 day.")
        self.assertEqual(home_signals._waited_detail("ToDo", 5), "Mostly ToDo; the oldest has waited 5 days.")
