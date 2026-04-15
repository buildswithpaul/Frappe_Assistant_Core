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
API endpoints for plugin management.
"""

from typing import Any, Dict

import frappe
from frappe import _


@frappe.whitelist(allow_guest=False)
def get_discovered_plugins():
    """
    Get list of all discovered plugins.

    Returns:
        List of plugin information
    """
    frappe.only_for("System Manager")

    try:
        from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

        plugin_manager = get_plugin_manager()
        plugins = plugin_manager.get_discovered_plugins()

        return {"success": True, "plugins": plugins}

    except Exception as e:
        frappe.log_error(title=_("Plugin Discovery Error"), message=str(e))
        frappe.throw(_("Failed to get plugins: {0}").format(str(e)))


@frappe.whitelist(allow_guest=False)
def refresh_plugins():
    """
    Refresh plugin discovery.

    Returns:
        Success status and plugin count
    """
    frappe.only_for("System Manager")

    try:
        from frappe_assistant_core.utils.plugin_manager import refresh_plugin_manager

        # Refresh plugin manager
        plugin_manager = refresh_plugin_manager()
        plugins = plugin_manager.get_discovered_plugins()

        return {
            "success": True,
            "message": _("Plugin discovery completed"),
            "plugin_count": len(plugins),
            "plugins": plugins,
        }

    except Exception as e:
        frappe.log_error(title=_("Plugin Refresh Error"), message=str(e))
        frappe.throw(_("Failed to refresh plugins: {0}").format(str(e)))


@frappe.whitelist(allow_guest=False)
def get_plugin_info(plugin_name: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific plugin.

    Args:
        plugin_name: Name of the plugin

    Returns:
        Plugin information
    """
    frappe.only_for("System Manager")

    try:
        from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

        plugin_manager = get_plugin_manager()
        plugin_info = plugin_manager.get_plugin_info(plugin_name)

        if not plugin_info:
            frappe.throw(_("Plugin '{0}' not found").format(plugin_name))

        return {"success": True, "plugin": plugin_info}

    except Exception as e:
        frappe.log_error(title=_("Plugin Info Error"), message=str(e))
        frappe.throw(_("Failed to get plugin info: {0}").format(str(e)))


@frappe.whitelist(allow_guest=False)
def get_available_tools():
    """
    Get list of all available tools from core and plugins.

    Returns:
        List of tools with metadata
    """
    try:
        from frappe_assistant_core.core.tool_registry import get_tool_registry

        registry = get_tool_registry()
        tools = registry.get_available_tools()
        stats = registry.get_stats()

        return {"success": True, "tools": tools, "stats": stats}

    except Exception as e:
        frappe.log_error(title=_("Tool Registry Error"), message=str(e))
        frappe.throw(_("Failed to get tools: {0}").format(str(e)))


@frappe.whitelist(allow_guest=False)
def refresh_tool_registry():
    """
    Refresh the tool registry.

    Returns:
        Success status and tool count
    """
    frappe.only_for("System Manager")

    try:
        from frappe_assistant_core.core.tool_registry import refresh_tool_registry

        registry = refresh_tool_registry()
        stats = registry.get_stats()

        return {"success": True, "message": _("Tool registry refreshed"), "stats": stats}

    except Exception as e:
        frappe.log_error(title=_("Tool Registry Refresh Error"), message=str(e))
        frappe.throw(_("Failed to refresh tool registry: {0}").format(str(e)))
