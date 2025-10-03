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
        self.description = "Discover and search available Frappe business reports across all modules. Use this tool to find the appropriate report for business questions before attempting custom data analysis. Returns a list of available reports with descriptions, modules, and types. Available reports include Sales Analytics, Territory Analysis, Customer Reports, P&L Statement, Balance Sheet, Receivables/Payables, Inventory Reports, Item Movement, Stock Valuation, Payroll, Attendance, and Leave Reports. Always search for existing reports first before building custom queries or analysis."
        self.requires_permission = None  # Permission checked dynamically per report

        self.inputSchema = {
            "type": "object",
            "properties": {
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
            # Import the report implementation
            from .report_tools import ReportTools

            # Execute report list using existing implementation
            return ReportTools.list_reports(
                module=arguments.get("module"), report_type=arguments.get("report_type")
            )

        except Exception as e:
            frappe.log_error(title=_("Report List Error"), message=f"Error listing reports: {str(e)}")

            return {"success": False, "error": str(e)}


# Make sure class name matches file name for discovery
report_list = ReportList
