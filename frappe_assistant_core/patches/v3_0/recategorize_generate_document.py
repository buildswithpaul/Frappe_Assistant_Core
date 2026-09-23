# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Re-categorize generate_document from read_only to write.

generate_document was hardcoded as read_only on the reasoning "renders markdown,
changes no Frappe records". But it SAVES a private Frappe File — a create side
effect — so its MCP annotation was wrongly ``readOnlyHint: true``. That let it
leak into read-only-only contexts (notably the delegate helper's write-free
toolset), where a delegated subtask could generate a document unasked.

The detector now classifies it as ``write``. Existing FAC Tool Configuration rows
were seeded with the old value, so re-detect for every row the admin has NOT
explicitly overridden (``category_override = 0``) and update both ``tool_category``
and ``auto_detected_category``. Deliberate admin overrides are left untouched.
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

    frappe.logger().info(f"recategorize_generate_document: updated {updated} tool category rows")
