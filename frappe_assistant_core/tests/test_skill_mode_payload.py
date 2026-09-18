import json

import frappe

from frappe_assistant_core.api.fac_endpoint import _build_tool_registry, mcp
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestSkillModePayload(BaseAssistantTest):
    def _payload_size(self, mode):
        settings = frappe.get_single("Assistant Core Settings")
        original = settings.skill_mode
        settings.skill_mode = mode
        settings.save(ignore_permissions=True)
        try:
            tools = mcp._handle_tools_list({}, tool_registry=_build_tool_registry())
            return len(json.dumps(tools, separators=(",", ":")))
        finally:
            settings.skill_mode = original
            settings.save(ignore_permissions=True)

    def test_replace_mode_is_materially_smaller(self):
        supplementary = self._payload_size("supplementary")
        replace = self._payload_size("replace")
        self.assertLess(replace, supplementary * 0.9)

    def test_replace_mode_keeps_every_tool(self):
        tools = mcp._handle_tools_list({}, tool_registry=_build_tool_registry())
        self.assertGreaterEqual(len(tools.get("tools", [])), 30)
