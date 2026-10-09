# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""A real Query Report for report-tool tests: rows of ToDo plus a totals row."""

import frappe

PROBE_DESCRIPTION = "fac-report-rows-probe"
REPORT_NAME = "FAC Row Cap Probe"


def make_todo_query_report(rows: int) -> str:
    """Insert ``rows`` probe ToDos and a non-standard Query Report over them.

    is_standard is set to "No" explicitly: on a developer-mode bench Frappe
    would otherwise make Administrator's report standard and write it to disk.
    """
    for _i in range(rows):
        frappe.get_doc({"doctype": "ToDo", "description": PROBE_DESCRIPTION}).insert()

    if not frappe.db.exists("Report", REPORT_NAME):
        frappe.get_doc(
            {
                "doctype": "Report",
                "report_name": REPORT_NAME,
                "ref_doctype": "ToDo",
                "report_type": "Query Report",
                "is_standard": "No",
                "module": "Desk",
                "add_total_row": 1,
                "prepared_report": 0,
                "query": (
                    "select name as `Name:Link/ToDo:120`, 1 as `Qty:Int:80` "
                    f"from `tabToDo` where description = '{PROBE_DESCRIPTION}'"
                ),
            }
        ).insert()
    return REPORT_NAME
