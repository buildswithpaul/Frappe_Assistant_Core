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
Migration hooks for tool cache management.

This module provides hooks that integrate with Frappe's migration system
to automatically refresh tool discovery cache when needed.
"""

from typing import Any, Dict

import frappe
from frappe import _


def after_migrate():
    """
    Hook called after bench migrate completes.

    This ensures tool cache is refreshed with any new tools
    that may have been added during migration.
    """
    try:
        frappe.logger("migration_hooks").info("Starting post-migration tool cache refresh")

        # Import here to avoid circular imports
        from frappe_assistant_core.utils.tool_cache import refresh_tool_cache

        # Force refresh to ensure all changes are picked up
        result = refresh_tool_cache(force=True)

        if result.get("success"):
            stats = result.get("stats", {})
            tools_count = stats.get("cached_tools_count", 0)

            frappe.logger("migration_hooks").info(
                f"Successfully refreshed tool cache: {tools_count} tools discovered"
            )
        else:
            error = result.get("error", "Unknown error")
            frappe.logger("migration_hooks").warning(f"Tool cache refresh had issues: {error}")

    except Exception as e:
        # Don't fail migration due to cache issues
        frappe.logger("migration_hooks").error(f"Failed to refresh tool cache after migration: {str(e)}")


def before_migrate():
    """
    Hook called before bench migrate starts.

    This clears tool cache to ensure clean state for migration.
    """
    try:
        frappe.logger("migration_hooks").info("Clearing tool cache before migration")

        from frappe_assistant_core.utils.tool_cache import get_tool_cache

        cache = get_tool_cache()
        cache.invalidate_cache()

        frappe.logger("migration_hooks").info("Tool cache cleared successfully")

    except Exception as e:
        # Don't fail migration due to cache issues
        frappe.logger("migration_hooks").warning(f"Failed to clear tool cache before migration: {str(e)}")


def after_install():
    """
    Hook called after app installation.

    Initializes tool discovery and cache for first-time setup.
    """
    try:
        frappe.logger("migration_hooks").info("Initializing tool discovery after app install")

        from frappe_assistant_core.core.enhanced_tool_registry import get_tool_registry

        # Discover and cache tools
        registry = get_tool_registry()
        result = registry.refresh_tools(force=True)

        if result.get("success"):
            tools_discovered = result.get("tools_discovered", 0)
            frappe.logger("migration_hooks").info(
                f"Tool discovery initialized: {tools_discovered} tools found"
            )
        else:
            error = result.get("error", "Unknown error")
            frappe.logger("migration_hooks").warning(f"Tool discovery initialization had issues: {error}")

    except Exception as e:
        frappe.logger("migration_hooks").error(f"Failed to initialize tool discovery: {str(e)}")


def after_uninstall():
    """
    Hook called after app uninstallation.

    Cleans up:
    1. Custom fields added to core doctypes
    2. Tool cache entries from this app
    """
    try:
        frappe.logger("migration_hooks").info("Starting cleanup after app uninstall")

        # Remove custom field from User doctype
        if frappe.db.exists("Custom Field", {"dt": "User", "fieldname": "assistant_enabled"}):
            frappe.delete_doc("Custom Field", "User-assistant_enabled", force=True, ignore_permissions=True)
            frappe.db.commit()
            frappe.logger("migration_hooks").info("Removed assistant_enabled custom field from User doctype")

        # Clean up tool cache
        from frappe_assistant_core.utils.tool_cache import get_tool_cache

        cache = get_tool_cache()
        cache.invalidate_cache()

        frappe.logger("migration_hooks").info("Cleanup completed after app uninstall")

    except Exception as e:
        frappe.logger("migration_hooks").warning(f"Failed to complete cleanup: {str(e)}")


def on_app_install(app_name: str):
    """
    Hook called when any app is installed.

    Args:
        app_name: Name of the installed app
    """
    try:
        frappe.logger("migration_hooks").info(f"App {app_name} installed, refreshing tool cache")

        from frappe_assistant_core.utils.tool_cache import refresh_tool_cache

        # Refresh cache to pick up any new tools from the installed app
        result = refresh_tool_cache(force=True)

        if result.get("success"):
            frappe.logger("migration_hooks").info(f"Tool cache refreshed after {app_name} installation")
        else:
            frappe.logger("migration_hooks").warning(
                f"Tool cache refresh after {app_name} installation had issues"
            )

    except Exception as e:
        frappe.logger("migration_hooks").warning(
            f"Failed to refresh tool cache after {app_name} installation: {str(e)}"
        )


def on_app_uninstall(app_name: str):
    """
    Hook called when any app is uninstalled.

    Args:
        app_name: Name of the uninstalled app
    """
    try:
        frappe.logger("migration_hooks").info(f"App {app_name} uninstalled, refreshing tool cache")

        from frappe_assistant_core.utils.tool_cache import refresh_tool_cache

        # Refresh cache to remove tools from the uninstalled app
        result = refresh_tool_cache(force=True)

        if result.get("success"):
            frappe.logger("migration_hooks").info(f"Tool cache refreshed after {app_name} uninstallation")
        else:
            frappe.logger("migration_hooks").warning(
                f"Tool cache refresh after {app_name} uninstallation had issues"
            )

    except Exception as e:
        frappe.logger("migration_hooks").warning(
            f"Failed to refresh tool cache after {app_name} uninstallation: {str(e)}"
        )


def get_migration_status() -> Dict[str, Any]:
    """
    Get status of migration-related tool cache operations.

    Returns:
        Status dictionary with cache and discovery information
    """
    try:
        from frappe_assistant_core.core.enhanced_tool_registry import get_tool_registry
        from frappe_assistant_core.utils.tool_cache import get_tool_cache

        cache = get_tool_cache()
        registry = get_tool_registry()

        return {
            "cache_stats": cache.get_cache_stats(),
            "registry_stats": registry.get_registry_stats(),
            "migration_hooks_active": True,
        }

    except Exception as e:
        return {"error": str(e), "migration_hooks_active": False}


# Export functions for hooks registration
__all__ = [
    "after_migrate",
    "before_migrate",
    "after_install",
    "after_uninstall",
    "on_app_install",
    "on_app_uninstall",
    "get_migration_status",
]
