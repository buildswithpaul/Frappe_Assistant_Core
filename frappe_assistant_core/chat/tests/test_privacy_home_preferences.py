# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""GDPR export and erasure cover the home-page preferences."""

from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.api import privacy
from frappe_assistant_core.chat.home_preferences import HOME_SIGNALS_CACHE_KEY
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestPrivacyHomePreferences(BaseAssistantTest):
    EMAIL = "privacy-home-prefs@example.com"

    def setUp(self):
        super().setUp()
        if not frappe.db.exists("User", self.EMAIL):
            frappe.get_doc(
                {"doctype": "User", "email": self.EMAIL, "first_name": "Privacy", "send_welcome_email": 0}
            ).insert(ignore_permissions=True)
        # Manufactured: production reaches this when a user saves Settings -> Home page.
        if not frappe.db.exists("FAC Chat User Preferences", self.EMAIL):
            frappe.get_doc(
                {
                    "doctype": "FAC Chat User Preferences",
                    "user": self.EMAIL,
                    "show_needs_you": 0,
                    "needs_you_count": 2,
                    "hidden_home_signals": '["approvals"]',
                    "show_suggested_prompts": 0,
                    "show_personalized_suggestions": 0,
                }
            ).insert(ignore_permissions=True)
        self.addCleanup(frappe.cache.hdel, HOME_SIGNALS_CACHE_KEY, self.EMAIL)
        self.addCleanup(frappe.set_user, "Administrator")
        # nosemgrep: frappe-setuser — the endpoints act on the session user
        frappe.set_user(self.EMAIL)
        client = MagicMock()
        client.export_user_data.return_value = {"status": "success", "data": {}}
        client.erase_user_data.return_value = {}
        patcher = patch.object(privacy, "_get_client", return_value=client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_export_includes_the_home_preference_fields(self):
        prefs = privacy.export_my_data()["data"]["faco"]["faco_preferences"]
        self.assertIs(prefs["show_needs_you"], False)
        self.assertEqual(prefs["needs_you_count"], 2)
        self.assertEqual(prefs["hidden_home_signals"], ["approvals"])
        self.assertIs(prefs["show_suggested_prompts"], False)
        self.assertIs(prefs["show_personalized_suggestions"], False)

    def test_erase_drops_the_cached_home_payload(self):
        frappe.cache.hset(HOME_SIGNALS_CACHE_KEY, self.EMAIL, {"items": []})
        with patch("frappe.utils.password.check_password"):
            privacy.erase_my_data(password="pw")
        self.assertFalse(frappe.db.exists("FAC Chat User Preferences", self.EMAIL))
        self.assertIsNone(frappe.cache.hget(HOME_SIGNALS_CACHE_KEY, self.EMAIL))
