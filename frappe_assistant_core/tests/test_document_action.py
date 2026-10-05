# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Tests for document_action's submit / cancel / amend actions.

Uses ERPNext's Telephony Call Type: it is submittable, has no controller logic and a
single mandatory field, so it works on the CI site, which installs ERPNext without
running the setup wizard (no Company to build accounting documents against). Its
DocPerms give System Manager read/write/create/delete but no submit/cancel/amend, which
makes a System Manager test user a real "can edit, cannot cancel or amend" user.
"""

import json
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.model.base_document import get_controller
from frappe.model.document import Document

from frappe_assistant_core.api.fac_endpoint import _build_tool_registry
from frappe_assistant_core.core.tool_registry import ToolRegistry
from frappe_assistant_core.mcp.server import TOOL_NAME_ALIASES, MCPServer
from frappe_assistant_core.plugins.core.tools.document_action import DocumentAction
from frappe_assistant_core.tests.base_test import BaseAssistantTest

TEST_DOCTYPE = "Telephony Call Type"


class DocumentActionTestCase(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        if not frappe.db.exists("DocType", TEST_DOCTYPE):
            self.skipTest(f"{TEST_DOCTYPE} not available (ERPNext not installed)")
        self.tool = DocumentAction()

    def make_doc(self, docstatus=0):
        doc = frappe.get_doc(
            {"doctype": TEST_DOCTYPE, "call_type": f"_Test FAC {frappe.generate_hash(length=8)}"}
        )
        doc.insert()
        if docstatus >= 1:
            doc.submit()
        if docstatus == 2:
            doc.cancel()
        return doc

    def db_docstatus(self, name):
        return frappe.db.get_value(TEST_DOCTYPE, name, "docstatus")

    def fac_comments(self, name):
        return frappe.get_all(
            "Comment",
            filters={
                "reference_doctype": TEST_DOCTYPE,
                "reference_name": name,
                "comment_type": "Comment",
                "content": ("like", "Cancelled via FAC%"),
            },
            pluck="content",
        )

    def login_as_system_manager(self):
        """A real user whose only DocPerm on TEST_DOCTYPE lacks submit, cancel and amend."""
        user = self.create_test_user(
            email=f"fac-submit-{frappe.generate_hash(length=8)}@example.com", roles=["System Manager"]
        )
        # nosemgrep: frappe-setuser — test runs as a restricted user; cleanup restores Administrator
        frappe.set_user(user.name)
        self.addCleanup(frappe.set_user, "Administrator")


class TestSubmitAction(DocumentActionTestCase):
    def test_submit_without_action_is_unchanged(self):
        doc = self.make_doc()

        result = self.tool.execute({"doctype": TEST_DOCTYPE, "name": doc.name})

        self.assertTrue(result.get("success"), result)
        self.assertEqual(result["docstatus"], 1)
        self.assertEqual(result["message"], f"{TEST_DOCTYPE} '{doc.name}' submitted successfully")
        self.assertEqual(self.db_docstatus(doc.name), 1)

    def test_submit_keeps_its_existing_error_messages(self):
        doc = self.make_doc(docstatus=1)

        result = self.tool.execute({"doctype": TEST_DOCTYPE, "name": doc.name, "action": "submit"})

        self.assertFalse(result.get("success"))
        self.assertEqual(
            result["error"],
            f"Cannot submit submitted document {TEST_DOCTYPE} '{doc.name}'. "
            "Only draft documents can be submitted.",
        )
        self.assertIn("get_document", result["suggestion"])
        self.assertNotIn("document_get", result["suggestion"])

    def test_submit_next_steps_name_real_tools_and_plain_cancel_permission(self):
        doc = self.make_doc()

        result = self.tool.execute({"doctype": TEST_DOCTYPE, "name": doc.name})

        steps = result["next_steps"]
        self.assertIn("Use get_document to view the submitted document", steps)
        self.assertIn(
            "You can cancel it later with document_action (action 'cancel', with the user's reason)", steps
        )
        self.assertFalse(any("document_get" in step or "Submit permissions" in step for step in steps), steps)

    def test_submit_next_steps_without_cancel_permission(self):
        doc = self.make_doc()

        # Allow everything except cancel, so only the next_steps line changes.
        with patch(
            "frappe.has_permission",
            side_effect=lambda doctype=None, ptype="read", *a, **kw: ptype != "cancel",
        ):
            result = self.tool.execute({"doctype": TEST_DOCTYPE, "name": doc.name})

        self.assertTrue(result.get("success"), result)
        self.assertIn("You don't have permission to cancel it", result["next_steps"])

    def test_invalid_action_is_refused_with_the_valid_actions(self):
        doc = self.make_doc(docstatus=1)

        result = self.tool.execute({"doctype": TEST_DOCTYPE, "name": doc.name, "action": "delete"})

        self.assertFalse(result.get("success"))
        self.assertEqual(result["valid_actions"], ["submit", "cancel", "amend"])
        self.assertIn("submit, cancel, amend", result["error"])
        self.assertEqual(self.db_docstatus(doc.name), 1)


class TestCancelAction(DocumentActionTestCase):
    def test_cancel_submitted_doc_records_the_reason_word_for_word(self):
        doc = self.make_doc(docstatus=1)
        # Long, punctuated and multi-line, so any shortening or rewording would show.
        reason = (
            "The customer (Acme Traders) called on 12 Sept and said this was raised twice, "
            'once by Priya and once by the "auto-bill" job. Keep the other copy; this one '
            "must go.\nDon't reuse the number."
        )

        result = self.tool.execute(
            {"doctype": TEST_DOCTYPE, "name": doc.name, "action": "cancel", "reason": reason}
        )

        self.assertTrue(result.get("success"), result)
        self.assertEqual(result["name"], doc.name)
        self.assertEqual(result["docstatus"], 2)
        self.assertEqual(result["saved_reason"], reason)
        self.assertIn(reason, result["message"])
        self.assertEqual(self.db_docstatus(doc.name), 2)
        self.assertEqual(
            self.fac_comments(doc.name),
            [f"Cancelled via FAC by Administrator. Reason given by user: {reason}"],
        )

    def test_action_matching_ignores_case(self):
        doc = self.make_doc(docstatus=1)

        result = self.tool.execute(
            {"doctype": TEST_DOCTYPE, "name": doc.name, "action": "Cancel", "reason": "Wrong party"}
        )

        self.assertTrue(result.get("success"), result)
        self.assertEqual(self.db_docstatus(doc.name), 2)

    def test_cancel_without_a_reason_is_refused(self):
        doc = self.make_doc(docstatus=1)

        for reason in (None, "", "   "):
            with self.subTest(reason=reason):
                arguments = {"doctype": TEST_DOCTYPE, "name": doc.name, "action": "cancel"}
                if reason is not None:
                    arguments["reason"] = reason

                result = self.tool.execute(arguments)

                self.assertFalse(result.get("success"))
                self.assertIn("reason is required", result["error"])
                self.assertIn("Ask the user", result["suggestion"])
                self.assertNotIn("saved_reason", result)
                self.assertEqual(self.db_docstatus(doc.name), 1)
                self.assertEqual(self.fac_comments(doc.name), [])

    def test_cancel_draft_is_refused(self):
        doc = self.make_doc(docstatus=0)

        result = self.tool.execute(
            {"doctype": TEST_DOCTYPE, "name": doc.name, "action": "cancel", "reason": "Not needed"}
        )

        self.assertFalse(result.get("success"))
        self.assertIn("because it is a draft", result["error"])
        self.assertIn("Do not submit it just to cancel it", result["error"])
        self.assertIn("delete it", result["suggestion"])
        self.assertIn("leave it", result["suggestion"])
        self.assertIn("Never submit it as a step toward cancelling", result["suggestion"])
        self.assertEqual(self.db_docstatus(doc.name), 0)

    def test_tool_docs_say_never_submit_a_draft_to_cancel_it(self):
        """Both the tool description and the action parameter (sent even in skill replace mode)."""
        action_doc = self.tool.inputSchema["properties"]["action"]["description"]
        for text, expected in (
            (self.tool.description, "Only when the user explicitly asks to submit"),
            (self.tool.description, "Never submit as a step toward cancelling"),
            (self.tool.description, "If the document is a draft, do not submit it"),
            (self.tool.description, "offer to delete it or leave it"),
            (action_doc, "only when the user explicitly asks to submit"),
            (action_doc, "never as a step toward cancelling"),
            (action_doc, "if it is a draft, do not submit it"),
            (action_doc, "offer to delete it or leave it"),
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_cancel_already_cancelled_doc_is_refused(self):
        doc = self.make_doc(docstatus=2)

        result = self.tool.execute(
            {"doctype": TEST_DOCTYPE, "name": doc.name, "action": "cancel", "reason": "Not needed"}
        )

        self.assertFalse(result.get("success"))
        self.assertIn("already cancelled", result["error"])
        self.assertIn("'amend'", result["suggestion"])
        self.assertEqual(self.fac_comments(doc.name), [])

    def test_cancel_with_linked_submitted_doc_is_refused_and_rolled_back(self):
        """The real cancel runs (docstatus=2 is written, on_cancel fires) before Frappe's
        back-link check raises, so this also proves the savepoint undoes all of it."""
        doc = self.make_doc(docstatus=1)
        link_error = frappe.LinkExistsError(
            f"Cannot delete or cancel because {TEST_DOCTYPE} <a href='/app/x'>{doc.name}</a> "
            "is linked with Sales Invoice <a href='/app/sales-invoice/SINV-TEST-0001'>SINV-TEST-0001</a>"
        )

        with patch.object(Document, "check_no_back_links_exist", side_effect=link_error), patch(
            "frappe.desk.form.linked_with.get_submitted_linked_docs",
            return_value={"docs": [{"doctype": "Sales Invoice", "name": "SINV-TEST-0001", "docstatus": 1}]},
        ) as get_linked:
            result = self.tool.execute(
                {"doctype": TEST_DOCTYPE, "name": doc.name, "action": "cancel", "reason": "Duplicate"}
            )

        self.assertFalse(result.get("success"))
        self.assertEqual(result["error_type"], "LinkExistsError")
        self.assertEqual(result["linked_documents"], [{"doctype": "Sales Invoice", "name": "SINV-TEST-0001"}])
        self.assertIn("SINV-TEST-0001", result["error"])
        self.assertNotIn("<a", result["error"])
        self.assertIn("let them decide", result["suggestion"])
        get_linked.assert_called_once_with(TEST_DOCTYPE, doc.name, ignore_doctypes_on_cancel_all=[])

        self.assertEqual(self.db_docstatus(doc.name), 1)
        self.assertEqual(self.fac_comments(doc.name), [])

    def test_cancel_blocked_by_validation_returns_the_real_message(self):
        """Stands in for ERPNext refusing in on_cancel, e.g. a closed accounting period."""
        doc = self.make_doc(docstatus=1)

        with patch.object(
            get_controller(TEST_DOCTYPE),
            "on_cancel",
            create=True,
            side_effect=frappe.ValidationError("Books have been closed till <b>2024-03-31</b>"),
        ):
            result = self.tool.execute(
                {"doctype": TEST_DOCTYPE, "name": doc.name, "action": "cancel", "reason": "Duplicate"}
            )

        self.assertFalse(result.get("success"))
        self.assertEqual(result["error"], "Books have been closed till 2024-03-31")
        self.assertEqual(result["error_type"], "ValidationError")
        self.assertEqual(self.db_docstatus(doc.name), 1)
        self.assertEqual(self.fac_comments(doc.name), [])

    def test_cancel_without_cancel_permission_is_refused(self):
        doc = self.make_doc(docstatus=1)
        self.login_as_system_manager()

        result = self.tool.execute(
            {"doctype": TEST_DOCTYPE, "name": doc.name, "action": "cancel", "reason": "Duplicate"}
        )

        self.assertFalse(result.get("success"))
        self.assertIn("Insufficient cancel permissions", result["error"])
        self.assertEqual(self.db_docstatus(doc.name), 1)

    @contextmanager
    def active_workflow(self, doc, transitions):
        """Make TEST_DOCTYPE look like it has an active Workflow, in memory only.

        Saving a real Workflow adds a workflow_state custom field (DDL), which would commit the
        test transaction, so the lookups are patched. call_type stands in as the state field.
        """
        workflow = frappe.get_doc(
            {
                "doctype": "Workflow",
                "name": "FAC Test Workflow",
                "workflow_name": "FAC Test Workflow",
                "document_type": TEST_DOCTYPE,
                "is_active": 1,
                "workflow_state_field": "call_type",
                "states": [
                    {"state": doc.call_type, "doc_status": "1"},
                    {"state": "Approved", "doc_status": "1"},
                    {"state": "Cancelled", "doc_status": "2"},
                ],
                "transitions": transitions,
            }
        )
        real_get_doc = frappe.get_doc

        def get_doc(*args, **kwargs):
            if args == ("Workflow", "FAC Test Workflow"):
                return workflow
            return real_get_doc(*args, **kwargs)

        with patch("frappe.model.workflow.get_workflow_name", return_value="FAC Test Workflow"), patch(
            "frappe.get_doc", side_effect=get_doc
        ):
            yield

    def test_workflow_refusal_names_the_cancel_action_from_the_current_state(self):
        doc = self.make_doc(docstatus=1)
        transitions = [
            {
                "state": doc.call_type,
                "action": "Approve",
                "next_state": "Approved",
                "allowed": "System Manager",
            },
            {
                "state": doc.call_type,
                "action": "Void",
                "next_state": "Cancelled",
                "allowed": "Accounts Manager",
            },
        ]

        with self.active_workflow(doc, transitions):
            result = self.tool.execute(
                {"doctype": TEST_DOCTYPE, "name": doc.name, "action": "cancel", "reason": "Duplicate"}
            )

        self.assertFalse(result.get("success"))
        self.assertIn("active Workflow", result["error"])
        self.assertEqual(
            result["workflow_cancel_actions"],
            [{"action": "Void", "next_state": "Cancelled", "allowed_role": "Accounts Manager"}],
        )
        self.assertIn("run_workflow", result["suggestion"])
        self.assertIn("action 'Void'", result["suggestion"])
        self.assertNotIn("Approve", result["suggestion"])
        self.assertEqual(self.db_docstatus(doc.name), 1)

    def test_workflow_refusal_without_a_cancel_step_from_the_current_state(self):
        doc = self.make_doc(docstatus=1)
        # A cancel step exists, but only from another state.
        transitions = [
            {
                "state": doc.call_type,
                "action": "Approve",
                "next_state": "Approved",
                "allowed": "System Manager",
            },
            {"state": "Approved", "action": "Void", "next_state": "Cancelled", "allowed": "System Manager"},
        ]

        with self.active_workflow(doc, transitions):
            result = self.tool.execute(
                {"doctype": TEST_DOCTYPE, "name": doc.name, "action": "cancel", "reason": "Duplicate"}
            )

        self.assertFalse(result.get("success"))
        self.assertEqual(result["workflow_cancel_actions"], [])
        self.assertIn("no cancel step", result["error"])
        self.assertIn(doc.call_type, result["error"])
        self.assertIn("administrator", result["suggestion"])
        self.assertIn("deactivate the workflow", result["suggestion"])
        self.assertNotIn("run_workflow", result["suggestion"])
        self.assertEqual(self.db_docstatus(doc.name), 1)


class TestAmendAction(DocumentActionTestCase):
    def test_amend_cancelled_doc_creates_a_draft(self):
        doc = self.make_doc(docstatus=2)

        result = self.tool.execute({"doctype": TEST_DOCTYPE, "name": doc.name, "action": "amend"})

        self.assertTrue(result.get("success"), result)
        self.assertEqual(result["name"], f"{doc.name}-1")
        self.assertEqual(result["amended_from"], doc.name)
        self.assertEqual(result["docstatus"], 0)
        self.assertTrue(any("update_document" in step for step in result["next_steps"]))
        self.assertTrue(any("document_action" in step for step in result["next_steps"]))

        amended = frappe.db.get_value(
            TEST_DOCTYPE, result["name"], ["docstatus", "amended_from", "call_type"], as_dict=True
        )
        self.assertEqual(amended.docstatus, 0)
        self.assertEqual(amended.amended_from, doc.name)
        # TEST_DOCTYPE is named by field:call_type; Frappe keeps that field in sync with the name.
        self.assertEqual(amended.call_type, result["name"])
        self.assertEqual(self.db_docstatus(doc.name), 2)

    def test_amend_twice_is_refused(self):
        doc = self.make_doc(docstatus=2)
        first = self.tool.execute({"doctype": TEST_DOCTYPE, "name": doc.name, "action": "amend"})
        self.assertTrue(first.get("success"), first)

        result = self.tool.execute({"doctype": TEST_DOCTYPE, "name": doc.name, "action": "amend"})

        self.assertFalse(result.get("success"))
        self.assertIn("already been amended", result["error"])
        self.assertEqual(result["amended_document"], first["name"])

    def test_amend_submitted_or_draft_doc_is_refused(self):
        for docstatus, expected in ((1, "because it is submitted"), (0, "because it is a draft")):
            with self.subTest(docstatus=docstatus):
                doc = self.make_doc(docstatus=docstatus)

                result = self.tool.execute({"doctype": TEST_DOCTYPE, "name": doc.name, "action": "amend"})

                self.assertFalse(result.get("success"))
                self.assertIn(expected, result["error"])
                self.assertFalse(frappe.db.exists(TEST_DOCTYPE, {"amended_from": doc.name}))

    def test_amend_without_amend_permission_is_refused(self):
        doc = self.make_doc(docstatus=2)
        self.login_as_system_manager()

        result = self.tool.execute({"doctype": TEST_DOCTYPE, "name": doc.name, "action": "amend"})

        self.assertFalse(result.get("success"))
        self.assertIn("Insufficient amend permissions", result["error"])
        self.assertFalse(frappe.db.exists(TEST_DOCTYPE, {"amended_from": doc.name}))


class TestPermissionDenials(DocumentActionTestCase):
    """A refused submit / cancel / amend says why.

    The DocType-level pre-check already returns a clear "Insufficient <action>
    permissions" message, covered by the tests above. These cover the step after it:
    Frappe refusing the operation on the document itself, which it signals by raising
    `frappe.PermissionError` with no message and keeping the reason in
    `frappe.flags.error_message`. Reporting `str(e)` gave an empty error, and reporting
    `error_type` from the class name rendered a bare "PermissionError" with nothing to
    act on.
    """

    def setUp(self):
        super().setUp()
        frappe.flags.pop("error_message", None)
        self.addCleanup(lambda: frappe.flags.pop("error_message", None))
        log_error = patch("frappe.log_error")
        self.log_error = log_error.start()
        self.addCleanup(log_error.stop)

    @contextmanager
    def _refused_by_frappe(self, method, ptype):
        """Let the pre-check pass, then have Frappe refuse the document itself."""
        refusal = frappe.new_doc(TEST_DOCTYPE)
        with patch(
            "frappe_assistant_core.core.security_config.validate_document_access",
            return_value={"success": True, "role": "Default"},
        ), patch.object(Document, method, side_effect=lambda *a, **k: refusal.raise_no_permission_to(ptype)):
            yield

    def assert_reported_as_a_denial(self, result):
        self.assertFalse(result.get("success"), result)
        self.assertEqual(result.get("error_type"), "permission_error", result)
        self.assertTrue(result.get("error"), result)
        # Frappe's reason — not an empty string, and not the bare class name.
        self.assertNotEqual(result["error"], "PermissionError")
        self.assertNotIn("<", result["error"])
        self.assertTrue(self.log_error.call_args.kwargs["message"].endswith(result["error"]))

    def test_a_refused_submit_says_why(self):
        doc = self.make_doc()

        with self._refused_by_frappe("submit", "submit"):
            result = self.tool.execute({"doctype": TEST_DOCTYPE, "name": doc.name, "action": "submit"})

        self.assert_reported_as_a_denial(result)
        # The old handler blamed the document's required fields for a permission denial.
        self.assertNotIn("required fields", result.get("suggestion", ""))
        self.assertEqual(self.db_docstatus(doc.name), 0)

    def test_a_refused_cancel_says_why_and_leaves_the_document_submitted(self):
        doc = self.make_doc(docstatus=1)

        with self._refused_by_frappe("cancel", "cancel"):
            result = self.tool.execute(
                {"doctype": TEST_DOCTYPE, "name": doc.name, "action": "cancel", "reason": "Duplicate"}
            )

        self.assert_reported_as_a_denial(result)
        self.assertEqual(result.get("docstatus"), 1)
        # The savepoint is rolled back, so no on_cancel side effect survives.
        self.assertEqual(self.db_docstatus(doc.name), 1)
        self.assertEqual(self.fac_comments(doc.name), [])

    def test_a_refused_amend_says_why_and_creates_no_draft(self):
        doc = self.make_doc(docstatus=2)

        with self._refused_by_frappe("insert", "create"):
            result = self.tool.execute({"doctype": TEST_DOCTYPE, "name": doc.name, "action": "amend"})

        self.assert_reported_as_a_denial(result)
        self.assertFalse(frappe.db.exists(TEST_DOCTYPE, {"amended_from": doc.name}))


class TestCancelAndAmendGuidance(DocumentActionTestCase):
    """Other tools send the LLM to document_action for cancel and amend."""

    def test_run_workflow_without_workflow_suggests_the_matching_action(self):
        from frappe_assistant_core.plugins.core.tools.run_workflow import RunWorkflow

        doc = self.make_doc(docstatus=1)

        for requested, expected in (("Cancel", "cancel"), ("Amend", "amend"), ("Approve", "submit")):
            with self.subTest(requested=requested):
                result = RunWorkflow().execute(
                    {"doctype": TEST_DOCTYPE, "name": doc.name, "action": requested}
                )

                self.assertFalse(result.get("success"))
                self.assertIn(f"'document_action' tool with action '{expected}'", result["suggestion"])

    def test_update_document_on_cancelled_doc_suggests_amend(self):
        from frappe_assistant_core.plugins.core.tools.update_document import DocumentUpdate

        doc = self.make_doc(docstatus=2)

        result = DocumentUpdate().execute(
            {"doctype": TEST_DOCTYPE, "name": doc.name, "data": {"call_type": "changed"}}
        )

        self.assertFalse(result.get("success"))
        self.assertIn("cancelled", result["error"])
        self.assertIn("document_action with action 'amend'", result["suggestion"])


class TestSubmitDocumentAlias(DocumentActionTestCase):
    """submit_document is a hidden, temporary alias for document_action in tools/call."""

    def call(self, tool_name, arguments):
        # The same per-request registry the MCP endpoint builds for the current user.
        return MCPServer("test")._handle_tools_call(
            {"name": tool_name, "arguments": arguments}, _build_tool_registry()
        )

    def test_old_name_runs_document_action(self):
        doc = self.make_doc()

        result = self.call("submit_document", {"doctype": TEST_DOCTYPE, "name": doc.name})

        self.assertFalse(result["isError"], result)
        # tools/call returns the tool's own output; the _safe_execute envelope
        # (success / result / execution_time) stays server-side.
        payload = json.loads(result["content"][0]["text"])
        self.assertTrue(payload["success"], payload)
        self.assertEqual(payload["docstatus"], 1)
        self.assertNotIn("execution_time", payload)
        self.assertEqual(self.db_docstatus(doc.name), 1)

    def test_old_name_goes_through_the_document_action_entry(self):
        """Same tool instance and the same _safe_execute (argument validation, role check, audit)."""
        arguments = {"doctype": TEST_DOCTYPE, "name": "X", "action": "cancel", "reason": "Duplicate"}

        with patch.object(
            DocumentAction, "_safe_execute", autospec=True, return_value={"success": True}
        ) as safe_execute:
            result = self.call("submit_document", arguments)

        self.assertFalse(result["isError"], result)
        safe_execute.assert_called_once()
        tool, called_with = safe_execute.call_args.args
        self.assertEqual(tool.name, "document_action")
        self.assertEqual(called_with, arguments)

    def test_old_name_is_refused_when_document_action_is_not_accessible(self):
        doc = self.make_doc()

        with patch.object(
            ToolRegistry,
            "_is_tool_accessible",
            autospec=True,
            side_effect=lambda _registry, tool_name, *args, **kwargs: tool_name != "document_action",
        ):
            result = self.call("submit_document", {"doctype": TEST_DOCTYPE, "name": doc.name})

        self.assertTrue(result["isError"])
        self.assertIn("not found", result["content"][0]["text"])
        self.assertEqual(self.db_docstatus(doc.name), 0)

    def test_old_name_is_not_listed(self):
        tools = MCPServer("test")._handle_tools_list({}, _build_tool_registry())["tools"]
        names = [tool["name"] for tool in tools]

        self.assertIn("document_action", names)
        self.assertNotIn("submit_document", names)

    def test_alias_target_asks_for_approval_and_is_destructive(self):
        """Callers (AR, MCP clients) decide approval from the tool's name and annotations."""
        from frappe_assistant_core.chat.api.tools import _DEFAULT_APPROVAL_TOOLS

        target = TOOL_NAME_ALIASES["submit_document"]

        self.assertEqual(target, "document_action")
        self.assertIn(target, _DEFAULT_APPROVAL_TOOLS)
        self.assertEqual(_build_tool_registry()[target]["annotations"].get("destructiveHint"), True)
