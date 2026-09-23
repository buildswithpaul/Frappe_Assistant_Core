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
FACO Plugin for Frappe Assistant Core.

Provides tools migrated from frappe_assistant_copilot:
  - send_email: queues email via the site's Email Account
  - generate_document: renders rich-block content to HTML/PDF documents
  - browser_get_form_data: read form field values from the current page
  - browser_get_page_context: get structured info about the current page
  - browser_capture_diagnostics: collect console + network errors + screenshot
  - browser_navigate_to: navigate the user's browser to a Frappe route
  - browser_take_screenshot: capture a screenshot of the current page
  - browser_wait_for_page: wait for the page to finish loading

Utility modules (not registered as tools):
  - rich_blocks: helper imported by generate_document
  - base_browser_tool: base class for all browser tools
  - browser_bridge: Socket.IO + Redis bridge for browser tool communication
"""

from typing import Any, Dict, List, Optional, Tuple

from frappe_assistant_core.plugins.base_plugin import BasePlugin


class FacoPlugin(BasePlugin):
    """
    Plugin bundling tools originally shipped in frappe_assistant_copilot.

    The chat UI itself lives in frappe_assistant_core/chat/ and is gated
    by Assistant Core Settings.enable_fac_chat. This plugin's tools are
    available to MCP clients (Claude Desktop etc.) and to the chat UI
    when enabled; the plugin can also be enabled standalone for users
    who only want the extra tools via BYO-LLM.
    """

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": "faco",
            "display_name": "FACO Tools",
            "description": (
                "Tools migrated from frappe_assistant_copilot — email, "
                "document generation, rich-block rendering, and browser "
                "automation. Available to both MCP clients and the optional "
                "FAC Chat UI."
            ),
            "version": "1.0.0",
            "author": "Paul Clinton",
            "dependencies": [],
            "requires_restart": False,
        }

    def get_tools(self) -> List[str]:
        # Tools migrated from frappe_assistant_copilot.
        # base_browser_tool, browser_bridge, and rich_blocks are utility modules
        # imported by tools above; they are NOT themselves tools.
        return [
            "send_email",
            "generate_document",
            "browser_get_form_data",
            "browser_get_page_context",
            "browser_capture_diagnostics",
            "browser_navigate_to",
            "browser_take_screenshot",
            "browser_wait_for_page",
        ]

    def validate_environment(self) -> Tuple[bool, Optional[str]]:
        # No environment dependencies for these tools.
        return True, None
