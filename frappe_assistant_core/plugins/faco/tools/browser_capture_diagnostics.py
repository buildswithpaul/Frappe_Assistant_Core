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

"""Collect every signal a screen problem needs, in one approved call."""

from typing import Any

from frappe_assistant_core.plugins.faco.tools import screenshot_vision
from frappe_assistant_core.plugins.faco.tools.base_browser_tool import BaseBrowserTool


class BrowserCaptureDiagnostics(BaseBrowserTool):
    """Page context + console errors + failed requests + screenshot, in one call.

    Composite rather than three granular tools for two reasons. The model
    reliably gathers all three instead of choosing one, and the user clicks one
    approval card instead of three.
    """

    def __init__(self):
        super().__init__()
        self.name = "browser_capture_diagnostics"
        self.description = (
            "Diagnose a problem the user is seeing on their screen. Returns the "
            "page context, recent browser console errors, recent FAILED network "
            "requests including the error type and the server's error message "
            "(the Frappe traceback too, when available), and a screenshot. "
            "USE THIS FIRST whenever the user reports that something is broken, "
            "erroring, blank, frozen or 'not working', or asks you to look at "
            "what they are seeing. Do not ask them to read the error out to you "
            "— go and look. This is the expected first action, not an extra "
            "tool call. "
            "The console and network errors usually name the exact cause; a "
            "screenshot alone cannot, because the error dialog truncates the "
            "traceback."
        )

        self.inputSchema = {
            "type": "object",
            "properties": {
                "include_screenshot": {
                    "type": "boolean",
                    "description": "Also capture a screenshot. Leave on unless the user only asked about errors.",
                    "default": True,
                },
                "since_seconds": {
                    "type": "integer",
                    "description": "How far back to look for console and network errors.",
                    # Matches the recorder's MAX_AGE_MS (the hint's own aging
                    # cutoff) — anything narrower reopens the bug where the
                    # hint fires for an entry the drain can no longer reach.
                    "default": 300,
                    "minimum": 5,
                    "maximum": 300,
                },
                "max_console": {
                    "type": "integer",
                    "description": "Maximum console entries to return.",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                },
                "max_network": {
                    "type": "integer",
                    "description": "Maximum network entries to return. Failures are returned first.",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": [],
        }

        # Screenshot capture (45s) plus draining the buffers. A 45s budget would
        # expire mid-capture on the screenshot alone.
        self._timeout = 60

    @property
    def tool_name(self) -> str:
        return "capture_diagnostics"

    def get_tool_params(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "include_screenshot": arguments.get("include_screenshot", True),
            "since_seconds": arguments.get("since_seconds", 300),
            "max_console": arguments.get("max_console", 20),
            "max_network": arguments.get("max_network", 20),
        }

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Run the capture, then attach the screenshot for the vision API.

        A screenshot failure never fails the call — the console and network
        entries are the more useful half and must still come back.
        """
        result = super().execute(arguments)

        if not result.get("success"):
            return result

        screenshot = result.get("screenshot") or {}
        image = screenshot_vision.read_image_content(screenshot.get("file_url"))
        if image:
            result["_image_content"] = image

        return result
