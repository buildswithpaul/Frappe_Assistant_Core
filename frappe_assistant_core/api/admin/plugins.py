# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0-or-later — see <https://www.gnu.org/licenses/>.

import frappe
from frappe import _


@frappe.whitelist()
def get_tool_registry() -> dict:
    """Fetch assistant Tool Registry with detailed information."""
    frappe.only_for(["System Manager", "Assistant Admin"])
    from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

    try:
        plugin_manager = get_plugin_manager()
        tools = plugin_manager.get_all_tools()
        enabled_plugins = plugin_manager.get_enabled_plugins()

        formatted_tools = []
        for tool_name, tool_info in tools.items():
            formatted_tools.append(
                {
                    "name": tool_name.replace("_", " ").title(),
                    "category": tool_info.plugin_name.replace("_", " ").title(),
                    "category_id": tool_info.plugin_name,
                    "description": tool_info.description,
                    "enabled": tool_info.plugin_name in enabled_plugins,
                }
            )

        formatted_tools.sort(key=lambda x: (x["category"], x["name"]))

        return {"tools": formatted_tools}
    except Exception as e:
        frappe.log_error(f"Failed to get tool registry: {str(e)}")
        return {"tools": []}


@frappe.whitelist()
def get_plugin_stats() -> dict:
    """Get plugin statistics for admin dashboard."""
    frappe.only_for(["System Manager", "Assistant Admin"])
    from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

    try:
        plugin_manager = get_plugin_manager()
        discovered = plugin_manager.get_discovered_plugins()
        enabled = plugin_manager.get_enabled_plugins()

        plugins = []
        for plugin in discovered:
            plugins.append(
                {
                    "name": plugin["display_name"],
                    "plugin_id": plugin["name"],
                    "enabled": plugin["name"] in enabled,
                }
            )

        return {"enabled_count": len(enabled), "total_count": len(discovered), "plugins": plugins}
    except Exception as e:
        frappe.log_error(f"Failed to get plugin stats: {str(e)}")
        return {"enabled_count": 0, "total_count": 0, "plugins": []}


@frappe.whitelist()
def get_tool_stats() -> dict:
    """Get tool statistics for admin dashboard."""
    frappe.only_for(["System Manager", "Assistant Admin"])
    from frappe_assistant_core.core.tool_registry import get_tool_registry
    from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

    try:
        plugin_manager = get_plugin_manager()
        tool_registry = get_tool_registry()

        tools = plugin_manager.get_all_tools()

        external_tools = tool_registry._get_external_tools()
        tools.update(external_tools)

        categories = {}
        for _tool_name, tool_info in tools.items():
            category = tool_info.plugin_name
            categories[category] = categories.get(category, 0) + 1

        return {"total_tools": len(tools), "categories": categories}
    except Exception as e:
        frappe.log_error(f"Failed to get tool stats: {str(e)}")
        return {"total_tools": 0, "categories": {}}


@frappe.whitelist(methods=["POST"])
def toggle_plugin(plugin_name: str, enable: bool):
    """Enable or disable a plugin.

    Uses atomic DocType updates via FAC Plugin Configuration for
    reliable state persistence across Gunicorn workers.
    """
    frappe.only_for(["System Manager", "Assistant Admin"])
    from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

    try:
        plugin_manager = get_plugin_manager()

        if enable:
            plugin_manager.enable_plugin(plugin_name)
            message = f"Plugin '{plugin_name}' enabled successfully"
        else:
            plugin_manager.disable_plugin(plugin_name)
            message = f"Plugin '{plugin_name}' disabled successfully"

        cache = frappe.cache()
        cache.delete_keys("plugin_*")
        cache.delete_keys("tool_registry_*")
        cache.delete_keys("fac_plugin_*")

        frappe.clear_document_cache("FAC Plugin Configuration", plugin_name)
        frappe.clear_document_cache("Assistant Core Settings", "Assistant Core Settings")

        plugin_manager.refresh_plugins()

        return {"success": True, "message": _(message)}
    except Exception as e:
        frappe.log_error(f"Failed to toggle plugin '{plugin_name}': {str(e)}")
        return {"success": False, "message": _(f"Error: {str(e)}")}
