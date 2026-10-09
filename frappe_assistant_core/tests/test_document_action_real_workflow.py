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
document_action against a real, saved Workflow (review of #257).

test_document_action.py stands a Workflow in for the real thing by patching
get_workflow_name and frappe.get_doc. That covers the cancel refusal's wording,
but it never lets Frappe enforce the workflow, and two defects lived exactly
there:

  * submit skipped approval. On doc.submit() Frappe validates the workflow
    while the state is still unchanged, so no transition is checked, and only
    then sets the first submitted state. A user with plain submit permission
    reached a state only an approver could.
  * amend failed. frappe.copy_doc carries the cancelled workflow state onto
    the new draft, and Frappe refuses a new document that starts anywhere but
    the workflow's first state. Desk resets the state for a new document.

Saving a Workflow normally adds a workflow_state column, and DDL would commit
the test transaction. Bank Transaction already has a spare Data field,
reference_number, so it serves as the state field and nothing but DML runs.
It is a light ERPNext doctype with no Company dependency, and its standard
permissions give Accounts User submit without cancel.
"""

import frappe
from frappe.model.workflow import apply_workflow

from frappe_assistant_core.plugins.core.tools.document_action import DocumentAction
from frappe_assistant_core.tests.base_test import BaseAssistantTest

DOCTYPE = "Bank Transaction"
APPROVE = "FAC Test Approve"
CANCEL = "FAC Test Cancel"


class RealWorkflowTestCase(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        if not frappe.db.exists("DocType", DOCTYPE) or not frappe.db.exists("Role", "Accounts Manager"):
            self.skipTest(f"{DOCTYPE} not available (ERPNext not installed)")
        self.tool = DocumentAction()
        tag = frappe.generate_hash(length=6)
        self.states = {k: f"FAC Test {tag} {k}" for k in ("Draft", "Approved", "Cancelled")}

    def tearDown(self):
        frappe.set_user("Administrator")
        for name in frappe.get_all("Workflow", filters={"document_type": DOCTYPE}, pluck="name"):
            if name.startswith("FAC Test "):
                frappe.delete_doc("Workflow", name, force=True, ignore_permissions=True)
        self.forget_workflow()
        super().tearDown()

    def forget_workflow(self):
        # get_workflow_name caches per doctype in Redis, which the test rollback does not reach.
        frappe.cache.hdel("workflow", DOCTYPE)
        frappe.clear_cache(doctype=DOCTYPE)

    def make_workflow(self, approve_role="Accounts Manager"):
        """Draft -(Approve, approve_role)-> Approved -(Cancel, Accounts Manager)-> Cancelled."""
        for state in self.states.values():
            frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state}).insert()
        for action in (APPROVE, CANCEL):
            if not frappe.db.exists("Workflow Action Master", action):
                frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert()

        st = self.states
        frappe.get_doc(
            {
                "doctype": "Workflow",
                "workflow_name": f"FAC Test {st['Draft'].split()[2]}",
                "document_type": DOCTYPE,
                "is_active": 1,
                "workflow_state_field": "reference_number",
                "send_email_alert": 0,
                "states": [
                    {"state": st["Draft"], "doc_status": "0", "allow_edit": "Accounts User"},
                    {"state": st["Approved"], "doc_status": "1", "allow_edit": "Accounts Manager"},
                    {"state": st["Cancelled"], "doc_status": "2", "allow_edit": "Accounts Manager"},
                ],
                "transitions": [
                    {
                        "state": st["Draft"],
                        "action": APPROVE,
                        "next_state": st["Approved"],
                        "allowed": approve_role,
                        "allow_self_approval": 1,
                    },
                    {
                        "state": st["Approved"],
                        "action": CANCEL,
                        "next_state": st["Cancelled"],
                        "allowed": "Accounts Manager",
                        "allow_self_approval": 1,
                    },
                ],
            }
        ).insert()
        self.forget_workflow()

    def make_transaction(self):
        return frappe.get_doc(
            {"doctype": DOCTYPE, "date": frappe.utils.nowdate(), "deposit": 10, "description": "FAC test"}
        ).insert()

    def db_state(self, name):
        return frappe.db.get_value(DOCTYPE, name, ["docstatus", "reference_number"], as_dict=True)


class TestSubmitUnderWorkflow(RealWorkflowTestCase):
    def test_submit_cannot_skip_the_approval_step(self):
        """A clerk with submit permission but not the approver's role stays in Draft."""
        self.make_workflow(approve_role="Accounts Manager")
        clerk = self.make_throwaway_user("fac-clerk", roles=("Accounts User",))
        # nosemgrep: frappe-setuser — runs as a real Accounts User; tearDown restores Administrator
        frappe.set_user(clerk)
        doc = self.make_transaction()

        # The workflow itself refuses this user the transition...
        with self.assertRaises(frappe.ValidationError):
            apply_workflow(frappe.get_doc(DOCTYPE, doc.name), APPROVE)

        # ...so document_action must not reach the approved state another way.
        result = self.tool.execute({"doctype": DOCTYPE, "name": doc.name, "action": "submit"})

        self.assertFalse(result.get("success"), result)
        self.assertIn("active Workflow", result["error"])
        self.assertEqual(
            result["workflow_submit_actions"],
            [{"action": APPROVE, "next_state": self.states["Approved"], "allowed_role": "Accounts Manager"}],
        )
        self.assertIn("run_workflow", result["suggestion"])
        self.assertEqual(self.db_state(doc.name), {"docstatus": 0, "reference_number": self.states["Draft"]})

    def test_submit_is_refused_for_administrator_too(self):
        """Administrator may approve, but through the workflow, so its rules and log apply."""
        self.make_workflow()
        doc = self.make_transaction()

        result = self.tool.execute({"doctype": DOCTYPE, "name": doc.name})

        self.assertFalse(result.get("success"), result)
        self.assertEqual(self.db_state(doc.name)["docstatus"], 0)

    def test_create_document_with_submit_keeps_a_draft(self):
        """create_document's submit=True reached the same doc.submit() and skipped approval too."""
        from frappe_assistant_core.plugins.core.tools.create_document import DocumentCreate

        self.make_workflow(approve_role="Accounts Manager")
        clerk = self.make_throwaway_user("fac-clerk", roles=("Accounts User",))
        # nosemgrep: frappe-setuser — runs as a real Accounts User; tearDown restores Administrator
        frappe.set_user(clerk)

        result = DocumentCreate().execute(
            {
                "doctype": DOCTYPE,
                "data": {"date": frappe.utils.nowdate(), "deposit": 10, "description": "FAC test"},
                "submit": True,
            }
        )

        self.assertTrue(result.get("success"), result)
        self.assertFalse(result["submitted"])
        self.assertIn("active Workflow", result["submit_error"])
        self.assertIn("run_workflow", result["suggestion"])
        self.assertEqual(
            self.db_state(result["name"]), {"docstatus": 0, "reference_number": self.states["Draft"]}
        )


class TestAmendUnderWorkflow(RealWorkflowTestCase):
    def test_amend_of_a_workflow_cancelled_document_starts_in_the_draft_state(self):
        """The path the cancel refusal sends users down: cancel with run_workflow, then amend."""
        self.make_workflow()
        doc = self.make_transaction()
        apply_workflow(frappe.get_doc(DOCTYPE, doc.name), APPROVE)
        apply_workflow(frappe.get_doc(DOCTYPE, doc.name), CANCEL)
        self.assertEqual(
            self.db_state(doc.name), {"docstatus": 2, "reference_number": self.states["Cancelled"]}
        )

        result = self.tool.execute({"doctype": DOCTYPE, "name": doc.name, "action": "amend"})

        self.assertTrue(result.get("success"), result)
        self.assertEqual(result["amended_from"], doc.name)
        self.assertEqual(
            self.db_state(result["name"]), {"docstatus": 0, "reference_number": self.states["Draft"]}
        )
