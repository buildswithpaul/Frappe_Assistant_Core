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

"""
generate_report must send a MultiSelectList filter as a list, as Desk does.

The final filter cleanup turned every list into its Python repr, so Accounts
Receivable got ``party="['CUST-1']"`` and handed it to ``isin()``, which failed
with "'str' object has no attribute 'nodes_'". The tool then returned
``success: True`` with no rows, because a failed Script Report carries its error
without a ``status``.
"""

import datetime
from unittest.mock import patch

import frappe

from frappe_assistant_core.plugins.core.tools.report_tools import ReportTools
from frappe_assistant_core.tests.base_test import BaseAssistantTest

MULTI = {"fieldname": "party", "fieldtype": "MultiSelectList", "options": "party_type"}


class TestNormalizeFilterValues(BaseAssistantTest):
    def test_list_stays_a_list(self):
        result = ReportTools._normalize_filter_values({"party": ["A", "B"]}, {"party": MULTI})
        self.assertEqual(result["party"], ["A", "B"])

    def test_single_value_for_a_multiselect_is_wrapped(self):
        result = ReportTools._normalize_filter_values({"party": "A"}, {"party": MULTI})
        self.assertEqual(result["party"], ["A"])

    def test_list_for_an_undeclared_filter_is_not_stringified(self):
        result = ReportTools._normalize_filter_values({"cost_center": ("X",)}, None)
        self.assertEqual(result["cost_center"], ["X"])

    def test_scalars_and_dates_keep_their_shape(self):
        result = ReportTools._normalize_filter_values(
            {"company": "C", "range": 30, "show": True, "to_date": datetime.date(2026, 10, 18), "x": None},
            {"company": {"fieldtype": "Link"}},
        )
        self.assertEqual(result, {"company": "C", "range": 30, "show": True, "to_date": "2026-10-18"})


class TestAccountsReceivablePartyFilter(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        if not frappe.db.exists("Report", "Accounts Receivable"):
            self.skipTest("ERPNext not installed")
        self.customer = frappe.db.get_value("Customer", {}, "name")
        if not self.customer:
            self.skipTest("no Customer on this site")

    def _run(self, party):
        return ReportTools.execute_report(
            "Accounts Receivable", {"party_type": "Customer", "party": party}, max_rows=5
        )

    def test_party_as_a_list_runs(self):
        result = self._run([self.customer])
        self.assertTrue(result.get("success"), result)
        self.assertEqual(result["filters_applied"]["party"], [self.customer])

    def test_party_as_a_single_name_runs(self):
        result = self._run(self.customer)
        self.assertTrue(result.get("success"), result)
        self.assertEqual(result["filters_applied"]["party"], [self.customer])


class TestScriptReportFailureIsReported(BaseAssistantTest):
    def test_a_raising_script_report_is_not_a_success(self):
        if not frappe.db.exists("Report", "Accounts Receivable"):
            self.skipTest("ERPNext not installed")
        # Production reaches this whenever the report's own execute() raises.
        with patch("frappe.desk.query_report.run", autospec=True, side_effect=ValueError("boom")):
            result = ReportTools.execute_report("Accounts Receivable", {})
        self.assertFalse(result["success"])
        self.assertIn("boom", result["error"])
