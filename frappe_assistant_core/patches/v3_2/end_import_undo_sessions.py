# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
End the import sessions undo left behind (#34538).

Undo was removed (#34002). A session that was Undoing at the deploy stays Undoing, its queued job
names a function that is gone, and no tool moves a Partially Undone session on; both kept holding
the user's file. They become Partially Completed, the state of an import some of whose rows are
in: the import tools can carry on from there. The engine writes them, as only it may.
"""

import frappe
from frappe import _

from frappe_assistant_core.assistant_core.doctype.fac_import_session.fac_import_session import engine_session

DOCTYPE = "FAC Import Session"
LEFT_BY_UNDO = ("Undoing", "Partially Undone")


def execute():
    if not frappe.db.table_exists(DOCTYPE):
        return
    for name in frappe.get_all(DOCTYPE, filters={"status": ["in", LEFT_BY_UNDO]}, pluck="name"):
        session = engine_session(name)
        session.status = "Partially Completed"
        session.log_step(
            "Undo",
            "Warning",
            _("Import undo was removed, so the undo of this import ended where it was. Check the records."),
        )
        session.save(ignore_permissions=True)
