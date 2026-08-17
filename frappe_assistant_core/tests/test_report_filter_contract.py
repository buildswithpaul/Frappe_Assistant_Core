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
Regression tests for: https://github.com/buildswithpaul/Frappe_Assistant_Core/issues/229

report_requirements is the discovery tool a model is told to call before
generate_report, and the two disagreed about their own contract: the validator
carried a hardcoded fieldname -> accepted-values map that had nothing to do with
the report being run.

`range` alone means four different things across the standard apps:

  * Data ageing buckets — "30, 60, 90, 120" on Accounts Payable/Receivable
    (+ Summary) and "30, 60, 90" on Stock Ageing. The map rejected every one of
    these advertised defaults.
  * Weekly|Monthly|Quarterly|Half-Yearly|Yearly on Sales and Stock Analytics.
  * Daily|Weekly|Monthly on Website Analytics — 'Daily' was rejected.
  * Monthly|Quarterly on Sales Pipeline Analytics — the map accepted 'Weekly',
    which that report does not offer.

Validation is now driven by the report's own declared filter definitions, the
same discovery report_requirements advertises from. The contract test at the
bottom is the audit: it asserts every advertised default is executable, for every
report report_list exposes.
"""

from unittest.mock import MagicMock

import frappe

from frappe_assistant_core.plugins.core.tools.report_requirements import (
    ReportRequirements,
    discover_filter_definitions,
    normalize_filter_options,
)
from frappe_assistant_core.plugins.core.tools.report_tools import ReportTools
from frappe_assistant_core.tests.base_test import BaseAssistantTest

# The real Accounts Payable Summary and Sales Pipeline Analytics contracts, which
# assign incompatible meanings to the same fieldname.
AGEING_RANGE = {
    "fieldname": "range",
    "label": "Ageing Range",
    "fieldtype": "Data",
    "default": "30, 60, 90, 120",
}
PERIODICITY_RANGE = {
    "fieldname": "range",
    "label": "Range",
    "fieldtype": "Select",
    "options": ["Monthly", "Quarterly"],
    "default": "Monthly",
}


def report_stub(name="Test Report", report_type="Script Report"):
    doc = MagicMock()
    doc.name = name
    doc.report_type = report_type
    return doc


class TestNormalizeFilterOptions(BaseAssistantTest):
    """A constrained value set must be advertised as an explicit list of values."""

    def test_escaped_newline_string_becomes_a_list(self):
        """Read from a .js file, so the newline arrives as a literal backslash-n."""
        filter_def = normalize_filter_options(
            {"fieldname": "range", "fieldtype": "Select", "options": "Monthly\\nQuarterly"}
        )
        self.assertEqual(filter_def["options"], ["Monthly", "Quarterly"])

    def test_real_newline_string_becomes_a_list(self):
        """A Report.filters child-table row carries a real newline."""
        filter_def = normalize_filter_options(
            {"fieldname": "ageing_based_on", "fieldtype": "Select", "options": "Posting Date\nDue Date"}
        )
        self.assertEqual(filter_def["options"], ["Posting Date", "Due Date"])

    def test_list_options_are_cleaned(self):
        filter_def = normalize_filter_options(
            {"fieldname": "range", "fieldtype": "Select", "options": [" Weekly ", "", "Monthly"]}
        )
        self.assertEqual(filter_def["options"], ["Weekly", "Monthly"])

    def test_autocomplete_is_also_value_constrained(self):
        filter_def = normalize_filter_options(
            {"fieldname": "party_type", "fieldtype": "Autocomplete", "options": "Customer\\nSupplier"}
        )
        self.assertEqual(filter_def["options"], ["Customer", "Supplier"])

    def test_link_options_are_a_doctype_not_a_value_set(self):
        filter_def = normalize_filter_options(
            {"fieldname": "company", "fieldtype": "Link", "options": "Company"}
        )
        self.assertEqual(filter_def["options"], "Company", "a Link target must stay a DocType name")

    def test_missing_options_left_alone(self):
        filter_def = normalize_filter_options({"fieldname": "range", "fieldtype": "Data"})
        self.assertNotIn("options", filter_def)


class TestOptionsArrayParsing(BaseAssistantTest):
    """Option arrays are parsed straight out of report JS."""

    def setUp(self):
        super().setUp()
        self.tool = ReportRequirements()

    def _options_for(self, js_options):
        parsed = self.tool._parse_js_filter_array(
            f'{{ fieldname: "group_by", fieldtype: "Select", options: {js_options} }}'
        )
        return parsed["filters"][0].get("options")

    def test_empty_first_option_does_not_shift_the_values(self):
        """Regression: a leading "" made naive quote-pairing capture the separators.

        POS Register advertised options of [", ", ", ", ", ", ", "] because of this.
        """
        self.assertEqual(
            self._options_for('["", "POS Profile", "Cashier", "Payment Method", "Customer"]'),
            ["POS Profile", "Cashier", "Payment Method", "Customer"],
        )

    def test_plain_string_array(self):
        self.assertEqual(self._options_for('["Value", "Quantity"]'), ["Value", "Quantity"])

    def test_value_label_object_array_returns_values_only(self):
        self.assertEqual(
            self._options_for(
                '[{ value: "Daily", label: __("Daily") }, { value: "Weekly", label: __("Weekly") }]'
            ),
            ["Daily", "Weekly"],
        )

    def test_translated_string_array(self):
        self.assertEqual(self._options_for('[__("Open"), __("Closed")]'), ["Open", "Closed"])


class TestDefinitionDrivenValidation(BaseAssistantTest):
    """Accepted values come from the report being run, not from a global guess."""

    def _validate(self, filters, definitions):
        return ReportTools._validate_filters(filters, report_stub(), definitions)

    def test_ageing_range_default_is_accepted(self):
        """The reported failure: the advertised default was rejected outright."""
        result = self._validate({"range": "30, 60, 90, 120"}, {"range": AGEING_RANGE})

        self.assertTrue(result["valid"], result["errors"])

    def test_stock_ageing_range_default_is_accepted(self):
        result = self._validate({"range": "30, 60, 90"}, {"range": dict(AGEING_RANGE, default="30, 60, 90")})

        self.assertTrue(result["valid"], result["errors"])

    def test_periodicity_range_accepts_its_own_option(self):
        result = self._validate({"range": "Monthly"}, {"range": PERIODICITY_RANGE})

        self.assertTrue(result["valid"], result["errors"])

    def test_periodicity_range_rejects_a_value_it_does_not_offer(self):
        """The map accepted Weekly here; Sales Pipeline Analytics does not offer it."""
        result = self._validate({"range": "Weekly"}, {"range": PERIODICITY_RANGE})

        self.assertFalse(result["valid"])
        self.assertEqual(result["error_details"][0]["type"], "invalid_option")
        self.assertEqual(result["error_details"][0]["accepted_values"], ["Monthly", "Quarterly"])

    def test_error_message_lists_the_accepted_values(self):
        """Preserved from the previous behaviour, and now the values are correct."""
        result = self._validate({"range": "Weekly"}, {"range": PERIODICITY_RANGE})

        self.assertIn("Must be one of: Monthly, Quarterly", result["errors"][0])

    def test_same_fieldname_validated_differently_per_report(self):
        """One fieldname, two reports, two contracts — the point of the fix."""
        self.assertTrue(self._validate({"range": "30, 60, 90, 120"}, {"range": AGEING_RANGE})["valid"])
        self.assertFalse(self._validate({"range": "30, 60, 90, 120"}, {"range": PERIODICITY_RANGE})["valid"])

    def test_undeclared_filter_is_not_second_guessed(self):
        """Guessing at a filter the report never declared is what caused this bug."""
        result = self._validate({"range": "anything at all"}, {})

        self.assertTrue(result["valid"], result["errors"])

    def test_multi_value_selection_is_not_treated_as_an_enum_choice(self):
        result = self._validate({"range": ["Monthly", "Quarterly"]}, {"range": PERIODICITY_RANGE})

        self.assertTrue(result["valid"], result["errors"])

    def test_empty_values_are_skipped(self):
        result = self._validate({"range": "", "other": None}, {"range": PERIODICITY_RANGE})

        self.assertTrue(result["valid"], result["errors"])

    def test_invalid_date_is_reported(self):
        result = self._validate(
            {"report_date": "not a date"}, {"report_date": {"fieldname": "report_date", "fieldtype": "Date"}}
        )

        self.assertFalse(result["valid"])
        self.assertEqual(result["error_details"][0]["type"], "invalid_date")

    def test_unambiguous_alternative_date_format_is_accepted(self):
        """getdate() is deliberately lenient; only unparseable input is an error."""
        result = self._validate(
            {"report_date": "31-12-2024"}, {"report_date": {"fieldname": "report_date", "fieldtype": "Date"}}
        )

        self.assertTrue(result["valid"], result["errors"])

    def test_valid_date_passes(self):
        result = self._validate(
            {"report_date": "2024-12-31"}, {"report_date": {"fieldname": "report_date", "fieldtype": "Date"}}
        )

        self.assertTrue(result["valid"], result["errors"])

    def test_unknown_link_record_is_reported_with_suggestions(self):
        definitions = {"company": {"fieldname": "company", "fieldtype": "Link", "options": "Company"}}
        result = self._validate({"company": "No Such Company 229"}, definitions)

        self.assertFalse(result["valid"])
        self.assertEqual(result["error_details"][0]["type"], "unknown_record")
        self.assertEqual(result["error_details"][0]["target_doctype"], "Company")

    def test_existing_link_record_passes(self):
        company = frappe.db.get_value("Company", {}, "name")
        if not company:
            self.skipTest("no Company records on this site")

        definitions = {"company": {"fieldname": "company", "fieldtype": "Link", "options": "Company"}}
        result = self._validate({"company": company}, definitions)

        self.assertTrue(result["valid"], result["errors"])

    def test_link_options_naming_a_companion_field_is_not_a_doctype(self):
        """Accounts Payable Summary's `party` has options: "party_type", a fieldname."""
        definitions = {"party": {"fieldname": "party", "fieldtype": "Link", "options": "party_type"}}
        result = self._validate({"party": "Some Supplier"}, definitions)

        self.assertTrue(result["valid"], result["errors"])


