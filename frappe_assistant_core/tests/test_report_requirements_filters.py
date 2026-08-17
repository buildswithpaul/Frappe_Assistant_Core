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
Regression tests for: https://github.com/buildswithpaul/Frappe_Assistant_Core/issues/203

report_requirements returned empty filter definitions for custom Script Reports
whose filters are defined in the .js file, and did so silently. Reproduced two
real triggers and verified the fixes:

  * JSON-style quoted keys ("fieldname": "x") — the regex only matched bare
    keys (fieldname:), so every filter object was skipped.
  * filters built programmatically (filters: get_filters()) — the builder's
    returned array is resolved instead of being discarded.

Also adds the Report.filters child table as a discovery source, and a
discovery_diagnostics payload so empty results are debuggable.
"""

from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.plugins.core.tools.report_requirements import ReportRequirements
from frappe_assistant_core.tests.base_test import BaseAssistantTest

_BARE_KEYS = """
frappe.query_reports["X"] = { filters: [
    { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", reqd: 1 },
    { fieldname: "bom", label: __("BOM"), fieldtype: "Link", options: "BOM" }
] };
"""

_QUOTED_KEYS = """
frappe.query_reports["X"] = { "filters": [
    { "fieldname": "company", "label": __("Company"), "fieldtype": "Link", "options": "Company", "reqd": 1 },
    { "fieldname": "bom", "label": __("BOM"), "fieldtype": "Link", "options": "BOM" }
] };
"""

_PROGRAMMATIC = """
function gf() { return [ { fieldname: "company", fieldtype: "Link", options: "Company", reqd: 1 } ]; }
frappe.query_reports["X"] = { filters: gf() };
"""

_TEMPLATE_LITERAL = """
frappe.query_reports["X"] = { filters: [
    { fieldname: "company", label: `Company`, fieldtype: "Link", options: "Company", reqd: 1 }
] };
"""


class TestJsFilterParsing(BaseAssistantTest):
    """The JS parser must tolerate the legal syntax variants that previously
    produced a silent empty result."""

    def setUp(self):
        super().setUp()
        self.tool = ReportRequirements()

    def test_bare_keys_parse(self):
        parsed, note = self.tool._extract_filters_from_js(_BARE_KEYS)
        self.assertIsNone(note)
        self.assertEqual([f["fieldname"] for f in parsed["filters"]], ["company", "bom"])
        self.assertEqual(parsed["required_filters"], ["company"])

    def test_quoted_keys_parse(self):
        """Regression: JSON-style quoted keys used to yield 0 filters."""
        parsed, note = self.tool._extract_filters_from_js(_QUOTED_KEYS)
        self.assertIsNone(note)
        self.assertEqual([f["fieldname"] for f in parsed["filters"]], ["company", "bom"])
        self.assertEqual(parsed["required_filters"], ["company"])

    def test_template_literal_label_parses_fieldname(self):
        parsed, note = self.tool._extract_filters_from_js(_TEMPLATE_LITERAL)
        self.assertIsNone(note)
        self.assertEqual(parsed["filters"][0]["fieldname"], "company")
        self.assertEqual(parsed["filters"][0].get("label"), "Company")

    def test_programmatic_filters_resolve_local_builder(self):
        """A local get_filters() builder is a discoverable filter source."""
        parsed, note = self.tool._extract_filters_from_js(_PROGRAMMATIC)
        self.assertIsNone(note)
        self.assertEqual([f["fieldname"] for f in parsed["filters"]], ["company"])
        self.assertEqual(parsed["required_filters"], ["company"])

    def test_missing_filters_key_reports_note(self):
        parsed, note = self.tool._extract_filters_from_js("frappe.query_reports['X'] = {};")
        self.assertIsNone(parsed)
        self.assertIn("no 'filters:' key", note)


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
        rows = [{"label": "No fieldname"}, {"fieldname": "ok"}]
        parsed = self.tool._parse_filters_child_table(rows)
        self.assertEqual([f["fieldname"] for f in parsed["filters"]], ["ok"])


class TestDiscoveryOrchestration(BaseAssistantTest):
    """_discover_report_filters prefers the child table and always
    returns a diagnostics payload."""

    def setUp(self):
        super().setUp()
        self.tool = ReportRequirements()

    def test_child_table_wins_and_short_circuits_js(self):
        report_doc = MagicMock()
        report_doc.module = "Selling"
        report_doc.get.return_value = [
            {"fieldname": "company", "label": "Company", "fieldtype": "Link", "mandatory": 1}
        ]

        parsed, diagnostics = self.tool._discover_report_filters("Some Report", report_doc)

        self.assertEqual([f["fieldname"] for f in parsed["filters"]], ["company"])
        self.assertEqual(diagnostics["filters_child_table"]["status"], "success")
        # JS path not attempted when the child table satisfied discovery.
        self.assertNotIn("javascript", diagnostics)

    def test_empty_child_table_falls_through_to_js_with_diagnostics(self):
        report_doc = MagicMock()
        report_doc.module = "Nonexistent Module XYZ"
        report_doc.get.return_value = []  # empty child table

        parsed, diagnostics = self.tool._discover_report_filters("No Such Report", report_doc)

        self.assertIsNone(parsed)
        self.assertEqual(diagnostics["filters_child_table"]["status"], "empty")
        # JS discovery was attempted and recorded (even though it found nothing).
        self.assertIn("javascript", diagnostics)


class TestERPNextSharedFilters(BaseAssistantTest):
    """Standard ERPNext financial reports inherit filters from shared JavaScript."""

    def setUp(self):
        super().setUp()
        self.tool = ReportRequirements()

    def test_financial_statement_fallback_uses_period_filter_names(self):
        requirements = self.tool._analyze_filter_requirements("Profit and Loss Statement", "Script Report")

        rendered = str(requirements)
        self.assertIn("period_start_date", rendered)
        self.assertIn("period_end_date", rendered)
        self.assertIn("filter_based_on", rendered)
        self.assertIn("does not use from_date and to_date", rendered)

    def test_profit_and_loss_discovers_real_filter_contract(self):
        if "erpnext" not in frappe.get_installed_apps():
            self.skipTest("ERPNext is not installed")

        parsed = self.tool._parse_script_report_filters("Profit and Loss Statement", "Accounts")

        self.assertIsNotNone(parsed)
        fieldnames = [filter_def["fieldname"] for filter_def in parsed["filters"]]
        self.assertIn("company", fieldnames)
        self.assertIn("filter_based_on", fieldnames)
        self.assertIn("period_start_date", fieldnames)
        self.assertIn("period_end_date", fieldnames)
        self.assertIn("periodicity", fieldnames)
        self.assertIn("selected_view", fieldnames)
        self.assertNotIn("from_date", fieldnames)
        self.assertNotIn("to_date", fieldnames)
        self.assertIn("company", parsed["required_filters"])
        self.assertIn("periodicity", parsed["required_filters"])
        self.assertIn("period_start_date", parsed["conditional_required_filters"])
        self.assertIn("period_end_date", parsed["conditional_required_filters"])

        definitions = {item["fieldname"]: item for item in parsed["filters"]}
        self.assertEqual(definitions["filter_based_on"]["options"], ["Fiscal Year", "Date Range"])
        self.assertIn("Date Range", definitions["period_start_date"]["mandatory_depends_on"])


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


def _patched_get_doc(overrides):
    """Patch frappe.get_doc for specific (doctype, name) pairs only.

    A blanket patch also intercepts frappe.get_cached_value, which routes
    through get_cached_doc -> get_doc, so unrelated framework lookups would
    blow up and mask what the test is actually asserting.
    """
    real_get_doc = frappe.get_doc

    def fake(*args, **kwargs):
        key = tuple(args[:2]) if len(args) >= 2 and all(isinstance(a, str) for a in args[:2]) else None
        result = overrides.get(key) if key else None
        if isinstance(result, Exception):
            raise result
        if result is not None:
            return result
        return real_get_doc(*args, **kwargs)

    return patch.object(frappe, "get_doc", side_effect=fake)


class TestDiscoveryRunsForEveryReportType(BaseAssistantTest):
    """Issue #223: discovery used to be gated to Script Reports, so every other
    type returned no filters AND no diagnostics — indistinguishable from a
    report that genuinely takes none."""

    def setUp(self):
        super().setUp()
        self.tool = ReportRequirements()

    def test_diagnostics_always_carry_a_status(self):
        for report_type in ("Script Report", "Query Report", "Custom Report", "Report Builder"):
            _parsed, diagnostics = self.tool._discover_report_filters(
                "X", _report_doc(report_type=report_type)
            )
            self.assertIn("status", diagnostics, report_type)
            self.assertIn(
                diagnostics["status"], ("resolved", "no_filters_declared", "unresolved"), report_type
            )

    def test_custom_report_inherits_from_reference_report(self):
        """A Custom Report has no configuration of its own; its contract is the
        report named in reference_report."""
        parent = _report_doc(name="Parent Report", module="Selling")
        parent.get.return_value = [{"fieldname": "company", "fieldtype": "Link", "mandatory": 1}]
        child = _report_doc(
            name="My Custom",
            report_type="Custom Report",
            reference_report="Parent Report",
            module="Selling",
        )

        with _patched_get_doc({("Report", "Parent Report"): parent}):
            parsed, diagnostics = self.tool._discover_report_filters("My Custom", child)

        self.assertEqual(diagnostics["reference_report"], "Parent Report")
        self.assertEqual([f["fieldname"] for f in parsed["filters"]], ["company"])

    def test_missing_reference_report_is_diagnosed_not_raised(self):
        child = _report_doc(report_type="Custom Report", reference_report="Gone", module="Selling")
        with _patched_get_doc({("Report", "Gone"): Exception("not found")}):
            _parsed, diagnostics = self.tool._discover_report_filters("My Custom", child)
        self.assertIn("reference_report_error", diagnostics)
        self.assertIn("status", diagnostics)


class TestQueryReportPlaceholders(BaseAssistantTest):
    """A Query Report's SQL placeholders are a binding filter contract:
    frappe.db.sql() raises when a named placeholder has no value."""

    def setUp(self):
        super().setUp()
        self.tool = ReportRequirements()

    def test_named_placeholders_become_required_filters(self):
        doc = _report_doc(
            report_type="Query Report",
            query="select name from `tabSales Order` where company = %(company)s and docstatus = %(status)s",
        )
        parsed, diagnostics = self.tool._discover_report_filters("Q", doc)

        self.assertEqual(parsed["required_filters"], ["company", "status"])
        self.assertEqual(diagnostics["status"], "resolved")

    def test_placeholders_are_deduplicated_in_order(self):
        doc = _report_doc(
            report_type="Query Report",
            query="select a from t where c = %(company)s or d = %(company)s or e = %(year)s",
        )
        parsed, _diagnostics = self.tool._discover_report_filters("Q", doc)
        self.assertEqual(parsed["required_filters"], ["company", "year"])

    def test_query_without_placeholders_declares_no_filters(self):
        """A positive answer, not a failure — 12 Query Reports on a stock bench."""
        doc = _report_doc(report_type="Query Report", query="select name from `tabWork Order`")
        _parsed, diagnostics = self.tool._discover_report_filters("Q", doc)
        self.assertEqual(diagnostics["status"], "no_filters_declared")

    def test_positional_placeholders_are_not_guessed(self):
        for query in (
            "select name from `tabItem` where item_code = %s",
            "select name from `tabItem` where item_group in (%s)",
            "select name, ifnull(item_name, %s) from `tabItem`",
        ):
            doc = _report_doc(report_type="Query Report", query=query)
            _parsed, diagnostics = self.tool._discover_report_filters("Q", doc)
            self.assertEqual(diagnostics["status"], "unresolved", query)
            self.assertIn("positional", diagnostics["query_placeholders"]["note"])

    def test_escaped_percent_is_not_a_positional_placeholder(self):
        """LIKE '%%foo%%' and date_format(t,'%%H:%%i:%%s') are literal percents."""
        doc = _report_doc(
            report_type="Query Report",
            query="select date_format(creation, '%%H:%%i:%%s') from `tabItem` where name like '%%sales%%'",
        )
        _parsed, diagnostics = self.tool._discover_report_filters("Q", doc)
        self.assertEqual(diagnostics["status"], "no_filters_declared")

    def test_script_reports_do_not_use_the_sql_source(self):
        doc = _report_doc(report_type="Script Report", query="select %(company)s from t")
        _parsed, diagnostics = self.tool._discover_report_filters("S", doc)
        self.assertNotIn("query_placeholders", diagnostics)
