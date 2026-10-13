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

"""Frappe Insights plugin: read Insights v3 dashboards and charts, with their numbers."""

from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _

from frappe_assistant_core.plugins.base_plugin import BasePlugin


class InsightsPlugin(BasePlugin):
    def get_info(self) -> Dict[str, Any]:
        return {
            "name": "insights",
            "display_name": "Frappe Insights",
            "description": "Read Insights v3 dashboards and charts, with their numbers, as the user",
            "version": "1.0.0",
            "author": "Frappe Assistant Core Team",
            "category": "Business Intelligence",
            "dependencies": [],
            "requires_restart": False,
        }

    def get_tools(self) -> List[str]:
        return ["list_insights_dashboards", "get_insights_dashboard", "get_insights_chart"]

    def validate_environment(self) -> Tuple[bool, Optional[str]]:
        if "insights" not in frappe.get_installed_apps() or not frappe.db.exists(
            "DocType", "Insights Dashboard v3"
        ):
            return False, _("Frappe Insights v3 is not installed")
        return True, None
