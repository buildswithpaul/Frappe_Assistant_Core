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
Generate Report Tool for Core Plugin.
Execute Frappe reports for business data and analytics.
"""

from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool

from .report_tools import DEFAULT_MAX_ROWS, MAX_ROWS_CAP, ReportTools


class GenerateReport(BaseTool):
    """
    Tool for executing Frappe reports.

    Provides capabilities for:
    - Query Report execution
    - Script Report execution
    - Report Builder execution
    - Automatic filter handling
    """

    def __init__(self):
        super().__init__()
        self.name = "generate_report"

        self.description = "Execute a Frappe report. IMPORTANT: Always call report_requirements(report_name) FIRST to get mandatory filters and valid options, then call this tool with explicit filters. Missing filters are auto-defaulted (dates, company) which often returns empty data. Supports Script Reports, Query Reports, and Custom Reports. Report Builder reports are not supported. Large/prepared reports are handled automatically with polling. Returns at most max_rows rows (default 500); check truncated and row_count."
        self.requires_permission = None  # Permission checked dynamically per report

        self.inputSchema = {
            "type": "object",
            "properties": {
                "report_name": {
                    "type": "string",
                    "description": "Exact name of the Frappe report to execute (e.g., 'Accounts Receivable Summary', 'Sales Analytics', 'Stock Balance'). Use report_list to find available reports.",
                },
                "filters": {
                    "type": "object",
                    "default": {},
                    "description": "Filter key-value pairs. Get valid keys and values from report_requirements first — values are validated against that report's own declared filters, and the same filter name can accept different values in a different report. Dates: YYYY-MM-DD. Link fields (company, customer) must be exact DB names. Select fields must match that report's advertised options exactly.",
                },
                "format": {
                    "type": "string",
                    "enum": ["json", "csv", "excel"],
                    "default": "json",
                    "description": "Output format. Use 'json' for data analysis, 'csv' for exports, 'excel' for spreadsheet files.",
                },
                "max_rows": {
                    "type": "integer",
                    "default": DEFAULT_MAX_ROWS,
                    "minimum": 1,
                    "maximum": MAX_ROWS_CAP,
                    "description": "Most rows to return (default 500, at most 5000). row_count always gives the full count and truncated says whether rows were left out. A report's totals row is kept.",
                },
                "summary_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "Return columns, row_count and the report's summary without any rows. Use it to size a large report before fetching rows.",
                },
            },
            "required": ["report_name"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute report generation"""
        try:
            # Execute report using existing implementation
            return ReportTools.execute_report(
                report_name=arguments.get("report_name"),
                filters=arguments.get("filters", {}),
                format=arguments.get("format", "json"),
                max_rows=arguments.get("max_rows", DEFAULT_MAX_ROWS),
                summary_only=bool(arguments.get("summary_only", False)),
            )

        except Exception as e:
            frappe.log_error(title=_("Generate Report Error"), message=f"Error generating report: {str(e)}")

            return {"success": False, "error": str(e)}


# Make sure class name matches file name for discovery
generate_report = GenerateReport
