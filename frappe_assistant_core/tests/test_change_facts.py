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
from frappe_assistant_core.tests.base_test import (
    CUSTOM_TEST_DOCTYPE,
    BaseAssistantTest,
    ensure_custom_test_doctype,
)
from frappe_assistant_core.utils.change_facts import change_facts
from frappe_assistant_core.utils.customisation import customisation_impact


class TestChangeFacts(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        ensure_custom_test_doctype()
        super().setUpClass()

    def setUp(self):
        super().setUp()
        # The class shares one transaction, so rows a test inserts would leak into later tests.
        frappe.db.savepoint("change_facts")
        self.addCleanup(frappe.db.rollback, save_point="change_facts")

    def test_business_create_facts(self):
        facts = change_facts("create_document", {"doctype": "Note", "data": {"title": "x"}})
        self.assertEqual(
            facts,
            {
                "doctype_kind": "business",
                "is_money_or_stock": False,
                "submits": False,
                "sends_messages": False,
                "custom_doctype": False,
                "affects_others": False,
                "exists": None,
                "bulk": False,
            },
        )

    def test_facts_are_real_bools(self):
        facts = change_facts("create_document", {"doctype": "Journal Entry", "data": {}})
        for key in (
            "is_money_or_stock",
            "submits",
            "sends_messages",
            "bulk",
            "custom_doctype",
            "affects_others",
        ):
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
        facts = result.pop("facts")
        self.assertEqual(facts, change_facts("create_document", tool_input))
        self.assertEqual(result, {"success": True, **customisation_impact("create_document", tool_input)})

    def test_document_action_and_run_workflow_submit(self):
        base = {"doctype": "Note", "name": "x"}
        self.assertTrue(change_facts("document_action", base)["submits"])
        for action in ("submit", "cancel", "amend"):
            self.assertTrue(change_facts("document_action", {**base, "action": action})["submits"], action)
        self.assertTrue(change_facts("run_workflow", {**base, "action": "Approve"})["submits"])

    def test_assignment_rule_sends_messages(self):
        # An admin creates an Assignment Rule for that doctype in Desk; the test rollback removes it.
        rule = frappe.get_doc(
            {
                "doctype": "Assignment Rule",
                "__newname": "FAC facts test rule",
                "document_type": "Note",
                "assign_condition": "1 == 1",
                "rule": "Round Robin",
                "description": "x",
                "priority": 0,
                "assignment_days": [{"day": "Monday"}],
                "users": [{"user": "Administrator"}],
            }
        ).insert(ignore_permissions=True)
        self.assertTrue(change_facts("create_document", {"doctype": "Note", "data": {}})["sends_messages"])
        rule.db_set("disabled", 1)
        self.assertFalse(change_facts("create_document", {"doctype": "Note", "data": {}})["sends_messages"])

    def test_workflow_email_alert_sends_messages(self):
        # An admin creates an active Workflow with email alerts for that doctype in Desk,
        # adding its state from the link field first; fresh sites have no Workflow State rows.
        if not frappe.db.exists("Workflow State", "FAC Facts Draft"):
            frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": "FAC Facts Draft"}).insert(
                ignore_permissions=True
            )
        frappe.get_doc(
            {
                "doctype": "Workflow",
                "workflow_name": "FAC facts test workflow",
                "document_type": "Note",
                "is_active": 1,
                "send_email_alert": 1,
                "workflow_state_field": "title",
                "states": [{"state": "FAC Facts Draft", "doc_status": "0", "allow_edit": "All"}],
            }
        ).insert(ignore_permissions=True)
        self.assertTrue(change_facts("create_document", {"doctype": "Note", "data": {}})["sends_messages"])

    def test_webhook_sends_messages(self):
        # An admin creates a Webhook on that doctype in Desk; the test rollback removes it.
        frappe.get_doc(
            {
                "doctype": "Webhook",
                "__newname": "FAC facts test webhook",
                "webhook_doctype": "Note",
                "webhook_docevent": "after_insert",
                "request_url": "https://example.com/hook",
                "request_structure": "Form URL-Encoded",
                "enabled": 1,
            }
        ).insert(ignore_permissions=True)
        self.assertTrue(change_facts("create_document", {"doctype": "Note", "data": {}})["sends_messages"])

    def test_password_field_doctype_is_user_admin(self):
        # Google Calendar sits in the Integrations module and has Password fields but no api_key.
        facts = change_facts("create_document", {"doctype": "Google Calendar", "data": {}})
        self.assertEqual(facts["doctype_kind"], "user_admin")

    def test_automation_doctypes_are_system(self):
        for doctype in ("Assignment Rule", "Auto Repeat", "Reminder"):
            facts = change_facts("create_document", {"doctype": doctype, "data": {}})
            self.assertEqual(facts["doctype_kind"], "system", doctype)

    def test_string_docstatus_submits(self):
        facts = change_facts("update_document", {"doctype": "Note", "name": "x", "data": {"docstatus": "1"}})
        self.assertTrue(facts["submits"])

    def test_create_never_reports_exists(self):
        facts = change_facts("create_document", {"doctype": "Note", "name": "x", "data": {}})
        self.assertIsNone(facts["exists"])

    def test_custom_doctype_fact(self):
        facts = change_facts("create_document", {"doctype": CUSTOM_TEST_DOCTYPE, "data": {}})
        self.assertIs(facts["custom_doctype"], True)
        self.assertIs(facts["affects_others"], False)
        self.assertIs(
            change_facts("create_document", {"doctype": "Note", "data": {}})["custom_doctype"], False
        )

    def test_go_live_doctypes_affect_others(self):
        for doctype in ("Web Page", "Workspace", "Letter Head", "Print Format", "Dashboard Chart"):
            facts = change_facts("create_document", {"doctype": doctype, "data": {}})
            self.assertIs(facts["affects_others"], True, doctype)

    def test_go_live_fields_affect_others(self):
        for data in ({"public": 1}, {"public": "1"}, {"notify_on_login": True}, {"is_default": 1}):
            facts = change_facts("create_document", {"doctype": "Note", "data": data})
            self.assertIs(facts["affects_others"], True, data)
        for data in ({"public": 0}, {"public": "0"}, {"title": "public"}):
            facts = change_facts("update_document", {"doctype": "Note", "name": "x", "data": data})
            self.assertIs(facts["affects_others"], False, data)

    def test_batch_records_that_go_live_affect_others(self):
        create = {"doctype": "Note", "records": [{"title": "a"}, {"title": "b", "public": 1}]}
        self.assertIs(change_facts("create_document", create)["affects_others"], True)
        update = {"doctype": "Note", "records": [{"name": "a", "data": {"notify_on_login": 1}}]}
        self.assertIs(change_facts("update_document", update)["affects_others"], True)
        quiet = {"doctype": "Note", "records": [{"title": "a"}, {"name": "b", "data": {"title": "c"}}]}
        self.assertIs(change_facts("create_document", quiet)["affects_others"], False)
        for odd in ("x", ["x"], [{"name": "a", "data": "x"}]):
            facts = change_facts("create_document", {"doctype": "Note", "records": odd})
            self.assertIs(facts["affects_others"], True, odd)
        self.assertIs(
            change_facts("update_document", {"doctype": "Note", "data": "x"})["affects_others"], True
        )

    def test_doctype_event_server_script_sends_messages(self):
        frappe.conf.server_script_enabled = 1
        self.addCleanup(frappe.conf.pop, "server_script_enabled", None)
        # An admin writes a DocType Event Server Script for that doctype in Desk.
        script = frappe.get_doc(
            {
                "doctype": "Server Script",
                "name": "FAC facts test script",
                "script_type": "DocType Event",
                "reference_doctype": "Note",
                "doctype_event": "After Insert",
                "script": "pass",
            }
        ).insert(ignore_permissions=True)
        self.assertTrue(change_facts("create_document", {"doctype": "Note", "data": {}})["sends_messages"])
        script.db_set("disabled", 1)
        self.assertFalse(change_facts("create_document", {"doctype": "Note", "data": {}})["sends_messages"])

    def test_exception_is_logged_and_empty(self):
        from unittest.mock import patch

        with patch(
            "frappe_assistant_core.utils.change_facts._facts", side_effect=RuntimeError("boom")
        ), patch("frappe_assistant_core.utils.change_facts.frappe.logger") as logger:
            self.assertEqual(change_facts("create_document", {"doctype": "Note"}), {})
        message = logger.return_value.warning.call_args.args[0]
        self.assertIn("Note", message)
