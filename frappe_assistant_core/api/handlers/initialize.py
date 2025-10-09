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
Initialize handler for MCP protocol
Handles server initialization and capability declaration
"""

from typing import Any, Dict, Optional

import frappe

from frappe_assistant_core.constants.definitions import (
    MCP_PROTOCOL_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
    ErrorCodes,
    ErrorMessages,
)
from frappe_assistant_core.utils.logger import api_logger


def get_app_version(app_name: str) -> str:
    """
    Get version of a Frappe app.

    Args:
        app_name: Name of the app

    Returns:
        Version string or empty string if not found
    """
    try:
        if app_name == "frappe_assistant_core":
            from frappe_assistant_core import __version__

            return __version__
        else:
            # For other apps, try to import and get __version__
            module = __import__(app_name)
            version = getattr(module, "__version__", None)
            return version if version else ""
    except ImportError:
        return ""


def handle_initialize(params: Dict[str, Any], request_id: Optional[Any]) -> Dict[str, Any]:
    """Handle MCP initialize request with prompts capabilities"""
    try:
        api_logger.debug(f"Handling initialize request with params: {params}")

        response = {
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {"listChanged": True},
                    "prompts": {},  # Declare prompts capability
                    "resources": {"subscribe": True, "listChanged": True},
                    "logging": {},
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": get_app_version("frappe_assistant_core") or SERVER_VERSION,
                },
            },
        }

        # Only include id if it's not None
        if request_id is not None:
            response["id"] = request_id

        api_logger.info("Initialize request completed successfully")
        return response

    except Exception as e:
        api_logger.error(f"Error in handle_initialize: {e}")

        response = {
            "jsonrpc": "2.0",
            "error": {
                "code": ErrorCodes.INTERNAL_ERROR,
                "message": ErrorMessages.INTERNAL_ERROR,
                "data": str(e),
            },
        }

        # Only include id if it's not None
        if request_id is not None:
            response["id"] = request_id

        return response
