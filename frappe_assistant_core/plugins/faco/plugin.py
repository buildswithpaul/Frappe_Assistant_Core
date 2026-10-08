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
  - attach_chat_file: attaches a file the user uploaded in chat to a document
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
    by Assistant Core Settings.enable_fac_chat.

    These tools reach FAC Cloud only. Each of them needs something no other
    MCP client can supply: the browser tools run inside the FAC Chat page over
    Socket.IO, and generate_document renders through FAC Chat's rich-block
    renderer. Offered to Claude Desktop, a browser tool would publish a
    realtime request nobody is listening for and fail only after the 30 second
    timeout, so they are hidden from every caller that is not FAC Cloud —
    see utils/mcp_caller.py. send_email carried no such dependency and now
    lives in the core plugin, where every client can still use it.
    """

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": "faco",
            "display_name": "FACO Tools",
            "description": (
                "Document generation and browser automation for FAC Chat. "
                "These tools run inside the FAC Chat page, so they are "
                "available to FAC Cloud only and stay hidden from other MCP "
                "clients such as Claude Desktop."
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
            "generate_document",
            "attach_chat_file",
            "browser_get_form_data",
            "browser_get_page_context",
            "browser_capture_diagnostics",
            "browser_navigate_to",
            "browser_take_screenshot",
            "browser_wait_for_page",
        ]

    def is_fac_cloud_only(self) -> bool:
        return True

    def validate_environment(self) -> Tuple[bool, Optional[str]]:
        # No environment dependencies for these tools.
        return True, None
