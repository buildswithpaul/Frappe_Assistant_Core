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
Site-level tests for report_requirements filter discovery.

Issues: #203 (silent empty results for JS-defined filters) and #220 (filters
composed across files, and discovery gated to Script Reports).

The JS parsing itself is covered by ``test_js_filter_resolver``, which needs no
site. What is tested here is the orchestration around it: source precedence,
diagnostics, Custom Report dereferencing, Query Report SQL placeholders, and
the guarantee that an unresolved report never gets invented filter names.
"""

from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.plugins.core.tools.report_requirements import ReportRequirements
from frappe_assistant_core.tests.base_test import BaseAssistantTest


def _report_doc(**kwargs):
    """A Report-like mock. ``name`` needs explicit assignment on MagicMock."""
    doc = MagicMock()
    doc.name = kwargs.pop("name", "Some Report")
    doc.module = kwargs.pop("module", "Nonexistent Module XYZ")
    doc.report_type = kwargs.pop("report_type", "Script Report")
    doc.query = kwargs.pop("query", "")
    doc.reference_report = kwargs.pop("reference_report", None)
    doc.get.return_value = kwargs.pop("child_rows", [])
    for key, value in kwargs.items():
        setattr(doc, key, value)
    return doc


class TestFiltersChildTableSource(BaseAssistantTest):
    """Report.filters child-table rows are a structured discovery source."""

    def setUp(self):
        super().setUp()
        self.tool = ReportRequirements()

    def test_child_table_rows_convert_to_filters(self):
        rows = [
            {"fieldname": "company", "label": "Company", "fieldtype": "Link", "mandatory": 1},
            {"fieldname": "bom", "label": "BOM", "fieldtype": "Link"},
        ]
        parsed = self.tool._parse_filters_child_table(rows)
        self.assertEqual([f["fieldname"] for f in parsed["filters"]], ["company", "bom"])
        self.assertEqual(parsed["required_filters"], ["company"])
        self.assertEqual(parsed["optional_filters"], ["bom"])

    def test_rows_without_fieldname_skipped(self):
        parsed = self.tool._parse_filters_child_table([{"label": "No fieldname"}, {"fieldname": "ok"}])
        self.assertEqual([f["fieldname"] for f in parsed["filters"]], ["ok"])


class TestDiscoveryOrchestration(BaseAssistantTest):
    """_discover_report_filters prefers structured sources and always
    returns a diagnostics payload."""

    def setUp(self):
        super().setUp()
        self.tool = ReportRequirements()

    def test_child_table_wins_and_short_circuits_js(self):
        doc = _report_doc(
            module="Selling",
            child_rows=[{"fieldname": "company", "label": "Company", "fieldtype": "Link", "mandatory": 1}],
        )
        parsed, diagnostics = self.tool._discover_report_filters("Some Report", doc)

        self.assertEqual([f["fieldname"] for f in parsed["filters"]], ["company"])
        self.assertEqual(diagnostics["filters_child_table"]["status"], "success")
        self.assertEqual(diagnostics["status"], "resolved")
        self.assertEqual(diagnostics["requiredness"], "declared_in_report_filters")
        # JS path not attempted when the child table satisfied discovery.
        self.assertNotIn("javascript", diagnostics)

    def test_empty_child_table_falls_through_to_js_with_diagnostics(self):
        doc = _report_doc(name="No Such Report")
        parsed, diagnostics = self.tool._discover_report_filters("No Such Report", doc)

        self.assertIsNone(parsed)
        self.assertEqual(diagnostics["filters_child_table"]["status"], "empty")
        self.assertEqual(diagnostics["status"], "unresolved")
        # JS discovery was attempted and recorded (even though it found nothing).
        self.assertIn("javascript", diagnostics)

    def test_custom_report_inherits_from_reference_report(self):
        """A Custom Report carries no config of its own; issue #220 — discovery
        used to stop there and return nothing."""
        parent = _report_doc(name="Parent Report", module="Selling")
        parent.get.return_value = [{"fieldname": "company", "fieldtype": "Link", "mandatory": 1}]
        child = _report_doc(name="My Custom", report_type="Custom Report", reference_report="Parent Report")

        with patch.object(frappe, "get_doc", return_value=parent):
            parsed, diagnostics = self.tool._discover_report_filters("My Custom", child)

        self.assertEqual(diagnostics["reference_report"], "Parent Report")
        self.assertEqual([f["fieldname"] for f in parsed["filters"]], ["company"])


class TestQueryReportPlaceholders(BaseAssistantTest):
    """A Query Report's SQL placeholders are a binding filter contract."""

    def setUp(self):
        super().setUp()
        self.tool = ReportRequirements()

    def test_named_placeholders_become_required_filters(self):
        doc = _report_doc(
            report_type="Query Report",
            query="select name from `tabSales Order` where company = %(company)s and docstatus = %(status)s",
        )
        parsed, diagnostics = self.tool._discover_report_filters("Q", doc)

        self.assertEqual(sorted(parsed["required_filters"]), ["company", "status"])
        self.assertEqual(diagnostics["status"], "resolved")
        self.assertEqual(diagnostics["requiredness"], "declared_in_sql_placeholders")

    def test_query_without_placeholders_declares_no_filters(self):
        """This is an answer, not a failure — 12 Query Reports on a stock bench."""
        doc = _report_doc(report_type="Query Report", query="select name from `tabWork Order`")
        parsed, diagnostics = self.tool._discover_report_filters("Q", doc)

        self.assertEqual(parsed["filters"], [])
        self.assertEqual(diagnostics["status"], "no_filters_declared")

    def test_positional_placeholders_are_not_guessed(self):
        doc = _report_doc(report_type="Query Report", query="select name from `tabItem` where item_code = %s")
        parsed, diagnostics = self.tool._discover_report_filters("Q", doc)

        self.assertIsNone(parsed)
        self.assertIn("positional", diagnostics["query_placeholders"]["note"])


