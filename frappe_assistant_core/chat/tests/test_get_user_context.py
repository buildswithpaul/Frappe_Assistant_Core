# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""_get_user_context must resolve the Frappe User whether given a docname or email.

Registration now keys AR by email (_ar_user_id), so _get_user_context is called
with an email. For ordinary staff the email IS the User docname, so the lookup
works. But for the Administrator account (docname "Administrator", email
paul.clinton@...), an email lookup finds no User docname and the context — name,
locale, timezone, role — was silently dropped. This pins that it resolves via
the email field too.
"""

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestGetUserContext(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def test_context_populated_for_email_of_administrator(self):
        from frappe_assistant_core.chat.api.auth import _get_user_context

        admin_email = frappe.db.get_value("User", "Administrator", "email")
        self.assertTrue(admin_email and "@" in admin_email)

        ctx = _get_user_context(admin_email)

        # Must NOT be empty — the Administrator's context should resolve via email.
        self.assertTrue(ctx, "context dropped for Administrator's email")
        self.assertEqual(ctx.get("email"), admin_email)
        self.assertEqual(ctx.get("user_role"), "Admin")  # Administrator has System Manager
        self.assertTrue(ctx.get("display_name"))

    def test_context_populated_for_email_username_staff(self):
        from frappe_assistant_core.chat.api.auth import _get_user_context

        email = "ctx_staff@example.com"
        if not frappe.db.exists("User", email):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": email,
                    "first_name": "Ctx",
                    "enabled": 1,
                    "send_welcome_email": 0,
                }
            ).insert(ignore_permissions=True)

        ctx = _get_user_context(email)
        self.assertEqual(ctx.get("email"), email)
        self.assertEqual(ctx.get("display_name"), "Ctx")
