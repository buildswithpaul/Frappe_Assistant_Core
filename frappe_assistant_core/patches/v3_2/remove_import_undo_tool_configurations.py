# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Delete the stored settings of the removed import undo tools (#34002).

preview_import_undo and undo_import no longer exist. Their FAC Tool Configuration rows (named
after the tool, with their role access rows) are deleted here, so a site's tool list and its
Desk settings never show a tool that isn't there. after_migrate's tool sync would delete them
too; this makes it explicit, and idempotent: a site without the rows is left alone.
"""

import frappe

DOCTYPE = "FAC Tool Configuration"
TOOLS = ("preview_import_undo", "undo_import")


def execute():
    delete_configurations(TOOLS)


def delete_configurations(tools) -> None:
    """Delete the FAC Tool Configuration rows of removed tools, and the registry's cached copies.
    Also used by the patches of the import tools merged into others."""
    if not frappe.db.table_exists(DOCTYPE):
        return

    removed = False
    for tool in tools:
        if frappe.db.exists(DOCTYPE, tool):
            frappe.delete_doc(DOCTYPE, tool, force=True, ignore_permissions=True)
            removed = True

    if removed:
        # The registry caches the configurations (60 seconds) and each row by name.
        frappe.cache.delete_value("fac_tool_registry_configs")
        frappe.cache.delete_value("fac_tool_configurations")
        for tool in tools:
            frappe.cache.delete_value(f"fac_tool_config_{tool}")
