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


@mcp.register(allow_guest=True, xss_safe=True)
def handle_mcp():
    """
    MCP StreamableHTTP endpoint.

    This is the main entry point for all MCP requests. It uses our custom
    MCP server implementation which properly handles JSON serialization.

    Endpoint: /api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp
    Protocol: MCP 2025-03-26 StreamableHTTP

    Implements OAuth 2.0 Protected Resource (RFC 9728) with proper 401 responses.
    """
    from frappe.oauth import get_server_url
    from werkzeug.wrappers import Response

    # Check for Bearer token in Authorization header
    auth_header = frappe.request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        # Return 401 with WWW-Authenticate header per RFC 9728
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

    # Validate OAuth token
    token = auth_header[7:]  # Remove "Bearer " prefix
    try:
        # Validate token using Frappe's OAuth Bearer Token doctype
        bearer_token = frappe.get_doc("OAuth Bearer Token", {"access_token": token})

        # Check if token is active
        if bearer_token.status != "Active":
            raise frappe.AuthenticationError("Token is not active")

        # Check if token has expired
        import datetime

        if bearer_token.expiration_time < datetime.datetime.now():
            raise frappe.AuthenticationError("Token has expired")

        # Set the user session
        frappe.set_user(bearer_token.user)

    except frappe.DoesNotExistError:
        # Token not found
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
        # Return 401 for invalid/expired tokens per MCP spec
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

    # Check if user has assistant access enabled
    if not _check_assistant_enabled(frappe.session.user):
        frappe.throw(f"Assistant access is disabled for user {frappe.session.user}", frappe.PermissionError)

    # Import tools (they auto-register via decorators)
    _import_tools()

    # Return None to let the decorator continue with MCP handling
    return None
