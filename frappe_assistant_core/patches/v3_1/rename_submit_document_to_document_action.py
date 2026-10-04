# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Carry the submit_document tool's settings over to its new name, document_action.

FAC Tool Configuration rows are named after their tool. On every migrate,
after_migrate's _sync_tool_configurations creates a default row (enabled, "Allow All")
for any tool without one and deletes rows whose tool no longer exists. Left alone, the
first migrate after the rename would replace a site's settings for this tool - enabled,
role access and category override - with those defaults.

Patches run before after_migrate, so renaming the row here means the sync then finds
document_action already configured. Renaming (rather than copying) keeps the row's role
access rows. The stored module path is pointed at the new file and, unless an admin
overrode the category, the category is re-detected: the tool can cancel, so it is
privileged. This replaces the earlier recategorize_submit_document patch.

A site without a submit_document row (e.g. a fresh install) is left alone.
"""

import frappe
from frappe.model.rename_doc import rename_doc

from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.utils.tool_category_detector import detect_tool_category

DOCTYPE = "FAC Tool Configuration"
OLD_NAME = "submit_document"
NEW_NAME = "document_action"
NEW_MODULE_PATH = "frappe_assistant_core.plugins.core.tools.document_action.DocumentAction"


def execute():
    if not frappe.db.table_exists(DOCTYPE) or not frappe.db.exists(DOCTYPE, OLD_NAME):
        return

    if frappe.db.exists(DOCTYPE, NEW_NAME):
        # Only happens when a default row for the new name was created before this ran (e.g. an
        # admin toggled document_action between deploying and migrating). The old row holds the
        # settings the site actually chose, so it wins.
        frappe.logger().warning(
            f"{__name__}: replacing the existing {NEW_NAME} row with the settings of {OLD_NAME}"
        )
        frappe.delete_doc(DOCTYPE, NEW_NAME, force=True, ignore_permissions=True)

    # frappe.model's rename_doc, not the frappe.rename_doc wrapper, which has no ignore_permissions.
    rename_doc(
        DOCTYPE,
        OLD_NAME,
        NEW_NAME,
        force=True,
        ignore_permissions=True,
        show_alert=False,
        rebuild_search=False,
    )

    updates = {"module_path": NEW_MODULE_PATH}
    if not frappe.db.get_value(DOCTYPE, NEW_NAME, "category_override"):
        tool = get_tool_registry().get_tool(NEW_NAME)
        try:
            category = detect_tool_category(tool) if tool else None
        except Exception:
            category = None
        if category:
            updates.update(tool_category=category, auto_detected_category=category)

    frappe.db.set_value(DOCTYPE, NEW_NAME, updates, update_modified=False)

    # rename_doc skips the controller hooks that normally clear these name-keyed caches.
    for key in (
        f"fac_tool_config_{OLD_NAME}",
        f"fac_tool_config_{NEW_NAME}",
        "fac_tool_configurations",
        "fac_tool_registry_*",
    ):
        frappe.cache.delete_keys(key)

    frappe.logger().info(f"{__name__}: renamed {OLD_NAME} to {NEW_NAME}, updated {sorted(updates)}")
