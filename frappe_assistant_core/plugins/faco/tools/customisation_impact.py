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

"""Tells FAC Cloud whether a customisation write needs an approval card."""

from typing import Any, Dict

from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.utils.customisation import customisation_impact


class CustomisationImpact(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "customisation_impact"
        self.description = (
            "Used by FAC Cloud to decide whether a customisation write needs an approval card: reports "
            "whether the write would change anything other than its builder can feel yet. Never writes. "
            "Not for answering users. Switching this tool or the FAC Cloud plugin off makes every "
            "customisation write ask for approval again."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "tool_name": {"type": "string", "description": "The write tool about to run"},
                "tool_input": {"type": "object", "description": "The arguments that tool would receive"},
            },
            "required": ["tool_name", "tool_input"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_name = arguments.get("tool_name")
        tool_input = arguments.get("tool_input")
        if not isinstance(tool_name, str) or not tool_name or not isinstance(tool_input, dict):
            return {"success": False, "error": _("tool_name and tool_input are required")}
        return {"success": True, **customisation_impact(tool_name, tool_input)}
