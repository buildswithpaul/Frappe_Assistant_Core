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
    that may have been added during migration, and installs/updates
    system prompt categories and templates.
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

    # Install/update system prompt categories (must run before templates)
    _install_system_prompt_categories()

    # Install/update system prompt templates
    _install_system_prompt_templates()

    # Sync tool configurations from discovered plugins
    _sync_tool_configurations()


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

    Initializes tool discovery, cache, and system prompt templates.
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

    # Install system prompt categories (must run before templates)
    _install_system_prompt_categories()

    # Install system prompt templates
    _install_system_prompt_templates()

    # Sync tool configurations from discovered plugins
    _sync_tool_configurations()


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


def _install_system_prompt_categories():
    """
    Install system prompt categories from data file.

    Categories provide hierarchical organization for prompt templates.
    Uses nested set model for efficient tree queries.
    """
    import json
    import os

    try:
        # Check if Prompt Category table exists
        if not frappe.db.table_exists("Prompt Category"):
            frappe.logger("migration_hooks").info(
                "Prompt Category table not yet created, skipping category installation"
            )
            return

        # Load data file
        data_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "system_prompt_categories.json"
        )

        if not os.path.exists(data_path):
            frappe.logger("migration_hooks").warning(f"Prompt category data not found at {data_path}")
            return

        with open(data_path) as f:
            categories = json.load(f)

        created_count = 0
        updated_count = 0

        # First pass: create/update categories without parent references
        for cat_data in categories:
            category_id = cat_data.get("category_id")

            existing = frappe.db.exists("Prompt Category", category_id)

            if existing:
                # Update existing category
                doc = frappe.get_doc("Prompt Category", category_id)
                needs_update = False

                for field in ["category_name", "description", "icon", "color", "is_group"]:
                    if cat_data.get(field) is not None and doc.get(field) != cat_data.get(field):
                        doc.set(field, cat_data.get(field))
                        needs_update = True

                if needs_update:
                    doc.flags.ignore_permissions = True
                    doc.save()
                    updated_count += 1
            else:
                # Create new category (without parent first to avoid ordering issues)
                doc = frappe.new_doc("Prompt Category")
                doc.category_id = category_id
                doc.category_name = cat_data.get("category_name")
                doc.description = cat_data.get("description")
                doc.icon = cat_data.get("icon")
                doc.color = cat_data.get("color")
                doc.is_group = cat_data.get("is_group", 0)
                doc.flags.ignore_permissions = True
                doc.insert()
                created_count += 1

        # Second pass: set parent relationships
        for cat_data in categories:
            parent_id = cat_data.get("parent_prompt_category")
            if parent_id:
                category_id = cat_data.get("category_id")
                doc = frappe.get_doc("Prompt Category", category_id)
                if doc.parent_prompt_category != parent_id:
                    doc.parent_prompt_category = parent_id
                    doc.flags.ignore_permissions = True
                    doc.save()

        frappe.db.commit()

        frappe.logger("migration_hooks").info(
            f"System prompt categories: {created_count} created, {updated_count} updated"
        )

    except Exception as e:
        frappe.logger("migration_hooks").error(f"Failed to install system prompt categories: {str(e)}")


def _install_system_prompt_templates():
    """
    Install system prompt templates from fixtures.

    These are reference templates that come with FAC and demonstrate
    best practices for creating prompt templates.

    System templates have is_system=1 and cannot be deleted by users.
    """
    import json
    import os

    try:
        # Check if Prompt Template table exists
        if not frappe.db.table_exists("Prompt Template"):
            frappe.logger("migration_hooks").info(
                "Prompt Template table not yet created, skipping system prompt installation"
            )
            return

        # Load data file (in data/ directory to avoid Frappe's auto-import from fixtures/)
        data_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "system_prompt_templates.json"
        )

        if not os.path.exists(data_path):
            frappe.logger("migration_hooks").warning(f"Prompt template data not found at {data_path}")
            return

        with open(data_path) as f:
            templates = json.load(f)

        # Get list of valid prompt_ids from JSON file
        valid_prompt_ids = {t.get("prompt_id") for t in templates}

        # Clean up system templates that are no longer in the JSON file
        existing_system_templates = frappe.get_all(
            "Prompt Template", filters={"is_system": 1}, fields=["name", "prompt_id"]
        )

        deleted_count = 0
        for existing in existing_system_templates:
            if existing.prompt_id not in valid_prompt_ids:
                # This system template is no longer in our JSON, remove it
                doc = frappe.get_doc("Prompt Template", existing.name)
                doc.flags.allow_system_delete = True  # Bypass on_trash check
                doc.delete(ignore_permissions=True)
                deleted_count += 1
                frappe.logger("migration_hooks").info(
                    f"Removed obsolete system prompt template: {existing.prompt_id}"
                )

        created_count = 0
        updated_count = 0

        for template_data in templates:
            prompt_id = template_data.get("prompt_id")

            # Check if system template already exists
            existing = frappe.db.get_value(
                "Prompt Template", {"prompt_id": prompt_id, "is_system": 1}, "name"
            )

            if existing:
                # Update existing system template
                doc = frappe.get_doc("Prompt Template", existing)

                # Only update if content has changed
                needs_update = False
                for field in ["title", "description", "template_content", "rendering_engine", "category"]:
                    if template_data.get(field) is not None and doc.get(field) != template_data.get(field):
                        doc.set(field, template_data.get(field))
                        needs_update = True

                # Update arguments if changed
                if "arguments" in template_data:
                    # Clear and recreate arguments
                    doc.arguments = []
                    for arg_data in template_data["arguments"]:
                        doc.append("arguments", arg_data)
                    needs_update = True

                if needs_update:
                    doc.flags.ignore_permissions = True
                    doc.save()
                    updated_count += 1
                    frappe.logger("migration_hooks").debug(f"Updated system prompt template: {prompt_id}")
            else:
                # Create new system template
                doc = frappe.new_doc("Prompt Template")
                doc.prompt_id = prompt_id
                doc.title = template_data.get("title")
                doc.description = template_data.get("description")
                doc.status = template_data.get("status", "Published")
                doc.visibility = template_data.get("visibility", "Public")
                doc.is_system = 1
                doc.rendering_engine = template_data.get("rendering_engine", "Jinja2")
                doc.template_content = template_data.get("template_content")
                doc.owner_user = "Administrator"
                doc.category = template_data.get("category")

                # Add arguments
                for arg_data in template_data.get("arguments", []):
                    doc.append("arguments", arg_data)

                doc.flags.ignore_permissions = True
                doc.insert()
                created_count += 1
                frappe.logger("migration_hooks").debug(f"Created system prompt template: {prompt_id}")

        frappe.db.commit()

        frappe.logger("migration_hooks").info(
            f"System prompt templates: {created_count} created, {updated_count} updated, {deleted_count} removed"
        )

    except Exception as e:
        frappe.logger("migration_hooks").error(f"Failed to install system prompt templates: {str(e)}")


