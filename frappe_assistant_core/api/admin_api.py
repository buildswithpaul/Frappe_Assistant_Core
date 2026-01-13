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

        # Clear plugin-related caches to ensure UI shows correct state
        cache = frappe.cache()
        cache.delete_keys("plugin_*")
        cache.delete_keys("tool_registry_*")

        # Refresh plugin manager's internal cache
        plugin_manager.refresh_plugins()

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


# ============================================================================
# Tool Configuration Management APIs
# ============================================================================


@frappe.whitelist()
def get_tool_configurations():
    """
    Get all tool configurations with detailed information.

    Returns a list of tools with their configuration status, category,
    and role access settings.
    """
    from frappe_assistant_core.core.tool_registry import get_tool_registry
    from frappe_assistant_core.utils.plugin_manager import get_plugin_manager
    from frappe_assistant_core.utils.tool_category_detector import get_category_info

    try:
        plugin_manager = get_plugin_manager()
        tool_registry = get_tool_registry()
        all_tools = plugin_manager.get_all_tools()
        enabled_plugins = plugin_manager.get_enabled_plugins()

        # Get all existing configurations
        existing_configs = {}
        if frappe.db.table_exists("FAC Tool Configuration"):
            configs = frappe.get_all(
                "FAC Tool Configuration",
                fields=[
                    "name",
                    "tool_name",
                    "plugin_name",
                    "enabled",
                    "tool_category",
                    "auto_detected_category",
                    "category_override",
                    "role_access_mode",
                    "description",
                ],
            )
            for config in configs:
                tool_name = config.get("tool_name") or config.get("name")
                existing_configs[tool_name] = config

        tool_list = []
        for tool_name, tool_info in all_tools.items():
            plugin_enabled = tool_info.plugin_name in enabled_plugins

            # Get configuration if exists
            config = existing_configs.get(tool_name, {})
            tool_enabled = config.get("enabled", 1) if config else 1
            category = config.get("tool_category", "read_write") if config else "read_write"
            auto_category = config.get("auto_detected_category", "") if config else ""
            category_override = config.get("category_override", 0) if config else 0
            role_access_mode = config.get("role_access_mode", "Allow All") if config else "Allow All"

            # Get role access if configured
            role_access = []
            if config:
                try:
                    role_access = frappe.get_all(
                        "FAC Tool Role Access",
                        filters={"parent": config.get("name")},
                        fields=["role", "allow_access"],
                    )
                except Exception:
                    pass

            # Get category display info
            category_info = get_category_info(category)

            tool_list.append(
                {
                    "name": tool_name,
                    "display_name": tool_name.replace("_", " ").title(),
                    "description": tool_info.description,
                    "plugin_name": tool_info.plugin_name,
                    "plugin_display_name": tool_info.plugin_name.replace("_", " ").title(),
                    "plugin_enabled": plugin_enabled,
                    "tool_enabled": bool(tool_enabled),
                    "effectively_enabled": plugin_enabled and bool(tool_enabled),
                    "category": category,
                    "category_label": category_info.get("label", "Unknown"),
                    "category_color": category_info.get("color", "gray"),
                    "category_icon": category_info.get("icon", "fa-question"),
                    "auto_detected_category": auto_category,
                    "category_override": bool(category_override),
                    "role_access_mode": role_access_mode,
                    "role_access": role_access,
                    "has_config": bool(config),
                }
            )

        # Sort by plugin name, then by tool name
        tool_list.sort(key=lambda x: (x["plugin_name"], x["name"]))

        return {"success": True, "tools": tool_list}

    except Exception as e:
        frappe.log_error(f"Failed to get tool configurations: {str(e)}")
        return {"success": False, "error": str(e), "tools": []}


