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

"""Tests for the tool packs plugins declare (#34608)."""

from collections import Counter
from unittest.mock import patch

from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.plugin_manager import PluginManager, get_plugin_manager


class TestToolPacks(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.manager = get_plugin_manager()
        self.all_plugins = set(self.manager._discovered_plugins)
        # Production reads the enabled set from FAC Plugin Configuration rows; enabling a plugin
        # commits, so the enabled set is patched here instead.
        patcher = patch.object(PluginManager, "get_enabled_plugins", autospec=True)
        self.enabled = patcher.start()
        self.enabled.return_value = self.all_plugins
        self.addCleanup(patcher.stop)

    def test_every_tool_in_at_most_one_pack(self):
        counts = Counter(tool for pack in self.manager.get_tool_packs() for tool in pack.tools)
        self.assertEqual({tool: n for tool, n in counts.items() if n > 1}, {})

    def test_pack_tools_exist(self):
        registered = {tool for plugin in self.manager._discovered_plugins.values() for tool in plugin.tools}
        for pack in self.manager.get_tool_packs():
            self.assertFalse(set(pack.tools) - registered, f"pack {pack.id} lists unregistered tools")

    def test_expected_packs_declared(self):
        ids = [pack.id for pack in self.manager.get_tool_packs()]
        self.assertEqual(
            ids,
            ["analysis", "browser", "builder", "crm", "dashboards", "helpdesk", "insights"],
        )

    def test_disabled_plugin_has_no_packs(self):
        # Which tools then carry a pack in tools/list: test_tool_pack_listing.
        self.enabled.return_value = {"core"}
        self.assertEqual([pack.id for pack in self.manager.get_tool_packs()], ["builder"])
