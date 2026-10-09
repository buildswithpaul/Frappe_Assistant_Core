# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""A user the MCP endpoint will refuse must not be connected to FAC Cloud.

`fac_endpoint.handle_mcp` answers 403 to a user whose Enable Assistant Access
is off. Every connect path used to seat such a user anyway: the seat was billed,
chat opened, and each load made FAC Cloud call back into the refusal. On prod one
user produced 28 identical Error Logs in two days.
"""

from unittest.mock import create_autospec, patch

import frappe
from assistant_runtime_sdk.client import AssistantRuntimeClient

from frappe_assistant_core.tests.base_test import BaseAssistantTest

CLIENT = "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client"
AUTH_CLIENT = "frappe_assistant_core.chat.api.auth.get_fac_cloud_client"


class TestAssistantAccessPrerequisite(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.client = create_autospec(AssistantRuntimeClient, instance=True)

    def _make_user(self, email, assistant_enabled=True):
        if not frappe.db.exists("User", email):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": email,
                    "first_name": "Prereq",
                    "enabled": 1,
                    "send_welcome_email": 0,
                }
            ).insert(ignore_permissions=True)
        if not assistant_enabled:
            # How production gets here: an admin unticks Enable Assistant
            # Access on the User form.
            u = frappe.get_doc("User", email)
            u.assistant_enabled = 0
            u.save(ignore_permissions=True)
        return email

    def test_add_user_refuses_before_any_seat_is_created(self):
        from frappe_assistant_core.chat.api.users import add_user

        email = self._make_user("prereq_add_off@example.com", assistant_enabled=False)
        with patch(CLIENT, return_value=self.client):
            result = add_user(user_id=email)

        self.assertFalse(result["success"])
        self.assertIn("Enable Assistant Access", result["error"])
        self.client.register_user.assert_not_called()
        self.client.add_user_mcp_server.assert_not_called()

    def test_add_user_still_seats_a_user_with_access_on(self):
        from frappe_assistant_core.chat.api.users import add_user

        email = self._make_user("prereq_add_on@example.com")
        self.client.register_user.return_value = {"user_id": email}
        tokens = {
            "client_id": "c",
            "client_secret": "s",
            "access_token": "a",
            "refresh_token": "r",
            "expires_in": 3600,
        }
        with patch(CLIENT, return_value=self.client), patch(
            "frappe_assistant_core.chat.api.auth._get_or_create_ar_oauth_client"
        ), patch("frappe_assistant_core.chat.api.auth._generate_oauth_tokens_for_user", return_value=tokens):
            result = add_user(user_id=email)

        self.assertTrue(result["success"], result)
        self.client.register_user.assert_called_once()

    def test_invite_refuses_an_existing_user_with_access_off(self):
        from frappe_assistant_core.chat.api.users import invite_user

        email = self._make_user("prereq_invite_off@example.com", assistant_enabled=False)
        with patch(CLIENT, return_value=self.client):
            result = invite_user(user_id=email)

        self.assertFalse(result["success"])
        self.client.invite_user.assert_not_called()

    def test_self_connect_refuses_before_any_seat_is_created(self):
        from frappe_assistant_core.chat.api.auth import _register_user_with_ar

        email = self._make_user("prereq_self_off@example.com", assistant_enabled=False)
        with patch(AUTH_CLIENT, return_value=self.client):
            with self.assertRaises(frappe.ValidationError):
                _register_user_with_ar(email)

        self.client.register_user.assert_not_called()

    def test_recovery_does_not_reconnect_a_user_with_access_off(self):
        from frappe_assistant_core.chat.api.auth import _do_user_recovery

        email = self._make_user("prereq_recover_off@example.com", assistant_enabled=False)
        self.client.get_user_auth_status.return_value = {"user_exists": True}
        with self.assertRaises(frappe.ValidationError):
            _do_user_recovery(self.client, email)

        self.client.register_user.assert_not_called()


class TestVerifySiteConnection(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.client = create_autospec(AssistantRuntimeClient, instance=True)
        self.client.test_mcp_server.return_value = {"success": True, "error": None}

    def test_asks_fac_cloud_to_call_back_as_the_caller(self):
        from frappe_assistant_core.chat.api.auth import _ar_user_id, verify_site_connection

        with patch(AUTH_CLIENT, return_value=self.client):
            result = verify_site_connection()

        self.assertTrue(result["success"])
        self.client.test_mcp_server.assert_called_once_with(
            user_id=_ar_user_id("Administrator"), server_name="Main Frappe Site"
        )
