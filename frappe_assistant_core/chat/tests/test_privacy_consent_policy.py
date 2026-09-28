# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Every user learns the workspace's memory-consent policy (spec §8.1, F4).

The first-run tour pre-ticks memory consent only on an Opt-Out workspace. The
policy used to ride inside the admin-only ``tenant`` block, so a member never
saw it, and both the SPA and the mobile app pre-ticked the box even on Opt-In
workspaces. ``get_privacy_config`` now projects it to a top-level
``default_memory_consent`` for every user; retention and the privacy contact
stay admin-only.

Runs as throwaway users with the AR client mocked, so nothing leaves the site
and no real account is touched.
"""

from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest

TENANT_CONFIG = {
    "default_memory_consent": "Opt-Out",
    "conversation_retention_days": 90,
    "privacy_contact_email": "dpo@example.com",
}


class TestPrivacyConsentPolicy(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.member = self.make_throwaway_user("consent-member")
        self.admin = self.make_throwaway_user("consent-admin", roles=("System Manager",))
        self.client = MagicMock()
        self.client.get_user.return_value = {"memory_consent": False, "processing_restricted": False}
        patcher = patch("frappe_assistant_core.chat.api.privacy._get_client", return_value=self.client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _config_as(self, user: str) -> dict:
        from frappe_assistant_core.chat.api.privacy import get_privacy_config

        frappe.set_user(user)
        return get_privacy_config()

    def test_a_member_gets_the_policy_without_the_tenant_block(self):
        self.client.get_tenant_privacy_config.return_value = {
            **TENANT_CONFIG,
            "default_memory_consent": "Opt-In",
        }

        config = self._config_as(self.member)

        self.assertFalse(config["is_admin"])
        self.assertEqual(config["default_memory_consent"], "Opt-In")
        self.assertNotIn("tenant", config)

    def test_a_member_on_an_opt_out_workspace_gets_opt_out(self):
        self.client.get_tenant_privacy_config.return_value = dict(TENANT_CONFIG)

        self.assertEqual(self._config_as(self.member)["default_memory_consent"], "Opt-Out")

    def test_an_admin_gets_the_policy_and_the_full_tenant_block(self):
        self.client.get_tenant_privacy_config.return_value = dict(TENANT_CONFIG)

        config = self._config_as(self.admin)

        self.assertTrue(config["is_admin"])
        self.assertEqual(config["default_memory_consent"], "Opt-Out")
        self.assertEqual(config["tenant"], TENANT_CONFIG)

    def test_an_unreachable_ar_yields_no_policy(self):
        self.client.get_tenant_privacy_config.side_effect = RuntimeError("AR down")

        member = self._config_as(self.member)
        admin = self._config_as(self.admin)

        self.assertIsNone(member["default_memory_consent"])
        self.assertIsNone(admin["default_memory_consent"])
        self.assertIsNone(admin["tenant"])

    def test_a_missing_or_unknown_policy_is_none(self):
        for reply in (None, {}, {"default_memory_consent": "opt-out"}, {"default_memory_consent": ""}):
            with self.subTest(reply=reply):
                self.client.get_tenant_privacy_config.return_value = reply
                self.assertIsNone(self._config_as(self.member)["default_memory_consent"])