class TestNoInventedFilters(BaseAssistantTest):
    """Guidance for an unresolved report must not assert filter names.

    The previous implementation guessed from the report's name and was wrong
    for every report it matched: it claimed Profit and Loss Statement requires
    `from_date`/`to_date` and Balance Sheet requires `as_on_date`, none of
    which exist on those reports.
    """

    def setUp(self):
        super().setUp()
        self.tool = ReportRequirements()

    def test_generic_guidance_names_no_filters(self):
        for report_type in ("Script Report", "Query Report", "Custom Report", "Report Builder"):
            guidance = self.tool._generic_filter_guidance(report_type, {})
            self.assertEqual(guidance["common_required_filters"], [])
            self.assertEqual(guidance["common_optional_filters"], [])
            blob = " ".join(guidance["guidance"])
            for invented in ("as_on_date", "from_date", "to_date", "tree_type", "value_quantity"):
                self.assertNotIn(invented, blob)

    def test_name_pattern_guessing_is_gone(self):
        self.assertFalse(hasattr(self.tool, "_analyze_filter_requirements"))


class TestSharedNamespaceLoader(BaseAssistantTest):
    """The shared-JS lookup must stay inside installed apps' public/js trees."""

    def setUp(self):
        super().setUp()
        self.tool = ReportRequirements()

    def test_non_identifier_namespaces_are_rejected(self):
        for bad in ("../../etc/passwd", "erpnext/../../secret", "", "noDotsHere", "a..b", "a.b/c"):
            self.assertIsNone(self.tool._load_shared_namespace(bad))

    def test_unknown_namespace_returns_none(self):
        self.assertIsNone(self.tool._load_shared_namespace("definitely.not.a.real.namespace"))


class TestErpnextFinancialStatements(BaseAssistantTest):
    """End-to-end regression for the report named in issue #220."""

    def setUp(self):
        super().setUp()
        self.tool = ReportRequirements()
        if "erpnext" not in frappe.get_installed_apps():
            self.skipTest("erpnext not installed")
        if not frappe.db.exists("Report", "Profit and Loss Statement"):
            self.skipTest("Profit and Loss Statement not present")

    def test_profit_and_loss_resolves_the_real_contract(self):
        result = self.tool.execute({"report_name": "Profit and Loss Statement", "include_columns": False})
        self.assertTrue(result["success"])
        self.assertEqual(result["filter_discovery_status"], "resolved")

        names = [f["fieldname"] for f in result["filters_definition"]]
        # Inherited from erpnext.financial_statements via $.extend + get_filters()
        for expected in ("company", "filter_based_on", "periodicity", "from_fiscal_year"):
            self.assertIn(expected, names)
        # Appended by the report itself via ["filters"].push(...)
        for expected in ("selected_view", "accumulated_values", "include_default_book_entries"):
            self.assertIn(expected, names)
        # Fields the old fallback invented must not appear.
        self.assertNotIn("from_date", names)
        self.assertNotIn("to_date", names)

    def test_conditional_date_range_contract_is_preserved(self):
        result = self.tool.execute({"report_name": "Profit and Loss Statement", "include_columns": False})
        by_name = {f["fieldname"]: f for f in result["filters_definition"]}
        self.assertIn("period_start_date", by_name)
        self.assertEqual(
            by_name["period_start_date"]["mandatory_depends_on"],
            "eval:doc.filter_based_on == 'Date Range'",
        )
        self.assertIn("period_start_date", result.get("conditional_filter_names", []))

    def test_select_options_are_clean_values(self):
        result = self.tool.execute({"report_name": "Profit and Loss Statement", "include_columns": False})
        by_name = {f["fieldname"]: f for f in result["filters_definition"]}
        self.assertEqual(by_name["selected_view"]["options"], ["Report", "Growth", "Margin"])
        self.assertEqual(by_name["periodicity"]["options"], ["Monthly", "Quarterly", "Half-Yearly", "Yearly"])
