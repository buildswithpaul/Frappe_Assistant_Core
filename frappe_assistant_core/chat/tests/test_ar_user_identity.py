# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Tests for _ar_user_id() — the email-keyed identity FAC sends to AR.

AR keys AR Tenant Users by email. For ordinary staff the Frappe username IS
their email, so normalization is a pass-through; the case that matters is the
Administrator account, whose username ("Administrator") is not an email but
whose User record carries the owner's email. That account must resolve to its
email so the owner is recognized as the tenant owner on AR.
"""

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestArUserIdentity(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def _make_user(self, email):
        if not frappe.db.exists("User", email):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": email,
                    "first_name": "Ident",
                    "enabled": 1,
                    "send_welcome_email": 0,
                }
            ).insert(ignore_permissions=True)
        return email

    def test_email_username_passes_through(self):
        """A staff user whose username is already an email resolves to itself."""
        from frappe_assistant_core.chat.api.auth import _ar_user_id

        email = self._make_user("ident_staff@example.com")
        self.assertEqual(_ar_user_id(email), "ident_staff@example.com")

    def test_administrator_resolves_to_its_email(self):
        """Administrator (username has no '@') resolves to the User.email field.

        Patched rather than read from the site: an untouched Frappe install
        leaves that field as the `admin@example.com` placeholder, which is
        deliberately NOT an identity — see test_placeholder_identity.py. This
        asserts the normalization itself, on a site whose admin has a real
        address.
        """
        from unittest.mock import patch

        from frappe_assistant_core.chat.api.auth import _ar_user_id

        with patch("frappe.db.get_value", return_value="owner@promantia.com"):
            self.assertEqual(_ar_user_id("Administrator"), "owner@promantia.com")

    def test_defaults_to_session_user(self):
        """With no argument, normalizes the current session user."""
        from frappe_assistant_core.chat.api.auth import _ar_user_id

        email = self._make_user("ident_session@example.com")
        frappe.set_user(email)
        try:
            self.assertEqual(_ar_user_id(), "ident_session@example.com")
        finally:
            frappe.set_user("Administrator")
