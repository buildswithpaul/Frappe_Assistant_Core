# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Migration patch: Move plugin enabled/disabled state from JSON field to DocType records.

This patch migrates the enabled_plugins_list JSON array from Assistant Core Settings
to individual FAC Plugin Configuration records for atomic operations and proper caching.

Before: Assistant Core Settings.enabled_plugins_list = '["core", "visualization"]'
After: One FAC Plugin Configuration record per plugin with enabled=1 or enabled=0
"""

import json

import frappe


def execute():
    """Migrate enabled_plugins_list JSON to FAC Plugin Configuration records."""
    frappe.reload_doc("assistant_core", "doctype", "fac_plugin_configuration")

    # 1. Read existing JSON from Assistant Core Settings
    enabled_list = []
    try:
        settings = frappe.get_single("Assistant Core Settings")
        json_value = getattr(settings, "enabled_plugins_list", None)
        if json_value:
            enabled_list = json.loads(json_value)
            if not isinstance(enabled_list, list):
                enabled_list = []
    except Exception as e:
        frappe.log_error(
            title="Plugin Migration: Failed to read existing settings",
            message=str(e),
        )
        # Default to core if we can't read existing settings
        enabled_list = ["core"]

    # 2. Get all discovered plugins
    discovered_plugins = {}
    try:
        from frappe_assistant_core.utils.plugin_manager import PluginDiscovery

        discovery = PluginDiscovery()
        discovered_plugins = discovery.discover_plugins()
    except Exception as e:
        frappe.log_error(
            title="Plugin Migration: Failed to discover plugins",
            message=str(e),
        )

    # 3. Create FAC Plugin Configuration for each discovered plugin
    created_count = 0
    for plugin_name, plugin_info in discovered_plugins.items():
        if not frappe.db.exists("FAC Plugin Configuration", plugin_name):
            try:
                doc = frappe.new_doc("FAC Plugin Configuration")
                doc.plugin_name = plugin_name
                doc.display_name = getattr(plugin_info, "display_name", plugin_name.replace("_", " ").title())
                doc.enabled = 1 if plugin_name in enabled_list else 0
                doc.description = getattr(plugin_info, "description", "")
                doc.discovered_at = frappe.utils.now()
                doc.insert(ignore_permissions=True)
                created_count += 1
            except Exception as e:
                frappe.log_error(
                    title=f"Plugin Migration: Failed to create config for {plugin_name}",
                    message=str(e),
                )

    frappe.db.commit()

    if created_count > 0:
        frappe.log_error(
            title="Plugin Migration Complete",
            message=f"Created {created_count} FAC Plugin Configuration records from enabled_plugins_list: {enabled_list}",
        )
