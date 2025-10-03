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
Dashboard Manager Tool - Core dashboard creation and management

Provides comprehensive dashboard creation, management, and CRUD operations
for both Insights app and core Frappe Dashboard.
"""

import json
from typing import Any, Dict, List, Optional

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool


class CreateDashboard(BaseTool):
    """
    Create Frappe dashboards with multiple charts.

    Creates dashboards in Frappe's Dashboard DocType with proper chart configuration
    and time series support. This is NOT for Insights app - it creates standard
    Frappe dashboards.
    """

    def __init__(self):
        super().__init__()
        self.name = "create_dashboard"
        self.description = self._get_description()
        self.requires_permission = None  # Permission checked dynamically per DocType

        self.inputSchema = {
            "type": "object",
            "properties": {
                "dashboard_name": {"type": "string", "description": "Dashboard title/name"},
                "doctype": {"type": "string", "description": "Primary data source DocType"},
                "chart_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Array of existing Dashboard Chart names to add to this dashboard. Use create_dashboard_chart tool first to create charts.",
                },
                "filters": {"type": "object", "description": "Global dashboard filters"},
                "share_with": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of users/roles to share dashboard with",
                },
                "auto_refresh": {"type": "boolean", "default": True, "description": "Enable auto refresh"},
                "refresh_interval": {
                    "type": "string",
                    "enum": ["5_minutes", "15_minutes", "30_minutes", "1_hour", "24_hours"],
                    "default": "1_hour",
                    "description": "Auto refresh interval",
                },
                "template_type": {
                    "type": "string",
                    "enum": ["sales", "financial", "inventory", "hr", "executive", "custom"],
                    "default": "custom",
                    "description": "Dashboard template type",
                },
                "mobile_optimized": {
                    "type": "boolean",
                    "default": True,
                    "description": "Optimize for mobile viewing",
                },
            },
            "required": ["dashboard_name", "chart_names"],
        }

    def _get_description(self) -> str:
        """Get tool description"""
        return """Create Frappe dashboards by linking existing charts into organized views. Creates standard Frappe Dashboard documents, NOT Insights dashboards. WORKFLOW: First create individual charts using create_dashboard_chart tool, then use this tool to create a dashboard container that links those charts together. IMPORTANT: Charts must already exist before creating the dashboard. CAPABILITIES: Multi-chart dashboards, user and role-based sharing, mobile responsive layout, export to PDF/Excel. Use this to organize multiple related charts (sales charts, inventory charts, financial charts) into cohesive dashboard views for business monitoring and reporting."""

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Create comprehensive dashboard"""
        try:
            dashboard_name = arguments.get("dashboard_name")
            chart_names = arguments.get("chart_names", [])
            doctype = arguments.get("doctype")  # Optional now
            filters = arguments.get("filters", {})
            share_with = arguments.get("share_with", [])
            auto_refresh = arguments.get("auto_refresh", True)
            refresh_interval = arguments.get("refresh_interval", "1_hour")
            template_type = arguments.get("template_type", "custom")
            mobile_optimized = arguments.get("mobile_optimized", True)

            # Validate that charts exist
            if not chart_names:
                return {
                    "success": False,
                    "error": "No charts specified. Use create_dashboard_chart to create charts first.",
                }

            # Verify all charts exist
            missing_charts = []
            chart_links = []
            for chart_name in chart_names:
                if not frappe.db.exists("Dashboard Chart", chart_name):
                    missing_charts.append(chart_name)
                else:
                    chart_links.append({"chart": chart_name, "width": "Half"})

            if missing_charts:
                return {
                    "success": False,
                    "error": f"Charts not found: {', '.join(missing_charts)}. Use create_dashboard_chart to create them first.",
                }

            # Create the dashboard
            dashboard_result = self._create_frappe_dashboard(
                dashboard_name, chart_links, share_with, auto_refresh, mobile_optimized
            )

            return dashboard_result

        except Exception as e:
            frappe.log_error(
                title=_("Dashboard Creation Error"),
                message=f"Error creating dashboard {dashboard_name}: {str(e)}",
            )

            return {"success": False, "error": str(e), "dashboard_name": dashboard_name}

    def _create_frappe_dashboard(
        self,
        dashboard_name: str,
        chart_links: List[Dict],
        share_with: List[str],
        auto_refresh: bool,
        mobile_optimized: bool,
    ) -> Dict[str, Any]:
        """Create dashboard using core Frappe Dashboard"""
        try:
            # Create Dashboard document with provided chart links
            dashboard_doc = frappe.get_doc(
                {
                    "doctype": "Dashboard",
                    "dashboard_name": dashboard_name,
                    "module": "Custom",
                    "is_standard": 0,
                    "charts": chart_links,  # Use the chart links we already validated
                }
            )
            dashboard_doc.insert()

            # Setup permissions
            self._setup_dashboard_sharing(dashboard_doc.name, share_with)

            # Extract chart names from links
            chart_names = [link["chart"] for link in chart_links]

            return {
                "success": True,
                "dashboard_type": "frappe_dashboard",
                "dashboard_name": dashboard_name,
                "dashboard_id": dashboard_doc.name,
                "dashboard_url": f"/app/dashboard/{dashboard_doc.name}",
                "charts_linked": len(chart_names),
                "mobile_optimized": mobile_optimized,
                "auto_refresh": auto_refresh,
                "charts": chart_names,
                "permissions": share_with,
            }

        except Exception as e:
            return {"success": False, "error": f"Frappe dashboard creation failed: {str(e)}"}

    def _setup_dashboard_sharing(self, dashboard_id: str, share_with: List[str]) -> Dict[str, Any]:
        """Setup dashboard sharing and permissions"""
        users_with_access = []

        for user_or_role in share_with:
            try:
                if frappe.db.exists("User", user_or_role):
                    frappe.share.add("Dashboard", dashboard_id, user_or_role, read=1)
                    users_with_access.append(user_or_role)
                elif frappe.db.exists("Role", user_or_role):
                    role_users = frappe.get_all("Has Role", filters={"role": user_or_role}, fields=["parent"])
                    for role_user in role_users:
                        frappe.share.add("Dashboard", dashboard_id, role_user.parent, read=1)
                        users_with_access.append(role_user.parent)
            except Exception as e:
                frappe.logger("dashboard_manager").warning(f"Failed to share with {user_or_role}: {str(e)}")

        return {
            "users_with_access": list(set(users_with_access)),
            "shared_count": len(set(users_with_access)),
        }