def _sync_tool_configurations():
    """
    Sync tool configurations from discovered plugins.

    This function:
    1. Discovers all tools from enabled plugins
    2. Creates FAC Tool Configuration records for new tools
    3. Auto-detects tool categories
    4. Does NOT modify existing configurations (preserves user changes)
    """
    try:
        # Check if FAC Tool Configuration table exists
        if not frappe.db.table_exists("FAC Tool Configuration"):
            frappe.logger("migration_hooks").info(
                "FAC Tool Configuration table not yet created, skipping tool sync"
            )
            return

        from frappe_assistant_core.utils.plugin_manager import get_plugin_manager
        from frappe_assistant_core.utils.tool_category_detector import detect_tool_category

        plugin_manager = get_plugin_manager()

        # Get all tools from all discovered plugins (not just enabled)
        discovered_plugins = plugin_manager.get_discovered_plugins()
        all_tools = plugin_manager.get_all_tools()

        # Also get external tools from hooks
        external_tools = _get_external_tools_for_sync()

        created_count = 0
        skipped_count = 0

        # Process plugin tools
        for tool_name, tool_info in all_tools.items():
            if frappe.db.exists("FAC Tool Configuration", tool_name):
                skipped_count += 1
                continue

            # Detect category
            try:
                category = detect_tool_category(tool_info.instance)
            except Exception:
                category = "read_write"

            # Create configuration
            config = frappe.new_doc("FAC Tool Configuration")
            config.tool_name = tool_name
            config.plugin_name = tool_info.plugin_name
            config.description = tool_info.description or ""
            config.enabled = 1  # Default to enabled
            config.tool_category = category
            config.auto_detected_category = category
            config.category_override = 0
            config.role_access_mode = "Allow All"
            config.source_app = getattr(tool_info.instance, "source_app", "frappe_assistant_core")
            config.module_path = (
                f"{tool_info.instance.__class__.__module__}.{tool_info.instance.__class__.__name__}"
            )

            config.flags.ignore_permissions = True
            config.insert()
            created_count += 1

        # Process external tools
        for tool_name, tool_data in external_tools.items():
            if frappe.db.exists("FAC Tool Configuration", tool_name):
                skipped_count += 1
                continue

            config = frappe.new_doc("FAC Tool Configuration")
            config.tool_name = tool_name
            config.plugin_name = "custom_tools"
            config.description = tool_data.get("description", "")
            config.enabled = 1
            config.tool_category = "read_write"  # Default for external tools
            config.auto_detected_category = "read_write"
            config.category_override = 0
            config.role_access_mode = "Allow All"
            config.source_app = tool_data.get("source_app", "external")
            config.module_path = tool_data.get("module_path", "")

            config.flags.ignore_permissions = True
            config.insert()
            created_count += 1

        frappe.db.commit()

        frappe.logger("migration_hooks").info(
            f"Tool configurations synced: {created_count} created, {skipped_count} already exist"
        )

    except Exception as e:
        frappe.logger("migration_hooks").error(f"Failed to sync tool configurations: {str(e)}")


def _get_external_tools_for_sync() -> dict:
    """Get external tools from hooks for sync."""
    external_tools = {}

    try:
        assistant_tools_hooks = frappe.get_hooks("assistant_tools") or []
        for tool_path in assistant_tools_hooks:
            try:
                parts = tool_path.rsplit(".", 1)
                if len(parts) == 2:
                    module_path, class_name = parts
                    module = __import__(module_path, fromlist=[class_name])
                    tool_class = getattr(module, class_name)
                    tool_instance = tool_class()
                    tool_name = getattr(tool_instance, "name", parts[0].split(".")[-1])

                    external_tools[tool_name] = {
                        "name": tool_name,
                        "description": getattr(tool_instance, "description", "External tool"),
                        "source_app": getattr(tool_instance, "source_app", parts[0].split(".")[0]),
                        "module_path": tool_path,
                    }
            except Exception as e:
                frappe.logger("migration_hooks").warning(f"Failed to load external tool {tool_path}: {e}")
    except Exception as e:
        frappe.logger("migration_hooks").warning(f"Failed to get external tools: {e}")

    return external_tools


# Export functions for hooks registration
__all__ = [
    "after_migrate",
    "before_migrate",
    "after_install",
    "after_uninstall",
    "on_app_install",
    "on_app_uninstall",
    "get_migration_status",
    "_sync_tool_configurations",
]
