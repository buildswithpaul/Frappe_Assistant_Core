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
Browser tool to get structured page context from the current browser page.
"""

from typing import Any

from frappe_assistant_core.plugins.faco.tools.base_browser_tool import BaseBrowserTool


class BrowserGetPageContext(BaseBrowserTool):
    """
    Get structured context about the current page in the user's browser.

    Returns information about:
    - Page type (Form, List, Report, Dashboard, etc.)
    - Current DocType and document name (if applicable)
    - URL and route information
    - Visible content and interactive elements
    - DOM content extraction (field values, visible text, etc.)

    This tool is useful for understanding what the user is currently viewing
    before taking actions or providing context-aware assistance.
    """

    def __init__(self):
        super().__init__()
        self.name = "browser_get_page_context"
        self.description = (
            "Get structured information about the current page in the user's browser. "
            "Returns page type, doctype, document name, URL, and DOM content. "
            "Use this to understand what the user is viewing before providing assistance."
        )

        self.inputSchema = {
            "type": "object",
            "properties": {},
            "required": [],
        }

    @property
    def tool_name(self) -> str:
        return "get_page_context"

    def get_tool_params(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return {}
