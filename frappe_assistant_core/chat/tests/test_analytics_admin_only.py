# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Tests for the admin-only gate on usage analytics endpoints.

Usage analytics expose team-wide token spend, so they must reject any user
without System Manager. This is defense-in-depth behind the route guard.
"""

from unittest.mock import create_autospec, patch

import frappe
from assistant_runtime_sdk import AssistantRuntimeClient

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestAnalyticsAdminOnly(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def _make_non_admin(self, email):
        if not frappe.db.exists("User", email):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": email,
                    "first_name": "NA",
                    "enabled": 1,
                    "send_welcome_email": 0,
                }
            ).insert(ignore_permissions=True)
        u = frappe.get_doc("User", email)
        u.set("roles", [])
        u.save(ignore_permissions=True)
        return email

    def test_non_admin_rejected_from_analytics(self):
        email = self._make_non_admin("analytics_nonadmin@example.com")
        frappe.set_user(email)

        from frappe_assistant_core.chat.api.analytics import (
            get_analytics_data,
            get_conversation_analytics,
            get_message_credits,
        )

        try:
            with self.assertRaises(frappe.PermissionError):
                get_analytics_data()
            with self.assertRaises(frappe.PermissionError):
                get_conversation_analytics()
            with self.assertRaises(frappe.PermissionError):
                get_message_credits(conversation_id="c1")
        finally:
            frappe.set_user("Administrator")

    def test_admin_passes_the_gate(self):
        frappe.set_user("Administrator")
        from frappe_assistant_core.chat.api.analytics import get_analytics_data

        # No client -> not-registered error dict, never a PermissionError.
        with patch(
            "frappe_assistant_core.chat.api.analytics._get_client",
            return_value=None,
        ):
            res = get_analytics_data()

        self.assertIsInstance(res, dict)
        self.assertIn("error", res)

    def _analytics_with_rows(self, rows):
        from frappe_assistant_core.chat.api.analytics import get_analytics_data

        client = create_autospec(AssistantRuntimeClient, instance=True)
        client.get_token_analytics.return_value = {
            "summary": {},
            "daily": [],
            "by_model": [],
            "by_source": [],
            "by_user": rows,
        }
        with patch(
            "frappe_assistant_core.chat.api.analytics._get_client",
            return_value=client,
        ):
            return get_analytics_data()

    def test_by_user_rows_carry_full_names(self):
        email = "analytics_named@example.com"
        if not frappe.db.exists("User", email):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": email,
                    "first_name": "Avery",
                    "last_name": "Lee",
                    "enabled": 1,
                    "send_welcome_email": 0,
                }
            ).insert(ignore_permissions=True)

        res = self._analytics_with_rows(
            [
                {"user_id": email, "credits_consumed": 5},
                {"user_id": "gone@example.com", "credits_consumed": 1},
            ]
        )

        self.assertEqual(res["by_user"][0]["full_name"], "Avery Lee")
        self.assertIsNone(res["by_user"][1]["full_name"])

    def test_administrator_row_resolves_by_email(self):
        # AR reports the user's email as user_id; the Administrator's User
        # name is "Administrator", so only an email lookup resolves it.
        admin_email = frappe.db.get_value("User", "Administrator", "email")
        admin_name = frappe.db.get_value("User", "Administrator", "full_name")

        res = self._analytics_with_rows([{"user_id": admin_email, "credits_consumed": 2}])

        self.assertTrue(admin_name)
        # AR keys by docname when it holds an "@", so another User whose docname IS the
        # Administrator's email (possible on a real site) outranks the email match by design.
        docname_owner = frappe.db.get_value("User", admin_email, "full_name")
        self.assertEqual(res["by_user"][0]["full_name"], docname_owner or admin_name)

    def test_row_keyed_by_old_docname_resolves_after_an_email_change(self):
        # AR keys a user by the docname when it has an "@". A user seated as old@ whose email was
        # later changed keeps reporting under old@, so the lookup must match the docname too.
        old, new = "analytics_old@example.com", "analytics_new@example.com"
        frappe.get_doc(
            {
                "doctype": "User",
                "email": old,
                "first_name": "Morgan",
                "last_name": "Hale",
                "enabled": 1,
                "send_welcome_email": 0,
            }
        ).insert(ignore_permissions=True)
        # Production reaches this by editing the email on an existing User; the docname stays put.
        frappe.db.set_value("User", old, "email", new)

        res = self._analytics_with_rows(
            [
                {"user_id": old, "credits_consumed": 3},
                {"user_id": new, "credits_consumed": 1},
            ]
        )

        self.assertEqual(res["by_user"][0]["full_name"], "Morgan Hale")
        self.assertEqual(res["by_user"][1]["full_name"], "Morgan Hale")

    def test_user_id_matches_case_insensitively(self):
        email = "analytics_case@example.com"
        frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": "Avery",
                "last_name": "Case",
                "enabled": 1,
                "send_welcome_email": 0,
            }
        ).insert(ignore_permissions=True)

        res = self._analytics_with_rows([{"user_id": email.upper(), "credits_consumed": 1}])

        self.assertEqual(res["by_user"][0]["full_name"], "Avery Case")
