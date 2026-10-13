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

import json
from typing import Any, Dict

import frappe

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.plugins.insights.chart_data import (
    MAX_CHARTS,
    chart_names,
    dashboard_filters,
    notes,
    parse_items,
    resolve_filters,
    row_budget,
    unknown_overrides,
)
from frappe_assistant_core.plugins.insights.reader import (
    can_read,
    insights_access_error,
    not_found,
    read_chart,
)

DASHBOARD = "Insights Dashboard v3"


def overrides_from(arguments: Dict[str, Any]) -> list:
    raw = arguments.get("filters") or []
    return json.loads(raw) if isinstance(raw, str) else raw


def filters_out(resolved: list[dict]) -> list[dict]:
    return [
        {
            "name": f["name"],
            "type": f["type"],
            "operator": f["operator"],
            "value": f["value"],
            "source": f["source"],
        }
        for f in resolved
    ]


class GetInsightsDashboard(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "get_insights_dashboard"
        self.description = (
            "Read a Frappe Insights dashboard as the user sees it: its filters and, for each chart, "
            "the chart's numbers with the dashboard's default filters (or the overrides given)."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Insights Dashboard v3 name"},
                "filters": {
                    "type": "array",
                    "description": "Override dashboard filters by their name",
                    "items": {
                        "type": "object",
                        "properties": {
                            "filter": {"type": "string"},
                            "operator": {"type": "string"},
                            "value": {},
                        },
                    },
                },
                "max_rows_per_chart": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
            },
            "required": ["name"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        denied = insights_access_error()
        if denied:
            return denied
        name = arguments.get("name")
        if not can_read(DASHBOARD, name):
            return not_found("dashboard", name)
        dashboard = frappe.get_doc(DASHBOARD, name)
        items = parse_items(dashboard.items)
        overrides = overrides_from(arguments)
        filters = dashboard_filters(items)
        resolved = resolve_filters(filters, overrides)
        per_chart = min(max(int(arguments.get("max_rows_per_chart") or 50), 1), 200)
        names = chart_names(items)
        charts, used = [], 0
        for chart_name in names[:MAX_CHARTS]:
            entry = read_chart(chart_name, resolved, row_budget(per_chart, used))
            used += len(entry.get("rows") or [])
            charts.append(entry)
        return {
            "success": True,
            "name": dashboard.name,
            "title": dashboard.title,
            "filters": filters_out(resolved),
            "unknown_filters": unknown_overrides(filters, overrides),
            "charts": charts,
            "more_charts": [
                {"name": n, "title": frappe.db.get_value("Insights Chart v3", n, "title")}
                for n in names[MAX_CHARTS:]
            ],
            "notes": notes(items),
        }
