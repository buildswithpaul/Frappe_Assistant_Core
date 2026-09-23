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
Base class for browser tools that communicate with the FACO widget via Socket.IO.
"""

import uuid
from abc import abstractmethod
from typing import Any, Optional

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool

# Default timeout for browser tool responses (in seconds)
BROWSER_TOOL_TIMEOUT = 30


class BaseBrowserTool(BaseTool):
    """
    Base class for all browser tools.

    Browser tools execute in the user's browser via the FACO widget.
    They communicate using Frappe's realtime (Socket.IO) infrastructure:

    1. Tool sends request via frappe.publish_realtime()
    2. FACO widget receives request and executes
    3. Widget sends result back via frappe.call()
    4. Tool retrieves result from Redis cache

    Subclasses must implement:
    - tool_name: The name of the tool (used for routing in widget)
    - get_tool_params(): Convert arguments to widget-specific params
    """

    def __init__(self):
        super().__init__()
        self.source_app = "frappe_assistant_core"
        self.category = "Browser"
        self.requires_permission = None  # Browser tools don't require DocType permissions
        self._timeout = BROWSER_TOOL_TIMEOUT

    @property
    @abstractmethod
    def tool_name(self) -> str:
        """The tool name used for routing in the widget."""
        pass

    @abstractmethod
    def get_tool_params(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Convert tool arguments to parameters for the widget handler.

        Args:
            arguments: The arguments passed to the tool

        Returns:
            Parameters dict to send to the widget
        """
        pass

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the browser tool by sending request to widget and waiting for response.

        Args:
            arguments: Tool-specific arguments

        Returns:
            Result from the browser widget
        """
        from frappe_assistant_core.plugins.faco.tools.browser_bridge import (
            send_browser_tool_call,
            wait_for_browser_response,
        )

        user = frappe.session.user
        call_id = str(uuid.uuid4())

        # Get tool-specific parameters
        params = self.get_tool_params(arguments)

        # Send tool call to browser
        send_browser_tool_call(
            user=user,
            call_id=call_id,
            tool_name=self.tool_name,
            params=params,
            session_id=getattr(frappe.local, "ar_session_id", None),
        )

        # Wait for response from browser
        result, last_state = wait_for_browser_response(
            call_id=call_id,
            timeout=self._timeout,
        )

        if result is None:
            return {
                "success": False,
                "error": self._timeout_reason(last_state),
            }

        if result.get("error"):
            return {
                "success": False,
                "error": result.get("error"),
            }

        return {
            "success": True,
            **result,
        }

    def _timeout_reason(self, last_state: Optional[str]) -> str:
        """Explain which phase ran out, so the model can react usefully.

        A single "browser tool timed out" string taught the agent nothing — it
        retried identically and burned the budget again. These three cases want
        three different follow-ups: give up, wait for the human, or capture less.
        """
        from frappe_assistant_core.plugins.faco.tools.browser_bridge import (
            ACK_AWAITING_USER,
            ACK_EXECUTING,
        )

        if last_state == ACK_AWAITING_USER:
            return _(
                "The user did not respond to the approval prompt in time. "
                "Ask them whether to try again rather than retrying automatically."
            )
        if last_state == ACK_EXECUTING:
            return _(
                "The browser started the operation but did not finish in time. "
                "If capturing a screenshot, retry with full_page=false or a narrower selector."
            )
        return _(
            "The FAC widget did not respond. It may be closed, on a page where it "
            "is not mounted, or the user navigated away. Continue without browser data."
        )

    def set_timeout(self, timeout: int) -> None:
        """Set the timeout for browser response (in seconds)."""
        self._timeout = timeout
