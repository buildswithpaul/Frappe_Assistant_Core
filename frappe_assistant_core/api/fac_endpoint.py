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
MCP StreamableHTTP Endpoint

Custom MCP implementation that properly handles JSON serialization
and integrates seamlessly with Frappe's existing tool infrastructure.
"""

import frappe
from frappe import _

from frappe_assistant_core.mcp.server import MCPServer


def _get_mcp_server_name():
    """Get MCP server name from settings or use default."""
    try:
        settings = frappe.get_single("Assistant Core Settings")
        return settings.mcp_server_name or "frappe-assistant-core"
    except Exception:
        return "frappe-assistant-core"


# Create MCP server instance with name from settings
mcp = MCPServer(_get_mcp_server_name())


def _check_assistant_enabled(user: str) -> bool:
    """Check if assistant is enabled for user."""
    try:
        assistant_enabled = frappe.db.get_value("User", user, "assistant_enabled")
        if assistant_enabled is None:
            return False
        return bool(int(assistant_enabled)) if assistant_enabled else False
    except Exception:
        return False


def _import_tools():
    """Import and register all enabled tools from plugin manager."""
    try:
        from frappe_assistant_core.core.tool_registry import get_tool_registry
        from frappe_assistant_core.mcp.tool_adapter import register_base_tool

        # Clear existing tools to avoid duplicates on subsequent requests
        # This is necessary because mcp is a module-level global instance
        mcp._tool_registry.clear()

        # Get available tools (respects enabled/disabled state and permissions)
        registry = get_tool_registry()
        available_tools = registry.get_available_tools(user=frappe.session.user)

        # Register each enabled tool with MCP server
        tool_count = 0
        for tool_metadata in available_tools:
            tool_name = tool_metadata.get("name")
            if tool_name:
                tool_instance = registry.get_tool(tool_name)
                if tool_instance:
                    register_base_tool(mcp, tool_instance)
                    tool_count += 1

        frappe.logger().info(f"Registered {tool_count} enabled tools for user {frappe.session.user}")

    except Exception as e:
        frappe.log_error(title="Tool Import Error", message=f"Error importing tools: {str(e)}")


def _authenticate_mcp_request():
    """
    Authenticate MCP requests using OAuth Bearer tokens, API key/secret, or session cookies.

    Supports three authentication methods:
    1. OAuth 2.0 Bearer tokens: "Authorization: Bearer <token>"
    2. API Key/Secret: "Authorization: token <api_key>:<api_secret>"
    3. Session cookies: "Cookie: sid=<session_id>" (for internal agent-to-MCP calls)

    Returns:
        str: Authenticated username
        None: Authentication failed (returns 401 response directly)
    """
    from frappe.oauth import get_server_url
    from werkzeug.wrappers import Response

    # Check for session cookie first (for internal agent calls)
    # When allow_guest=True, we need to manually check the session
    cookie_header = frappe.request.headers.get("Cookie", "")

    if cookie_header and "sid=" in cookie_header:
        try:
            # Extract sid from cookie
            import re

            sid_match = re.search(r"sid=([^;]+)", cookie_header)
            if sid_match:
                sid = sid_match.group(1)

                # Validate session using direct database query
                # This is necessary because allow_guest=True bypasses normal session validation
                session_data = frappe.db.sql(
                    """SELECT user FROM tabSessions WHERE sid = %s LIMIT 1""", (sid,), as_dict=True
                )

                if session_data and len(session_data) > 0:
                    user = session_data[0].get("user")
                    if user and user != "Guest":
                        frappe.set_user(user)
                        frappe.logger().info(f"Session cookie authenticated for user: {user}")
                        return user
        except Exception as e:
            frappe.logger().debug(f"Session cookie validation failed: {str(e)}")
            # Continue to other auth methods

    auth_header = frappe.request.headers.get("Authorization", "")

    # Try OAuth Bearer token authentication first
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Remove "Bearer " prefix
        try:
            # Validate token using Frappe's OAuth Bearer Token doctype
            bearer_token = frappe.get_doc("OAuth Bearer Token", {"access_token": token})

            # Check if token is active
            if bearer_token.status != "Active":
                frappe.logger().error(f"Token is not active. Status: {bearer_token.status}")
                raise frappe.AuthenticationError("Token is not active")

            # Check if token has expired
            import datetime

            if bearer_token.expiration_time < datetime.datetime.now():
                frappe.logger().error(
                    f"Token has expired. Expiration: {bearer_token.expiration_time}, Now: {datetime.datetime.now()}"
                )
                raise frappe.AuthenticationError("Token has expired")

            # Set the user session
            frappe.set_user(bearer_token.user)
            frappe.logger().info(f"OAuth token validated successfully for user: {bearer_token.user}")
            return bearer_token.user

        except frappe.DoesNotExistError:
            frappe.logger().error(f"OAuth Bearer Token not found for access_token: {token[:20]}...")
            # Token not found - return 401
            frappe_url = get_server_url()
            metadata_url = f"{frappe_url}/.well-known/oauth-protected-resource"

            response = Response()
            response.status_code = 401
            response.headers["WWW-Authenticate"] = (
                f'Bearer realm="Frappe Assistant Core", '
                f'error="invalid_token", '
                f'error_description="Token not found", '
                f'resource_metadata="{metadata_url}"'
            )
            response.headers["Content-Type"] = "application/json"
            response.data = frappe.as_json({"error": "invalid_token", "message": "Token not found"})
            return response

        except Exception as e:
            # Log the error for debugging
            frappe.logger().error(f"OAuth token validation error: {type(e).__name__}: {str(e)}")
            frappe.log_error(title="OAuth Token Validation Error", message=f"{type(e).__name__}: {str(e)}")

            # Return 401 for invalid/expired tokens
            frappe_url = get_server_url()
            metadata_url = f"{frappe_url}/.well-known/oauth-protected-resource"

            response = Response()
            response.status_code = 401
            response.headers["WWW-Authenticate"] = (
                f'Bearer realm="Frappe Assistant Core", '
                f'error="invalid_token", '
                f'error_description="{str(e)}", '
                f'resource_metadata="{metadata_url}"'
            )
            response.headers["Content-Type"] = "application/json"
            response.data = frappe.as_json({"error": "invalid_token", "message": str(e)})
            return response

    # Try API Key/Secret authentication (for STDIO clients)
    elif auth_header.startswith("token "):
        try:
            # Extract token from "token api_key:api_secret" format
            token_part = auth_header[6:]  # Remove "token " prefix
            if ":" in token_part:
                api_key, api_secret = token_part.split(":", 1)
                frappe.logger().debug(f"Attempting API key authentication for key: {api_key[:10]}...")

                # Validate using database lookup
                user_data = frappe.db.get_value(
                    "User", {"api_key": api_key, "enabled": 1}, ["name", "api_secret"]
                )

                if user_data:
                    user, _ = user_data
                    # Compare the provided secret with stored secret
                    from frappe.utils.password import get_decrypted_password

                    decrypted_secret = get_decrypted_password("User", user, "api_secret")

                    if api_secret == decrypted_secret:
                        # Set user context for this request
                        frappe.set_user(str(user))
                        frappe.logger().info(f"API key authentication successful for user: {user}")
                        return str(user)
                    else:
                        frappe.logger().warning("API secret mismatch")
                        raise frappe.AuthenticationError("Invalid API credentials")
                else:
                    frappe.logger().warning(f"API key not found: {api_key[:10]}...")
                    raise frappe.AuthenticationError("Invalid API credentials")
            else:
                frappe.logger().warning("Invalid API key format - missing colon separator")
                raise frappe.AuthenticationError("Invalid API key format")

        except frappe.AuthenticationError as e:
            # Return 401 for invalid API credentials
            frappe_url = get_server_url()
            metadata_url = f"{frappe_url}/.well-known/oauth-protected-resource"

            response = Response()
            response.status_code = 401
            response.headers["WWW-Authenticate"] = (
                f'Bearer realm="Frappe Assistant Core", ' f'resource_metadata="{metadata_url}"'
            )
            response.headers["Content-Type"] = "application/json"
            response.data = frappe.as_json({"error": "invalid_credentials", "message": str(e)})
            return response

        except Exception as e:
            frappe.logger().error(f"API key authentication error: {type(e).__name__}: {str(e)}")
            frappe.log_error(title="API Key Authentication Error", message=f"{type(e).__name__}: {str(e)}")

            # Return 401 for other errors
            frappe_url = get_server_url()
            metadata_url = f"{frappe_url}/.well-known/oauth-protected-resource"

            response = Response()
            response.status_code = 401
            response.headers["WWW-Authenticate"] = (
                f'Bearer realm="Frappe Assistant Core", ' f'resource_metadata="{metadata_url}"'
            )
            response.headers["Content-Type"] = "application/json"
            response.data = frappe.as_json({"error": "authentication_error", "message": str(e)})
            return response

    # No valid authentication method found
    frappe.logger().warning("No valid authentication method found in request")
    frappe_url = get_server_url()
    metadata_url = f"{frappe_url}/.well-known/oauth-protected-resource"

    response = Response()
    response.status_code = 401
    response.headers["WWW-Authenticate"] = (
        f'Bearer realm="Frappe Assistant Core", ' f'resource_metadata="{metadata_url}"'
    )
    response.headers["Content-Type"] = "application/json"
    response.data = frappe.as_json({"error": "unauthorized", "message": "Authentication required"})
    return response


@mcp.register(allow_guest=True, xss_safe=True, methods=["GET", "POST", "HEAD"])
def handle_mcp():
    """
    MCP StreamableHTTP endpoint.

    This is the main entry point for all MCP requests. It uses our custom
    MCP server implementation which properly handles JSON serialization.

    Endpoint: /api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp
    Protocol: MCP 2025-03-26 StreamableHTTP

    Supports two authentication methods:
    1. OAuth 2.0 Bearer tokens: "Authorization: Bearer <token>" (for web clients)
    2. API Key/Secret: "Authorization: token <api_key>:<api_secret>" (for STDIO clients)
    """
    from frappe.oauth import get_server_url
    from werkzeug.wrappers import Response

    # Handle HEAD request for connectivity check (Claude Web uses this)
    if frappe.request.method == "HEAD":
        # Return 401 with WWW-Authenticate header to indicate auth is required
        frappe_url = get_server_url()
        metadata_url = f"{frappe_url}/.well-known/oauth-protected-resource"

        response = Response()
        response.status_code = 401
        response.headers["WWW-Authenticate"] = (
            f'Bearer realm="Frappe Assistant Core", ' f'resource_metadata="{metadata_url}"'
        )
        return response

    # Authenticate the request (supports both OAuth and API key)
    auth_result = _authenticate_mcp_request()

    # If authentication failed, auth_result is a Response object with 401
    if isinstance(auth_result, Response):
        return auth_result

    # Authentication successful - auth_result is the username
    authenticated_user = auth_result

    # Check if user has assistant access enabled
    if not _check_assistant_enabled(authenticated_user):
        frappe.throw(
            _("Assistant access is disabled for user {0}").format(authenticated_user), frappe.PermissionError
        )

    # Import tools (they auto-register via decorators)
    _import_tools()

    # Return None to let the decorator continue with MCP handling
    return None
