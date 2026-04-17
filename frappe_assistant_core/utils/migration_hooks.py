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

    # Install/update system skills
    _install_system_skills()

    # Install/update skills from other apps
    _install_app_skills()

    # Sync plugin configurations from discovered plugins
    _sync_plugin_configurations()

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

    # Install system skills
    _install_system_skills()

    # Install skills from other apps
    _install_app_skills()

    # Sync plugin configurations from discovered plugins
    _sync_plugin_configurations()

    # Sync tool configurations from discovered plugins
    _sync_tool_configurations()

    # Set default values for Assistant Core Settings
    _set_settings_defaults()


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


def before_app_uninstall(app_name: str):
    """
    Hook fired before any app is uninstalled (``before_app_uninstall``).

    Removes ``FAC Skill`` rows registered by that app via the
    ``assistant_skills`` hook. FAC's own system skills are left alone —
    FAC's ``after_uninstall`` handles full teardown when FAC itself is
    removed.
    """
    if app_name == "frappe_assistant_core":
        return

    try:
        if not frappe.db.table_exists("FAC Skill"):
            return

        orphans = frappe.get_all(
            "FAC Skill",
            filters={"source_app": app_name, "is_system": 1},
            fields=["name", "skill_id"],
        )
        if not orphans:
            return

        for row in orphans:
            doc = frappe.get_doc("FAC Skill", row.name)
            doc.flags.allow_system_delete = True
            doc.delete(ignore_permissions=True)

        frappe.db.commit()
        frappe.logger("migration_hooks").info(
            f"Removed {len(orphans)} skill(s) registered by uninstalled app '{app_name}'"
        )
    except Exception as e:
        frappe.logger("migration_hooks").warning(
            f"Failed to clean up skills for uninstalled app '{app_name}': {str(e)}"
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

        # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal — app-bundled seed JSON, path derived from __file__
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

        # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal — app-bundled seed JSON, path derived from __file__
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


def _install_system_skills():
    """
    Install system skills from manifest.

    These are reference skills that come with FAC and provide guidance
    on how to use tools effectively.

    System skills have is_system=1 and cannot be deleted by users.
    """
    import json
    import os

    try:
        # Check if Skill table exists
        if not frappe.db.table_exists("FAC Skill"):
            frappe.logger("migration_hooks").info(
                "Skill table not yet created, skipping system skill installation"
            )
            return

        # Load manifest
        app_dir = os.path.dirname(os.path.dirname(__file__))
        data_path = os.path.join(app_dir, "data", "system_skills.json")

        if not os.path.exists(data_path):
            frappe.logger("migration_hooks").warning(f"System skills manifest not found at {data_path}")
            return

        # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal — app-bundled skills manifest, path derived from __file__
        with open(data_path) as f:
            skills_manifest = json.load(f)

        # Skills content directory
        docs_skills_dir = os.path.join(os.path.dirname(app_dir), "docs", "skills")

        # Get list of valid skill_ids from manifest
        valid_skill_ids = {s.get("skill_id") for s in skills_manifest}

        # Clean up system skills that are no longer in the manifest
        existing_system_skills = frappe.get_all(
            "FAC Skill", filters={"is_system": 1}, fields=["name", "skill_id"]
        )

        deleted_count = 0
        for existing in existing_system_skills:
            if existing.skill_id not in valid_skill_ids:
                doc = frappe.get_doc("FAC Skill", existing.name)
                doc.flags.allow_system_delete = True
                doc.delete(ignore_permissions=True)
                deleted_count += 1
                frappe.logger("migration_hooks").info(f"Removed obsolete system skill: {existing.skill_id}")

        created_count = 0
        updated_count = 0

        for skill_data in skills_manifest:
            skill_id = skill_data.get("skill_id")

            # Read content from markdown file
            content_file = skill_data.get("content_file")
            content = ""
            if content_file:
                content_path = os.path.join(docs_skills_dir, content_file)
                if os.path.exists(content_path):
                    # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal — skill markdown under app docs dir, filename from app-controlled manifest
                    with open(content_path) as f:
                        content = f.read()
                else:
                    frappe.logger("migration_hooks").warning(f"Skill content file not found: {content_path}")
                    continue

            # Check if system skill already exists
            existing = frappe.db.get_value("FAC Skill", {"skill_id": skill_id, "is_system": 1}, "name")

            if existing:
                # Update existing system skill
                doc = frappe.get_doc("FAC Skill", existing)

                needs_update = False
                for field in ["title", "description", "skill_type", "linked_tool", "category"]:
                    if skill_data.get(field) is not None and doc.get(field) != skill_data.get(field):
                        doc.set(field, skill_data.get(field))
                        needs_update = True

                if content and doc.content != content:
                    doc.content = content
                    needs_update = True

                if doc.source_app != "frappe_assistant_core":
                    doc.source_app = "frappe_assistant_core"
                    needs_update = True

                if needs_update:
                    doc.flags.ignore_permissions = True
                    doc.save()
                    updated_count += 1
                    frappe.logger("migration_hooks").debug(f"Updated system skill: {skill_id}")
            else:
                # Create new system skill
                doc = frappe.new_doc("FAC Skill")
                doc.skill_id = skill_id
                doc.title = skill_data.get("title")
                doc.description = skill_data.get("description")
                doc.status = skill_data.get("status", "Published")
                doc.visibility = skill_data.get("visibility", "Public")
                doc.is_system = 1
                doc.skill_type = skill_data.get("skill_type", "Tool Usage")
                doc.linked_tool = skill_data.get("linked_tool")
                doc.content = content
                doc.owner_user = "Administrator"
                doc.category = skill_data.get("category")
                doc.source_app = "frappe_assistant_core"

                doc.flags.ignore_permissions = True
                doc.insert()
                created_count += 1
                frappe.logger("migration_hooks").debug(f"Created system skill: {skill_id}")

        frappe.db.commit()

        frappe.logger("migration_hooks").info(
            f"System skills: {created_count} created, {updated_count} updated, {deleted_count} removed"
        )

    except Exception as e:
        frappe.logger("migration_hooks").error(f"Failed to install system skills: {str(e)}")


def _install_app_skills():
    """
    Install skills from other apps via the ``assistant_skills`` hook.

    Any Frappe app can register skills by adding to its hooks.py::

        assistant_skills = [
            {
                "app": "my_app",
                "manifest": "data/my_skills.json",
                "content_dir": "data/skills"
            }
        ]

    Path resolution:
        Both ``manifest`` and ``content_dir`` are resolved relative to the
        app's Python package directory (what ``frappe.get_app_path(app)``
        returns — e.g. ``.../my_app/my_app/``). Do not prefix paths with
        the app name.

    The manifest JSON has the same structure as FAC's system_skills.json.

    Skills installed via this hook have ``is_system=1`` and ``source_app``
    set to the app name for lifecycle management and cleanup.
    """
    import json
    import os

    try:
        if not frappe.db.table_exists("FAC Skill"):
            return

        hook_entries = frappe.get_hooks("assistant_skills") or []
        if not hook_entries:
            return

        total_created = 0
        total_updated = 0
        total_deleted = 0

        for entry in hook_entries:
            app_name = entry.get("app")
            manifest_rel = entry.get("manifest")
            content_dir_rel = entry.get("content_dir")

            if not app_name or not manifest_rel:
                frappe.logger("migration_hooks").warning(
                    f"assistant_skills entry missing 'app' or 'manifest': {entry!r}"
                )
                continue

            try:
                app_path = frappe.get_app_path(app_name)
            except Exception:
                frappe.logger("migration_hooks").warning(
                    f"App '{app_name}' not found, skipping skill installation"
                )
                continue

            # Both manifest and content_dir are relative to the app's package dir.
            manifest_path = os.path.join(app_path, manifest_rel)
            content_dir = os.path.join(app_path, content_dir_rel) if content_dir_rel else None

            if not os.path.exists(manifest_path):
                frappe.logger("migration_hooks").warning(
                    f"Skills manifest not found at {manifest_path} for app '{app_name}'"
                )
                continue

            # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal — manifest path from frappe.get_app_path, not user input
            with open(manifest_path) as f:
                skills_manifest = json.load(f)

            # Track valid skill_ids from this app for cleanup
            valid_ids = {s.get("skill_id") for s in skills_manifest}

            # Clean up skills from this app that are no longer in its manifest
            existing = frappe.get_all(
                "FAC Skill",
                filters={"is_system": 1, "source_app": app_name},
                fields=["name", "skill_id"],
            )
            for e in existing:
                if e.skill_id not in valid_ids:
                    doc = frappe.get_doc("FAC Skill", e.name)
                    doc.flags.allow_system_delete = True
                    doc.delete(ignore_permissions=True)
                    total_deleted += 1
                    frappe.logger("migration_hooks").info(
                        f"Removed obsolete app skill: {e.skill_id} (from {app_name})"
                    )

            # Install/update each skill
            for skill_data in skills_manifest:
                skill_id = skill_data.get("skill_id")

                # Read content from markdown file
                content = ""
                content_file = skill_data.get("content_file")
                if content_file and content_dir:
                    content_path = os.path.join(content_dir, content_file)
                    if os.path.exists(content_path):
                        # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal — skill markdown under app-controlled content_dir, filename from app-controlled manifest
                        with open(content_path) as f:
                            content = f.read()
                    else:
                        frappe.logger("migration_hooks").warning(
                            f"Skill content file not found: {content_path}"
                        )
                        continue

                existing_name = frappe.db.get_value(
                    "FAC Skill", {"skill_id": skill_id, "is_system": 1}, "name"
                )

                if existing_name:
                    # Update existing skill.
                    # Manifest-owned fields are re-synced every migration so app
                    # authors can evolve metadata. Fields NOT synced here (owner_user,
                    # is_system) are set once on create and never overwritten.
                    doc = frappe.get_doc("FAC Skill", existing_name)
                    needs_update = False

                    for field in [
                        "title",
                        "description",
                        "status",
                        "visibility",
                        "skill_type",
                        "linked_tool",
                        "category",
                    ]:
                        if skill_data.get(field) is not None and doc.get(field) != skill_data.get(field):
                            doc.set(field, skill_data.get(field))
                            needs_update = True

                    if content and doc.content != content:
                        doc.content = content
                        needs_update = True

                    if doc.source_app != app_name:
                        doc.source_app = app_name
                        needs_update = True

                    if needs_update:
                        doc.flags.ignore_permissions = True
                        doc.save()
                        total_updated += 1
                else:
                    # Create new skill
                    doc = frappe.new_doc("FAC Skill")
                    doc.skill_id = skill_id
                    doc.title = skill_data.get("title")
                    doc.description = skill_data.get("description")
                    doc.status = skill_data.get("status", "Published")
                    doc.visibility = skill_data.get("visibility", "Public")
                    doc.is_system = 1
                    doc.skill_type = skill_data.get("skill_type", "Workflow")
                    doc.linked_tool = skill_data.get("linked_tool")
                    doc.category = skill_data.get("category")
                    doc.content = content
                    doc.owner_user = "Administrator"
                    doc.source_app = app_name

                    doc.flags.ignore_permissions = True
                    doc.insert()
                    total_created += 1

        frappe.db.commit()

        if total_created or total_updated or total_deleted:
            frappe.logger("migration_hooks").info(
                f"App skills: {total_created} created, {total_updated} updated, {total_deleted} removed"
            )

    except Exception as e:
        frappe.logger("migration_hooks").error(f"Failed to install app skills: {str(e)}")


def _sync_plugin_configurations():
    """
    Sync plugin configurations from discovered plugins.

    This function:
    1. Discovers all available plugins
    2. Creates FAC Plugin Configuration records for new plugins
    3. Removes orphan configurations for plugins that no longer exist
    4. Preserves existing plugin enabled/disabled states
    5. Does NOT modify existing configurations (preserves user changes)
    """
    try:
        # Check if FAC Plugin Configuration table exists
        if not frappe.db.table_exists("tabFAC Plugin Configuration"):
            frappe.logger("migration_hooks").info(
                "FAC Plugin Configuration table not yet created, skipping plugin sync"
            )
            return

        from frappe_assistant_core.utils.plugin_manager import PluginDiscovery

        discovery = PluginDiscovery()
        discovered_plugins = discovery.discover_plugins()
        discovered_plugin_names = set(discovered_plugins.keys())

        # Load existing enabled state from legacy JSON (for migration)
        legacy_enabled = set()
        try:
            settings = frappe.get_single("Assistant Core Settings")
            enabled_list = getattr(settings, "enabled_plugins_list", None)
            if enabled_list:
                import json

                legacy_enabled = set(json.loads(enabled_list))
        except Exception:
            pass

        created_count = 0
        skipped_count = 0
        deleted_count = 0

        # Create new plugin configurations
        for plugin_name, plugin_info in discovered_plugins.items():
            if frappe.db.exists("FAC Plugin Configuration", plugin_name):
                skipped_count += 1
                continue

            # Determine if plugin should be enabled
            # Use legacy JSON state if available, otherwise default to enabled
            is_enabled = 1 if plugin_name in legacy_enabled or not legacy_enabled else 0

            # Create configuration
            config = frappe.new_doc("FAC Plugin Configuration")
            config.plugin_name = plugin_name
            config.display_name = plugin_info.display_name
            config.description = plugin_info.description
            config.enabled = is_enabled
            config.discovered_at = frappe.utils.now()

            config.flags.ignore_permissions = True
            config.insert()
            created_count += 1

        # Cleanup orphan plugin configurations (plugins that no longer exist)
        existing_configs = frappe.get_all("FAC Plugin Configuration", pluck="plugin_name")
        for config_name in existing_configs:
            if config_name not in discovered_plugin_names:
                try:
                    frappe.delete_doc(
                        "FAC Plugin Configuration",
                        config_name,
                        force=True,
                        ignore_permissions=True,
                    )
                    deleted_count += 1
                    frappe.logger("migration_hooks").info(
                        f"Removed orphan plugin configuration: {config_name}"
                    )
                except Exception as e:
                    frappe.logger("migration_hooks").warning(
                        f"Failed to delete orphan plugin config '{config_name}': {e}"
                    )

        frappe.db.commit()

        frappe.logger("migration_hooks").info(
            f"Plugin configurations synced: {created_count} created, {skipped_count} already exist, {deleted_count} removed"
        )

    except Exception as e:
        frappe.logger("migration_hooks").error(f"Failed to sync plugin configurations: {str(e)}")


def _set_settings_defaults():
    """Set default values for Assistant Core Settings on fresh install.

    Reads defaults from DocField metadata and applies them, matching
    ERPNext's pattern. For existing sites, use migration patches instead.
    """
    default_values = frappe.db.sql(
        """SELECT fieldname, `default` FROM `tabDocField`
        WHERE parent=%s AND `default` IS NOT NULL AND `default` != ''""",
        "Assistant Core Settings",
    )
    if default_values:
        try:
            doc = frappe.get_doc("Assistant Core Settings")
            for fieldname, value in default_values:
                doc.set(fieldname, value)
            doc.flags.ignore_mandatory = True
            doc.save(ignore_permissions=True)
            frappe.logger("migration_hooks").info("Set default values for Assistant Core Settings")
        except frappe.ValidationError:
            pass


def _sync_tool_configurations():
    """
    Sync tool configurations from discovered plugins.

    This function:
    1. Discovers all tools from enabled plugins
    2. Creates FAC Tool Configuration records for new tools
    3. Auto-detects tool categories
    4. Removes orphan configurations for tools that no longer exist
    5. Does NOT modify existing configurations (preserves user changes)
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

        # Build set of all discovered tool names
        discovered_tool_names = set(all_tools.keys()) | set(external_tools.keys())

        created_count = 0
        skipped_count = 0
        deleted_count = 0

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

        # Cleanup orphan tool configurations (tools that no longer exist)
        existing_configs = frappe.get_all("FAC Tool Configuration", pluck="tool_name")
        for config_name in existing_configs:
            if config_name not in discovered_tool_names:
                try:
                    frappe.delete_doc(
                        "FAC Tool Configuration",
                        config_name,
                        force=True,
                        ignore_permissions=True,
                    )
                    deleted_count += 1
                    frappe.logger("migration_hooks").info(f"Removed orphan tool configuration: {config_name}")
                except Exception as e:
                    frappe.logger("migration_hooks").warning(
                        f"Failed to delete orphan tool config '{config_name}': {e}"
                    )

        frappe.db.commit()

        frappe.logger("migration_hooks").info(
            f"Tool configurations synced: {created_count} created, {skipped_count} already exist, {deleted_count} removed"
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
    "_sync_plugin_configurations",
    "_sync_tool_configurations",
]
