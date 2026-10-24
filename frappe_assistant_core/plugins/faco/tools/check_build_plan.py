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

"""Checks a FACO build plan against the site before FAC Cloud shows the plan card."""

from typing import Any, Dict

from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.utils.customisation import check_plan_changes

# The most changes FAC Cloud puts in one build plan.
MAX_PLAN_CHANGES = 50


class CheckBuildPlan(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "check_build_plan"
        self.description = (
            "Used by FAC Cloud before it shows a build plan: reports, for each planned change, why it "
            "cannot be written as listed (an unknown doctype or a child table) and whether it goes live. "
            "Never writes. Not for answering users."
        )
        self.requires_permission = None
        self.required_roles = ["System Manager"]
        self.inputSchema = {
            "type": "object",
            "properties": {
                "changes": {
                    "type": "array",
                    "description": "The plan's changes: doctype, action, name or identity, goes_live",
                    "items": {"type": "object"},
                    "maxItems": MAX_PLAN_CHANGES,
                },
            },
            "required": ["changes"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        changes = arguments.get("changes")
        if not isinstance(changes, list) or not all(isinstance(change, dict) for change in changes):
            return {"success": False, "error": _("changes must be a list of objects")}
        if len(changes) > MAX_PLAN_CHANGES:
            return {
                "success": False,
                "error": _("A build plan can list at most {0} changes").format(MAX_PLAN_CHANGES),
            }
        return {"success": True, "results": check_plan_changes(changes)}