@frappe.whitelist()
def toggle_tool(tool_name: str, enabled: bool):
    """
    Enable or disable an individual tool.

    Args:
        tool_name: The name of the tool to toggle
        enabled: True to enable, False to disable

    Returns:
        Success status and message
    """
    from frappe_assistant_core.core.tool_registry import get_tool_registry
    from frappe_assistant_core.utils.plugin_manager import get_plugin_manager
    from frappe_assistant_core.utils.tool_category_detector import detect_tool_category

    try:
        # Validate tool exists
        plugin_manager = get_plugin_manager()
        all_tools = plugin_manager.get_all_tools()

        if tool_name not in all_tools:
            return {"success": False, "message": _(f"Tool '{tool_name}' not found")}

        # Convert enabled to boolean
        enabled = frappe.utils.cint(enabled)

        # Use savepoint for atomic operation
        frappe.db.savepoint("toggle_tool")

        try:
            # Get or create tool configuration
            if frappe.db.exists("FAC Tool Configuration", tool_name):
                config = frappe.get_doc("FAC Tool Configuration", tool_name)
                config.enabled = enabled
                config.save(ignore_permissions=True)
            else:
                # Create new configuration
                tool_info = all_tools[tool_name]
                category = detect_tool_category(tool_info.instance)

                config = frappe.new_doc("FAC Tool Configuration")
                config.tool_name = tool_name
                config.plugin_name = tool_info.plugin_name
                config.description = tool_info.description
                config.enabled = enabled
                config.tool_category = category
                config.auto_detected_category = category
                config.source_app = getattr(tool_info.instance, "source_app", "frappe_assistant_core")
                config.insert(ignore_permissions=True)

            frappe.db.release_savepoint("toggle_tool")
            frappe.db.commit()

            # Clear caches
            tool_registry = get_tool_registry()
            tool_registry.clear_cache()

            cache = frappe.cache()
            cache.delete_keys("fac_tool_*")

            action = "enabled" if enabled else "disabled"
            return {"success": True, "message": _(f"Tool '{tool_name}' {action} successfully")}

        except Exception as e:
            frappe.db.rollback_savepoint("toggle_tool")
            raise e

    except Exception as e:
        frappe.log_error(f"Failed to toggle tool '{tool_name}': {str(e)}")
        return {"success": False, "message": _(f"Error: {str(e)}")}


@frappe.whitelist()
def bulk_toggle_tools(tool_names: list, enabled: bool):
    """
    Enable or disable multiple tools at once.

    Args:
        tool_names: List of tool names to toggle
        enabled: True to enable, False to disable

    Returns:
        Success status with details
    """
    if isinstance(tool_names, str):
        import json

        tool_names = json.loads(tool_names)

    results = {"success": True, "toggled": [], "failed": []}

    for tool_name in tool_names:
        result = toggle_tool(tool_name, enabled)
        if result.get("success"):
            results["toggled"].append(tool_name)
        else:
            results["failed"].append({"name": tool_name, "error": result.get("message")})

    if results["failed"]:
        results["success"] = False
        results["message"] = _(f"Failed to toggle {len(results['failed'])} tools")
    else:
        action = "enabled" if enabled else "disabled"
        results["message"] = _(f"Successfully {action} {len(results['toggled'])} tools")

    return results


@frappe.whitelist()
def update_tool_category(tool_name: str, category: str, override: bool = True):
    """
    Update the category for a tool.

    Args:
        tool_name: The name of the tool
        category: The new category (read_only, write, read_write, dangerous)
        override: Whether to mark this as a manual override

    Returns:
        Success status and message
    """
    from frappe_assistant_core.core.tool_registry import get_tool_registry
    from frappe_assistant_core.utils.plugin_manager import get_plugin_manager
    from frappe_assistant_core.utils.tool_category_detector import detect_tool_category

    valid_categories = ["read_only", "write", "read_write", "dangerous"]
    if category not in valid_categories:
        return {"success": False, "message": _(f"Invalid category. Must be one of: {valid_categories}")}

    try:
        # Validate tool exists
        plugin_manager = get_plugin_manager()
        all_tools = plugin_manager.get_all_tools()

        if tool_name not in all_tools:
            return {"success": False, "message": _(f"Tool '{tool_name}' not found")}

        # Get or create tool configuration
        if frappe.db.exists("FAC Tool Configuration", tool_name):
            config = frappe.get_doc("FAC Tool Configuration", tool_name)
        else:
            # Create new configuration
            tool_info = all_tools[tool_name]
            auto_category = detect_tool_category(tool_info.instance)

            config = frappe.new_doc("FAC Tool Configuration")
            config.tool_name = tool_name
            config.plugin_name = tool_info.plugin_name
            config.description = tool_info.description
            config.enabled = 1
            config.auto_detected_category = auto_category
            config.source_app = getattr(tool_info.instance, "source_app", "frappe_assistant_core")

        config.tool_category = category
        config.category_override = 1 if override else 0
        config.save(ignore_permissions=True)

        frappe.db.commit()

        # Clear caches
        tool_registry = get_tool_registry()
        tool_registry.clear_cache()

        return {"success": True, "message": _(f"Tool '{tool_name}' category updated to '{category}'")}

    except Exception as e:
        frappe.log_error(f"Failed to update tool category for '{tool_name}': {str(e)}")
        return {"success": False, "message": _(f"Error: {str(e)}")}


