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

        self.description = "Execute pre-built Frappe business reports (Script Reports, Query Reports, Custom Reports) with filtering and formatting. This is the primary tool for generating professional business reports including sales analytics, financial statements, profit/loss reports, customer insights, inventory tracking, and territory performance. These reports are pre-optimized, professionally formatted, and ready for management presentation with proper calculations and totals. SUPPORTED TYPES: Script Reports (Python-based), Query Reports (SQL-based), Custom Reports (advanced implementations). NOT SUPPORTED: Report Builder reports (these are simple DocType list views without business logic). FILTER VALIDATION: All filter values (company names, customer names, etc.) are validated before execution - you will receive clear error messages with suggestions if invalid values are provided. IMPORTANT: Many reports require mandatory filters - use the report_requirements tool first to discover required filters and valid filter values, then use report_list to find available reports before executing. Always prefer using existing reports over custom analysis tools when available. NOTE: Large reports marked as 'Prepared Reports' (like Stock Balance, Sales Analytics) are automatically handled - the tool will wait for completion (up to 5 minutes) and return data when ready. If a report takes longer than the timeout, you'll receive guidance to retry. Cached reports return immediately with full data."
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
                    "description": "Report-specific filters as key-value pairs. CRITICAL: Filter values must be EXACT, valid names from the database. Link fields (company, customer, supplier, item, etc.) are validated - invalid names will be rejected with suggestions. Select fields (tree_type, doc_type, range, etc.) must use exact enum values. Dates must be valid (YYYY-MM-DD format recommended). Common filters: {'company': 'Exact Company Name'}, {'from_date': '2024-01-01', 'to_date': '2024-12-31'}, {'customer': 'Exact Customer Name'}. For Sales Analytics: requires 'doc_type' (Sales Invoice/Sales Order/Quotation) and 'tree_type' (Customer/Item/Territory). Use report_requirements tool to discover required filters and valid options.",
                },
                "format": {
                    "type": "string",
                    "enum": ["json", "csv", "excel"],
                    "default": "json",
                    "description": "Output format. Use 'json' for data analysis, 'csv' for exports, 'excel' for spreadsheet files.",
                },
            },
            "required": ["report_name"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute report generation"""
        try:
            # Import the report implementation
            from .report_tools import ReportTools

            # Execute report using existing implementation
            return ReportTools.execute_report(
                report_name=arguments.get("report_name"),
                filters=arguments.get("filters", {}),
                format=arguments.get("format", "json"),
            )

        except Exception as e:
            frappe.log_error(title=_("Generate Report Error"), message=f"Error generating report: {str(e)}")

            return {"success": False, "error": str(e)}


# Make sure class name matches file name for discovery
generate_report = GenerateReport
