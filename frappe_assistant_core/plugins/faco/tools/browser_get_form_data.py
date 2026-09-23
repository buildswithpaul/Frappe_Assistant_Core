# Frappe Assistant Core - Browser Tools
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
Browser tool to get form field data from the current page.
"""

from typing import Any

from frappe_assistant_core.plugins.faco.tools.base_browser_tool import BaseBrowserTool


class BrowserGetFormData(BaseBrowserTool):
    """
    Get form field values from the current page.

    This is a specialized tool for when the user is on a form page (document view).
    It extracts all field values from the form, including:
    - Standard fields (text, number, date, etc.)
    - Link fields
    - Child table data
    - Form state (is_new, is_dirty, docstatus)

    Use this when you specifically need form field values rather than general page context.
    For non-form pages, use browser_get_page_context instead.
    """

    def __init__(self):
        super().__init__()
        self.name = "browser_get_form_data"
        self.description = (
            "Get all form field values from the current page. "
            "Only works when user is viewing a document form. "
            "Returns field values, child tables, and form state. "
            "Use browser_get_page_context for non-form pages."
        )

        self.inputSchema = {
            "type": "object",
            "properties": {
                "include_child_tables": {
                    "type": "boolean",
                    "description": "Include data from child tables in the form.",
                    "default": True,
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Specific field names to retrieve. "
                        "If not provided, all visible fields are returned."
                    ),
                },
            },
            "required": [],
        }

    @property
    def tool_name(self) -> str:
        return "get_form_data"

    def get_tool_params(self, arguments: dict[str, Any]) -> dict[str, Any]:
        params = {
            "include_child_tables": arguments.get("include_child_tables", True),
        }

        if "fields" in arguments:
            params["fields"] = arguments["fields"]

        return params
