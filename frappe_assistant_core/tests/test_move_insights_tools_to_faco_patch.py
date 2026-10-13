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

"""The patch that re-points the Insights tools' stored configuration from their old plugin to faco.

The after_migrate sync never updates an existing FAC Tool Configuration row, so without it a site
that ran the short-lived "insights" plugin keeps plugin_name "insights" on all three rows, and
bulk_toggle_tools_by_category("faco") misses them.
"""

import frappe

from frappe_assistant_core.patches.v3_2.move_insights_tools_to_faco_plugin import TOOLS, execute
from frappe_assistant_core.tests.base_test import BaseAssistantTest

DOCTYPE = "FAC Tool Configuration"


class TestMoveInsightsToolsToFacoPatch(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        if not frappe.db.table_exists(DOCTYPE):
            self.skipTest(f"{DOCTYPE} does not exist on this site")
        # Production: the sync wrote these rows while the tools lived in plugins/insights.
        for tool in TOOLS:
            frappe.db.delete(DOCTYPE, {"tool_name": tool})
            frappe.get_doc(
                {
                    "doctype": DOCTYPE,
                    "tool_name": tool,
                    "plugin_name": "insights",
                    "enabled": 0,
                    "tool_category": "read_only",
                    "module_path": f"frappe_assistant_core.plugins.insights.tools.{tool}.X",
                }
            ).insert(ignore_permissions=True)

    def test_rows_move_to_faco_and_keep_their_enabled_flag(self):
        execute()
        for tool, cls in TOOLS.items():
            row = frappe.db.get_value(DOCTYPE, tool, ["plugin_name", "module_path", "enabled"], as_dict=True)
            self.assertEqual(row.plugin_name, "faco", tool)
            self.assertEqual(row.module_path, f"frappe_assistant_core.plugins.faco.tools.{tool}.{cls}")
            # An administrator who switched a tool off keeps it off.
            self.assertEqual(row.enabled, 0, tool)

    def test_a_site_without_the_rows_is_left_alone(self):
        for tool in TOOLS:
            frappe.db.delete(DOCTYPE, {"tool_name": tool})
        execute()
        self.assertFalse(frappe.db.exists(DOCTYPE, {"tool_name": ["in", list(TOOLS)]}))
