# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Re-categorize undo_import from write to privileged (#34003).

undo_import cancels and deletes the records an import created, as delete_document deletes
one, so MCP clients must be told it is destructive (``destructiveHint: true``, which only the
privileged category gives). Its FAC Tool Configuration row was seeded as write at migrate, and
tools/list reads the stored category first, so the row is corrected here unless an
administrator chose its category (category_override).
"""

import frappe

TOOL = "undo_import"
CATEGORY = "privileged"


def execute():
    if not frappe.db.table_exists("FAC Tool Configuration"):
        return
    row = frappe.db.get_value(
        "FAC Tool Configuration", TOOL, ["tool_category", "category_override"], as_dict=True
    )
    if not row or row.category_override or row.tool_category == CATEGORY:
        return
    frappe.db.set_value(
        "FAC Tool Configuration",
        TOOL,
        {"tool_category": CATEGORY, "auto_detected_category": CATEGORY},
        update_modified=False,
    )
