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

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.plugins.insights.chart_data import chart_names
from frappe_assistant_core.plugins.insights.reader import insights_access_error


class ListInsightsDashboards(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "list_insights_dashboards"
        self.description = (
            "List the Frappe Insights dashboards the user can open, optionally searching titles. "
            "Use it to find the dashboard that answers a data question, then read it with get_insights_dashboard."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "search": {"type": "string", "description": "Words to find in dashboard titles"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
            },
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        denied = insights_access_error()
        if denied:
            return denied
        limit = min(max(int(arguments.get("limit") or 20), 1), 50)
        search = (arguments.get("search") or "").strip()
        filters = [["title", "like", f"%{search}%"]] if search else []
        rows = frappe.get_list(
            "Insights Dashboard v3",
            fields=["name", "title", "workbook", "items", "modified"],
            filters=filters,
            order_by="modified desc",
            limit_page_length=limit,
        )
        return {
            "success": True,
            "dashboards": [
                {
                    "name": r.name,
                    "title": r.title,
                    "workbook": r.workbook,
                    "chart_count": len(chart_names(r["items"])),
                    "modified": str(r.modified),
                }
                for r in rows
            ],
        }
