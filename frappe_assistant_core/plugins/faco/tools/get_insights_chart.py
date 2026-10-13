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

from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.plugins.faco.insights.chart_data import (
    chart_names,
    dashboard_filters,
    parse_items,
    resolve_filters,
    unknown_overrides,
)
from frappe_assistant_core.plugins.faco.insights.reader import (
    can_read,
    insights_access_error,
    not_found,
    read_chart,
)
from frappe_assistant_core.plugins.faco.insights.tool import InsightsTool
from frappe_assistant_core.plugins.faco.tools.get_insights_dashboard import (
    DASHBOARD,
    filters_out,
    overrides_from,
)


class GetInsightsChart(InsightsTool):
    def __init__(self):
        super().__init__()
        self.name = "get_insights_chart"
        self.description = (
            "Read one Frappe Insights chart in depth. Pass the dashboard it is on to apply that "
            "dashboard's filters (defaults, or overrides by filter name)."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Insights Chart v3 name"},
                "dashboard": {"type": "string", "description": "Insights Dashboard v3 the chart is on"},
                "filters": {"type": "array", "items": {"type": "object"}},
                "max_rows": {"type": "integer", "minimum": 1, "maximum": 500, "default": 200},
            },
            "required": ["name"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        denied = insights_access_error()
        if denied:
            return denied
        name, dashboard = arguments.get("name"), arguments.get("dashboard")
        if not can_read("Insights Chart v3", name):
            return not_found("chart", name)
        overrides = overrides_from(arguments)
        resolved, unknown = [], []
        if dashboard:
            if not can_read(DASHBOARD, dashboard):
                return not_found("dashboard", dashboard)
            items = parse_items(frappe.db.get_value(DASHBOARD, dashboard, "items"))
            filters = dashboard_filters(items)
            resolved, unknown = resolve_filters(filters, overrides), unknown_overrides(filters, overrides)
        elif overrides:
            unknown = [o.get("filter") for o in overrides if isinstance(o, dict)]
        max_rows = min(max(int(arguments.get("max_rows") or 200), 1), 500)
        entry = read_chart(name, resolved, max_rows)
        if dashboard and name not in chart_names(items):
            off = _("This chart is not on dashboard {0}, so none of its filters apply.").format(dashboard)
            entry["note"] = f"{off} {entry['note']}" if entry.get("note") else off
        return {
            "success": "error" not in entry,
            "chart": entry,
            "filters": filters_out(resolved),
            "unknown_filters": unknown,
        }
