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
Clean refactored Assistant API with modular handlers and proper logging
"""

import json
from typing import Any, Dict, Optional

import frappe
from frappe import _

from frappe_assistant_core.api.handlers import (
    handle_initialize,
    handle_prompts_get,
    handle_prompts_list,
    handle_tool_call,
    handle_tools_list,
)
from frappe_assistant_core.constants.definitions import (
    MCP_PROTOCOL_VERSION,
    ErrorCodes,
    ErrorMessages,
    LogMessages,
)
from frappe_assistant_core.utils.logger import api_logger


@frappe.whitelist(allow_guest=True, methods=["POST"])
def handle_assistant_request() -> Dict[str, Any]:
    """Handle assistant protocol requests"""

    # SECURITY: Handle both session-based and token-based authentication
    authenticated_user = _authenticate_request()
    if not authenticated_user:
        api_logger.warning("Authentication failed - no valid session or token")
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": ErrorCodes.AUTHENTICATION_REQUIRED,
                "message": ErrorMessages.AUTHENTICATION_REQUIRED,
            },
        }

    # SECURITY: Check if user has assistant access
    from frappe_assistant_core.utils.permissions import check_assistant_permission

    if not check_assistant_permission(authenticated_user):
        api_logger.warning(f"Access denied for user: {authenticated_user}")
        return {
            "jsonrpc": "2.0",
            "error": {"code": ErrorCodes.AUTHENTICATION_REQUIRED, "message": ErrorMessages.ACCESS_DENIED},
        }

    api_logger.info(LogMessages.API_AUTHENTICATED.format(authenticated_user))

    # CRITICAL: Ensure user context is maintained for the entire request
    frappe.set_user(authenticated_user)

    try:
        # Log connection
        log_assistant_connection()
    except Exception as e:
        api_logger.debug(f"Connection logging failed: {e}")

    try:
        # Get request data
        data = _extract_request_data()
        api_logger.debug(LogMessages.API_RECEIVED_DATA.format(data))

        # Validate JSON-RPC 2.0 format
        validation_response = _validate_jsonrpc_request(data)
        if validation_response:
            return validation_response

        method = data.get("method")
        params = data.get("params", {})
        request_id = data.get("id")

        api_logger.debug(LogMessages.METHOD_PARAMS.format(method, params))

        # Handle different assistant methods using modular handlers
        if method == "initialize":
            response = handle_initialize(params, request_id)
            _log_assistant_audit("initialize", params, response, "Success")
            return response
        elif method == "tools/list":
            response = handle_tools_list(request_id)
            _log_assistant_audit("get_metadata", params, response, "Success")
            return response
        elif method == "tools/call":
            response = handle_tool_call(params, request_id)
            # Note: Tool execution audit logging is now handled by BaseTool._safe_execute
            # No need for duplicate audit logging at the API level
            return response
        elif method == "prompts/list":
            response = handle_prompts_list(request_id)
            _log_assistant_audit("get_prompts", params, response, "Success")
            return response
        elif method == "prompts/get":
            response = handle_prompts_get(params, request_id)
            _log_assistant_audit("get_prompt", params, response, "Success")
            return response
        elif method == "notifications/cancelled":
            from frappe_assistant_core.api.assistant_api_notification_handler import (
                handle_notification_cancelled,
            )

            return handle_notification_cancelled(params, request_id)
        else:
            response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": ErrorCodes.METHOD_NOT_FOUND,
                    "message": ErrorMessages.METHOD_NOT_FOUND.format(method),
                },
            }

            # Only include id if it's not None
            if request_id is not None:
                response["id"] = request_id

            return response

    except Exception as e:
        api_logger.error(f"Assistant API Error: {str(e)}")

        response = {
            "jsonrpc": "2.0",
            "error": {
                "code": ErrorCodes.INTERNAL_ERROR,
                "message": ErrorMessages.INTERNAL_ERROR,
                "data": str(e),
            },
        }

        # Only include id if it's not None and we have access to data
        if "data" in locals() and isinstance(data, dict) and data.get("id") is not None:
            response["id"] = data["id"]

        return response


def _extract_request_data() -> Dict[str, Any]:
    """Extract request data from Frappe request context"""
    if hasattr(frappe.local, "form_dict") and frappe.local.form_dict:
        return frappe.local.form_dict
    elif hasattr(frappe, "request") and frappe.request.data:
        return json.loads(frappe.request.data.decode("utf-8"))
    else:
        return {}


def _validate_jsonrpc_request(data: Any) -> Optional[Dict[str, Any]]:
    """Validate JSON-RPC 2.0 request format"""
    if not isinstance(data, dict) or data.get("jsonrpc") != "2.0":
        response = {
            "jsonrpc": "2.0",
            "error": {"code": ErrorCodes.INVALID_REQUEST, "message": ErrorMessages.INVALID_REQUEST_FORMAT},
        }

        # Only include id if it exists and is not None
        if isinstance(data, dict) and data.get("id") is not None:
            response["id"] = data["id"]

        return response

    return None


def _log_assistant_audit(action: str, params: Dict[str, Any], response: Dict[str, Any], status: str):
    """Log assistant action for audit purposes"""
    try:
        log_assistant_audit(action, params, response, status)
    except Exception as e:
        api_logger.debug(f"Audit logging failed: {e}")


def log_assistant_connection():
    """Log assistant connection for monitoring purposes"""
    try:
        # Create a log entry for connection tracking
        user = frappe.session.user
        user_ip = frappe.local.request_ip if hasattr(frappe.local, "request_ip") else "Unknown"

        api_logger.info(f"Assistant connection established - User: {user}, IP: {user_ip}")

        # You can extend this to create database logs if needed
        # For now, just log to the application log

    except Exception as e:
        api_logger.error(f"Error logging connection: {e}")


def log_assistant_audit(action: str, params: Dict[str, Any], response: Dict[str, Any], status: str):
    """Log assistant actions for audit and compliance"""
    try:
        user = frappe.session.user

        # Log the action
        api_logger.info(f"Assistant Audit - User: {user}, Action: {action}, Status: {status}")

        # For detailed audit logs, you can extend this to create database records
        # This is particularly useful for compliance and monitoring
        audit_data = {
            "user": user,
            "action": action,
            "status": status,
            "timestamp": frappe.utils.now(),
            "params_summary": str(params)[:500] if params else "",  # Truncate for storage
            "has_error": "error" in response if response else False,
        }

        api_logger.debug(f"Assistant Audit Details: {audit_data}")

    except Exception as e:
        api_logger.error(f"Error in audit logging: {e}")


@frappe.whitelist(methods=["GET", "POST"])
def get_usage_statistics() -> Dict[str, Any]:
    """Get usage statistics for the assistant"""
    try:
        # SECURITY: Handle both session-based and token-based authentication
        authenticated_user = _authenticate_request()
        if not authenticated_user:
            api_logger.warning("Usage statistics requested without valid authentication")
            frappe.throw(_("Authentication required"))

        # SECURITY: Check if user has assistant access
        from frappe_assistant_core.utils.permissions import check_assistant_permission

        user_roles = frappe.get_roles(authenticated_user)
        api_logger.debug(f"User {authenticated_user} has roles: {user_roles}")

        if not check_assistant_permission(authenticated_user):
            api_logger.warning(f"Access denied for user: {authenticated_user} with roles: {user_roles}")
            frappe.throw(_("Access denied - insufficient permissions"))

        api_logger.info(f"Usage statistics requested by user: {authenticated_user}")
        api_logger.info(f"Current site: {frappe.local.site}")

        # Get actual usage statistics
        today = frappe.utils.today()
        week_start = frappe.utils.add_days(today, -7)

        # Connection statistics are no longer tracked (Assistant Connection Log removed)
        # Using audit log activity as a proxy for connection activity
        try:
            total_connections = frappe.db.count("Assistant Audit Log") or 0
            today_connections = frappe.db.count("Assistant Audit Log", {"creation": (">=", today)}) or 0
            week_connections = frappe.db.count("Assistant Audit Log", {"creation": (">=", week_start)}) or 0
        except Exception as e:
            api_logger.warning(f"Connection stats error: {e}")
            total_connections = today_connections = week_connections = 0

        # Audit log statistics with error handling
        try:
            total_audit = frappe.db.count("Assistant Audit Log") or 0
            today_audit = frappe.db.count("Assistant Audit Log", {"creation": (">=", today)}) or 0
            week_audit = frappe.db.count("Assistant Audit Log", {"creation": (">=", week_start)}) or 0
        except Exception as e:
            api_logger.warning(f"Audit stats error: {e}")
            total_audit = today_audit = week_audit = 0

        # Tool statistics from plugin manager
        try:
            from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

            plugin_manager = get_plugin_manager()
            all_tools = plugin_manager.get_all_tools()
            total_tools = len(all_tools)
            enabled_tools = len(all_tools)  # All loaded tools are enabled
            api_logger.debug(f"Tool stats: total={total_tools}, enabled={enabled_tools}")
        except Exception as e:
            api_logger.warning(f"Tool stats error: {e}")
            total_tools = enabled_tools = 0

        # Recent activity with error handling
        try:
            recent_activity = (
                frappe.db.get_list(
                    "Assistant Audit Log",
                    fields=["action", "tool_name", "user", "status", "timestamp"],
                    order_by="timestamp desc",
                    limit=10,
                )
                or []
            )
        except Exception as e:
            api_logger.warning(f"Recent activity error: {e}")
            recent_activity = []

        # Return statistics in the format expected by frontend
        result = {
            "success": True,
            "data": {
                "connections": {
                    "total": total_connections,
                    "today": today_connections,
                    "this_week": week_connections,
                },
                "audit_logs": {"total": total_audit, "today": today_audit, "this_week": week_audit},
                "tools": {"total": total_tools, "enabled": enabled_tools},
                "recent_activity": recent_activity,
            },
        }

        api_logger.debug(f"Usage statistics result: {result}")
        return result

    except Exception as e:
        api_logger.error(f"Error getting usage statistics: {e}")
        return {"success": False, "error": str(e)}


@frappe.whitelist(methods=["GET", "POST"])
def ping() -> Dict[str, Any]:
    """Ping endpoint for testing connectivity"""
    try:
        # SECURITY: Handle both session-based and token-based authentication
        authenticated_user = _authenticate_request()
        if not authenticated_user:
            frappe.throw(_("Authentication required"))

        # SECURITY: Check if user has assistant access
        from frappe_assistant_core.utils.permissions import check_assistant_permission

        if not check_assistant_permission(authenticated_user):
            frappe.throw(_("Access denied"))

        return {
            "success": True,
            "message": "pong",
            "timestamp": frappe.utils.now(),
            "user": authenticated_user,
        }

    except Exception as e:
        api_logger.error(f"Error in ping: {e}")
        return {"success": False, "message": f"Ping failed: {str(e)}"}


@frappe.whitelist(methods=["GET", "POST"])
def force_test_logging() -> Dict[str, Any]:
    """Force test logging for debugging purposes"""
    try:
        # SECURITY: Handle both session-based and token-based authentication
        authenticated_user = _authenticate_request()
        if not authenticated_user:
            frappe.throw(_("Authentication required"))

        # SECURITY: Check if user has assistant access
        from frappe_assistant_core.utils.permissions import check_assistant_permission

        if not check_assistant_permission(authenticated_user):
            frappe.throw(_("Access denied"))

        # Force a test log entry
        api_logger.info(f"Force test logging triggered by user: {authenticated_user}")

        return {
            "success": True,
            "message": "Test logging completed",
            "timestamp": frappe.utils.now(),
            "user": authenticated_user,
        }

    except Exception as e:
        api_logger.error(f"Error in force test logging: {e}")
        return {"success": False, "message": f"Force test logging failed: {str(e)}"}


def _authenticate_request() -> Optional[str]:
    """
    Handle session-based, OAuth2.0 Bearer token, and API key authentication
    Returns the authenticated user or None if authentication fails

    Note: OAuth2.0 Bearer tokens are automatically validated by Frappe's auth system
    and frappe.session.user is set before this function is called
    """

    # Check if user is already authenticated (covers session and OAuth2.0 Bearer tokens)
    if frappe.session.user and frappe.session.user != "Guest":
        # Check if user has assistant access enabled
        if not _check_assistant_enabled(frappe.session.user):
            api_logger.warning(f"User {frappe.session.user} has assistant access disabled")
            return None

        auth_header = frappe.get_request_header("Authorization", "") or ""
        if auth_header.startswith("Bearer "):
            api_logger.debug(f"OAuth2.0 Bearer token authentication successful: {frappe.session.user}")
        else:
            api_logger.debug(f"Session authentication successful: {frappe.session.user}")
        return frappe.session.user

    # Fallback to API key authentication for legacy clients
    auth_header = frappe.get_request_header("Authorization")
    api_logger.debug(f"Authorization header: {auth_header}")

    if auth_header and auth_header.startswith("token "):
        try:
            # Extract token from "token api_key:api_secret" format
            token_part = auth_header[6:]  # Remove "token " prefix
            if ":" in token_part:
                api_key, api_secret = token_part.split(":", 1)
                api_logger.debug(f"Extracted API key: {api_key}")

                # Custom validation using database lookup and password verification
                user_data = frappe.db.get_value(
                    "User", {"api_key": api_key, "enabled": 1}, ["name", "api_secret"]
                )

                api_logger.debug(f"User data found: {bool(user_data)}")

                if user_data:
                    user, _ = user_data
                    # Compare the provided secret with stored secret
                    from frappe.utils.password import get_decrypted_password

                    decrypted_secret = get_decrypted_password("User", user, "api_secret")

                    if api_secret == decrypted_secret:
                        # Check if user has assistant access enabled
                        if not _check_assistant_enabled(str(user)):
                            api_logger.warning(f"User {user} has assistant access disabled")
                            return None

                        # Set user context for this request
                        frappe.set_user(str(user))
                        api_logger.debug(f"API key authentication successful: {user}")
                        return str(user)
                    else:
                        api_logger.debug("API secret mismatch")
                else:
                    api_logger.debug("No user found with provided API key")

        except Exception as e:
            api_logger.error(f"API key authentication failed: {e}")
    else:
        api_logger.debug("No valid authorization header found")

    api_logger.debug("Authentication failed")
    return None


def _check_assistant_enabled(user: str) -> bool:
    """
    Check if the assistant_enabled field is enabled for the user.

    Args:
        user: Username to check

    Returns:
        bool: True if assistant is enabled, False otherwise
    """
    try:
        # Get the assistant_enabled field value for the user
        assistant_enabled = frappe.db.get_value("User", user, "assistant_enabled")

        # If the field doesn't exist or is not set, default to disabled for security
        if assistant_enabled is None:
            api_logger.debug(f"assistant_enabled field not found for user {user}, defaulting to disabled")
            return False

        # Convert to boolean (handles 0/1, "0"/"1", and boolean values)
        is_enabled = bool(int(assistant_enabled)) if assistant_enabled else False

        api_logger.debug(f"User {user} assistant_enabled: {is_enabled}")
        return is_enabled

    except Exception as e:
        # If there's any error checking the field, default to disabled for security
        api_logger.error(f"Error checking assistant_enabled for user {user}: {e}")
        return False
