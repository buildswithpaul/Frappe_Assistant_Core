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
    """Import and register all tools from plugins directory."""
    try:
        # Import the tool registry (has all existing BaseTool instances)
        from frappe_assistant_core.core.tool_registry import get_tool_registry
        from frappe_assistant_core.mcp.tool_adapter import register_base_tool

        # Get all registered tools
        registry = get_tool_registry()

        # Register each tool with our MCP server
        for tool_name in registry._tools.keys():
            tool_instance = registry.get_tool(tool_name)
            if tool_instance:
                register_base_tool(mcp, tool_instance)

        frappe.logger().info(f"Registered {len(mcp._tool_registry)} tools with MCP server")

    except Exception as e:
        frappe.log_error(title="Tool Import Error", message=f"Error importing tools: {str(e)}")


@mcp.register(allow_guest=False, xss_safe=True)
def handle_mcp():
    """
    MCP StreamableHTTP endpoint.

    This is the main entry point for all MCP requests. It uses our custom
    MCP server implementation which properly handles JSON serialization.

    Endpoint: /api/method/frappe_assistant_core.api.mcp_endpoint.handle_mcp
    Protocol: MCP 2025-03-26 StreamableHTTP
    """
    # Check if user has assistant access enabled
    if not _check_assistant_enabled(frappe.session.user):
        frappe.throw(f"Assistant access is disabled for user {frappe.session.user}", frappe.PermissionError)

    # Import tools (they auto-register via decorators)
    _import_tools()
