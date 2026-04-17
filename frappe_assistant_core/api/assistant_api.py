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

from typing import Any, Dict, Optional

import frappe
from frappe import _

from frappe_assistant_core.utils.logger import api_logger


@frappe.whitelist(methods=["GET", "POST"])
def get_usage_statistics() -> Dict[str, Any]:
    """Get usage statistics for the assistant"""
    try:
        # SECURITY: Handle both session-based and token-based authentication
        authenticated_user = _authenticate_request()
        if not authenticated_user:
            api_logger.warning("Usage statistics requested without valid authentication")
            frappe.throw(_("Authentication required"))

        # SECURITY: Restrict global usage statistics to assistant admins
        from frappe_assistant_core.utils.permissions import check_assistant_admin_permission

        user_roles = frappe.get_roles(authenticated_user)
        api_logger.debug(f"User {authenticated_user} has roles: {user_roles}")

        if not check_assistant_admin_permission(authenticated_user):
            api_logger.warning(
                f"Usage statistics denied for non-admin user: {authenticated_user} with roles: {user_roles}"
            )
            frappe.throw(_("Access denied - administrator permissions required"))

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
    api_logger.debug(f"Authorization header present: {bool(auth_header)}")

    if auth_header and auth_header.startswith("token "):
        try:
            # Extract token from "token api_key:api_secret" format
            token_part = auth_header[6:]  # Remove "token " prefix
            if ":" in token_part:
                api_key, api_secret = token_part.split(":", 1)
                api_logger.debug("API key extracted from token header")

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
                        # nosemgrep: frappe-semgrep-rules.rules.security.frappe-setuser — user authenticated via API key:secret comparison above
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
