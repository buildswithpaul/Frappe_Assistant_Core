"""
A migration plan is kept on its first file's session now (#34351), not in a FAC Migration Plan
record: a session that still names one of those records names nothing, and Frappe's link check
would refuse every save of it. Frappe's migrate removes the DocType itself, as its code is gone.
"""

import frappe

SESSION = "FAC Import Session"


def execute():
    frappe.reload_doc("assistant_core", "doctype", "fac_import_session")
    linked = frappe.get_all(
        SESSION, filters={"migration_plan": ["is", "set"]}, fields=["name", "migration_plan"]
    )
    for row in linked:
        if not frappe.db.exists(SESSION, row.migration_plan):
            frappe.db.set_value(SESSION, row.name, "migration_plan", None, update_modified=False)
