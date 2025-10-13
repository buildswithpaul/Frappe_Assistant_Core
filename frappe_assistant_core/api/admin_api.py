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

import frappe
from frappe import _


@frappe.whitelist()
def get_server_settings():
    """Fetch assistant Server Settings with caching."""
    from frappe_assistant_core.utils.cache import get_cached_server_settings

    return get_cached_server_settings()


@frappe.whitelist()
def update_server_settings(**kwargs):
    """Update Assistant Core Settings."""
    settings = frappe.get_single("Assistant Core Settings")

    # Update only the fields that are provided
    updated = False
    for field in [
        "server_enabled",
        "enforce_artifact_streaming",
        "response_limit_prevention",
        "streaming_line_threshold",
        "streaming_char_threshold",
    ]:
        if field in kwargs:
            setattr(settings, field, kwargs[field])
            updated = True

    if updated:
        settings.save()

        # Clear ALL caches using wildcard pattern to catch redis_cache decorated functions
        cache = frappe.cache()
        cache.delete_keys("*get_cached_server_settings*")
        cache.delete_keys("assistant_*")

        # Clear document cache
        frappe.clear_document_cache("Assistant Core Settings", "Assistant Core Settings")

        # Force frappe to clear its internal caches
        frappe.clear_cache(doctype="Assistant Core Settings")

    return {"message": _("Assistant Core Settings updated successfully.")}


@frappe.whitelist()
def get_tool_registry():
    """Fetch assistant Tool Registry with detailed information."""
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
                    "category_id": tool_info.plugin_name,  # Add actual plugin ID for toggling
                    "description": tool_info.description,
                    "enabled": tool_info.plugin_name in enabled_plugins,
                }
            )

        # Sort by category and then by name
        formatted_tools.sort(key=lambda x: (x["category"], x["name"]))

        return {"tools": formatted_tools}
    except Exception as e:
        frappe.log_error(f"Failed to get tool registry: {str(e)}")
        return {"tools": []}


@frappe.whitelist()
def get_plugin_stats():
    """Get plugin statistics for admin dashboard."""
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
                    "plugin_id": plugin["name"],  # Add actual plugin ID for toggling
                    "enabled": plugin["name"] in enabled,
                }
            )

        return {"enabled_count": len(enabled), "total_count": len(discovered), "plugins": plugins}
    except Exception as e:
        frappe.log_error(f"Failed to get plugin stats: {str(e)}")
        return {"enabled_count": 0, "total_count": 0, "plugins": []}


@frappe.whitelist()
def get_tool_stats():
    """Get tool statistics for admin dashboard."""
    from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

    try:
        plugin_manager = get_plugin_manager()
        tools = plugin_manager.get_all_tools()

        categories = {}
        for _tool_name, tool_info in tools.items():
            category = tool_info.plugin_name
            categories[category] = categories.get(category, 0) + 1

        return {"total_tools": len(tools), "categories": categories}
    except Exception as e:
        frappe.log_error(f"Failed to get tool stats: {str(e)}")
        return {"total_tools": 0, "categories": {}}


@frappe.whitelist()
def toggle_plugin(plugin_name: str, enable: bool):
    """Enable or disable a plugin."""
    from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

    try:
        plugin_manager = get_plugin_manager()

        if enable:
            plugin_manager.enable_plugin(plugin_name)
            message = f"Plugin '{plugin_name}' enabled successfully"
        else:
            plugin_manager.disable_plugin(plugin_name)
            message = f"Plugin '{plugin_name}' disabled successfully"

        return {"success": True, "message": _(message)}
    except Exception as e:
        frappe.log_error(f"Failed to toggle plugin '{plugin_name}': {str(e)}")
        return {"success": False, "message": _(f"Error: {str(e)}")}


@frappe.whitelist(methods=["GET", "POST"])
def get_usage_statistics():
    """Get usage statistics for the assistant."""
    from frappe_assistant_core.utils.logger import api_logger
    from frappe_assistant_core.utils.permissions import check_assistant_permission

    try:
        if not check_assistant_permission(frappe.session.user):
            frappe.throw(_("Access denied - insufficient permissions"))

        api_logger.info(f"Usage statistics requested by user: {frappe.session.user}")

        today = frappe.utils.today()
        week_start = frappe.utils.add_days(today, -7)

        # Audit log statistics
        try:
            total_audit = frappe.db.count("Assistant Audit Log") or 0
            today_audit = frappe.db.count("Assistant Audit Log", {"creation": (">=", today)}) or 0
            week_audit = frappe.db.count("Assistant Audit Log", {"creation": (">=", week_start)}) or 0
        except Exception as e:
            api_logger.warning(f"Audit stats error: {e}")
            total_audit = today_audit = week_audit = 0

        # Tool statistics
        try:
            from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

            plugin_manager = get_plugin_manager()
            all_tools = plugin_manager.get_all_tools()
            total_tools = len(all_tools)
            enabled_tools = len(all_tools)
            api_logger.debug(f"Tool stats: total={total_tools}, enabled={enabled_tools}")
        except Exception as e:
            api_logger.warning(f"Tool stats error: {e}")
            total_tools = enabled_tools = 0

        # Recent activity
        try:
            recent_activity = (
                frappe.db.get_list(
                    "Assistant Audit Log",
                    fields=["action", "tool_name", "user", "status", "timestamp"],
                    order_by="timestamp desc",
                    limit=10,
                )
                or []
            )
        except Exception as e:
            api_logger.warning(f"Recent activity error: {e}")
            recent_activity = []

        return {
            "success": True,
            "data": {
                "connections": {"total": total_audit, "today": today_audit, "this_week": week_audit},
                "audit_logs": {"total": total_audit, "today": today_audit, "this_week": week_audit},
                "tools": {"total": total_tools, "enabled": enabled_tools},
                "recent_activity": recent_activity,
            },
        }

    except Exception as e:
        api_logger.error(f"Error getting usage statistics: {e}")
        return {"success": False, "error": str(e)}


@frappe.whitelist(methods=["GET", "POST"])
def ping():
    """Ping endpoint for testing connectivity."""
    from frappe_assistant_core.utils.logger import api_logger
    from frappe_assistant_core.utils.permissions import check_assistant_permission

    try:
        if not check_assistant_permission(frappe.session.user):
            frappe.throw(_("Access denied"))

        return {
            "success": True,
            "message": "pong",
            "timestamp": frappe.utils.now(),
            "user": frappe.session.user,
        }

    except Exception as e:
        api_logger.error(f"Error in ping: {e}")
        return {"success": False, "message": f"Ping failed: {str(e)}"}
