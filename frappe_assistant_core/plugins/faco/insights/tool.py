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

"""What the Insights tools share: they load only on a site that has Frappe Insights v3."""

from typing import Optional, Tuple

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool


def insights_installed() -> bool:
    # Installed on this site, not merely present on the bench; v3 is the version the tools read.
    return "insights" in frappe.get_installed_apps() and bool(
        frappe.db.exists("DocType", "Insights Dashboard v3")
    )


class InsightsTool(BaseTool):
    """Base for the Insights tools. Abstract, so the plugin loader never registers it as a tool."""

    def validate_dependencies(self) -> Tuple[bool, Optional[str]]:
        if not insights_installed():
            return False, _("Frappe Insights v3 is not installed")
        return super().validate_dependencies()
