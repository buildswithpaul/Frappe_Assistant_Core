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
Tool Adapter for BaseTool Compatibility

Allows existing BaseTool-based tools to work with the new MCP server
without rewriting them. This is a compatibility layer.
"""

from typing import Any, Dict


def register_base_tool(mcp_server, tool_instance):
    """
    Register a BaseTool instance with the MCP server.

    This adapter allows existing tools that inherit from BaseTool
    to work with our new MCP server without modification.

    Args:
        mcp_server: MCPServer instance
        tool_instance: Instance of BaseTool or compatible class

    Example:
        ```python
        from frappe_assistant_core.plugins.core.tools.list_documents import DocumentList
        from frappe_assistant_core.api.mcp_endpoint import mcp

        # Register existing tool
        register_base_tool(mcp, DocumentList())
        ```
    """

    # Create wrapper function that calls tool's execute method
    def tool_wrapper(**arguments):
        """Wrapper that calls BaseTool.execute()"""
        return tool_instance._safe_execute(arguments)

    # Register with MCP server
    mcp_server.add_tool(
        {
            "name": tool_instance.name,
            "description": tool_instance.description,
            "inputSchema": tool_instance.inputSchema,
            "annotations": getattr(tool_instance, "annotations", None),
            "fn": tool_wrapper,
        }
    )


def register_all_base_tools(mcp_server, tool_instances):
    """
    Register multiple BaseTool instances.

    Args:
        mcp_server: MCPServer instance
        tool_instances: List of BaseTool instances
    """
    for tool in tool_instances:
        register_base_tool(mcp_server, tool)
