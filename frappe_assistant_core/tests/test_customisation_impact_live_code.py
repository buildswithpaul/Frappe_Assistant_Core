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

"""changes_live_code for code that lives in child rows and in field conditions (#34514).

FAC Cloud skips the card for a write on an approved build plan only when customisation_impact
says it changes no live code, so each case here reads real stored records, not a patched one.
"""

import frappe

from frappe_assistant_core.plugins.core.tools.create_document import DocumentCreate
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.customisation import customisation_impact

WORKFLOW = "FAC Live Code Workflow"
CUSTOM_FIELD = "ToDo-fac_live_code_note"
PROPERTY_SETTER = "ToDo-description-depends_on-fac-live-code"
NOTIFICATION = "FAC Live Code Notification"
OPEN = "eval:doc.status == 'Open'"


def _impact(tool: str, doctype: str, data: dict | None = None, name: str | None = None) -> dict:
    tool_input = {"doctype": doctype, "data": data or {}}
    if name:
        tool_input["name"] = name
    return customisation_impact(tool, tool_input)


def _db_insert(values: dict) -> frappe.model.document.Document:
    """Write a record and its child rows without the doctype's hooks; rolled back with the test."""
    doc = frappe.get_doc(values)
    doc.set_parent_in_children()
    doc.db_insert()
    for row in doc.get_all_children():
        row.db_insert()
    return doc


