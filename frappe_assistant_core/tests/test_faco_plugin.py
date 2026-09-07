# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Tests for the FACO plugin and its migrated tools.
Verifies the plugin class satisfies the BasePlugin contract and that
each migrated tool is importable and correctly configured.
"""

from frappe_assistant_core.plugins.faco.plugin import FacoPlugin
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.tool_category_detector import READ_ONLY_TOOLS


class TestFacoPlugin(BaseAssistantTest):
    def test_plugin_class_importable(self):
        plugin = FacoPlugin()
        self.assertIsNotNone(plugin)

    def test_plugin_info_name(self):
        info = FacoPlugin().get_info()
        self.assertEqual(info["name"], "faco")
        self.assertEqual(info["display_name"], "FACO Tools")
        self.assertIn("version", info)
        self.assertIn("description", info)
        self.assertEqual(info["requires_restart"], False)

    def test_plugin_get_tools_returns_registered_tools(self):
        tools = FacoPlugin().get_tools()
        # Communication / document tools
        self.assertIn("send_email", tools)
        self.assertIn("generate_document", tools)
        # Browser automation tools
        for name in (
            "browser_get_form_data",
            "browser_get_page_context",
            "browser_capture_diagnostics",
            "browser_navigate_to",
            "browser_take_screenshot",
            "browser_wait_for_page",
        ):
            self.assertIn(name, tools)
        # Utility modules must NOT appear as tools
        self.assertNotIn("rich_blocks", tools)
        self.assertNotIn("base_browser_tool", tools)
        self.assertNotIn("browser_bridge", tools)

    def test_plugin_validate_environment_passes_with_no_deps(self):
        ok, err = FacoPlugin().validate_environment()
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_every_browser_tool_is_read_only_classified(self):
        """Regression: browser_capture_diagnostics was added to the plugin but
        missed in READ_ONLY_TOOLS, so it was gated by AR's server-side
        ApprovalHook instead of the widget's own confirmation card.

        Derives the browser tool list from the plugin's actual registration
        (not a hardcoded copy of it) so a future browser_* tool added here
        without a matching READ_ONLY_TOOLS entry fails this test instead of
        shipping silently misclassified.
        """
        browser_tools = [name for name in FacoPlugin().get_tools() if name.startswith("browser_")]
        self.assertTrue(browser_tools, "expected the plugin to register at least one browser_ tool")
        for tool_name in browser_tools:
            self.assertIn(tool_name, READ_ONLY_TOOLS)


class TestFacoToolDiscovery(BaseAssistantTest):
    def test_send_email_tool_module_importable(self):
        """The send_email tool module must be importable from the plugin path."""
        from frappe_assistant_core.plugins.faco.tools import send_email

        self.assertTrue(hasattr(send_email, "SendEmail"))

    def test_send_email_tool_class_metadata(self):
        """SendEmail tool must declare its name and source_app correctly."""
        from frappe_assistant_core.plugins.faco.tools.send_email import SendEmail

        tool = SendEmail()
        self.assertEqual(tool.name, "send_email")
        self.assertEqual(tool.source_app, "frappe_assistant_core")

    def test_generate_document_tool_module_importable(self):
        from frappe_assistant_core.plugins.faco.tools import generate_document

        self.assertTrue(hasattr(generate_document, "GenerateDocument"))

    def test_generate_document_tool_class_metadata(self):
        from frappe_assistant_core.plugins.faco.tools.generate_document import GenerateDocument

        tool = GenerateDocument()
        self.assertEqual(tool.name, "generate_document")
        self.assertEqual(tool.source_app, "frappe_assistant_core")

    def test_rich_blocks_module_importable(self):
        # rich_blocks is a utility module, not a tool — verify it imports cleanly
        # so that generate_document can use it.
        from frappe_assistant_core.plugins.faco.tools import rich_blocks

        # Verify both public symbols imported by generate_document are present.
        self.assertTrue(hasattr(rich_blocks, "preprocess_rich_blocks"))
        self.assertTrue(hasattr(rich_blocks, "restore_rich_blocks"))

    def test_all_browser_tools_module_importable(self):
        """Each browser tool's module must be importable from plugins/faco/tools/."""
        from frappe_assistant_core.plugins.faco.tools import (
            browser_capture_diagnostics,
            browser_get_form_data,
            browser_get_page_context,
            browser_navigate_to,
            browser_take_screenshot,
            browser_wait_for_page,
        )

        self.assertTrue(hasattr(browser_get_form_data, "BrowserGetFormData"))
        self.assertTrue(hasattr(browser_get_page_context, "BrowserGetPageContext"))
        self.assertTrue(hasattr(browser_navigate_to, "BrowserNavigateTo"))
        self.assertTrue(hasattr(browser_take_screenshot, "BrowserTakeScreenshot"))
        self.assertTrue(hasattr(browser_wait_for_page, "BrowserWaitForPage"))
        self.assertTrue(hasattr(browser_capture_diagnostics, "BrowserCaptureDiagnostics"))

    def test_browser_tool_class_metadata(self):
        """Each browser tool reports its tool-name correctly and source_app=frappe_assistant_core."""
        from frappe_assistant_core.plugins.faco.tools.browser_capture_diagnostics import (
            BrowserCaptureDiagnostics,
        )
        from frappe_assistant_core.plugins.faco.tools.browser_get_form_data import BrowserGetFormData
        from frappe_assistant_core.plugins.faco.tools.browser_get_page_context import BrowserGetPageContext
        from frappe_assistant_core.plugins.faco.tools.browser_navigate_to import BrowserNavigateTo
        from frappe_assistant_core.plugins.faco.tools.browser_take_screenshot import BrowserTakeScreenshot
        from frappe_assistant_core.plugins.faco.tools.browser_wait_for_page import BrowserWaitForPage

        expected = {
            BrowserGetFormData(): ("browser_get_form_data", "get_form_data"),
            BrowserGetPageContext(): ("browser_get_page_context", "get_page_context"),
            BrowserNavigateTo(): ("browser_navigate_to", "navigate_to"),
            BrowserTakeScreenshot(): ("browser_take_screenshot", "take_screenshot"),
            BrowserWaitForPage(): ("browser_wait_for_page", "wait_for_page"),
            BrowserCaptureDiagnostics(): ("browser_capture_diagnostics", "capture_diagnostics"),
        }
        for tool, (expected_name, expected_tool_name) in expected.items():
            self.assertEqual(tool.name, expected_name)
            self.assertEqual(tool.source_app, "frappe_assistant_core")
            self.assertEqual(tool.tool_name, expected_tool_name)

    def test_base_browser_tool_importable(self):
        """The utility module BaseBrowserTool must be importable."""
        from frappe_assistant_core.plugins.faco.tools.base_browser_tool import BaseBrowserTool

        self.assertTrue(BaseBrowserTool is not None)
