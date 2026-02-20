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
Clean tools handlers using the new plugin manager architecture.
Replaces workarounds with proper state management and error handling.
"""

from typing import Any, Dict, Optional

import frappe

from frappe_assistant_core.constants.definitions import ErrorCodes, ErrorMessages, LogMessages
from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.utils.logger import api_logger
from frappe_assistant_core.utils.plugin_manager import PluginError, PluginNotFoundError, PluginValidationError


def handle_tools_list(request_id: Optional[Any]) -> Dict[str, Any]:
    """Handle tools/list request - return available tools"""
    try:
        api_logger.debug(LogMessages.TOOLS_LIST_REQUEST)

        registry = get_tool_registry()
        tools = registry.get_available_tools(user=frappe.session.user)

        response = {"jsonrpc": "2.0", "result": {"tools": tools}}

        if request_id is not None:
            response["id"] = request_id

        api_logger.info(
            f"Tools list request completed for user {frappe.session.user}, returned {len(tools)} tools"
        )
        return response

    except Exception as e:
        api_logger.error(f"Error in handle_tools_list: {e}")

        response = {
            "jsonrpc": "2.0",
            "error": {
                "code": ErrorCodes.INTERNAL_ERROR,
                "message": ErrorMessages.INTERNAL_ERROR,
                "data": str(e),
            },
        }

        if request_id is not None:
            response["id"] = request_id

        return response


def handle_tool_call(params: Dict[str, Any], request_id: Optional[Any]) -> Dict[str, Any]:
    """Handle tools/call request - execute specific tool"""
    try:
        api_logger.debug(LogMessages.TOOL_CALL_REQUEST.format(params))

        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            response = {
                "jsonrpc": "2.0",
                "error": {"code": ErrorCodes.INVALID_PARAMS, "message": ErrorMessages.MISSING_TOOL_NAME},
            }
            if request_id is not None:
                response["id"] = request_id
            return response

        # Execute tool using registry
        registry = get_tool_registry()
        api_logger.info(f"Executing tool {tool_name} for user {frappe.session.user}")

        try:
            result = registry.execute_tool(tool_name, arguments)
        except ValueError as e:
            # Tool not found
            api_logger.warning(f"Tool {tool_name} not available for user {frappe.session.user}: {str(e)}")
            response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": ErrorCodes.INVALID_PARAMS,
                    "message": ErrorMessages.UNKNOWN_TOOL.format(tool_name),
                },
            }
            if request_id is not None:
                response["id"] = request_id
            return response
        except PermissionError as e:
            # Permission denied
            api_logger.warning(
                f"Permission denied for tool {tool_name} and user {frappe.session.user}: {str(e)}"
            )
            response = {
                "jsonrpc": "2.0",
                "error": {"code": ErrorCodes.AUTHENTICATION_REQUIRED, "message": ErrorMessages.ACCESS_DENIED},
            }
            if request_id is not None:
                response["id"] = request_id
            return response
        except frappe.ValidationError as e:
            # Validation error - provide more specific details
            api_logger.error(f"Validation error in tool {tool_name} for user {frappe.session.user}: {str(e)}")
            response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": ErrorCodes.INVALID_PARAMS,
                    "message": f"Tool validation failed: {str(e)}",
                    "data": {"tool_name": tool_name, "error_type": "ValidationError", "details": str(e)},
                },
            }
            if request_id is not None:
                response["id"] = request_id
            return response
        except Exception as e:
            # All other execution errors - provide detailed logging
            api_logger.error(
                f"Tool execution failed for {tool_name} (user: {frappe.session.user}): {str(e)}",
                exc_info=True,
            )
            response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": ErrorCodes.INTERNAL_ERROR,
                    "message": f"Tool execution failed: {str(e)}",
                    "data": {"tool_name": tool_name, "error_type": type(e).__name__, "details": str(e)},
                },
            }
            if request_id is not None:
                response["id"] = request_id
            return response

        # Ensure result is a string for Claude Desktop compatibility
        if not isinstance(result, str):
            result = str(result)

        response = {"jsonrpc": "2.0", "result": {"content": [{"type": "text", "text": result}]}}

        if request_id is not None:
            response["id"] = request_id

        api_logger.info(f"Tool call completed successfully: {tool_name}")
        return response

    except Exception as e:
        api_logger.error(f"Error in handle_tool_call: {e}")

        response = {
            "jsonrpc": "2.0",
            "error": {
                "code": ErrorCodes.INTERNAL_ERROR,
                "message": ErrorMessages.INTERNAL_ERROR,
                "data": str(e),
            },
        }

        if request_id is not None:
            response["id"] = request_id

        return response