class TestLiveCodeInChildRowsAndConditions(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for doctype, field, names in (
            ("Workflow State", "workflow_state_name", ("Pending", "Approved")),
            ("Workflow Action Master", "workflow_action_name", ("Approve", "Reject")),
        ):
            for name in names:
                if not frappe.db.exists(doctype, name):
                    frappe.get_doc({"doctype": doctype, field: name}).insert(ignore_permissions=True)
        # Production reaches this when a builder saves a Workflow on ToDo whose approve transition
        # carries a condition. db_insert skips on_update, which would add a workflow_state column
        # to ToDo (DDL commits, so the row would escape the rollback).
        cls.workflow = _db_insert(
            {
                "doctype": "Workflow",
                "name": WORKFLOW,
                "workflow_name": WORKFLOW,
                "document_type": "ToDo",
                "is_active": 0,
                "workflow_state_field": "workflow_state",
                "states": [
                    {"state": "Pending", "doc_status": "0", "allow_edit": "System Manager"},
                    {"state": "Approved", "doc_status": "0", "allow_edit": "System Manager"},
                ],
                "transitions": [
                    {
                        "state": "Pending",
                        "action": "Approve",
                        "next_state": "Approved",
                        "allowed": "System Manager",
                        "condition": "doc.priority == 'High'",
                    },
                    {
                        "state": "Approved",
                        "action": "Reject",
                        "next_state": "Pending",
                        "allowed": "System Manager",
                    },
                ],
            }
        )
        # Production reaches this when a builder adds a field to ToDo that shows only for open
        # ToDos. db_insert skips the column it would add (DDL commits).
        _db_insert(
            {
                "doctype": "Custom Field",
                "name": CUSTOM_FIELD,
                "dt": "ToDo",
                "fieldname": "fac_live_code_note",
                "label": "FAC Live Code Note",
                "fieldtype": "Data",
                "depends_on": OPEN,
                "mandatory_depends_on": "status",
            }
        )
        # Production reaches this when Customize Form hides ToDo's description until it is open;
        # db_insert skips the cache hooks.
        _db_insert(
            {
                "doctype": "Property Setter",
                "name": PROPERTY_SETTER,
                "doc_type": "ToDo",
                "doctype_or_field": "DocField",
                "field_name": "description",
                "property": "depends_on",
                "property_type": "Code",
                "value": OPEN,
            }
        )
        # Production reaches this when a builder switches on a notification that copies a manager
        # on every new high-priority ToDo.
        cls.notification = frappe.get_doc(
            {
                "doctype": "Notification",
                "name": NOTIFICATION,
                "subject": "New ToDo",
                "document_type": "ToDo",
                "event": "New",
                "channel": "Email",
                "enabled": 1,
                "message": "A ToDo was created.",
                "recipients": [
                    {
                        "receiver_by_role": "System Manager",
                        "condition": "doc.priority == 'High'",
                        "cc": "manager@example.com",
                    }
                ],
            }
        ).insert(ignore_permissions=True)

    def _transition(self, index: int) -> str:
        return self.workflow.transitions[index].name

    # Workflow Transition condition

    def test_editing_one_transitions_condition_changes_live_code(self):
        edited = [{"name": self._transition(0), "condition": "doc.priority == 'Low'"}]
        self.assertIs(
            _impact("update_document", "Workflow", {"transitions": edited}, WORKFLOW)["changes_live_code"],
            True,
        )

    def test_a_condition_on_an_appended_or_replaced_transition_changes_live_code(self):
        appended = [
            {"name": self._transition(0)},
            {"state": "Approved", "action": "Approve", "next_state": "Approved", "condition": "True"},
        ]
        replaced = [
            {"state": "Pending", "action": "Approve", "next_state": "Approved"},
            {
                "state": "Approved",
                "action": "Reject",
                "next_state": "Pending",
                "condition": "doc.priority == 'High'",
            },
        ]
        for rows in (appended, replaced):
            r = _impact("update_document", "Workflow", {"transitions": rows}, WORKFLOW)
            self.assertIs(r["changes_live_code"], True, rows)

    def _stored_transitions(self) -> list[dict]:
        """The stored transition rows as replace-mode input: every value column, no row names."""
        rows = frappe.get_all(
            "Workflow Transition", filters={"parent": WORKFLOW}, fields=["*"], order_by="idx asc"
        )
        meta = frappe.get_meta("Workflow Transition")
        return [
            {df.fieldname: row.get(df.fieldname) for df in meta.fields if df.fieldname in row} for row in rows
        ]

    def test_transitions_that_keep_their_conditions_do_not_change_live_code(self):
        same_named = [
            {"name": self._transition(0), "condition": "doc.priority == 'High'", "allowed": "System Manager"}
        ]
        # The second transition holds no code, so its audience is not code either.
        other_row = [{"name": self._transition(1), "allowed": "All"}]
        deleted = [{"name": self._transition(0), "_delete": True}]
        for rows in (same_named, other_row, deleted, self._stored_transitions()):
            r = _impact("update_document", "Workflow", {"transitions": rows}, WORKFLOW)
            self.assertIs(r["changes_live_code"], False, rows)

    def test_moving_an_unchanged_condition_to_another_transition_changes_live_code(self):
        # The condition text is unchanged, but it now gates a different move.
        moved = self._stored_transitions()
        moved[0]["condition"], moved[1]["condition"] = moved[1]["condition"], moved[0]["condition"]
        repointed = self._stored_transitions()
        repointed[0]["next_state"] = "Pending"
        named = [{"name": self._transition(0), "action": "Reject"}]
        widened = [{"name": self._transition(0), "allowed": "All"}]
        for rows in (moved, repointed, named, widened):
            r = _impact("update_document", "Workflow", {"transitions": rows}, WORKFLOW)
            self.assertIs(r["changes_live_code"], True, rows)

    def test_creating_a_workflow_with_a_transition_condition_changes_live_code(self):
        data = {"workflow_name": "New flow", "document_type": "ToDo"}
        with_condition = {
            **data,
            "transitions": [{"state": "Pending", "condition": "doc.priority == 'High'"}],
        }
        without = {**data, "transitions": [{"state": "Pending", "condition": ""}]}
        self.assertIs(_impact("create_document", "Workflow", with_condition)["changes_live_code"], True)
        self.assertIs(_impact("create_document", "Workflow", without)["changes_live_code"], False)

    # Custom Field and Property Setter eval: conditions

    def test_editing_a_custom_fields_eval_condition_changes_live_code(self):
        for data in (
            {"depends_on": "eval:doc.status == 'Closed'"},
            {"depends_on": "status"},
            {"read_only_depends_on": "eval:1"},
            {"mandatory_depends_on": "eval:doc.priority == 'High'"},
        ):
            r = _impact("update_document", "Custom Field", data, CUSTOM_FIELD)
            self.assertIs(r["changes_live_code"], True, data)

    def test_a_custom_fields_bare_fieldname_condition_is_not_code(self):
        for data in ({"mandatory_depends_on": "priority"}, {"depends_on": OPEN}, {"label": "Note"}):
            r = _impact("update_document", "Custom Field", data, CUSTOM_FIELD)
            self.assertIs(r["changes_live_code"], False, data)

    def test_creating_a_custom_field_with_an_eval_condition_changes_live_code(self):
        data = {"dt": "ToDo", "fieldname": "fac_new", "fieldtype": "Data"}
        for key in ("depends_on", "mandatory_depends_on", "read_only_depends_on"):
            r = _impact("create_document", "Custom Field", {**data, key: OPEN})
            self.assertIs(r["changes_live_code"], True, key)
        bare = _impact("create_document", "Custom Field", {**data, "depends_on": "status"})
        self.assertIs(bare["changes_live_code"], False)

    def test_a_property_setters_eval_condition_value_changes_live_code(self):
        r = _impact(
            "update_document", "Property Setter", {"value": "eval:doc.priority == 'High'"}, PROPERTY_SETTER
        )
        self.assertIs(r["changes_live_code"], True)
        same = _impact("update_document", "Property Setter", {"value": OPEN}, PROPERTY_SETTER)
        self.assertIs(same["changes_live_code"], False)
        data = {"doc_type": "ToDo", "doctype_or_field": "DocField", "field_name": "priority"}
        for prop, value, expected in (
            ("read_only_depends_on", OPEN, True),
            ("mandatory_depends_on", "eval:true", True),
            ("depends_on", "status", False),
            ("label", OPEN, False),
        ):
            r = _impact("create_document", "Property Setter", {**data, "property": prop, "value": value})
            self.assertIs(r["changes_live_code"], expected, prop)

    # Notification Recipient condition, cc and bcc

    def test_editing_a_recipients_code_changes_live_code(self):
        row = self.notification.recipients[0].name
        for change in (
            {"cc": "{{ doc.owner }}"},
            {"bcc": "audit@example.com"},
            {"condition": "doc.priority == 'Low'"},
        ):
            rows = [{"name": row, **change}]
            r = _impact("update_document", "Notification", {"recipients": rows}, NOTIFICATION)
            self.assertIs(r["changes_live_code"], True, change)
        appended = [{"receiver_by_role": "System Manager", "bcc": "{{ doc.owner }}"}]
        r = _impact("update_document", "Notification", {"recipients": appended}, NOTIFICATION)
        self.assertIs(r["changes_live_code"], True)

    def test_recipients_that_keep_their_code_do_not_change_live_code(self):
        row = self.notification.recipients[0].name
        same = [{"name": row, "cc": "manager@example.com", "receiver_by_role": "System Manager"}]
        r = _impact("update_document", "Notification", {"recipients": same}, NOTIFICATION)
        self.assertIs(r["changes_live_code"], False)

    def test_moving_a_recipients_cc_to_another_receiver_changes_live_code(self):
        # The cc is unchanged, but it now rides on emails to a different receiver.
        row = self.notification.recipients[0].name
        patched = [{"name": row, "receiver_by_role": "Administrator"}]
        replaced = [
            {
                "receiver_by_role": "Administrator",
                "condition": "doc.priority == 'High'",
                "cc": "manager@example.com",
            }
        ]
        for rows in (patched, replaced):
            r = _impact("update_document", "Notification", {"recipients": rows}, NOTIFICATION)
            self.assertIs(r["changes_live_code"], True, rows)

    # Script Report edits after a covered create (case 4)

    def test_editing_a_script_report_created_through_the_tool_changes_live_code(self):
        # Production reaches this report when FACO creates it on an approved build plan; AR's
        # create entry then covers the edit below, so this answer alone decides its card.
        data = {
            "report_name": "FAC Live Code Report",
            "ref_doctype": "ToDo",
            "report_type": "Script Report",
            "report_script": "data = [1]",
        }
        self.assertIs(_impact("create_document", "Report", data)["changes_live_code"], True)
        created = DocumentCreate().execute({"doctype": "Report", "data": data})
        self.assertTrue(created["success"], created)
        for change in ({"report_script": "data = [2]"}, {"javascript": "frappe.query_reports['x'] = {}"}):
            r = _impact("update_document", "Report", change, created["name"])
            self.assertIs(r["changes_live_code"], True, change)
        same = _impact("update_document", "Report", {"report_script": "data = [1]"}, created["name"])
        self.assertIs(same["changes_live_code"], False)