@frappe.whitelist()
def update_tool_role_access(tool_name: str, role_access_mode: str, roles: list = None):
    """
    Update role access settings for a tool.

    Args:
        tool_name: The name of the tool
        role_access_mode: "Allow All" or "Restrict to Listed Roles"
        roles: List of dicts with {role, allow_access} for restricted mode

    Returns:
        Success status and message
    """
    from frappe_assistant_core.core.tool_registry import get_tool_registry
    from frappe_assistant_core.utils.plugin_manager import get_plugin_manager
    from frappe_assistant_core.utils.tool_category_detector import detect_tool_category

    valid_modes = ["Allow All", "Restrict to Listed Roles"]
    if role_access_mode not in valid_modes:
        return {"success": False, "message": _(f"Invalid mode. Must be one of: {valid_modes}")}

    if isinstance(roles, str):
        import json

        roles = json.loads(roles)

    try:
        # Validate tool exists
        plugin_manager = get_plugin_manager()
        all_tools = plugin_manager.get_all_tools()

        if tool_name not in all_tools:
            return {"success": False, "message": _(f"Tool '{tool_name}' not found")}

        # Get or create tool configuration
        if frappe.db.exists("FAC Tool Configuration", tool_name):
            config = frappe.get_doc("FAC Tool Configuration", tool_name)
        else:
            # Create new configuration
            tool_info = all_tools[tool_name]
            category = detect_tool_category(tool_info.instance)

            config = frappe.new_doc("FAC Tool Configuration")
            config.tool_name = tool_name
            config.plugin_name = tool_info.plugin_name
            config.description = tool_info.description
            config.enabled = 1
            config.tool_category = category
            config.auto_detected_category = category
            config.source_app = getattr(tool_info.instance, "source_app", "frappe_assistant_core")

        config.role_access_mode = role_access_mode

        # Update role access table if in restricted mode
        if role_access_mode == "Restrict to Listed Roles" and roles:
            # Clear existing role access
            config.role_access = []

            # Add new role access entries
            for role_entry in roles:
                if isinstance(role_entry, dict):
                    config.append(
                        "role_access",
                        {"role": role_entry.get("role"), "allow_access": role_entry.get("allow_access", 1)},
                    )

        config.save(ignore_permissions=True)
        frappe.db.commit()

        # Clear caches
        tool_registry = get_tool_registry()
        tool_registry.clear_cache()

        return {"success": True, "message": _(f"Tool '{tool_name}' role access updated")}

    except Exception as e:
        frappe.log_error(f"Failed to update tool role access for '{tool_name}': {str(e)}")
        return {"success": False, "message": _(f"Error: {str(e)}")}


@frappe.whitelist()
def get_available_roles():
    """
    Get list of available roles for role access configuration.

    Returns:
        List of roles with names
    """
    try:
        roles = frappe.get_all(
            "Role",
            filters={"disabled": 0, "desk_access": 1},
            fields=["name", "role_name"],
            order_by="name",
        )

        # Also include some system roles that might be useful
        system_roles = ["System Manager", "Administrator"]
        for sr in system_roles:
            if not any(r["name"] == sr for r in roles):
                roles.append({"name": sr, "role_name": sr})

        return {"success": True, "roles": roles}

    except Exception as e:
        frappe.log_error(f"Failed to get available roles: {str(e)}")
        return {"success": False, "error": str(e), "roles": []}
