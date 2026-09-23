# Frappe Assistant Core - widget diagnostics settings tests
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0 License

"""The widget must obey the operator's privacy toggles, not a literal.

`get_page_context` hardcoded `enable_dom_extraction: true`, so turning the
setting off changed nothing for browser tools while appearing to work in the
admin UI. The diagnostics kill switch travels the same channel and would have
inherited the same bug.
"""

import re
from pathlib import Path

import frappe

from frappe_assistant_core.chat.api.settings.widget import get_widget_settings
from frappe_assistant_core.tests.base_test import BaseAssistantTest

WIDGET_JS = (
    Path(frappe.get_app_path("frappe_assistant_core"))
    / "public"
    / "chat"
    / "widget"
    / "widget_browser_tools.js"
)


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

    def test_dom_extraction_setting_is_read_not_hardcoded(self):
        source = WIDGET_JS.read_text()
        self.assertNotRegex(
            source,
            re.compile(r"enable_dom_extraction:\s*true"),
            "get_page_context must read the served setting, not a literal",
        )
