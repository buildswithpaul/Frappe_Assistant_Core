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

Now includes filtering based on:
- FAC Tool Configuration (individual tool enable/disable)
- Role-based access control
"""

from typing import Any, Dict, List, Optional

import frappe

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.utils.plugin_manager import ToolInfo, get_plugin_manager


class ToolRegistry:
    """
    Tool registry that delegates to the plugin manager and applies filtering.

    Filtering is applied based on:
    1. Plugin enable/disable status (from plugin manager)
    2. Individual tool enable/disable (from FAC Tool Configuration)
    3. Role-based access control (from FAC Tool Configuration)
    """

    def __init__(self):
        self.logger = frappe.logger("tool_registry")
        # Cache for tool configurations - cleared when configs change
        self._tool_config_cache: Optional[Dict[str, Any]] = None
        self._cache_key = "fac_tool_registry_configs"

    def _get_tool_configurations(self) -> Dict[str, Any]:
        """
        Get all tool configurations from cache or database.

        Returns:
            Dict mapping tool_name to configuration dict
        """
        # Try to get from cache first
        cached = frappe.cache.get_value(self._cache_key)
        if cached is not None:
            return cached

        configs = {}

        try:
            # Check if the DocType table exists
            if not frappe.db.table_exists("FAC Tool Configuration"):
                self.logger.debug("FAC Tool Configuration table does not exist yet")
                return configs

            # Fetch all tool configurations
            tool_configs = frappe.get_all(
                "FAC Tool Configuration",
                fields=[
                    "name",
                    "tool_name",
                    "plugin_name",
                    "enabled",
                    "tool_category",
                    "role_access_mode",
                ],
            )

            for config in tool_configs:
                tool_name = config.get("tool_name") or config.get("name")

                # Get role access settings for this tool
                role_access = []
                try:
                    role_access = frappe.get_all(
                        "FAC Tool Role Access",
                        filters={"parent": config.get("name")},
                        fields=["role", "allow_access"],
                    )
                except Exception:
                    pass  # Table might not exist or no role access configured

                configs[tool_name] = {
                    "enabled": config.get("enabled", 1),
                    "plugin_name": config.get("plugin_name"),
                    "tool_category": config.get("tool_category", "read_write"),
                    "role_access_mode": config.get("role_access_mode", "Allow All"),
                    "role_access": role_access,
                }

            # Cache for 60 seconds
            frappe.cache.set_value(self._cache_key, configs, expires_in_sec=60)

        except Exception as e:
            self.logger.warning(f"Failed to load tool configurations: {e}")

        return configs

    def _is_tool_enabled(self, tool_name: str) -> bool:
        """
        Check if a tool is enabled in FAC Tool Configuration.

        Args:
            tool_name: Name of the tool

        Returns:
            True if enabled or no configuration exists (default enabled)
        """
        configs = self._get_tool_configurations()

        if tool_name not in configs:
            # No configuration = enabled by default
            return True

        return bool(configs[tool_name].get("enabled", 1))

    def _check_role_access(self, tool_name: str, user: str) -> bool:
        """
        Check if user has role-based access to the tool.

        Args:
            tool_name: Name of the tool
            user: Username to check

        Returns:
            True if user has access, False otherwise
        """
        configs = self._get_tool_configurations()

        if tool_name not in configs:
            # No configuration = allow access by default
            return True

        config = configs[tool_name]
        role_access_mode = config.get("role_access_mode", "Allow All")

        # If mode is "Allow All", everyone has access
        if role_access_mode == "Allow All":
            return True

        # Get user's roles
        user_roles = set(frappe.get_roles(user))

        # System Manager always has access
        if "System Manager" in user_roles:
            return True

        # Check role access list
        role_access = config.get("role_access", [])
        for access in role_access:
            if access.get("role") in user_roles and access.get("allow_access"):
                return True

        # No matching role found
        return False

    def _is_tool_accessible(self, tool_name: str, user: str) -> bool:
        """
        Check if a tool is accessible to a user.

        Combines:
        1. Tool enabled status
        2. Role-based access control

        Args:
            tool_name: Name of the tool
            user: Username to check

        Returns:
            True if tool is accessible, False otherwise
        """
        # Check if tool is enabled
        if not self._is_tool_enabled(tool_name):
            self.logger.debug(f"Tool '{tool_name}' is disabled")
            return False

        # Check role-based access
        if not self._check_role_access(tool_name, user):
            self.logger.debug(f"User '{user}' does not have role access to tool '{tool_name}'")
            return False

        return True

    def clear_cache(self):
        """Clear the tool configuration cache."""
        frappe.cache.delete_value(self._cache_key)
        self._tool_config_cache = None

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

        Filtering order:
        1. Plugin-level: Only tools from enabled plugins (handled by plugin_manager)
        2. Tool-level: Only enabled tools (from FAC Tool Configuration)
        3. Role-level: Only tools user has role access to
        4. Permission-level: Only tools user has Frappe permission for

        Args:
            user: Username to check permissions for

        Returns:
            List of tools in MCP format
        """
        effective_user = user or frappe.session.user
        plugin_manager = get_plugin_manager()

        # Step 1: Get tools from enabled plugins
        tools = plugin_manager.get_all_tools()

        # Add external tools from hooks
        external_tools = self._get_external_tools()
        tools.update(external_tools)

        available_tools = []
        for tool_info in tools.values():
            try:
                tool_name = tool_info.name

                # Step 2 & 3: Check FAC Tool Configuration (enabled + role access)
                if not self._is_tool_accessible(tool_name, effective_user):
                    continue

                # Step 4: Check Frappe permissions for the tool
                if not self._check_tool_permission(tool_info.instance, effective_user):
                    continue

                available_tools.append(tool_info.instance.get_metadata())

            except Exception as e:
                self.logger.warning(f"Failed to get metadata for tool {tool_info.name}: {e}")

        return available_tools

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool with given arguments"""
        user = frappe.session.user

        # Check FAC Tool Configuration (enabled + role access) first
        if not self._is_tool_accessible(tool_name, user):
            raise PermissionError(f"Tool '{tool_name}' is not accessible")

        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found")

        # Check Frappe permissions
        if not self._check_tool_permission(tool, user):
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
        """Get tool registry statistics including configuration status"""
        plugin_manager = get_plugin_manager()
        all_tools = plugin_manager.get_all_tools()
        configs = self._get_tool_configurations()

        core_tools = []
        plugin_tools = []
        enabled_tools = []
        disabled_tools = []
        category_counts = {
            "read_only": 0,
            "write": 0,
            "read_write": 0,
            "privileged": 0,
        }

        for tool_info in all_tools.values():
            tool_name = tool_info.name

            if tool_info.plugin_name == "core":
                core_tools.append(tool_name)
            else:
                plugin_tools.append(tool_name)

            # Check configuration status
            if tool_name in configs:
                config = configs[tool_name]
                if config.get("enabled", 1):
                    enabled_tools.append(tool_name)
                else:
                    disabled_tools.append(tool_name)

                # Count categories
                category = config.get("tool_category", "read_write")
                if category in category_counts:
                    category_counts[category] += 1
            else:
                # No config = enabled by default
                enabled_tools.append(tool_name)
                category_counts["read_write"] += 1

        return {
            "total_tools": len(all_tools),
            "core_tools": len(core_tools),
            "plugin_tools": len(plugin_tools),
            "core_tool_names": core_tools,
            "plugin_tool_names": plugin_tools,
            "enabled_tools": len(enabled_tools),
            "disabled_tools": len(disabled_tools),
            "enabled_tool_names": enabled_tools,
            "disabled_tool_names": disabled_tools,
            "categories": category_counts,
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
                            plugin_name="custom_tools",  # Use actual plugin name for proper enable/disable tracking
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
