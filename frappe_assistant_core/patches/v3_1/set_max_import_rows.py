"""
Set Max Rows per Import (#34003) on existing sites: a Single DocType's schema default isn't
applied to a site whose Singles row already exists, so it would read 0.
"""

import frappe
from frappe.utils import cint


def execute():
    frappe.reload_doc("assistant_core", "doctype", "assistant_core_settings")
    if not cint(frappe.db.get_single_value("Assistant Core Settings", "max_import_rows")):
        frappe.db.set_single_value("Assistant Core Settings", "max_import_rows", 50000)
