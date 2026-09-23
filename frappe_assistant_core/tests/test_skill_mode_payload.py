import json

import frappe

from frappe_assistant_core.api.fac_endpoint import _build_tool_registry, mcp
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestSkillModePayload(BaseAssistantTest):
    def _tools_list(self, mode):
        settings = frappe.get_single("Assistant Core Settings")
        original = settings.skill_mode
        settings.skill_mode = mode
        settings.save(ignore_permissions=True)
        try:
            return mcp._handle_tools_list({}, tool_registry=_build_tool_registry())
        finally:
            settings.skill_mode = original
            settings.save(ignore_permissions=True)

    def _payload_size(self, mode):
        return len(json.dumps(self._tools_list(mode), separators=(",", ":")))

    def test_replace_mode_is_materially_smaller(self):
        supplementary = self._payload_size("supplementary")
        replace = self._payload_size("replace")
        self.assertLess(replace, supplementary * 0.9)

    def test_replace_mode_keeps_every_tool(self):
        """Replace mode trims the skill text, never the tool list.

        Compared against supplementary mode rather than a fixed count: how
        many tools a site exposes depends on which plugins it enables, so a
        threshold only ever measured the fixture. It read >= 30 and a bare CI
        site registers 15.
        """
        supplementary = {t["name"] for t in self._tools_list("supplementary").get("tools", [])}
        replace = {t["name"] for t in self._tools_list("replace").get("tools", [])}

        self.assertTrue(supplementary, "no tools registered at all — fixture is wrong")
        self.assertEqual(replace, supplementary)
