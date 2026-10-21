# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""get_current_code: the approval card diffs new code against what is stored, never leaking more."""

import frappe

from frappe_assistant_core.chat.api.current_code import CODE_KEYS, get_current_code
from frappe_assistant_core.tests.base_test import BaseAssistantTest

READER = "current-code-reader@example.com"
OUTSIDER = "current-code-outsider@example.com"
STORED = "frappe.msgprint('stored')"


def _make_user(email: str, roles: list[str]) -> None:
    if frappe.db.exists("User", email):
        frappe.delete_doc("User", email, force=True, ignore_permissions=True)
    user = frappe.get_doc(
        {"doctype": "User", "email": email, "first_name": "Code", "send_welcome_email": 0}
    ).insert(ignore_permissions=True)
    user.add_roles(*roles)


class TestGetCurrentCode(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        _make_user(READER, ["System Manager"])
        _make_user(OUTSIDER, [])
        # Created as Administrator and left disabled, so the throwaway script never runs on the site.
        self.script = frappe.get_doc(
            {
                "doctype": "Client Script",
                "name": "current-code-test-script",
                "dt": "ToDo",
                "view": "Form",
                "enabled": 0,
                "script": STORED,
            }
        ).insert()

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.delete_doc("Client Script", self.script.name, force=True, ignore_permissions=True)
        for email in (READER, OUTSIDER):
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        super().tearDown()

    def test_returns_stored_code_for_a_user_who_can_read(self):
        frappe.set_user(READER)
        out = get_current_code("Client Script", self.script.name, ["script"])
        self.assertEqual(out, {"script": STORED})

    def test_refused_for_a_user_without_read(self):
        frappe.set_user(OUTSIDER)
        with self.assertRaises(frappe.PermissionError):
            get_current_code("Client Script", self.script.name, ["script"])

    def test_ignores_fields_that_are_not_code(self):
        out = get_current_code("Client Script", self.script.name, ["script", "dt", "enabled"])
        self.assertEqual(out, {"script": STORED})

    def test_accepts_a_json_encoded_field_list(self):
        out = get_current_code("Client Script", self.script.name, '["script", "dt"]')
        self.assertEqual(out, {"script": STORED})

    def test_code_keys_match_the_card(self):
        self.assertEqual(
            list(CODE_KEYS),
            ["script", "condition", "query", "html", "javascript", "report_script", "css", "message"],
        )
