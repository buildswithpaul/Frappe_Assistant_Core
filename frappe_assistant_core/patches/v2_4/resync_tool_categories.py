# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Re-sync auto-detected tool categories from the detector.

Several tools (get_pending_approvals, the browser_* tools, generate_document,
send_email) were seeded into FAC Tool Configuration before they had hardcoded
categories, so they defaulted to ``read_write`` and were treated as write tools
(``readOnlyHint: false``) — making the assistant prompt for read-only actions
like reading the approval queue or capturing a screenshot.

This patch re-detects the category for every row the admin has NOT explicitly
overridden (``category_override = 0``) and updates both ``tool_category`` and
``auto_detected_category`` to the current detector value. Rows with a deliberate
admin override are left untouched.
"""

import frappe

from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.utils.tool_category_detector import detect_tool_category


def execute():
    if not frappe.db.table_exists("FAC Tool Configuration"):
        return

    registry = get_tool_registry()

    rows = frappe.get_all(
        "FAC Tool Configuration",
        filters={"category_override": 0},
        fields=["name", "tool_name", "tool_category"],
    )

    updated = 0
    for row in rows:
        tool = registry.get_tool(row.tool_name)
        if not tool:
            continue
        try:
            category = detect_tool_category(tool)
        except Exception:
            continue
        if category == row.tool_category:
            continue
        frappe.db.set_value(
            "FAC Tool Configuration",
            row.name,
            {"tool_category": category, "auto_detected_category": category},
            update_modified=False,
        )
        updated += 1

    frappe.logger().info(f"resync_tool_categories: updated {updated} tool category rows")
