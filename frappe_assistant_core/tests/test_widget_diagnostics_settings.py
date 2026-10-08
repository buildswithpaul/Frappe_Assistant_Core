# Frappe Assistant Core - widget diagnostics settings tests
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0 License

"""The widget must obey the operator's privacy toggles, not a literal.

Turning a privacy setting off once changed nothing for browser tools while appearing to
work in the admin UI. The launcher reads both flags from `get_widget_settings`, and a
server failure must never read as "everything allowed".
"""

from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.settings.widget import get_widget_settings
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestWidgetDiagnosticsSettings(BaseAssistantTest):
    def test_privacy_block_exposes_the_diagnostics_switch(self):
        privacy = get_widget_settings()["privacy"]
        self.assertIn("enable_browser_diagnostics", privacy)
        self.assertIsInstance(privacy["enable_browser_diagnostics"], bool)

    def test_diagnostics_default_is_on(self):
        settings = frappe.get_single("FAC Chat Settings")
        self.assertTrue(
            bool(settings.enable_browser_diagnostics),
            f"enable_browser_diagnostics must resolve truthy, got {settings.enable_browser_diagnostics!r}",
        )

    def test_success_returns_only_the_privacy_block(self):
        self.assertEqual(set(get_widget_settings()), {"privacy"})

    def test_privacy_flags_follow_the_settings(self):
        settings = frappe.get_single("FAC Chat Settings")
        privacy = get_widget_settings()["privacy"]
        self.assertEqual(privacy["enable_dom_extraction"], bool(settings.enable_dom_extraction))
        self.assertEqual(privacy["enable_browser_diagnostics"], bool(settings.enable_browser_diagnostics))

    def test_error_branch_carries_no_privacy_block(self):
        # The launcher reads a missing privacy block as "DOM extraction off"; defaulting the
        # flags to True here would turn a server failure into fail-open.
        with patch.object(frappe, "get_single", side_effect=Exception("settings unavailable")):
            self.assertEqual(get_widget_settings(), {})
