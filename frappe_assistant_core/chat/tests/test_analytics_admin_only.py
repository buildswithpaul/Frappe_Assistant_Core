# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Tests for the admin-only gate on usage analytics endpoints.

Usage analytics expose team-wide token spend, so they must reject any user
without System Manager. This is defense-in-depth behind the route guard.
"""

from unittest.mock import patch

import frappe

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
