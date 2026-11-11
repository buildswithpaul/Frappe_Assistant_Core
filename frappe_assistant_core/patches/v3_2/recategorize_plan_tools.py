# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Re-categorize plan_migration and plan_questions from write to read_only (#34547).

They write only a migration plan's settings and its sessions', as start_import_session and
dry_run_import do, yet each call raised an approval card: a three-file plan took five before its
run. The detector now classes them read_only. As recategorize_generate_document does, every
FAC Tool Configuration row of theirs the admin hasn't overridden takes the detected category.
"""

import frappe

from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.utils.tool_category_detector import detect_tool_category

TOOLS = ("plan_migration", "plan_questions")


def execute():
    if not frappe.db.table_exists("FAC Tool Configuration"):
        return
    registry = get_tool_registry()
    for row in frappe.get_all(
        "FAC Tool Configuration",
        filters={"category_override": 0, "tool_name": ["in", TOOLS]},
        fields=["name", "tool_name", "tool_category"],
    ):
        tool = registry.get_tool(row.tool_name)
        category = detect_tool_category(tool) if tool else None
        if category and category != row.tool_category:
            frappe.db.set_value(
                "FAC Tool Configuration",
                row.name,
                {"tool_category": category, "auto_detected_category": category},
                update_modified=False,
            )
