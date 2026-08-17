"""
Enhanced Base Plugin Class

Extended version of BasePlugin with advanced features:
- Plugin lifecycle management
- Dependency injection
- Configuration management
- Health monitoring
- Tool discovery and registration
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import frappe
from frappe import _

from frappe_assistant_core.plugins.base_plugin import BasePlugin
from frappe_assistant_core.core.base_tool import BaseTool
from .constants import DEFAULT_CONFIG


class EnhancedBasePlugin(BasePlugin):
    """
    Enhanced base plugin with lifecycle management and configuration.
    
    Features:
    - Plugin lifecycle hooks (on_enable, on_disable, on_health_check)
    - Configuration management
    - Dependency tracking
    - Tool discovery and registration
    - Health monitoring
    - Error recovery
    """

    def __init__(self):
        super().__init__()
        self.is_enabled = False
        self.is_healthy = True
        self.health_check_time = None
        self.last_error = None
        self.configuration = {}
        self.discovered_tools = []
        self.initialized_at = None

    def initialize(self) -> Tuple[bool, Optional[str]]:
        """Initialize plugin with full lifecycle."""
        try:
            info = self.get_info()
            frappe.logger().info(f"Initializing plugin: {info['name']}")

            self.configuration = self._load_configuration()

            is_valid, error = self.validate_environment()
            if not is_valid:
                self.last_error = error
                return False, error

            tool_list = self.get_tools()
            self.discovered_tools = tool_list
            frappe.logger().info(
                f"Discovered {len(tool_list)} tools in {info['name']}"
            )

            self.on_enable()

            self.is_enabled = True
            self.initialized_at = datetime.now()
            self.last_error = None

            frappe.logger().info(f"Plugin {info['name']} initialized successfully")
            return True, None

        except Exception as e:
            error_message = str(e)
            self.last_error = error_message
            frappe.log_error(
                title=_(f"Plugin Initialization Error"),
                message=f"{self.get_info()['name']}: {error_message}",
            )
            return False, error_message

    def shutdown(self) -> Tuple[bool, Optional[str]]:
        """Shutdown plugin gracefully."""
        try:
            frappe.logger().info(f"Shutting down plugin: {self.get_info()['name']}")
            self.on_disable()
            self.is_enabled = False
            return True, None
        except Exception as e:
            error_message = str(e)
            self.last_error = error_message
            return False, error_message

    def on_enable(self) -> None:
        """Called when plugin is enabled."""
        pass

    def on_disable(self) -> None:
        """Called when plugin is disabled."""
        pass

    def on_server_start(self) -> None:
        """Called when Frappe server starts."""
        pass

    def on_server_stop(self) -> None:
        """Called when Frappe server stops."""
        pass

    def on_health_check(self) -> Dict[str, Any]:
        """Called during health checks."""
        return {
            "status": "healthy" if self.is_healthy else "unhealthy",
            "timestamp": datetime.now().isoformat(),
        }

    def _load_configuration(self) -> Dict[str, Any]:
        """Load plugin configuration from multiple sources."""
        config = DEFAULT_CONFIG.copy()

        try:
            plugin_info = self.get_info()
            plugin_name = plugin_info["name"]

            site_config = frappe.get_value(
                "Assistant Core Settings",
                filters={"name": plugin_name},
                fieldname=["configuration"],
            )
            if site_config:
                import json
                plugin_config = json.loads(site_config[0])
                config.update(plugin_config)
        except Exception as e:
            frappe.logger().warning(f"Failed to load plugin configuration: {e}")

        return config

    def get_config(self, key: Optional[str] = None, default: Any = None) -> Any:
        """Get configuration value."""
        if key is None:
            return self.configuration
        return self.configuration.get(key, default)

    def set_config(self, key: str, value: Any) -> None:
        """Set configuration value."""
        self.configuration[key] = value
        frappe.logger().debug(f"Plugin config updated: {key} = {value}")

    def register_tool(self, tool_class: type) -> Optional[BaseTool]:
        """Register and instantiate a tool."""
        try:
            if not issubclass(tool_class, BaseTool):
                raise TypeError(f"{tool_class} is not a BaseTool subclass")

            tool = tool_class()
            frappe.logger().debug(f"Registered tool: {tool.name}")
            return tool
        except Exception as e:
            frappe.logger().error(f"Failed to register tool {tool_class}: {e}")
            return None

    def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        try:
            plugin_info = self.get_info()
            
            deps_ok = True
            missing_deps = []
            for dep in plugin_info.get("dependencies", []):
                try:
                    __import__(dep)
                except ImportError:
                    deps_ok = False
                    missing_deps.append(dep)

            custom_health = self.on_health_check()

            health_status = {
                "plugin": plugin_info["name"],
                "status": "healthy" if deps_ok and self.is_healthy else "unhealthy",
                "enabled": self.is_enabled,
                "dependencies": {
                    "ok": deps_ok,
                    "missing": missing_deps,
                },
                "tools_count": len(self.get_tools()),
                "last_error": self.last_error,
                "initialized_at": (
                    self.initialized_at.isoformat()
                    if self.initialized_at
                    else None
                ),
                "health_check_time": datetime.now().isoformat(),
                **custom_health,
            }

            self.health_check_time = datetime.now()
            return health_status

        except Exception as e:
            frappe.logger().error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "health_check_time": datetime.now().isoformat(),
            }

    def get_status(self) -> Dict[str, Any]:
        """Get current plugin status."""
        plugin_info = self.get_info()
        return {
            "name": plugin_info["name"],
            "display_name": plugin_info["display_name"],
            "version": plugin_info["version"],
            "enabled": self.is_enabled,
            "healthy": self.is_healthy,
            "tools_count": len(self.get_tools()),
            "initialized_at": (
                self.initialized_at.isoformat()
                if self.initialized_at
                else None
            ),
            "last_error": self.last_error,
        }