class TestFilterDefaultsUseSharedDiscovery(BaseAssistantTest):
    """Auto-applied defaults come from the same definitions that are advertised."""

    def test_declared_defaults_are_applied(self):
        filters = {}
        ReportTools._apply_filter_defaults(report_stub(), filters, {"range": AGEING_RANGE})

        self.assertEqual(filters["range"], "30, 60, 90, 120")

    def test_caller_values_are_never_overridden(self):
        filters = {"range": "15, 30"}
        ReportTools._apply_filter_defaults(report_stub(), filters, {"range": AGEING_RANGE})

        self.assertEqual(filters["range"], "15, 30")

    def test_definitions_without_defaults_add_nothing(self):
        filters = {}
        ReportTools._apply_filter_defaults(
            report_stub(), filters, {"company": {"fieldname": "company", "fieldtype": "Link"}}
        )

        self.assertEqual(filters, {})

    def test_applied_default_passes_validation(self):
        """The two halves of the contract, checked against each other."""
        definitions = {"range": AGEING_RANGE}
        filters = ReportTools._apply_filter_defaults(report_stub(), {}, definitions)

        self.assertTrue(ReportTools._validate_filters(filters, report_stub(), definitions)["valid"])


class TestAdvertisedDefaultsAreExecutable(BaseAssistantTest):
    """The contract test: what report_requirements advertises, generate_report accepts.

    This is the test that would have caught the original mismatch, and it is the
    standing audit across every report report_list exposes.
    """

    def _exposed_reports(self, report_type):
        listing = ReportTools.list_reports(report_type=report_type)
        self.assertTrue(listing.get("success"), listing)
        return [r for r in listing.get("reports", []) if not r.get("disabled")]

    def _contract_failures(self, report_type):
        failures = []
        checked = 0
        tool = ReportRequirements()

        for report in self._exposed_reports(report_type):
            try:
                requirements = tool.execute({"report_name": report.name, "include_columns": False})
            except Exception as e:
                failures.append(f"{report.name}: report_requirements raised {type(e).__name__}: {e}")
                continue

            if not requirements.get("success"):
                continue

            definitions = requirements.get("filters_definition") or []
            advertised = {
                d["fieldname"]: d["default"]
                for d in definitions
                if d.get("fieldname") and d.get("default") not in (None, "")
            }

            # A constrained filter must advertise its default as one of its own values.
            for definition in definitions:
                options = definition.get("options")
                default = definition.get("default")
                if definition.get("fieldtype") != "Select" or not isinstance(options, list) or not options:
                    continue
                if default and default not in options:
                    failures.append(
                        f"{report.name}.{definition['fieldname']}: default {default!r} "
                        f"is not among its advertised options {options}"
                    )

            if not advertised:
                continue

            checked += 1
            report_doc = frappe.get_doc("Report", report.name)
            validation = ReportTools._validate_filters(dict(advertised), report_doc)

            for detail in validation.get("error_details", []):
                # A missing record depends on this instance's data, not on the
                # advertise/validate contract.
                if detail["type"] == "unknown_record":
                    continue
                failures.append(
                    f"{report.name}.{detail['fieldname']}: advertised default {detail['value']!r} "
                    f"rejected as {detail['type']} (accepted: {detail.get('accepted_values')})"
                )

        return failures, checked

    def test_script_report_advertised_defaults_are_accepted(self):
        failures, checked = self._contract_failures("Script Report")

        if not checked:
            self.skipTest("no Script Reports with advertised defaults on this site")
        self.assertEqual(
            failures, [], f"{len(failures)} advertise/validate mismatches across {checked} Script Reports"
        )

    def test_query_report_advertised_defaults_are_accepted(self):
        failures, _checked = self._contract_failures("Query Report")

        self.assertEqual(failures, [], f"{len(failures)} advertise/validate mismatches in Query Reports")

    def test_known_offenders_now_pass(self):
        """The six reports the audit surfaced, named so a regression is unambiguous."""
        offenders = {
            "Accounts Payable": "30, 60, 90, 120",
            "Accounts Payable Summary": "30, 60, 90, 120",
            "Accounts Receivable": "30, 60, 90, 120",
            "Accounts Receivable Summary": "30, 60, 90, 120",
            "Stock Ageing": "30, 60, 90",
            "Website Analytics": "Daily",
        }

        tested = 0
        for report_name, advertised_range in offenders.items():
            if not frappe.db.exists("Report", report_name):
                continue
            tested += 1
            report_doc = frappe.get_doc("Report", report_name)
            definitions = discover_filter_definitions(report_doc)
            self.assertIn("range", definitions, f"{report_name} must declare a range filter")

            result = ReportTools._validate_filters({"range": advertised_range}, report_doc, definitions)
            self.assertTrue(result["valid"], f"{report_name}: {result['errors']}")

        if not tested:
            self.skipTest("none of the audited reports are installed")

    def test_sales_pipeline_analytics_rejects_weekly(self):
        """The permissive half of the same bug, against live metadata."""
        if not frappe.db.exists("Report", "Sales Pipeline Analytics"):
            self.skipTest("Sales Pipeline Analytics not installed")

        report_doc = frappe.get_doc("Report", "Sales Pipeline Analytics")
        definitions = discover_filter_definitions(report_doc)
        self.assertEqual(definitions["range"]["options"], ["Monthly", "Quarterly"])

        result = ReportTools._validate_filters({"range": "Weekly"}, report_doc, definitions)
        self.assertFalse(result["valid"], "Weekly is not an option this report offers")
