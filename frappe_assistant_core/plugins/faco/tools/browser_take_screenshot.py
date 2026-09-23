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
Browser tool to capture a screenshot of the current page.
"""

from typing import Any

from frappe_assistant_core.plugins.faco.tools import screenshot_vision
from frappe_assistant_core.plugins.faco.tools.base_browser_tool import BaseBrowserTool


class BrowserTakeScreenshot(BaseBrowserTool):
    """
    Capture a screenshot of the user's current browser page.

    This tool captures the page, uploads it as a Frappe File, and returns
    the screenshot image directly for vision analysis. The AI can see
    and analyze the screenshot without needing OCR.

    Use this when:
    - Debugging visual/layout issues
    - Verifying chart or dashboard appearance
    - When user reports "something looks wrong"
    - Understanding complex visual layouts

    Note: for error reports, prefer browser_capture_diagnostics — it also
    returns the console and network errors a screenshot cannot show.
    """

    def __init__(self):
        super().__init__()
        self.name = "browser_take_screenshot"
        self.description = (
            "Capture a screenshot of the current browser page. "
            "Returns the image, which you can see and analyse directly. "
            "Use for visual questions such as verifying a chart or a layout. "
            "If the user is reporting an ERROR or something not working, use "
            "browser_capture_diagnostics instead — it returns the console and "
            "network errors a screenshot cannot show."
        )

        self.inputSchema = {
            "type": "object",
            "properties": {
                "full_page": {
                    "type": "boolean",
                    "description": (
                        "Capture the full page including scrolled content. "
                        "If false, only captures the visible viewport."
                    ),
                    "default": False,
                },
                "selector": {
                    "type": "string",
                    "description": (
                        "CSS selector to capture a specific element instead of the full page. "
                        "Example: '.frappe-chart' or '#page-content'"
                    ),
                },
                "quality": {
                    "type": "integer",
                    "description": "Image quality (1-100). Lower values reduce size but decrease quality.",
                    "default": 80,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": [],
        }

        # Screenshots may take longer to process
        self._timeout = 45

    @property
    def tool_name(self) -> str:
        return "take_screenshot"

    def get_tool_params(self, arguments: dict[str, Any]) -> dict[str, Any]:
        params = {
            "full_page": arguments.get("full_page", False),
            "quality": arguments.get("quality", 80),
        }

        if "selector" in arguments:
            params["selector"] = arguments["selector"]

        return params

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Execute screenshot capture and include image data for vision API.

        After the base class captures the screenshot and uploads it, reads the
        file back from disk and includes the image bytes so the LLM can see
        the screenshot directly through its vision capability — no OCR needed.
        """
        result = super().execute(arguments)

        if not result.get("success") or not result.get("file_url"):
            return result

        image = screenshot_vision.read_image_content(result["file_url"])
        if image:
            result["_image_content"] = image

        return result
