# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Searching reports by what the user asked."""

import json
import unittest

import frappe

from frappe_assistant_core.plugins.core.tools.report_list import ReportList
from frappe_assistant_core.plugins.core.tools.report_search import (
    MAX_LIMIT,
    module_summary,
    search_reports,
    standard_report_purpose,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest

# Production reaches these reports the same way: a Query Report row built in the UI.
ALLOWED_REF_DOCTYPE = "Role"  # System Manager has "report" permission on it
DENIED_REF_DOCTYPE = "Language"  # System Manager has no "report" permission on it


class TestReportSearch(BaseAssistantTest):
    def _make_report(self, name: str, ref_doctype: str = ALLOWED_REF_DOCTYPE, **overrides) -> str:
        doc = frappe.get_doc(
            {
                "doctype": "Report",
                "report_name": name,
                "ref_doctype": ref_doctype,
                "report_type": "Query Report",
                "query": "select 1 as `n`",
                "is_standard": "No",
                "module": "Core",
                **overrides,
            }
        )
        doc.insert(ignore_permissions=True)
        # The class shares one transaction, so a report must not outlive its test and skew the next.
        self.addCleanup(frappe.delete_doc, "Report", doc.name, force=True, ignore_permissions=True)
        return doc.name

    @unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "ERPNext not installed")
    def test_search_finds_sales_analytics_for_sales_question(self):
        result = search_reports("how is sales doing")

        self.assertIn("Sales Analytics", [r["name"] for r in result["reports"][:3]])

    @unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "ERPNext not installed")
    def test_custom_report_ranks_above_equal_standard_match(self):
        # Same ref_doctype as Item-wise Sales History, so both match "sales" identically before the boost.
        self._make_report("Sales Zulu Overview", ref_doctype="Sales Order", module="Selling")

        names = [r["name"] for r in search_reports("sales")["reports"]]

        self.assertEqual(names[0], "Sales Zulu Overview")

    def test_custom_report_with_more_matches_ranks_first(self):
        self._make_report("Sales Performance by Region")

        top = search_reports("sales performance")["reports"][0]

        self.assertEqual(top["name"], "Sales Performance by Region")
        self.assertEqual(top["origin"], "custom")

    def test_result_carries_mandatory_filters_and_prepared_flag(self):
        # Production reaches this the way Desk does: a Report with Report Filter child rows.
        name = self._make_report(
            "Invoice Backlog Check",
            prepared_report=1,
            filters=[
                {"fieldname": "company", "label": "Company", "fieldtype": "Data", "mandatory": 1},
                {"fieldname": "territory", "label": "Territory", "fieldtype": "Data", "mandatory": 0},
            ],
        )

        found = {r["name"]: r for r in search_reports("invoice backlog")["reports"]}[name]

        self.assertTrue(found["prepared"])
        self.assertEqual(found["mandatory_filters"], ["company"])
        self.assertEqual(found["ref_doctype"], ALLOWED_REF_DOCTYPE)
        self.assertIn("purpose", found)

    @unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "ERPNext not installed")
    def test_standard_report_with_required_filter_lists_it_and_purpose(self):
        found = {r["name"]: r for r in search_reports("accounts receivable")["reports"]}

        self.assertIn("company", found["Accounts Receivable"]["mandatory_filters"])
        self.assertEqual(found["Accounts Receivable"]["origin"], "standard")
        self.assertEqual(
            found["Accounts Receivable"]["purpose"], standard_report_purpose("Accounts Receivable")
        )

    def test_no_match_returns_empty_with_hint(self):
        result = search_reports("zzqqxx nonexistent topic")

        self.assertEqual(result["count"], 0)
        self.assertEqual(result["reports"], [])
        self.assertIn("get_doctype_info", result["hint"])
        self.assertIn("module", result["hint"])

    def test_limit_is_capped_at_25(self):
        for i in range(MAX_LIMIT + 5):
            self._make_report(f"Limitcap Report {i:02d}")

        self.assertEqual(search_reports("limitcap", limit=100)["count"], MAX_LIMIT)
        self.assertEqual(search_reports("limitcap", limit=3)["count"], 3)

    def test_no_arguments_returns_module_summary_not_every_report(self):
        result = ReportList().execute({})

        self.assertTrue(result["success"])
        self.assertIn("modules", result)
        self.assertNotIn("reports", result)
        self.assertLess(len(json.dumps(result)), 4096)
        self.assertEqual(result, module_summary())

    def test_search_excludes_reports_user_cannot_run(self):
        denied = self._make_report("Secretive Ledger Digest", ref_doctype=DENIED_REF_DOCTYPE)
        allowed = self._make_report("Secretive Role Digest")
        user = self.make_throwaway_user("report-search", roles=("System Manager",))
        # nosemgrep: frappe-setuser — test acts as a non-Administrator inside the test transaction
        frappe.set_user(user)

        names = [r["name"] for r in search_reports("secretive digest")["reports"]]

        self.assertIn(allowed, names)
        self.assertNotIn(denied, names)

    def test_report_list_routes_query_to_search(self):
        self._make_report("Routing Probe Report")

        result = ReportList().execute({"query": "routing probe"})

        self.assertEqual(result["reports"][0]["name"], "Routing Probe Report")
