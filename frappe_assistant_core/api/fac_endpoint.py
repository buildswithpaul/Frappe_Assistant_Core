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

# Create MCP server instance
mcp = MCPServer("frappe-assistant-core")


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


@mcp.register(allow_guest=False, xss_safe=True)
def handle_mcp():
    """
    MCP StreamableHTTP endpoint.

    This is the main entry point for all MCP requests. It uses our custom
    MCP server implementation which properly handles JSON serialization.

    Endpoint: /api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp
    Protocol: MCP 2025-03-26 StreamableHTTP
    """
    # Check if user has assistant access enabled
    if not _check_assistant_enabled(frappe.session.user):
        frappe.throw(f"Assistant access is disabled for user {frappe.session.user}", frappe.PermissionError)

    # Import tools (they auto-register via decorators)
    _import_tools()

    # The response is already handled by the @mcp.register decorator
    # which calls mcp.handle() internally
