# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""generate_report reuses only a completed Prepared Report, on every Frappe version.

Frappe 16 replaced ``get_completed_prepared_report`` with ``get_last_processed_prepared_report``
(October 2026), which also returns reports that failed, so FAC looks the row up itself.
"""

import frappe
from frappe.core.doctype.prepared_report.prepared_report import process_filters_for_prepared_report

from frappe_assistant_core.plugins.core.tools.report_tools import completed_prepared_report
from frappe_assistant_core.tests.base_test import BaseAssistantTest

REPORT = "Stock Balance"
FILTERS = {"company": "Lookup Test Co", "from_date": "2026-10-01"}


class TestCompletedPreparedReport(BaseAssistantTest):
    def _prepared(self, status: str) -> str:
        # Manufactured: production writes this row when a prepared report's background job ends.
        # db_insert skips after_insert, which would enqueue a real report job.
        doc = frappe.get_doc(
            {
                "doctype": "Prepared Report",
                "report_name": REPORT,
                "status": status,
                "filters": process_filters_for_prepared_report(FILTERS),
            }
        )
        doc.db_insert()
        return doc.name

    def test_returns_the_completed_report(self):
        completed = self._prepared("Completed")
        self.assertEqual(completed_prepared_report(FILTERS, REPORT), completed)

    def test_ignores_a_report_that_failed(self):
        self._prepared("Error")
        self.assertIsNone(completed_prepared_report(FILTERS, REPORT))

    def test_ignores_another_users_report(self):
        name = self._prepared("Completed")
        frappe.db.set_value("Prepared Report", name, "owner", "someone.else@example.com")
        self.assertIsNone(completed_prepared_report(FILTERS, REPORT))
