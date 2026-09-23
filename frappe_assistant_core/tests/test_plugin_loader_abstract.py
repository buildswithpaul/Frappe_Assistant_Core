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
Regression test: plugin loader must skip abstract BaseTool subclasses when
discovering the concrete tool class inside a tool module.

When a tool module imports an abstract intermediate class (e.g. BaseBrowserTool)
and then defines the concrete class (e.g. BrowserGetFormData), dir(module) returns
names alphabetically. The abstract class name sorts before the concrete name, so
without the isabstract() guard the loader picks the abstract class, fails to
instantiate it, and silently drops the tool.
"""

import sys
import types

import frappe

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.plugin_manager import (
    PluginInfo,
    PluginManager,
    PluginState,
    get_plugin_manager,
)


class TestPluginLoaderAbstractClassSkip(BaseAssistantTest):
    """Regression: the plugin loader must skip abstract BaseTool subclasses
    when discovering the concrete tool class inside a tool module."""

    def setUp(self):
        super().setUp()
        self._faco_was_enabled = False  # safe default if the check below raises
        # Snapshot plugin state so tearDown can restore it.
        self._faco_was_enabled = bool(
            frappe.db.exists("FAC Plugin Configuration", {"plugin_name": "faco", "enabled": 1})
        )

    def tearDown(self):
        # Restore baseline: faco should be DISABLED after this test, matching
        # the MCP-only-default state assumed by the rest of the suite.
        pm = get_plugin_manager()
        if not self._faco_was_enabled:
            try:
                pm.disable_plugin("faco")
            except Exception:
                pass
        super().tearDown()

    def test_faco_plugin_loads_all_browser_tools(self):
        """All 5 browser tools plus non-browser faco tools must load successfully."""
        pm = get_plugin_manager()
        pm.enable_plugin("faco")
        loaded = pm.get_all_tools()

        # The plugin manager returns a dict keyed by tool name.
        for expected_tool in (
            "send_email",
            "generate_document",
            "browser_get_form_data",
            "browser_get_page_context",
            "browser_navigate_to",
            "browser_take_screenshot",
            "browser_wait_for_page",
        ):
            self.assertIn(
                expected_tool,
                loaded,
                f"plugin loader did not load '{expected_tool}' — abstract class guard may be missing",
            )


class TestPluginLoaderSkippedToolsDiagnostic(BaseAssistantTest):
    """FIX B: a tool that fails dependency validation must be recorded in
    ``skipped_tools`` with its reason, so the get_skipped_tools diagnostic API
    can explain why the tool is missing from the tool list."""

    PLUGIN = "_diag_fake_plugin"
    TOOL = "_diag_fake_tool"
    MODULE_PATH = f"frappe_assistant_core.plugins.{PLUGIN}.tools.{TOOL}"
    REASON = "Missing dependencies: numpy"

    def tearDown(self):
        sys.modules.pop(self.MODULE_PATH, None)
        super().tearDown()

    def _inject_fake_tool_module(self):
        """Register a synthetic tool module whose tool fails dependency validation."""

        class FakeDepFailTool(BaseTool):
            def __init__(self):
                super().__init__()
                self.name = "diag_fake_tool"
                self.description = "A fake tool that always fails dependency validation."
                self.inputSchema = {"type": "object", "properties": {}}

            def execute(self, arguments):  # pragma: no cover - never called
                return {}

            def validate_dependencies(self):
                return (False, TestPluginLoaderSkippedToolsDiagnostic.REASON)

        module = types.ModuleType(self.MODULE_PATH)
        module.FakeDepFailTool = FakeDepFailTool
        sys.modules[self.MODULE_PATH] = module

    def test_dependency_failure_recorded_in_skipped_tools(self):
        self._inject_fake_tool_module()

        pm = PluginManager()
        plugin_info = PluginInfo(
            name=self.PLUGIN,
            display_name="Diag Fake Plugin",
            description="",
            version="1.0.0",
            state=PluginState.ENABLED,
            tools=[self.TOOL],
        )

        result = pm._load_plugin_tools(self.PLUGIN, plugin_info)

        # The dependency-failing tool must NOT be loaded ...
        self.assertEqual(result, {})
        # ... but it MUST be recorded with its reason for the diagnostic API.
        self.assertIn("diag_fake_tool", pm.skipped_tools)
        self.assertEqual(pm.skipped_tools["diag_fake_tool"], self.REASON)

    def test_skipped_tools_attribute_exists_after_load(self):
        """The plugin manager always exposes a skipped_tools dict after a load."""
        pm = get_plugin_manager()
        pm.get_all_tools()
        self.assertIsInstance(getattr(pm, "skipped_tools", None), dict)
