# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Backfill FAC Chat Settings.enable_browser_diagnostics to its declared default.

FAC Chat Settings is a pre-existing Single, and Frappe only applies a
field's JSON `default` when a *document is created*. Singles also store
field values as individual rows in `tabSingles` rather than table columns,
so adding this Check field to an already-live Single leaves it with no row
at all on every upgraded site -- and cint(None) for a Check field resolves
to 0. The feature therefore shipped silently OFF everywhere except a
brand-new install, even though the doctype JSON says default "1".

A stored 0 is ambiguous by itself: it can mean "never migrated" (the bug
this patch fixes) or "an operator deliberately disabled it after the fix
already ran" (a choice we must not overwrite). Those two states look
identical if we only inspect the field, so this patch records its own
one-time completion in Patch Log -- the same bookkeeping Frappe itself
uses to guarantee a patch runs once via `bench migrate` -- so that a later
manual `bench execute` of this module (which bypasses that guarantee)
can tell it already made its one correction and must leave any later
value alone.
"""

import frappe

PATCH_NAME = "frappe_assistant_core.patches.v3_0.backfill_browser_diagnostics_default"


def execute():
    frappe.reload_doc("chat", "doctype", "fac_chat_settings")

    if frappe.db.exists("Patch Log", {"patch": PATCH_NAME, "skipped": 0}):
        return

    if not frappe.db.get_single_value("FAC Chat Settings", "enable_browser_diagnostics"):
        frappe.db.set_single_value("FAC Chat Settings", "enable_browser_diagnostics", 1)

    frappe.get_doc({"doctype": "Patch Log", "patch": PATCH_NAME}).insert(ignore_permissions=True)
