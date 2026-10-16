# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Users whose memory consent came from a pre-ticked switch are asked to confirm it.

AR withdraws that consent and reports ``memory_consent_pending`` (from its
reset_pre_ticked_memory_consent patch) on get_user_auth_status and get_user. FAC passes
the flag to the SPA and records the answer: keep turns consent back on; turn off keeps it
off and deletes the user's memories. The SDK client is autospecced so a call to a method
the pinned SDK lacks fails here instead of in production.
"""

from unittest.mock import create_autospec, patch

import frappe
from assistant_runtime_sdk.client import AssistantRuntimeClient

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestMemoryConsentConfirm(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.email = frappe.db.get_value("User", "Administrator", "email")
        self.client = create_autospec(AssistantRuntimeClient, instance=True)
        p = patch("frappe_assistant_core.chat.api.privacy._get_client", return_value=self.client)
        p.start()
        self.addCleanup(p.stop)

    def test_keeping_memory_grants_consent_and_deletes_nothing(self):
        from frappe_assistant_core.chat.api import privacy

        self.assertEqual(privacy.confirm_memory_consent(keep=True), {"memory_consent": True})
        self.client.update_user_consent.assert_called_once_with(
            user_id=self.email, consent_type="memory", granted=True
        )
        self.client.delete_all_memories.assert_not_called()

    def test_turning_memory_off_withdraws_consent_then_deletes_memories(self):
        from frappe_assistant_core.chat.api import privacy

        calls = []
        self.client.update_user_consent.side_effect = lambda **kw: calls.append("consent")
        self.client.delete_all_memories.side_effect = lambda **kw: calls.append("delete")

        self.assertEqual(privacy.confirm_memory_consent(keep="false"), {"memory_consent": False})
        self.client.update_user_consent.assert_called_once_with(
            user_id=self.email, consent_type="memory", granted=False
        )
        self.client.delete_all_memories.assert_called_once_with(user_id=self.email)
        self.assertEqual(calls, ["consent", "delete"])

    def test_privacy_config_reports_pending(self):
        from frappe_assistant_core.chat.api import privacy

        self.client.get_tenant_privacy_config.return_value = {"default_memory_consent": "Opt-In"}
        self.client.get_user.return_value = {
            "memory_consent": False,
            "memory_consent_pending": True,
            "processing_restricted": False,
        }
        config = privacy.get_privacy_config()
        self.assertIs(config["user_privacy"]["memory_consent_pending"], True)


class TestBootUserAuthCarriesPending(BaseAssistantTest):
    def test_format_user_auth_passes_pending_through(self):
        from frappe_assistant_core.chat.api.init import _format_user_auth

        settings = frappe._dict(registration_status="Registered")
        auth = _format_user_auth(
            {
                "user_exists": True,
                "user_status": "Active",
                "memory_consent_pending": True,
                "has_mcp_servers": True,
                "active_server_count": 1,
                "servers_with_expired_tokens": [],
                "ready_for_streaming": True,
            },
            settings,
        )
        self.assertIs(auth["memory_consent_pending"], True)
