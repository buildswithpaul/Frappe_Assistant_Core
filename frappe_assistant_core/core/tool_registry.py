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
Clean tool registry that provides a simple interface to the plugin manager.
Replaces the old wrapper with direct delegation to the plugin manager.
"""

from typing import Any, Dict, List, Optional

import frappe

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.utils.plugin_manager import ToolInfo, get_plugin_manager


class ToolRegistry:
    """
    Simple tool registry that delegates to the plugin manager.
    Provides clean interface for tool access without workarounds.
    """

    def __init__(self):
        self.logger = frappe.logger("tool_registry")

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Get a tool by name"""
        plugin_manager = get_plugin_manager()
        tools = plugin_manager.get_all_tools()

        # Check plugin tools first
        tool_info = tools.get(tool_name)
        if tool_info:
            return tool_info.instance

        # Check external tools
        external_tools = self._get_external_tools()
        external_tool_info = external_tools.get(tool_name)
        return external_tool_info.instance if external_tool_info else None

    def get_available_tools(self, user: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of available tools for user with permission checking.

        Args:
            user: Username to check permissions for

        Returns:
            List of tools in MCP format
        """
        plugin_manager = get_plugin_manager()
        tools = plugin_manager.get_all_tools()

        # Add external tools from hooks
        external_tools = self._get_external_tools()
        tools.update(external_tools)

        available_tools = []
        for tool_info in tools.values():
            try:
                # Check tool permissions for current user
                if self._check_tool_permission(tool_info.instance, user or frappe.session.user):
                    available_tools.append(tool_info.instance.get_metadata())
            except Exception as e:
                self.logger.warning(f"Failed to get metadata for tool {tool_info.name}: {e}")

        return available_tools

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool with given arguments"""
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found")

        # Check permissions
        if not self._check_tool_permission(tool, frappe.session.user):
            raise PermissionError(f"Permission denied for tool '{tool_name}'")

        # Use _safe_execute to ensure audit logging, timing, and error handling
        result = tool._safe_execute(arguments)

        # For tools that return the new format with success/error info, extract the result
        if isinstance(result, dict) and "success" in result:
            if result.get("success"):
                return result.get("result", result)
            else:
                # Raise appropriate exception based on error type
                error_type = result.get("error_type", "ExecutionError")
                error_message = result.get("error", "Tool execution failed")

                if error_type == "PermissionError":
                    raise PermissionError(error_message)
                elif error_type == "ValidationError":
                    raise frappe.ValidationError(error_message)
                elif error_type == "DependencyError":
                    raise Exception(f"Dependency error: {error_message}")
                else:
                    # Include error type and execution time in the message for better debugging
                    execution_time = result.get("execution_time", "unknown")
                    raise Exception(f"[{error_type}] {error_message} (execution_time: {execution_time}s)")

        return result

    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available"""
        tool = self.get_tool(tool_name)
        return tool is not None

    def refresh_tools(self) -> bool:
        """Refresh tool discovery"""
        plugin_manager = get_plugin_manager()
        return plugin_manager.refresh_plugins()

    def get_stats(self) -> Dict[str, Any]:
        """Get tool registry statistics"""
        plugin_manager = get_plugin_manager()
        all_tools = plugin_manager.get_all_tools()

        core_tools = []
        plugin_tools = []

        for tool_info in all_tools.values():
            if tool_info.plugin_name == "core":
                core_tools.append(tool_info.name)
            else:
                plugin_tools.append(tool_info.name)

        return {
            "total_tools": len(all_tools),
            "core_tools": len(core_tools),
            "plugin_tools": len(plugin_tools),
            "core_tool_names": core_tools,
            "plugin_tool_names": plugin_tools,
        }

    def refresh(self) -> bool:
        """Refresh tool registry"""
        return self.refresh_tools()

    def _get_external_tools(self) -> Dict[str, Any]:
        """Get external tools from hooks safely"""
        external_tools = {}

        try:
            # Only try to load external tools if frappe is properly initialized
            if not hasattr(frappe, "get_hooks") or not hasattr(frappe, "local"):
                return external_tools

            # Check if custom_tools plugin is enabled
            plugin_manager = get_plugin_manager()
            enabled_plugins = plugin_manager.get_enabled_plugins()

            if "custom_tools" not in enabled_plugins:
                self.logger.debug("custom_tools plugin is disabled, skipping external tool discovery")
                return external_tools

            # Get assistant_tools from hooks
            assistant_tools = frappe.get_hooks("assistant_tools") or []

            for tool_path in assistant_tools:
                try:
                    # Import the tool class
                    module_path, class_name = tool_path.rsplit(".", 1)
                    import importlib

                    module = importlib.import_module(module_path)
                    tool_class = getattr(module, class_name)

                    # Validate it's a BaseTool subclass
                    if hasattr(tool_class, "__bases__") and issubclass(tool_class, BaseTool):
                        tool_instance = tool_class()

                        # Create a ToolInfo-like object
                        from frappe_assistant_core.utils.plugin_manager import ToolInfo

                        tool_info = ToolInfo(
                            name=tool_instance.name,
                            plugin_name="external",
                            description=tool_instance.description,
                            instance=tool_instance,
                        )

                        external_tools[tool_instance.name] = tool_info

                        self.logger.info(
                            f"Loaded external tool '{tool_instance.name}' from {tool_instance.source_app}"
                        )

                except Exception as e:
                    self.logger.debug(f"Failed to load external tool from '{tool_path}': {e}")

        except Exception as e:
            self.logger.debug(f"Error loading external tools: {e}")

        return external_tools

    def _check_tool_permission(self, tool_instance: BaseTool, user: str) -> bool:
        """Check if user has permission to use the tool"""
        try:
            if tool_instance.requires_permission:
                tool_instance.check_permission()
            return True
        except Exception as e:
            self.logger.debug(f"Permission check failed for tool {tool_instance.name} and user {user}: {e}")
            return False


# Global registry instance
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get or create global tool registry instance"""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry
