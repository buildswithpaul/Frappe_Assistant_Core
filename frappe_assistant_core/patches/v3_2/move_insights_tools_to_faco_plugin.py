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

"""The Insights tools moved from their own "insights" plugin into the faco plugin.

FAC Tool Configuration is named by tool_name and the after_migrate sync skips rows that already
exist, so a site that ran the insights plugin would keep plugin_name "insights" on these rows, and
bulk_toggle_tools_by_category filters on that stored value. Only the plugin and module path change:
a tool an administrator switched off stays off. The orphaned "insights" FAC Plugin Configuration
row is removed by the sync's orphan cleanup.
"""

import frappe

DOCTYPE = "FAC Tool Configuration"
TOOLS = {
    "list_insights_dashboards": "ListInsightsDashboards",
    "get_insights_dashboard": "GetInsightsDashboard",
    "get_insights_chart": "GetInsightsChart",
}


def execute():
    if not frappe.db.table_exists(DOCTYPE):
        return
    for tool, cls in TOOLS.items():
        if frappe.db.exists(DOCTYPE, tool):
            frappe.db.set_value(
                DOCTYPE,
                tool,
                {
                    "plugin_name": "faco",
                    "module_path": f"frappe_assistant_core.plugins.faco.tools.{tool}.{cls}",
                },
                update_modified=False,
            )
