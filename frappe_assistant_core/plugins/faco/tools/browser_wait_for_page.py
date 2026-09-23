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
Browser tool to wait for page to finish loading.
"""

from typing import Any

from frappe_assistant_core.plugins.faco.tools.base_browser_tool import BaseBrowserTool


class BrowserWaitForPage(BaseBrowserTool):
    """
    Wait for the current page to finish loading.

    This tool waits until:
    - The page's DOM is fully loaded
    - Any pending AJAX requests are complete
    - The Frappe page is ready (page_container.page_ready)

    Optionally wait for specific content to appear on the page.

    Use this after navigation or when the page is still loading data.
    """

    def __init__(self):
        super().__init__()
        self.name = "browser_wait_for_page"
        self.description = (
            "Wait for the current page to finish loading. "
            "Waits for DOM ready and pending AJAX requests to complete. "
            "Optionally wait for specific text or element to appear. "
            "Returns page context once ready."
        )

        self.inputSchema = {
            "type": "object",
            "properties": {
                "timeout_ms": {
                    "type": "integer",
                    "description": "Maximum time to wait in milliseconds.",
                    "default": 10000,
                },
                "wait_for_text": {
                    "type": "string",
                    "description": "Wait until this text appears on the page.",
                },
                "wait_for_selector": {
                    "type": "string",
                    "description": "Wait until an element matching this CSS selector appears.",
                },
            },
            "required": [],
        }

    @property
    def tool_name(self) -> str:
        return "wait_for_page"

    def get_tool_params(self, arguments: dict[str, Any]) -> dict[str, Any]:
        params = {
            "timeout_ms": arguments.get("timeout_ms", 10000),
        }

        if "wait_for_text" in arguments:
            params["wait_for_text"] = arguments["wait_for_text"]

        if "wait_for_selector" in arguments:
            params["wait_for_selector"] = arguments["wait_for_selector"]

        return params
