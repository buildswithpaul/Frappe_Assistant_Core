# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Import Sessions (#34542): every user's import sessions for a System Manager, with the stuck ones
to release from their form."""

import frappe
from frappe import _

from frappe_assistant_core.utils import import_housekeeping


def execute(filters=None):
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only a System Manager sees every import session."), frappe.PermissionError)
    columns = [
        {
            "fieldname": "session",
            "label": _("Session"),
            "fieldtype": "Link",
            "options": "FAC Import Session",
            "width": 180,  # a whole IMP-2026-169299, not "IMP-2026-169…" (PR #392, L5)
        },
        {"fieldname": "user", "label": _("User"), "fieldtype": "Link", "options": "User", "width": 180},
        {"fieldname": "file_name", "label": _("File"), "fieldtype": "Data", "width": 200},
        {"fieldname": "target_doctype", "label": _("Imported As"), "fieldtype": "Data", "width": 130},
        {"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 130},
        {
            "fieldname": "migration_plan",
            "label": _("Plan"),
            "fieldtype": "Link",
            "options": "FAC Import Session",
            "width": 180,
        },
        {"fieldname": "plan_status", "label": _("Plan Status"), "fieldtype": "Data", "width": 140},
        {"fieldname": "last_step", "label": _("Last Step"), "fieldtype": "Data", "width": 170},
        {"fieldname": "age_days", "label": _("Days Since Last Change"), "fieldtype": "Int", "width": 120},
        {"fieldname": "holds_file", "label": _("Holds Its File"), "fieldtype": "Check", "width": 100},
        {
            "fieldname": "may_release",
            "label": _("Stuck? Release From Its Form"),
            "fieldtype": "Check",
            "width": 120,
        },
    ]
    return columns, import_housekeeping.sessions(filters)
