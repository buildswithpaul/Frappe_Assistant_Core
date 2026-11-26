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
Tools say when a call needs the user's confirmation (confirmation(), spec section 7.3).

The workflow case runs against a real saved Workflow, the way test_document_action_real_workflow
does: Bank Transaction's spare Data field serves as the state field, so only DML runs.
"""

import frappe

from frappe_assistant_core.mcp.tool_adapter import build_tool_dict
from frappe_assistant_core.plugins.core.tools.delete_document import DocumentDelete
from frappe_assistant_core.plugins.core.tools.document_action import DocumentAction
from frappe_assistant_core.plugins.core.tools.get_document import DocumentGet
from frappe_assistant_core.plugins.core.tools.run_workflow import RunWorkflow
from frappe_assistant_core.plugins.core.tools.send_email import SendEmail
from frappe_assistant_core.tests.base_test import BaseAssistantTest

CANCEL_QUESTION = "Cancel Sales Invoice SINV-1? Its accounting and stock entries will be reversed."


class TestToolConfirmation(BaseAssistantTest):
    def test_delete_single(self):
        question = DocumentDelete().confirmation({"doctype": "Customer", "name": "CUST-0001"})
        self.assertEqual(question, "Delete Customer CUST-0001? This can't be undone.")

    def test_delete_bulk(self):
        names = [f"CUST-{i:04d}" for i in range(100)]
        question = DocumentDelete().confirmation({"doctype": "Customer", "names": names})
        self.assertIn("100", question)
        for name in names[:3]:
            self.assertIn(name, question)
        self.assertNotIn(names[3], question)
        self.assertNotIn("\n", question)

    def test_delete_value_cannot_add_a_line(self):
        question = DocumentDelete().confirmation({"doctype": "Customer", "name": "A\nB " + "x" * 500})
        self.assertNotIn("\n", question)
        self.assertLess(len(question), 200)

    def test_delete_malformed_arguments_do_not_raise(self):
        self.assertIsInstance(DocumentDelete().confirmation({}), str)
        self.assertIsInstance(DocumentDelete().confirmation({"doctype": ["x"], "names": "abc"}), str)

    def test_document_action_cancel_normalised(self):
        tool = DocumentAction()
        base = {"doctype": "Sales Invoice", "name": "SINV-1"}
        self.assertEqual(tool.confirmation({**base, "action": " Cancel "}), CANCEL_QUESTION)
        self.assertIsNone(tool.confirmation({**base, "action": "submit"}))
        self.assertIsNone(tool.confirmation({**base, "action": "amend"}))
        self.assertIsNone(tool.confirmation(base))
        self.assertIsNone(tool.confirmation({**base, "action": None}))

    def test_send_email(self):
        question = SendEmail().confirmation(
            {"recipients": ["a@example.com", "b@example.com"], "subject": "Q3\nreport", "message": "x"}
        )
        self.assertEqual(question, "Send the email 'Q3 report' to a@example.com, b@example.com?")

    def test_send_email_recipients_string_and_capped(self):
        tool = SendEmail()
        self.assertIn("a@example.com", tool.confirmation({"recipients": "a@example.com", "subject": "s"}))
        many = [f"u{i}@example.com" for i in range(20)]
        question = tool.confirmation({"recipients": many, "subject": "s"})
        self.assertIn("u0@example.com", question)
        self.assertNotIn("u19@example.com", question)
        self.assertIn("15 more", question)
        self.assertIsInstance(tool.confirmation({}), str)

    def test_other_tools_none(self):
        self.assertIsNone(DocumentGet().confirmation({"doctype": "Customer", "name": "CUST-0001"}))

    def test_tool_dict_carries_confirmation(self):
        tool_dict = build_tool_dict(DocumentDelete())
        self.assertEqual(tool_dict["confirmationVerb"], "Delete")
        self.assertIn("Delete", tool_dict["confirmation"]({"doctype": "Customer", "name": "C"}))
        self.assertEqual(build_tool_dict(SendEmail())["confirmationVerb"], "Send")
        self.assertEqual(build_tool_dict(DocumentAction())["confirmationVerb"], "Cancel")
        plain = build_tool_dict(DocumentGet())
        self.assertEqual(plain["confirmationVerb"], "")
        self.assertIsNone(plain["confirmation"]({}))


DOCTYPE = "Bank Transaction"
APPROVE = "FAC Test Approve"
CANCEL = "FAC Test Cancel"


class TestRunWorkflowConfirmation(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        if not frappe.db.exists("DocType", DOCTYPE):
            self.skipTest(f"{DOCTYPE} not available (ERPNext not installed)")
        self.tool = RunWorkflow()
        tag = frappe.generate_hash(length=6)
        self.states = {k: f"FAC Test {tag} {k}" for k in ("Draft", "Approved", "Cancelled")}

    def tearDown(self):
        for name in frappe.get_all("Workflow", filters={"document_type": DOCTYPE}, pluck="name"):
            if name.startswith("FAC Test "):
                frappe.delete_doc("Workflow", name, force=True, ignore_permissions=True)
        self.forget_workflow()
        super().tearDown()

    def forget_workflow(self):
        # get_workflow_name caches per doctype in Redis, which the test rollback does not reach.
        frappe.cache.hdel("workflow", DOCTYPE)
        frappe.clear_cache(doctype=DOCTYPE)

    def make_workflow(self):
        """Draft -(Approve)-> Approved -(Cancel)-> Cancelled; Draft -(Cancel)-> Cancelled too."""
        for state in self.states.values():
            frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state}).insert()
        for action in (APPROVE, CANCEL):
            if not frappe.db.exists("Workflow Action Master", action):
                frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert()
        st = self.states
        # Production reaches this through a Workflow an administrator defines for the DocType in Desk.
        frappe.get_doc(
            {
                "doctype": "Workflow",
                "workflow_name": f"FAC Test {st['Draft'].split()[2]}",
                "document_type": DOCTYPE,
                "is_active": 1,
                "workflow_state_field": "reference_number",
                "send_email_alert": 0,
                "states": [
                    {"state": st["Draft"], "doc_status": "0", "allow_edit": "All"},
                    {"state": st["Approved"], "doc_status": "1", "allow_edit": "All"},
                    {"state": st["Cancelled"], "doc_status": "2", "allow_edit": "All"},
                ],
                "transitions": [
                    {
                        "state": st["Draft"],
                        "action": APPROVE,
                        "next_state": st["Approved"],
                        "allowed": "All",
                        "allow_self_approval": 1,
                    },
                    {
                        "state": st["Approved"],
                        "action": CANCEL,
                        "next_state": st["Cancelled"],
                        "allowed": "All",
                        "allow_self_approval": 1,
                    },
                ],
            }
        ).insert()
        self.forget_workflow()

    def test_cancel_transition_asks_and_approve_does_not(self):
        self.make_workflow()
        doc = frappe.get_doc(
            {"doctype": DOCTYPE, "date": frappe.utils.nowdate(), "deposit": 10, "description": "FAC test"}
        ).insert()
        # A new document starts in the first state; Approve is the one transition open from it.
        frappe.db.set_value(DOCTYPE, doc.name, "reference_number", self.states["Draft"])
        base = {"doctype": DOCTYPE, "name": doc.name}
        self.assertIsNone(self.tool.confirmation({**base, "action": APPROVE}))

        # Production reaches the Approved state by running Approve; this is the state it leaves behind.
        frappe.db.set_value(DOCTYPE, doc.name, "reference_number", self.states["Approved"])
        question = self.tool.confirmation({**base, "action": CANCEL})
        self.assertEqual(
            question,
            f"Cancel {DOCTYPE} {doc.name}? Its accounting and stock entries will be reversed.",
        )
        self.assertIsNone(self.tool.confirmation({**base, "action": "No Such Action"}))

    def test_lookup_failures_answer_none(self):
        self.assertIsNone(self.tool.confirmation({}))
        self.assertIsNone(self.tool.confirmation({"doctype": DOCTYPE, "name": "nope", "action": CANCEL}))
        self.assertIsNone(self.tool.confirmation({"doctype": 5, "name": ["x"], "action": CANCEL}))
