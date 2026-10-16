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
Report List Tool for Core Plugin.
Discover available Frappe reports for business intelligence.
"""

from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool


class ReportList(BaseTool):
    """
    Tool for discovering available Frappe reports.

    Provides capabilities for:
    - Listing reports by module
    - Filtering by report type
    - Permission-based filtering
    - Report metadata discovery
    """

    def __init__(self):
        super().__init__()
        self.name = "report_list"
        self.description = (
            "Find the report that answers a business question. Search with `query` first (for example "
            "'receivables overdue' or 'sales by territory'); results rank a custom report above a "
            "standard one. Then call report_requirements for the chosen report and generate_report to "
            "run it. If nothing fits, call get_doctype_info(topic=...) to find the data, then use "
            "list_documents with grouping. Cite the report and the filters you used in the answer. "
            "With no arguments it returns a count of reports per module, not every report."
        )
        self.requires_permission = None  # Permission checked dynamically per report

        self.inputSchema = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What the user wants to know, in their words. Ranks the reports you can run by how well they match.",
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "maximum": 25,
                    "description": "Maximum reports to return for a query (default 10, at most 25).",
                },
                "module": {
                    "type": "string",
                    "description": "Filter by Frappe module (e.g., 'Accounts', 'Selling', 'Stock', 'HR', 'CRM'). Leave empty to see all modules.",
                },
                "report_type": {
                    "type": "string",
                    "enum": ["Report Builder", "Query Report", "Script Report"],
                    "description": "Filter by report type. Script Reports are usually the most powerful for analytics. Leave empty to see all types.",
                },
            },
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute report list discovery"""
        try:
            module = arguments.get("module")
            report_type = arguments.get("report_type")

            if arguments.get("query"):
                from .report_search import DEFAULT_LIMIT, search_reports

                return search_reports(
                    arguments["query"], module=module, limit=arguments.get("limit", DEFAULT_LIMIT)
                )

            if module or report_type:
                from .report_tools import ReportTools

                return ReportTools.list_reports(module=module, report_type=report_type)

            from .report_search import module_summary

            return module_summary()

        except Exception as e:
            frappe.log_error(title=_("Report List Error"), message=f"Error listing reports: {str(e)}")

            return {"success": False, "error": str(e)}


# Make sure class name matches file name for discovery
report_list = ReportList
