# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Tests for connect_fac_mcp_server self-provisioning gate.

A FACO member (Active/Pending AR Tenant User) may self-provision their MCP
server; a non-member is blocked even if they hold System Manager, since the
seat — not the Frappe role — is what authorizes use.
"""

from unittest.mock import patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestConnectMcpMembership(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def _make_user(self, email, roles=None):
        if not frappe.db.exists("User", email):
            u = frappe.get_doc(
                {
                    "doctype": "User",
                    "email": email,
                    "first_name": "Connect",
                    "enabled": 1,
                    "send_welcome_email": 0,
                }
            )
            u.insert(ignore_permissions=True)
        u = frappe.get_doc("User", email)
        u.set("roles", [])
        for r in roles or []:
            u.append("roles", {"role": r})
        u.save(ignore_permissions=True)
        return email

    def test_member_can_self_provision(self):
        email = self._make_user("connect_member@example.com", roles=["Purchase Manager"])
        frappe.set_user(email)
        from frappe_assistant_core.chat.api.auth import connect_fac_mcp_server

        try:
            with patch(
                "frappe_assistant_core.chat.api.settings.access._is_faco_member",
                return_value=True,
            ), patch(
                "frappe_assistant_core.chat.api.auth._register_user_with_ar",
                return_value={"success": True, "user_id": email},
            ) as mock_reg:
                result = connect_fac_mcp_server()
        finally:
            frappe.set_user("Administrator")

        self.assertTrue(result.get("success"), f"member should self-provision, got {result}")
        mock_reg.assert_called_once()

    def test_non_member_blocked(self):
        """Even a System Manager who is not a member is blocked — the seat, not
        the role, authorizes self-provisioning."""
        email = self._make_user("connect_outsider@example.com", roles=["System Manager"])
        frappe.set_user(email)
        from frappe_assistant_core.chat.api.auth import connect_fac_mcp_server

        try:
            with patch(
                "frappe_assistant_core.chat.api.settings.access._is_faco_member",
                return_value=False,
            ), patch(
                "frappe_assistant_core.chat.api.auth._is_tenant_owner",
                return_value=False,
            ), patch(
                "frappe_assistant_core.chat.api.auth._register_user_with_ar",
            ) as mock_reg:
                with self.assertRaises(frappe.PermissionError):
                    connect_fac_mcp_server()
                mock_reg.assert_not_called()
        finally:
            frappe.set_user("Administrator")

    def test_owner_can_self_provision_without_seat(self):
        """The tenant owner may self-provision even before any AR Tenant User
        seat exists — breaking the chicken-and-egg where membership is created
        by the very call the guard would block."""
        email = self._make_user("connect_owner@example.com", roles=["System Manager"])
        frappe.set_user(email)
        from frappe_assistant_core.chat.api.auth import connect_fac_mcp_server

        try:
            with patch(
                "frappe_assistant_core.chat.api.settings.access._is_faco_member",
                return_value=False,
            ), patch(
                "frappe_assistant_core.chat.api.auth._is_tenant_owner",
                return_value=True,
            ), patch(
                "frappe_assistant_core.chat.api.auth._register_user_with_ar",
                return_value={"success": True, "user_id": email},
            ) as mock_reg:
                result = connect_fac_mcp_server()
        finally:
            frappe.set_user("Administrator")

        self.assertTrue(result.get("success"), f"owner should self-provision, got {result}")
        mock_reg.assert_called_once()
