# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""FAC Plugin Configuration DocType for individual plugin enable/disable control."""

import frappe
from frappe import _
from frappe.model.document import Document


class FACPluginConfiguration(Document):
    """
    Document class for FAC Plugin Configuration.

    Each plugin gets its own configuration record for atomic toggle operations.
    This replaces the JSON array approach in Assistant Core Settings.

    Fields:
        plugin_name: Unique identifier for the plugin
        display_name: Human-readable name shown in the UI
        enabled: Whether the plugin is enabled (default: 1)
        description: Description of what this plugin provides
        discovered_at: When this plugin was first discovered
        last_toggled_at: When this plugin was last enabled or disabled
    """

    def on_update(self):
        """Clear caches when plugin configuration changes."""
        self._clear_caches()

    def on_trash(self):
        """Clear caches when plugin configuration is deleted."""
        self._clear_caches()

    def _clear_caches(self):
        """Clear all plugin-related caches across workers."""
        cache = frappe.cache()

        # Clear plugin-specific caches
        cache.delete_keys(f"fac_plugin_config_{self.plugin_name}")
        cache.delete_keys("fac_plugin_configurations")
        cache.delete_keys("plugin_*")
        cache.delete_keys("tool_registry_*")

        # Clear document cache for this specific document
        frappe.clear_document_cache("FAC Plugin Configuration", self.plugin_name)

        # Also clear the Assistant Core Settings cache (for backward compatibility)
        frappe.clear_document_cache("Assistant Core Settings", "Assistant Core Settings")


@frappe.whitelist()
def get_plugin_enabled_status(plugin_name: str) -> dict:
    """
    Check if a plugin is enabled.

    Args:
        plugin_name: Name of the plugin

    Returns:
        Dict with enabled status
    """
    try:
        if frappe.db.exists("FAC Plugin Configuration", plugin_name):
            enabled = frappe.db.get_value("FAC Plugin Configuration", plugin_name, "enabled")
            return {
                "plugin_name": plugin_name,
                "enabled": bool(enabled),
                "exists": True,
            }
        else:
            # Plugin not configured yet - default to enabled
            return {
                "plugin_name": plugin_name,
                "enabled": True,
                "exists": False,
                "note": "No configuration exists - using default (enabled)",
            }
    except Exception as e:
        frappe.log_error(title=_("Plugin Status Error"), message=str(e))
        return {
            "plugin_name": plugin_name,
            "enabled": True,  # Default to enabled on error
            "error": str(e),
        }


@frappe.whitelist()
def toggle_plugin_state(plugin_name: str, enabled: bool) -> dict:
    """
    Enable or disable a plugin.

    Args:
        plugin_name: Name of the plugin
        enabled: True to enable, False to disable

    Returns:
        Dict with success status
    """
    try:
        enabled_int = 1 if enabled else 0

        if frappe.db.exists("FAC Plugin Configuration", plugin_name):
            doc = frappe.get_doc("FAC Plugin Configuration", plugin_name)
            doc.enabled = enabled_int
            doc.last_toggled_at = frappe.utils.now()
            doc.save(ignore_permissions=True)
        else:
            # Create new configuration
            doc = frappe.new_doc("FAC Plugin Configuration")
            doc.plugin_name = plugin_name
            doc.enabled = enabled_int
            doc.discovered_at = frappe.utils.now()
            doc.last_toggled_at = frappe.utils.now()
            doc.insert(ignore_permissions=True)

        frappe.db.commit()

        action = "enabled" if enabled else "disabled"
        return {
            "success": True,
            "plugin_name": plugin_name,
            "enabled": bool(enabled_int),
            "message": _(f"Plugin '{plugin_name}' {action} successfully"),
        }
    except Exception as e:
        frappe.log_error(title=_("Plugin Toggle Error"), message=str(e))
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_all_plugin_configurations() -> dict:
    """
    Get all plugin configurations.

    Returns:
        Dict with list of plugin configurations
    """
    try:
        configs = frappe.get_all(
            "FAC Plugin Configuration",
            fields=[
                "plugin_name",
                "display_name",
                "enabled",
                "description",
                "discovered_at",
                "last_toggled_at",
            ],
            order_by="plugin_name",
        )

        return {"success": True, "configurations": configs}
    except Exception as e:
        frappe.log_error(title=_("Get Plugin Configurations Error"), message=str(e))
        return {"success": False, "error": str(e), "configurations": []}
