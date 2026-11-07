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

"""Content-free facts about any managed write, for FAC Cloud's approval level."""

import frappe

from frappe_assistant_core.plugins.faco.tools.customisation_impact import CustomisationImpact
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.change_facts import change_facts


class TestChangeFacts(BaseAssistantTest):
    def test_business_create_facts(self):
        facts = change_facts("create_document", {"doctype": "Note", "data": {"title": "x"}})
        self.assertEqual(
            facts,
            {
                "doctype_kind": "business",
                "is_money_or_stock": False,
                "submits": False,
                "sends_messages": False,
                "exists": None,
                "bulk": False,
            },
        )

    def test_facts_are_real_bools(self):
        facts = change_facts("create_document", {"doctype": "Journal Entry", "data": {}})
        for key in ("is_money_or_stock", "submits", "sends_messages", "bulk"):
            self.assertIs(type(facts[key]), bool, key)

    def test_money_doctype(self):
        facts = change_facts("create_document", {"doctype": "Journal Entry", "data": {}})
        self.assertTrue(facts["is_money_or_stock"])

    def test_submit_flag(self):
        facts = change_facts("update_document", {"doctype": "Note", "name": "x", "data": {"docstatus": 1}})
        self.assertTrue(facts["submits"])
        facts = change_facts("update_document", {"doctype": "Note", "name": "x", "data": {}, "submit": True})
        self.assertTrue(facts["submits"])
        facts = change_facts("delete_document", {"doctype": "Note", "name": "x", "data": {"docstatus": 1}})
        self.assertFalse(facts["submits"])

    def test_todo_and_notified_doctypes_send_messages(self):
        self.assertTrue(change_facts("create_document", {"doctype": "ToDo", "data": {}})["sends_messages"])
        # An admin creates a Notification for that doctype in Desk; the test rollback removes it.
        frappe.get_doc(
            {
                "doctype": "Notification",
                "subject": "FAC facts test",
                "document_type": "Note",
                "event": "New",
                "channel": "System Notification",
                "enabled": 1,
                "message": "x",
                "recipients": [{"receiver_by_document_field": "owner"}],
            }
        ).insert(ignore_permissions=True)
        self.assertTrue(change_facts("create_document", {"doctype": "Note", "data": {}})["sends_messages"])

    def test_user_is_user_admin(self):
        facts = change_facts("update_document", {"doctype": "User", "name": "Administrator", "data": {}})
        self.assertEqual(facts["doctype_kind"], "user_admin")
        self.assertIs(facts["exists"], True)

    def test_customisation_and_system_kinds(self):
        self.assertEqual(
            change_facts("create_document", {"doctype": "Server Script", "data": {}})["doctype_kind"],
            "customisation",
        )
        self.assertEqual(
            change_facts("create_document", {"doctype": "System Settings", "data": {}})["doctype_kind"],
            "system",
        )

    def test_exists_for_missing_record(self):
        facts = change_facts("delete_document", {"doctype": "Note", "name": "no-such-note-fac"})
        self.assertIs(facts["exists"], False)

    def test_bulk_shape(self):
        self.assertTrue(change_facts("create_document", {"doctype": "Note", "records": []})["bulk"])
        self.assertTrue(change_facts("delete_document", {"doctype": "Note", "names": ["a"]})["bulk"])

    def test_bad_input_is_empty(self):
        self.assertEqual(change_facts("create_document", {"data": {}}), {})
        self.assertEqual(change_facts("create_document", {"doctype": "No Such Doctype Fac"}), {})
        self.assertEqual(change_facts("create_document", {"doctype": 5}), {})

    def test_impact_payload_carries_facts(self):
        tool_input = {"doctype": "Note", "data": {"title": "x"}}
        result = CustomisationImpact().execute({"tool_name": "create_document", "tool_input": tool_input})
        self.assertEqual(result["facts"], change_facts("create_document", tool_input))
        self.assertIs(result["success"], True)
        self.assertIn("changes_live_code", result)
        self.assertIn("switches_on", result)
