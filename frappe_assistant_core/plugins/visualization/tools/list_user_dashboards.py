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
List User Dashboards Tool - List all dashboards accessible to current user

List all dashboards accessible to the current user with filtering options.
"""

from typing import Any, Dict, List

import frappe
from frappe import _
from frappe.share import get_shared

from frappe_assistant_core.core.base_tool import BaseTool, permission_error_result


class ListUserDashboards(BaseTool):
    """List all dashboards accessible to current user"""

    def __init__(self):
        super().__init__()
        self.name = "list_user_dashboards"
        self.description = "List all dashboards accessible to the current user with filtering options"
        self.requires_permission = None

        self.inputSchema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "string",
                    "description": "List the dashboards this user owns (defaults to current user). Only dashboards the current user may read are returned, and another user's shares only to a user who may read DocShare.",
                },
                "dashboard_type": {
                    "type": "string",
                    "enum": ["insights", "frappe_dashboard", "all"],
                    "default": "all",
                    "description": "Type of dashboards to list",
                },
                "include_shared": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include dashboards shared with user",
                },
            },
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """List accessible dashboards"""
        try:
            user = arguments.get("user") or frappe.session.user
            dashboard_type = arguments.get("dashboard_type", "all")
            include_shared = arguments.get("include_shared", True)

            # Who a dashboard is shared with is read from DocShare, which Desk shows only to
            # those who may read it; the caller's own shares are always theirs to see.
            if (
                include_shared
                and user != frappe.session.user
                and not frappe.has_permission("DocShare", "read")
            ):
                return permission_error_result(
                    "Dashboard",
                    _("You may list only your own dashboards and those shared with you."),
                )

            fields = ["name", "dashboard_name", "creation", "modified", "module"]
            dashboards = []

            # get_list, as the Desk list view: the session user's read permission and the
            # Dashboard permission query apply (get_all skipped both).
            own_dashboards = frappe.get_list("Dashboard", filters={"owner": user}, fields=fields)

            for dashboard in own_dashboards:
                dashboards.append(
                    {
                        **dashboard,
                        "access_type": "owner",
                        "dashboard_type": "insights"
                        if dashboard.module == "Insights"
                        else "frappe_dashboard",
                    }
                )

            # Get shared dashboards if requested
            if include_shared:
                # Frappe's own lookup: shares to this user or to everyone (the old filter
                # matched share_name against the user, so it found nothing).
                own_names = {dashboard.name for dashboard in own_dashboards}
                shared_names = [name for name in get_shared("Dashboard", user) if name not in own_names]
                shared_dashboards = (
                    frappe.get_list("Dashboard", filters={"name": ["in", shared_names]}, fields=fields)
                    if shared_names
                    else []
                )
                for dashboard in shared_dashboards:
                    dashboards.append(
                        {
                            **dashboard,
                            "access_type": "shared",
                            "dashboard_type": "insights"
                            if dashboard.module == "Insights"
                            else "frappe_dashboard",
                        }
                    )

            # Filter by dashboard type if specified
            if dashboard_type != "all":
                dashboards = [d for d in dashboards if d["dashboard_type"] == dashboard_type]

            # Sort by modification date (newest first)
            dashboards.sort(key=lambda x: x["modified"], reverse=True)

            return {
                "success": True,
                "dashboards": dashboards,
                "total_count": len(dashboards),
                "user": user,
                "dashboard_type_filter": dashboard_type,
                "includes_shared": include_shared,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}
