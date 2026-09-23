# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Regression: the SPA boot path must use the single authoritative access gate.

The production lockout: ``initialize_spa`` (the SPA boot endpoint) built its
access block via ``init._build_access``, a stale COPY of ``can_use_faco`` that
still did the OLD Frappe-role check after ``can_use_faco`` had moved to
authoritative AR membership (``_is_faco_member``). A real Pending member with no
assistant Frappe role got ``can_use=False`` → lock screen, even though calling
``can_use_faco`` directly returned ``can_use=True``.

A 3rd stale copy lived in ``voice._user_can_use_faco`` (same role tuple).

These tests pin both ``_build_access`` and ``voice._user_can_use_faco`` to the
authoritative gate so the boot path and the standalone endpoint can never
diverge again.
"""

from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestInitializeSpaAccess(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def test_build_access_delegates_to_can_use_faco(self):
        """initialize_spa's access must come from the authoritative gate, not a
        stale role check. The gate's verdict is returned verbatim — the exact
        production-lockout scenario, where a member with NO assistant Frappe
        role must still get can_use=True."""
        from frappe_assistant_core.chat.api import init as init_mod

        sentinel = {
            "can_use": True,
            "status": "ready",
            "show_widget": True,
            "is_admin": False,
            "user": "paul.clinton@gmail.com",
            "fac_cloud_url": "https://assistantruntime.cloud",
            "preferences": {},
        }
        with patch(
            "frappe_assistant_core.chat.api.settings.access.can_use_faco",
            return_value=sentinel,
        ) as mock_gate:
            settings = frappe.get_single("FAC Chat Settings")
            result = init_mod._build_access(settings, "paul.clinton@gmail.com", [], False)

        self.assertTrue(
            mock_gate.called,
            "_build_access must delegate to can_use_faco, not reimplement the gate",
        )
        self.assertEqual(result, sentinel, "_build_access must return can_use_faco's verdict verbatim")

    def test_voice_gate_uses_membership_not_role(self):
        """voice._user_can_use_faco must use authoritative membership, not a
        Frappe role. A member is allowed; a non-member is denied even with
        System Manager (USE follows the seat, not the role)."""
        from frappe_assistant_core.chat.api.voice import _user_can_use_faco

        member = self._make_non_admin_user("voice.member@example.com")
        admin = self._make_non_admin_user("voice.admin@example.com")
        admin_doc = frappe.get_doc("User", admin)
        admin_doc.append("roles", {"role": "System Manager"})
        admin_doc.save(ignore_permissions=True)

        try:
            frappe.set_user(member)
            with patch(
                "frappe_assistant_core.chat.api.settings.access._is_faco_member",
                return_value=True,
            ):
                self.assertTrue(
                    _user_can_use_faco(),
                    "a FACO member must be allowed to use voice",
                )
            with patch(
                "frappe_assistant_core.chat.api.settings.access._is_faco_member",
                return_value=False,
            ):
                self.assertFalse(
                    _user_can_use_faco(),
                    "a non-member must be denied voice",
                )

            frappe.set_user(admin)
            with patch(
                "frappe_assistant_core.chat.api.settings.access._is_faco_member",
                return_value=False,
            ):
                self.assertFalse(
                    _user_can_use_faco(),
                    "a System Manager who is not a member must be denied voice",
                )
        finally:
            frappe.set_user("Administrator")

    def test_initialize_spa_queries_ar_auth_by_email_not_docname(self):
        """The SPA boot path must ask AR for auth status by the normalized AR
        identity (email), exactly like the standalone get_user_auth_status.

        Regression: initialize_spa passed the raw Frappe docname
        (frappe.session.user = "Administrator") to client.get_user_auth_status.
        AR keys AR Tenant Users by email, so the lookup found no seat →
        ready=False → the SPA rendered "Connect Your Account" on every load,
        even though the owner had an Active seat and get_user_auth_status
        (which normalizes to email) returned ready=True.
        """
        from frappe_assistant_core.chat.api import init as init_mod
        from frappe_assistant_core.chat.api.auth import _ar_user_id

        captured = {}

        def _fake_auth(user_id=None):
            captured["user_id"] = user_id
            return {
                "user_exists": True,
                "user_status": "Active",
                "has_mcp_servers": True,
                "active_server_count": 1,
                "servers_with_expired_tokens": [],
                "ready_for_streaming": True,
            }

        fake_client = MagicMock()
        fake_client.get_user_auth_status.side_effect = _fake_auth

        gate = {
            "can_use": True,
            "status": "ready",
            "show_widget": True,
            "is_admin": True,
            "user": "Administrator",
            "fac_cloud_url": "https://assistantruntime.cloud",
            "preferences": {},
        }

        with patch(
            "frappe_assistant_core.chat.api.settings.access.can_use_faco",
            return_value=gate,
        ), patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
            return_value=fake_client,
        ):
            result = init_mod.initialize_spa()

        expected = _ar_user_id("Administrator")
        self.assertEqual(
            captured.get("user_id"),
            expected,
            "initialize_spa must query AR auth by the email identity, not the docname",
        )
        self.assertNotEqual(
            captured.get("user_id"),
            "Administrator",
            "raw docname leaked to AR — the email-normalization sweep missed this call site",
        )
        self.assertTrue(
            result["user_auth"]["ready"],
            "a seated owner must boot ready, not to the Connect screen",
        )

    def _make_non_admin_user(self, email: str) -> str:
        """A user with NO System Manager / assistant roles, so the membership
        signal is the only thing that can grant access."""
        if not frappe.db.exists("User", email):
            u = frappe.get_doc(
                {
                    "doctype": "User",
                    "email": email,
                    "first_name": "Voice",
                    "enabled": 1,
                    "send_welcome_email": 0,
                }
            )
            u.insert(ignore_permissions=True)
        u = frappe.get_doc("User", email)
        u.set("roles", [])
        u.save(ignore_permissions=True)
        return email
