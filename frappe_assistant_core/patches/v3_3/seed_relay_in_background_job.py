# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Seed FAC Chat Settings.relay_in_background_job (off) on sites that predate the field.

get_single_value reads an absent row and a stored 0 alike, so presence is decided from the
Singles table. A value an administrator has already set is left alone.
"""

import frappe


def execute():
    singles = frappe.qb.DocType("Singles")
    row = (
        frappe.qb.from_(singles)
        .select(singles.field)
        .where((singles.doctype == "FAC Chat Settings") & (singles.field == "relay_in_background_job"))
        .run()
    )
    if not row:
        frappe.db.set_single_value("FAC Chat Settings", "relay_in_background_job", 0)
