# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Tests for team user-management endpoints (invite + member-audit SDK wrappers)."""

from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.api import users as users_api
from frappe_assistant_core.chat.api.auth import _ar_user_id
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestTeamUserEndpoints(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def _mock_client(self):
        client = MagicMock()
        client.invite_user.return_value = {"success": True, "user_id": "x@e.com", "status": "Pending"}
        client.revoke_invite.return_value = {"success": True}
        client.resend_invite.return_value = {"success": True}
        client.list_invites.return_value = {"invites": []}
        client.get_member_audit_log.return_value = {"entries": []}
        return client

    def test_invite_user_calls_sdk_with_actor(self):
        client = self._mock_client()
        with patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client):
            result = users_api.invite_user(user_id="x@e.com", user_role="Admin")
        self.assertTrue(result["success"])
        # FAC must pass invited_by = acting user's AR identity (email), since AR
        # keys its owner/admin authority check by email.
        kwargs = client.invite_user.call_args.kwargs
        self.assertEqual(kwargs.get("invited_by"), _ar_user_id("Administrator"))
        self.assertEqual(kwargs.get("user_role"), "Admin")

    def test_revoke_invite_passes_actor(self):
        client = self._mock_client()
        with patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client):
            result = users_api.revoke_invite(user_id="x@e.com")
        self.assertTrue(result["success"])
        self.assertEqual(
            client.revoke_invite.call_args.kwargs.get("revoked_by"), _ar_user_id("Administrator")
        )

    def test_resend_invite_passes_actor(self):
        client = self._mock_client()
        with patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client):
            result = users_api.resend_invite(user_id="x@e.com")
        self.assertTrue(result["success"])
        self.assertEqual(client.resend_invite.call_args.kwargs.get("resent_by"), _ar_user_id("Administrator"))

    def test_get_user_limit_status_surfaces_credit_quota(self):
        # UserLimitCard's credit pool used to be recomputed client-side from
        # credits_per_user x seats -- wrong under proration. The pool must
        # instead come straight from the tenant's subscription, through the
        # same flat-dict enrichment that already carries min_users etc.
        client = self._mock_client()
        client.get_user_limit_status.return_value = {"active_users": 5, "max_users": 10}
        client.get_tenant_info.return_value = {
            "subscription": {"min_users": 3, "credit_quota": 12345},
        }
        with patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client):
            result = users_api.get_user_limit_status()
        self.assertEqual(result["credit_quota"], 12345)

    def test_get_user_limit_status_credit_quota_defaults_to_zero(self):
        # A payments-less install's RuntimeGate.get_tenant_info default has no
        # credit_quota key at all (unlike the payments-installed-but-no-
        # subscription path, which does default it to 0) -- sub.get() alone
        # yields None here, not 0.
        client = self._mock_client()
        client.get_user_limit_status.return_value = {"active_users": 0, "max_users": 0}
        client.get_tenant_info.return_value = {"subscription": {}}
        with patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client):
            result = users_api.get_user_limit_status()
        self.assertEqual(result["credit_quota"], 0)

    def test_list_invites_passthrough(self):
        client = self._mock_client()
        with patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client):
            result = users_api.list_invites()
        self.assertEqual(result, {"invites": []})

    def test_get_member_audit_log_passthrough(self):
        client = self._mock_client()
        with patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client):
            result = users_api.get_member_audit_log()
        self.assertEqual(result, {"entries": []})

    def test_get_member_audit_log_passes_int_pagination(self):
        client = self._mock_client()
        with patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client):
            users_api.get_member_audit_log(limit="25", offset="5")
        kwargs = client.get_member_audit_log.call_args.kwargs
        self.assertEqual(kwargs.get("limit"), 25)
        self.assertEqual(kwargs.get("offset"), 5)

    def test_invite_requires_system_manager(self):
        frappe.set_user("Guest")
        try:
            with self.assertRaises(frappe.PermissionError):
                users_api.invite_user(user_id="x@e.com")
        finally:
            frappe.set_user("Administrator")

    def test_invite_user_creates_desk_notification(self):
        invited_email = "invitee_notif@example.com"
        if not frappe.db.exists("User", invited_email):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": invited_email,
                    "first_name": "Invitee",
                    "enabled": 1,
                    "send_welcome_email": 0,
                }
            ).insert(ignore_permissions=True)

        # Clear any prior notifications for a clean assert.
        frappe.db.delete("Notification Log", {"for_user": invited_email})

        client = self._mock_client()
        client.invite_user.return_value = {
            "success": True,
            "user_id": invited_email,
            "status": "Pending",
        }
        with patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client):
            result = users_api.invite_user(user_id=invited_email, user_role="User")

        self.assertTrue(result.get("success"))
        logs = frappe.get_all(
            "Notification Log",
            filters={"for_user": invited_email, "type": "Alert"},
            fields=["name", "subject"],
        )
        self.assertTrue(len(logs) >= 1, "expected a Desk notification for the invited user")
        self.assertIn("invite", logs[0]["subject"].lower())

    def test_invite_notification_skipped_for_nonexistent_user(self):
        # Inviting an email with no enabled User on this site must NOT raise.
        ghost = "ghost_nouser@example.com"
        self.assertFalse(frappe.db.exists("User", ghost))

        client = self._mock_client()
        client.invite_user.return_value = {
            "success": True,
            "user_id": ghost,
            "status": "Pending",
        }
        with patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client):
            result = users_api.invite_user(user_id=ghost, user_role="User")

        # Invite still succeeds; notification just silently skipped.
        self.assertTrue(result.get("success"))
        logs = frappe.get_all("Notification Log", filters={"for_user": ghost})
        self.assertEqual(len(logs), 0)

    def test_resend_invite_creates_desk_notification(self):
        invited_email = "invitee_resend@example.com"
        if not frappe.db.exists("User", invited_email):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": invited_email,
                    "first_name": "Resend",
                    "enabled": 1,
                    "send_welcome_email": 0,
                }
            ).insert(ignore_permissions=True)

        frappe.db.delete("Notification Log", {"for_user": invited_email})

        client = self._mock_client()
        with patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client):
            result = users_api.resend_invite(user_id=invited_email)

        self.assertTrue(result.get("success"))
        logs = frappe.get_all(
            "Notification Log",
            filters={"for_user": invited_email, "type": "Alert"},
            fields=["name", "subject"],
        )
        self.assertTrue(len(logs) >= 1, "expected a Desk notification on resend")
