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
Clean plugin management following Frappe standards.
Replaces the old implementation with thread-safe, production-ready code.
"""

import importlib
import inspect
import json
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import frappe

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.plugins.base_plugin import BasePlugin


class PluginState(Enum):
    """Plugin state enumeration"""

    DISCOVERED = "discovered"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class PluginInfo:
    """Plugin information structure"""

    name: str
    display_name: str
    description: str
    version: str
    state: PluginState
    tools: List[str]
    error_message: Optional[str] = None


@dataclass
class ToolInfo:
    """Tool information structure"""

    name: str
    plugin_name: str
    description: str
    instance: BaseTool


class PluginError(Exception):
    """Base plugin exception"""

    pass


class PluginNotFoundError(PluginError):
    """Plugin not found exception"""

    pass


class PluginValidationError(PluginError):
    """Plugin validation failed exception"""

    pass


class PluginConfig:
    """Plugin system configuration"""

    PLUGIN_BASE_PATH = "frappe_assistant_core.plugins"
    PLUGIN_CONFIG_DOCTYPE = "FAC Plugin Configuration"
    # Legacy - kept for backward compatibility during migration
    PLUGIN_SETTINGS_DOCTYPE = "Assistant Core Settings"
    PLUGIN_SETTINGS_FIELD = "enabled_plugins_list"
    DISCOVERY_PATTERN = "plugin.py"

    @classmethod
    def get_plugins_directory(cls) -> Path:
        """Get plugins directory path"""
        return Path(__file__).parent.parent / "plugins"


class PluginDiscovery:
    """Stateless plugin discovery service"""

    def __init__(self):
        self.logger = frappe.logger("plugin_discovery")

    def discover_plugins(self) -> Dict[str, PluginInfo]:
        """Discover all available plugins"""
        plugins = {}
        plugins_dir = PluginConfig.get_plugins_directory()

        if not plugins_dir.exists():
            self.logger.warning(f"Plugins directory not found: {plugins_dir}")
            return plugins

        for plugin_dir in plugins_dir.iterdir():
            if plugin_dir.is_dir() and not plugin_dir.name.startswith(("_", ".")):
                try:
                    plugin_info = self._discover_plugin(plugin_dir)
                    if plugin_info:
                        plugins[plugin_info.name] = plugin_info
                except Exception as e:
                    self.logger.error(f"Failed to discover plugin {plugin_dir.name}: {e}")
                    plugins[plugin_dir.name] = PluginInfo(
                        name=plugin_dir.name,
                        display_name=plugin_dir.name.title(),
                        description="Failed to load plugin",
                        version="unknown",
                        state=PluginState.ERROR,
                        tools=[],
                        error_message=str(e),
                    )

        return plugins

    def _discover_plugin(self, plugin_dir: Path) -> Optional[PluginInfo]:
        """Discover a single plugin"""
        plugin_file = plugin_dir / PluginConfig.DISCOVERY_PATTERN
        if not plugin_file.exists():
            return None

        # Import plugin module
        module_name = f"{PluginConfig.PLUGIN_BASE_PATH}.{plugin_dir.name}.plugin"
        module = importlib.import_module(module_name)

        # Find plugin class
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, BasePlugin) and attr is not BasePlugin:
                plugin_instance = attr()
                info = plugin_instance.get_info()

                return PluginInfo(
                    name=info["name"],
                    display_name=info.get("display_name", info["name"].title()),
                    description=info.get("description", ""),
                    version=info.get("version", "1.0.0"),
                    state=PluginState.DISCOVERED,
                    tools=plugin_instance.get_tools(),
                )

        return None


class PluginPersistence:
    """Handles plugin state persistence using FAC Plugin Configuration DocType.

    This replaces the old JSON-based approach in Assistant Core Settings with
    individual DocType records for atomic operations and proper caching.
    """

    def __init__(self):
        self.logger = frappe.logger("plugin_persistence")

    def load_enabled_plugins(self) -> Set[str]:
        """Load enabled plugin names from database.

        Uses FAC Plugin Configuration DocType for atomic reads.
        Falls back to legacy JSON field if DocType doesn't exist yet.
        """
        try:
            # Check if the new DocType table exists
            if frappe.db.table_exists("tabFAC Plugin Configuration"):
                # Use the new DocType-based approach (atomic, no JSON parsing)
                enabled = frappe.get_all(
                    PluginConfig.PLUGIN_CONFIG_DOCTYPE,
                    filters={"enabled": 1},
                    pluck="plugin_name",
                )
                return set(enabled)
            else:
                # Fallback to legacy JSON field during migration
                return self._load_from_legacy_json()

        except Exception as e:
            self.logger.error(f"Failed to load enabled plugins: {e}")
            # Fallback to legacy on error
            try:
                return self._load_from_legacy_json()
            except Exception:
                return set()

    def _load_from_legacy_json(self) -> Set[str]:
        """Load from legacy JSON field in Assistant Core Settings."""
        try:
            settings = frappe.get_single(PluginConfig.PLUGIN_SETTINGS_DOCTYPE)
            enabled_list = getattr(settings, PluginConfig.PLUGIN_SETTINGS_FIELD, None)

            if enabled_list:
                return set(json.loads(enabled_list))
            return set()
        except Exception as e:
            self.logger.error(f"Failed to load from legacy JSON: {e}")
            return set()

    def save_plugin_state(self, plugin_name: str, enabled: bool, plugin_info=None) -> bool:
        """Save a single plugin's enabled state.

        Uses atomic DocType update instead of read-modify-write JSON.
        """
        try:
            enabled_int = 1 if enabled else 0

            if frappe.db.exists(PluginConfig.PLUGIN_CONFIG_DOCTYPE, plugin_name):
                # Update existing record
                doc = frappe.get_doc(PluginConfig.PLUGIN_CONFIG_DOCTYPE, plugin_name)
                doc.enabled = enabled_int
                doc.last_toggled_at = frappe.utils.now()
                doc.save(ignore_permissions=True)
            else:
                # Create new record
                doc = frappe.new_doc(PluginConfig.PLUGIN_CONFIG_DOCTYPE)
                doc.plugin_name = plugin_name
                doc.enabled = enabled_int
                doc.discovered_at = frappe.utils.now()
                doc.last_toggled_at = frappe.utils.now()

                # Add plugin info if available
                if plugin_info:
                    doc.display_name = getattr(
                        plugin_info, "display_name", plugin_name.replace("_", " ").title()
                    )
                    doc.description = getattr(plugin_info, "description", "")

                doc.insert(ignore_permissions=True)

            frappe.db.commit()
            return True

        except Exception as e:
            self.logger.error(f"Failed to save plugin state for '{plugin_name}': {e}")
            return False

    def save_enabled_plugins(self, enabled_plugins: Set[str]) -> bool:
        """Save enabled plugin names to database.

        DEPRECATED: Use save_plugin_state() for individual plugin updates.
        This method is kept for backward compatibility.
        """
        try:
            # Also update legacy JSON field for backward compatibility
            settings = frappe.get_single(PluginConfig.PLUGIN_SETTINGS_DOCTYPE)
            setattr(settings, PluginConfig.PLUGIN_SETTINGS_FIELD, json.dumps(list(enabled_plugins)))
            settings.flags.ignore_permissions = True
            settings.save()
            frappe.db.commit()
            return True

        except Exception as e:
            self.logger.error(f"Failed to save enabled plugins (legacy): {e}")
            return False


class PluginManager:
    """
    Central plugin management service with proper state management.
    Thread-safe, transactional operations, clear responsibilities.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._discovered_plugins: Dict[str, PluginInfo] = {}
        self._enabled_plugins: Set[str] = set()
        self._loaded_tools: Dict[str, ToolInfo] = {}
        self._discovery = PluginDiscovery()
        self._persistence = PluginPersistence()
        self.logger = frappe.logger("plugin_manager")

        # Initialize state
        self._initialize()

    def _initialize(self):
        """Initialize the plugin service"""
        with self._lock:
            # Discover available plugins
            self._discovered_plugins = self._discovery.discover_plugins()

            # Load enabled plugins from persistence
            self._enabled_plugins = self._persistence.load_enabled_plugins()

            # Load tools from enabled plugins
            self._load_tools()

            self.logger.info(
                f"Plugin manager initialized: {len(self._discovered_plugins)} discovered, "
                f"{len(self._enabled_plugins)} enabled, {len(self._loaded_tools)} tools loaded"
            )

    def refresh_plugins(self) -> bool:
        """Refresh plugin discovery and reload state"""
        try:
            with self._lock:
                self._initialize()
                return True
        except Exception as e:
            self.logger.error(f"Failed to refresh plugin manager: {e}")
            return False

    def get_discovered_plugins(self) -> List[Dict[str, Any]]:
        """Get all discovered plugins in legacy format for compatibility"""
        with self._lock:
            plugins = []
            for plugin_info in self._discovered_plugins.values():
                plugins.append(
                    {
                        "name": plugin_info.name,
                        "display_name": plugin_info.display_name,
                        "description": plugin_info.description,
                        "version": plugin_info.version,
                        "discovered": True,
                        "can_enable": plugin_info.state != PluginState.ERROR,
                        "validation_error": plugin_info.error_message,
                        "loaded": plugin_info.name in self._enabled_plugins,
                        "tools": plugin_info.tools,
                    }
                )
            return plugins

    def get_enabled_plugins(self) -> Set[str]:
        """Get currently enabled plugin names.

        Always reads from database to ensure consistency across workers.
        """
        with self._lock:
            # Always read from database for cross-worker consistency
            db_enabled = self._persistence.load_enabled_plugins()

            # Update in-memory state if different (another worker may have changed it)
            if db_enabled != self._enabled_plugins:
                self._enabled_plugins = db_enabled
                self._load_tools()

            return self._enabled_plugins.copy()

    def get_all_tools(self) -> Dict[str, ToolInfo]:
        """Get tools from enabled plugins only.

        Ensures state is synced from database for cross-worker consistency.
        """
        with self._lock:
            # Sync state from database (this also reloads tools if needed)
            db_enabled = self._persistence.load_enabled_plugins()
            if db_enabled != self._enabled_plugins:
                self._enabled_plugins = db_enabled
                self._load_tools()

            return self._loaded_tools.copy()

    def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a plugin atomically using DocType-based persistence."""
        with self._lock:
            if plugin_name not in self._discovered_plugins:
                raise PluginNotFoundError(f"Plugin '{plugin_name}' not found")

            plugin_info = self._discovered_plugins[plugin_name]
            if plugin_info.state == PluginState.ERROR:
                raise PluginValidationError(f"Plugin '{plugin_name}' has errors: {plugin_info.error_message}")

            if plugin_name in self._enabled_plugins:
                return True  # Already enabled

            try:
                # Load plugin tools
                plugin_tools = self._load_plugin_tools(plugin_name, plugin_info)

                # Add to enabled set
                self._enabled_plugins.add(plugin_name)

                # Add tools to loaded tools
                self._loaded_tools.update(plugin_tools)

                # Persist state using new atomic method
                if not self._persistence.save_plugin_state(plugin_name, True, plugin_info):
                    raise PluginError("Failed to persist plugin state")

                # Also update legacy JSON for backward compatibility
                self._persistence.save_enabled_plugins(self._enabled_plugins)

                # Update plugin state
                plugin_info.state = PluginState.ENABLED

                self.logger.info(
                    f"Plugin '{plugin_name}' enabled successfully with {len(plugin_tools)} tools"
                )
                return True

            except Exception as e:
                # Rollback on failure
                self._enabled_plugins.discard(plugin_name)
                for tool_name in plugin_info.tools:
                    self._loaded_tools.pop(tool_name, None)

                self.logger.error(f"Failed to enable plugin '{plugin_name}': {e}")
                raise PluginError(f"Failed to enable plugin '{plugin_name}': {e}")

    def disable_plugin(self, plugin_name: str) -> bool:
        """Disable a plugin atomically using DocType-based persistence."""
        with self._lock:
            if plugin_name not in self._enabled_plugins:
                return True  # Already disabled

            try:
                plugin_info = self._discovered_plugins.get(plugin_name)
                if plugin_info:
                    # Remove tools
                    for tool_name in plugin_info.tools:
                        self._loaded_tools.pop(tool_name, None)

                    # Update plugin state
                    plugin_info.state = PluginState.DISABLED

                # Remove from enabled set
                self._enabled_plugins.discard(plugin_name)

                # Persist state using new atomic method
                if not self._persistence.save_plugin_state(plugin_name, False, plugin_info):
                    raise PluginError("Failed to persist plugin state")

                # Also update legacy JSON for backward compatibility
                self._persistence.save_enabled_plugins(self._enabled_plugins)

                self.logger.info(f"Plugin '{plugin_name}' disabled successfully")
                return True

            except Exception as e:
                self.logger.error(f"Failed to disable plugin '{plugin_name}': {e}")
                raise PluginError(f"Failed to disable plugin '{plugin_name}': {e}")

    def _load_tools(self):
        """Load tools from all enabled plugins"""
        self._loaded_tools.clear()

        for plugin_name in self._enabled_plugins:
            plugin_info = self._discovered_plugins.get(plugin_name)
            if plugin_info and plugin_info.state != PluginState.ERROR:
                try:
                    plugin_tools = self._load_plugin_tools(plugin_name, plugin_info)
                    self._loaded_tools.update(plugin_tools)
                except Exception as e:
                    self.logger.error(f"Failed to load tools for plugin '{plugin_name}': {e}")

    def _load_plugin_tools(self, plugin_name: str, plugin_info: PluginInfo) -> Dict[str, ToolInfo]:
        """Load tools for a specific plugin"""
        tools = {}

        for tool_name in plugin_info.tools:
            try:
                # Import tool module
                module_name = f"{PluginConfig.PLUGIN_BASE_PATH}.{plugin_name}.tools.{tool_name}"
                module = importlib.import_module(module_name)

                # Find tool class
                tool_class = None
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if inspect.isclass(attr) and issubclass(attr, BaseTool) and attr is not BaseTool:
                        tool_class = attr
                        break

                if tool_class:
                    tool_instance = tool_class()
                    tool_instance.source_app = "frappe_assistant_core"
                    tool_instance.category = plugin_info.display_name

                    # Validate dependencies
                    deps_valid, deps_error = tool_instance.validate_dependencies()
                    if not deps_valid:
                        self.logger.warning(
                            f"Tool {tool_instance.name} dependency validation failed: {deps_error}"
                        )
                        continue

                    tools[tool_instance.name] = ToolInfo(
                        name=tool_instance.name,
                        plugin_name=plugin_name,
                        description=tool_instance.description,
                        instance=tool_instance,
                    )

            except Exception as e:
                self.logger.error(f"Failed to load tool '{tool_name}' from plugin '{plugin_name}': {e}")

        return tools

    # Legacy compatibility properties
    @property
    def loaded_plugins(self) -> Dict[str, Any]:
        """Legacy compatibility property"""
        return {name: None for name in self._enabled_plugins}

    @property
    def plugin_tools(self) -> Dict[str, List[Any]]:
        """Legacy compatibility property"""
        tools_by_plugin = {}
        for tool_info in self._loaded_tools.values():
            if tool_info.plugin_name not in tools_by_plugin:
                tools_by_plugin[tool_info.plugin_name] = []
            tools_by_plugin[tool_info.plugin_name].append(tool_info.instance)
        return tools_by_plugin


# Global service instance with thread safety
_plugin_manager: Optional[PluginManager] = None
_manager_lock = threading.Lock()


def get_plugin_manager() -> PluginManager:
    """Get or create the global plugin manager instance"""
    global _plugin_manager

    if _plugin_manager is None:
        with _manager_lock:
            if _plugin_manager is None:
                _plugin_manager = PluginManager()

    return _plugin_manager


def refresh_plugin_manager() -> PluginManager:
    """Force refresh the global plugin manager"""
    global _plugin_manager

    with _manager_lock:
        _plugin_manager = None
        return get_plugin_manager()
