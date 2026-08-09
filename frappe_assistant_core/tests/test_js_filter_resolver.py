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
Regression tests for: https://github.com/buildswithpaul/Frappe_Assistant_Core/issues/220

``report_requirements`` misreported the filter contract of reports whose
filters are composed across files — a shared namespace supplies a base array
through a builder function and the report appends its own with ``.push()``.

These tests exercise the resolver directly. It imports nothing from frappe, so
this module runs standalone::

    python -m unittest frappe_assistant_core.tests.test_js_filter_resolver

Every snippet below is a minimal reproduction of a shape that exists in shipped
Frappe/ERPNext report JS. Where a test pins a defect, the docstring names it.
"""

import unittest

from frappe_assistant_core.plugins.core.tools.js_filter_resolver import (
    Unresolved,
    resolve_filters,
    scan,
)

# --- Shared namespace, ERPNext ``erpnext.financial_statements`` shape --------
SHARED_FINANCIAL = """
frappe.provide("erpnext.financial_statements");

erpnext.financial_statements = {
	filters: get_filters(),
	formatter: function (value, row, column, data, default_formatter) {
		return default_formatter(value, row, column, data);
	},
};

function get_filters() {
	let filters = [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "filter_based_on",
			label: __("Filter Based On"),
			fieldtype: "Select",
			options: ["Fiscal Year", "Date Range"],
			default: ["Fiscal Year"],
			reqd: 1,
		},
		{
			fieldname: "period_start_date",
			label: __("Start Date"),
			fieldtype: "Date",
			depends_on: "eval:doc.filter_based_on == 'Date Range'",
			mandatory_depends_on: "eval:doc.filter_based_on == 'Date Range'",
		},
		{
			fieldname: "from_fiscal_year",
			label: __("Start Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
			reqd: 1,
			depends_on: "eval:doc.filter_based_on == 'Fiscal Year'",
		},
		{
			fieldname: "presentation_currency",
			label: __("Currency"),
			fieldtype: "Select",
			options: erpnext.get_presentation_currency_list(),
		},
		{
			fieldname: "cost_center",
			label: __("Cost Center"),
			fieldtype: "MultiSelectList",
			get_data: function (txt) {
				return frappe.db.get_link_options("Cost Center", txt);
			},
			options: "Cost Center",
		},
	];

	let fy_filters = filters.filter((x) => {
		return ["from_fiscal_year"].includes(x.fieldname);
	});
	fy_filters.forEach((x) => {
		x.default = "2025-2026";
	});

	return filters;
}
"""

# ``$.extend({}, ns)`` then three pushes — profit_and_loss_statement.js shape.
PNL = """
frappe.query_reports["Profit and Loss Statement"] = $.extend({}, erpnext.financial_statements);

erpnext.utils.add_dimensions("Profit and Loss Statement", 10);

frappe.query_reports["Profit and Loss Statement"]["filters"].push({
	fieldname: "selected_view",
	label: __("Select View"),
	fieldtype: "Select",
	options: [
		{ value: "Report", label: __("Report View") },
		{ value: "Growth", label: __("Growth View") },
	],
	default: "Report",
	reqd: 1,
});

frappe.query_reports["Profit and Loss Statement"]["filters"].push({
	fieldname: "accumulated_values",
	label: __("Accumulated Values"),
	fieldtype: "Check",
	default: 1,
});
"""

# ``$.extend(ns, {...})`` — namespace as the FIRST argument — plus a splice.
CASH_FLOW = """
frappe.query_reports["Cash Flow"] = $.extend(erpnext.financial_statements, {
	name_field: "section",
});

frappe.query_reports["Cash Flow"]["filters"].splice(4, 1);

frappe.query_reports["Cash Flow"]["filters"].push({
	fieldname: "include_default_book_entries",
	label: __("Include Default FB Entries"),
	fieldtype: "Check",
	default: 1,
});
"""


def _shared_loader(mapping):
    return lambda namespace: mapping.get(namespace)


FINANCIAL_LOADER = _shared_loader({"erpnext.financial_statements": SHARED_FINANCIAL})


class TestScanner(unittest.TestCase):
    """The lexical layer must know where strings and comments begin and end."""

    def test_comment_bodies_are_blanked(self):
        sanitized, code, clean = scan('let a = 1; // filters: [{fieldname: "x"}]\nlet b = 2;')
        self.assertTrue(clean)
        self.assertNotIn("fieldname", sanitized)
        self.assertNotIn("fieldname", code)

    def test_string_contents_blanked_in_sanitized_but_kept_in_code(self):
        sanitized, code, clean = scan('let a = "has } brace and // slashes";')
        self.assertTrue(clean)
        self.assertNotIn("}", sanitized)
        self.assertIn("}", code)

    def test_offsets_are_preserved(self):
        source = 'a = "xx"; /* yy */ b = 1;'
        sanitized, code, _clean = scan(source)
        self.assertEqual(len(sanitized), len(source))
        self.assertEqual(len(code), len(source))

    def test_url_inside_string_is_not_a_comment(self):
        sanitized, _code, clean = scan('let u = "https://example.com/x"; let v = 1;')
        self.assertTrue(clean)
        self.assertIn("let v = 1;", sanitized)

    def test_unterminated_string_is_reported(self):
        _sanitized, _code, clean = scan('let a = "never closed;')
        self.assertFalse(clean)


class TestNoFabrication(unittest.TestCase):
    """The highest-severity class: asserting filters that do not exist.

    A wrong filter list is worse than an empty one — the caller sends a
    fabricated value, gets an empty result set, and reports it as a finding.
    """

    def test_fully_commented_out_config_yields_no_filters(self):
        """Regression: the old regex parser read `my_filter` out of a file whose
        entire contents are commented out, and reported it as required."""
        js = """
// frappe.query_reports["Calculated Discount Mismatch"] = {
// 	filters: [
// 		{
// 			"fieldname": "my_filter",
// 			"label": __("My Filter"),
// 			"fieldtype": "Data",
// 			"reqd": 1,
// 		},
// 	],
// };
"""
        result = resolve_filters(js, report_name="Calculated Discount Mismatch")
        self.assertEqual(result.filters, [])
        self.assertEqual(result.status, "no_filters_declared")

    def test_block_commented_config_yields_no_filters(self):
        js = '/* frappe.query_reports["X"] = { filters: [{fieldname: "ghost", reqd: 1}] }; */'
        result = resolve_filters(js, report_name="X")
        self.assertEqual(result.filters, [])

    def test_report_name_in_a_comment_does_not_create_filters(self):
        js = """
// See also frappe.query_reports["Other Report"]
frappe.query_reports["X"] = { filters: [{ fieldname: "real", fieldtype: "Data" }] };
"""
        result = resolve_filters(js, report_name="X")
        self.assertEqual([f["fieldname"] for f in result.filters], ["real"])

    def test_option_values_are_never_raw_js_fragments(self):
        """Every option must be a clean value — never `, { value: ` or `__(`."""
        result = resolve_filters(PNL, report_name="Profit and Loss Statement", load_shared=FINANCIAL_LOADER)
        for filter_def in result.filters:
            options = filter_def.get("options")
            if not isinstance(options, list):
                continue
            for option in options:
                if not isinstance(option, str):
                    continue
                for fragment in ("{", "}", "__(", "value:", "label:"):
                    self.assertNotIn(fragment, option, f"{filter_def['fieldname']} option {option!r}")


class TestEmptyIsAnAnswer(unittest.TestCase):
    """ "No filters declared" must be distinguishable from "could not parse"."""

    def test_explicit_empty_array(self):
        result = resolve_filters('frappe.query_reports["X"] = { filters: [] };', report_name="X")
        self.assertEqual(result.status, "no_filters_declared")
        self.assertEqual(result.filters, [])

    def test_empty_config_object(self):
        result = resolve_filters('frappe.query_reports["X"] = {};', report_name="X")
        self.assertEqual(result.status, "no_filters_declared")

    def test_config_without_filters_key(self):
        js = 'frappe.query_reports["X"] = { onload: function (r) { r.x = 1; } };'
        result = resolve_filters(js, report_name="X")
        self.assertEqual(result.status, "no_filters_declared")

    def test_genuinely_unparseable_stays_unresolved(self):
        js = 'frappe.query_reports["X"] = { filters: buildThem() };'
        result = resolve_filters(js, report_name="X")
        self.assertEqual(result.status, "unresolved")
        self.assertTrue(any("buildThem" in n for n in result.notes))


class TestLiteralArrays(unittest.TestCase):
    """Shapes covered by issue #203 must keep working."""

    def test_bare_keys(self):
        js = """
frappe.query_reports["X"] = { filters: [
    { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", reqd: 1 },
    { fieldname: "bom", label: __("BOM"), fieldtype: "Link", options: "BOM" }
] };
"""
        result = resolve_filters(js, report_name="X")
        self.assertEqual([f["fieldname"] for f in result.filters], ["company", "bom"])
        self.assertTrue(result.filters[0]["required"])
        self.assertFalse(result.filters[1]["required"])

    def test_json_style_quoted_keys(self):
        js = """
frappe.query_reports["X"] = { "filters": [
    { "fieldname": "company", "label": __("Company"), "fieldtype": "Link", "reqd": 1 }
] };
"""
        result = resolve_filters(js, report_name="X")
        self.assertEqual([f["fieldname"] for f in result.filters], ["company"])
        self.assertTrue(result.filters[0]["required"])

    def test_template_literal_label(self):
        js = 'frappe.query_reports["X"] = { filters: [{ fieldname: "c", label: `Company` }] };'
        result = resolve_filters(js, report_name="X")
        self.assertEqual(result.filters[0]["label"], "Company")

    def test_apostrophe_in_translated_label_survives(self):
        """`__("Payable Account's Party")` used to kill the label match."""
        js = """frappe.query_reports["X"] = { filters: [
    { fieldname: "c", label: __("Show Net Values in Party Account's Report") }
] };"""
        result = resolve_filters(js, report_name="X")
        self.assertEqual(result.filters[0]["label"], "Show Net Values in Party Account's Report")

    def test_layout_breaks_are_not_filters(self):
        js = """frappe.query_reports["X"] = { filters: [
    { fieldtype: "Break" },
    { fieldname: "c", fieldtype: "Data" }
] };"""
        result = resolve_filters(js, report_name="X")
        self.assertEqual([f["fieldname"] for f in result.filters], ["c"])

    def test_mandatory_is_an_alias_for_reqd(self):
        js = 'frappe.query_reports["X"] = { filters: [{ fieldname: "c", mandatory: 1 }] };'
        result = resolve_filters(js, report_name="X")
        self.assertTrue(result.filters[0]["required"])

    def test_first_filters_key_is_not_blindly_taken(self):
        """A nested `filters:` inside get_query must not win over the real one."""
        js = """
function get_filters() {
	let filters = [
		{
			fieldname: "customer",
			fieldtype: "Link",
			get_query: function () {
				return { filters: [["Customer", "disabled", "=", 0]] };
			},
		},
		{ fieldname: "company", fieldtype: "Link", reqd: 1 },
	];
	return filters;
}
frappe.query_reports["X"] = { filters: get_filters() };
"""
        result = resolve_filters(js, report_name="X")
        self.assertEqual([f["fieldname"] for f in result.filters], ["customer", "company"])


class TestOptionForms(unittest.TestCase):
    """Every option shape found in shipped report JS."""

    def _options(self, options_js, fieldtype="Select"):
        js = (
            f'frappe.query_reports["X"] = {{ filters: [{{ fieldname: "f", '
            f'fieldtype: "{fieldtype}", options: {options_js} }}] }};'
        )
        return resolve_filters(js, report_name="X").filters[0]

    def test_array_of_strings(self):
        self.assertEqual(self._options('["A", "B"]')["options"], ["A", "B"])

    def test_array_of_value_label_objects_returns_values_only(self):
        got = self._options('[{ value: "Report", label: __("Report View") }]')
        self.assertEqual(got["options"], ["Report"])

    def test_numeric_values_survive(self):
        """`[{value: 1, label: __("Jan")}]` must yield [1], not [] and not labels."""
        got = self._options('[{ value: 1, label: __("Jan") }, { value: 2, label: __("Feb") }]')
        self.assertEqual(got["options"], [1, 2])

    def test_leading_blank_choice_is_dropped(self):
        """`["", {value: "Item"...}]` used to desync quote pairing entirely."""
        got = self._options(
            '["", { value: "Item", label: __("Item") }, { value: "Customer", label: __("Customer") }]'
        )
        self.assertEqual(got["options"], ["Item", "Customer"])

    def test_newline_joined_select_string_is_split(self):
        got = self._options('"\\nDraft\\nSubmitted\\nCancelled"')
        self.assertEqual(got["options"], ["Draft", "Submitted", "Cancelled"])

    def test_link_doctype_string_kept_as_string(self):
        got = self._options('"Company"', fieldtype="Link")
        self.assertEqual(got["options"], "Company")

    def test_runtime_call_is_flagged_not_dropped(self):
        got = self._options("erpnext.get_presentation_currency_list()")
        self.assertNotIn("options", got)
        self.assertEqual(got["options_source"], "runtime")
        self.assertIn("get_presentation_currency_list", got["options_expr"])

    def test_get_data_callback_flags_runtime_options(self):
        js = """frappe.query_reports["X"] = { filters: [
    { fieldname: "f", fieldtype: "MultiSelectList", get_data: function (txt) { return []; } }
] };"""
        got = resolve_filters(js, report_name="X").filters[0]
        self.assertEqual(got["options_source"], "runtime")


class TestDefaultForms(unittest.TestCase):
    def _default(self, default_js):
        js = f'frappe.query_reports["X"] = {{ filters: [{{ fieldname: "f", default: {default_js} }}] }};'
        return resolve_filters(js, report_name="X").filters[0]

    def test_string_default(self):
        self.assertEqual(self._default('"Yearly"')["default"], "Yearly")

    def test_numeric_default(self):
        self.assertEqual(self._default("1")["default"], 1)

    def test_single_element_array_is_unwrapped(self):
        """`default: ["Fiscal Year"]` on a scalar Select must not stay a list."""
        self.assertEqual(self._default('["Fiscal Year"]')["default"], "Fiscal Year")

    def test_runtime_expression_is_surfaced_not_dropped(self):
        got = self._default('frappe.defaults.get_user_default("Company")')
        self.assertNotIn("default", got)
        self.assertEqual(got["default_source"], "runtime")
        self.assertIn("get_user_default", got["default_expr"])

    def test_indexed_array_literal_is_not_mistaken_for_the_default(self):
        """hrms `employee_birthday.js` writes `default: ["Jan",...,"Dec"][getMonth()]`.

        The array is only the head of the expression; one element is chosen at
        runtime. Returning the literal would hand the caller a 12-element list
        as the default of a scalar Select.
        """
        got = self._default('["Jan", "Feb", "Mar"][frappe.datetime.get_today().getMonth()]')
        self.assertNotIn("default", got)
        self.assertEqual(got["default_source"], "runtime")
        self.assertIn("getMonth", got["default_expr"])

    def test_literal_followed_by_a_method_call_is_not_taken_verbatim(self):
        got = self._default('"2025-01-01".slice(0, 4)')
        self.assertNotIn("default", got)
        self.assertEqual(got["default_source"], "runtime")

    def test_options_array_followed_by_filter_call_is_unresolved(self):
        js = (
            'frappe.query_reports["X"] = { filters: [{ fieldname: "f", fieldtype: "Select", '
            'options: ["A", "B"].filter((x) => x !== "B") }] };'
        )
        got = resolve_filters(js, report_name="X").filters[0]
        self.assertNotIn("options", got)
        self.assertEqual(got["options_source"], "runtime")


class TestConditionalMetadata(unittest.TestCase):
    def test_depends_on_with_apostrophes_is_not_truncated(self):
        """The old regex captured `eval:doc.filter_based_on == ` and stopped."""
        result = resolve_filters(PNL, report_name="Profit and Loss Statement", load_shared=FINANCIAL_LOADER)
        by_name = {f["fieldname"]: f for f in result.filters}
        expected = "eval:doc.filter_based_on == 'Date Range'"
        self.assertEqual(by_name["period_start_date"]["depends_on"], expected)
        self.assertEqual(by_name["period_start_date"]["mandatory_depends_on"], expected)

    def test_depends_on_does_not_leak_from_mandatory_depends_on(self):
        js = """frappe.query_reports["X"] = { filters: [
    { fieldname: "f", mandatory_depends_on: "eval:doc.a == 'b'" }
] };"""
        got = resolve_filters(js, report_name="X").filters[0]
        self.assertNotIn("depends_on", got)
        self.assertEqual(got["mandatory_depends_on"], "eval:doc.a == 'b'")


class TestCrossFileComposition(unittest.TestCase):
    """The core of issue #220."""

    def test_extend_clone_plus_push_yields_the_full_contract(self):
        result = resolve_filters(PNL, report_name="Profit and Loss Statement", load_shared=FINANCIAL_LOADER)
        self.assertEqual(result.status, "resolved")
        names = [f["fieldname"] for f in result.filters]
        # six inherited from the shared namespace, two appended by the report
        self.assertEqual(
            names,
            [
                "company",
                "filter_based_on",
                "period_start_date",
                "from_fiscal_year",
                "presentation_currency",
                "cost_center",
                "selected_view",
                "accumulated_values",
            ],
        )
        self.assertIn("shared:erpnext.financial_statements", result.sources)
        self.assertIn("builder:get_filters()", result.sources)
        self.assertIn("push", result.sources)

    def test_namespace_as_first_extend_argument(self):
        """cash_flow.js uses `$.extend(ns, {...})` with no `{}` clone."""
        result = resolve_filters(CASH_FLOW, report_name="Cash Flow", load_shared=FINANCIAL_LOADER)
        self.assertEqual(result.status, "resolved")
        self.assertIn("company", [f["fieldname"] for f in result.filters])
        self.assertIn("include_default_book_entries", [f["fieldname"] for f in result.filters])

    def test_splice_is_refused_not_replayed(self):
        """Index replay against a possibly-incomplete base array would remove
        the wrong filter silently. Refuse and say so instead."""
        result = resolve_filters(CASH_FLOW, report_name="Cash Flow", load_shared=FINANCIAL_LOADER)
        self.assertTrue(result.partial)
        self.assertTrue(any(".splice()" in n for n in result.notes))

    def test_missing_shared_source_is_diagnosed(self):
        result = resolve_filters(PNL, report_name="Profit and Loss Statement", load_shared=lambda ns: None)
        self.assertTrue(any("financial_statements" in n for n in result.notes))

    def test_resolution_does_not_leak_between_reports(self):
        """`$.extend` is shallow in the browser, so Cash Flow's mutations would
        corrupt P&L in a live session. Static resolution must deep-copy."""
        first = resolve_filters(CASH_FLOW, report_name="Cash Flow", load_shared=FINANCIAL_LOADER)
        second = resolve_filters(PNL, report_name="Profit and Loss Statement", load_shared=FINANCIAL_LOADER)
        self.assertNotIn("include_default_book_entries", [f["fieldname"] for f in second.filters])
        self.assertIn("presentation_currency", [f["fieldname"] for f in second.filters])
        self.assertIn("include_default_book_entries", [f["fieldname"] for f in first.filters])

    def test_report_name_bound_to_a_constant(self):
        """ERPNext v16 writes `const PL_REPORT_NAME = "..."` and subscripts
        query_reports with the constant, so a quoted-string-only match finds
        nothing and the whole contract is lost."""
        js = """
const PL_REPORT_NAME = "Profit and Loss Statement";

frappe.query_reports[PL_REPORT_NAME] = $.extend({}, erpnext.financial_statements);

frappe.query_reports[PL_REPORT_NAME]["filters"].push(
	{ fieldname: "report_template", label: __("Report Template"), fieldtype: "Link" },
	{ fieldname: "selected_view", label: __("Select View"), fieldtype: "Select", reqd: 1 }
);
"""
        result = resolve_filters(js, report_name="Profit and Loss Statement", load_shared=FINANCIAL_LOADER)
        self.assertEqual(result.status, "resolved")
        names = [f["fieldname"] for f in result.filters]
        self.assertIn("company", names)  # inherited through the constant subscript
        self.assertIn("report_template", names)  # multiple objects in one push()
        self.assertIn("selected_view", names)

    def test_push_only_report_with_no_base(self):
        js = """
frappe.query_reports["X"] = {};
frappe.query_reports["X"]["filters"].push({ fieldname: "extra", fieldtype: "Data" });
"""
        result = resolve_filters(js, report_name="X")
        self.assertEqual([f["fieldname"] for f in result.filters], ["extra"])


class TestBuilderFunctions(unittest.TestCase):
    def test_builder_declared_above_the_assignment(self):
        """payment_ledger.js declares get_filters() before using it."""
        js = """
function get_filters() {
	let filters = [
		{ fieldname: "company", fieldtype: "Link", options: "Company", reqd: 1 },
		{ fieldname: "party", fieldtype: "MultiSelectList", options: "party_type" },
	];
	return filters;
}

frappe.query_reports["Payment Ledger"] = { filters: get_filters() };
"""
        result = resolve_filters(js, report_name="Payment Ledger")
        self.assertEqual([f["fieldname"] for f in result.filters], ["company", "party"])

    def test_builder_returning_an_array_literal_directly(self):
        js = """
function gf() { return [{ fieldname: "company", fieldtype: "Link", reqd: 1 }]; }
frappe.query_reports["X"] = { filters: gf() };
"""
        result = resolve_filters(js, report_name="X")
        self.assertEqual([f["fieldname"] for f in result.filters], ["company"])

    def test_arrow_function_builder(self):
        js = """
const gf = () => {
	const filters = [{ fieldname: "company", fieldtype: "Link" }];
	return filters;
};
frappe.query_reports["X"] = { filters: gf() };
"""
        result = resolve_filters(js, report_name="X")
        self.assertEqual([f["fieldname"] for f in result.filters], ["company"])

    def test_builder_runtime_default_assignment_is_flagged(self):
        """get_filters() fills fiscal-year defaults after building the array.
        Reporting "no default" would send the caller hunting for a value the
        UI always pre-fills."""
        result = resolve_filters(PNL, report_name="Profit and Loss Statement", load_shared=FINANCIAL_LOADER)
        by_name = {f["fieldname"]: f for f in result.filters}
        self.assertEqual(by_name["from_fiscal_year"].get("default_source"), "runtime")
        self.assertTrue(any("from_fiscal_year" in n for n in result.notes))

    def test_unknown_builder_is_diagnosed(self):
        js = 'frappe.query_reports["X"] = { filters: notDefinedHere() };'
        result = resolve_filters(js, report_name="X")
        self.assertEqual(result.status, "unresolved")
        self.assertTrue(any("notDefinedHere" in n for n in result.notes))


class TestRuntimeInjection(unittest.TestCase):
    def test_add_dimensions_is_reported_as_partial(self):
        result = resolve_filters(PNL, report_name="Profit and Loss Statement", load_shared=FINANCIAL_LOADER)
        self.assertTrue(result.partial)
        self.assertTrue(any("add_dimensions" in n for n in result.notes))


class TestUnresolvedMarker(unittest.TestCase):
    def test_equality_and_normalisation(self):
        self.assertEqual(Unresolved("a  b"), Unresolved("a b"))
        self.assertNotEqual(Unresolved("a"), Unresolved("b"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class TestMalformedInputTerminates(unittest.TestCase):
    """Every input must produce an answer in bounded time.

    A stray closing bracket used to make the value reader stop where it
    started, spinning the enclosing array/object loop forever — an MCP worker
    wedged on a report file.
    """

    def _bounded(self, fn, *args):
        import threading

        box = {}
        thread = threading.Thread(target=lambda: box.setdefault("r", fn(*args)), daemon=True)
        thread.start()
        thread.join(10)
        self.assertFalse(thread.is_alive(), "resolver did not terminate")
        return box.get("r")

    def test_stray_closers_do_not_hang(self):
        for js in (
            'frappe.query_reports["X"] = { filters: [{ a: 1, ] }] };',
            'frappe.query_reports["X"] = { filters: [ 1, } ] };',
            'frappe.query_reports["X"] = { a: ) };',
            'frappe.query_reports["X"] = { filters: [[[[ };',
        ):
            result = self._bounded(resolve_filters, js, "X")
            self.assertIsNotNone(result)
            self.assertIn(result.status, ("resolved", "unresolved", "no_filters_declared"))

    def test_regex_containing_a_brace_does_not_unbalance_the_scan(self):
        js = """
frappe.query_reports["R"] = {
	onload: function (r) { r.h(r.h().replace(/}/g, "")); },
	filters: [{ fieldname: "company", fieldtype: "Link", reqd: 1 }]
};
"""
        result = self._bounded(resolve_filters, js, "R")
        self.assertEqual(result.status, "resolved")
        self.assertEqual([f["fieldname"] for f in result.filters], ["company"])

    def test_regex_containing_slash_star_does_not_open_a_comment(self):
        """`/^[0-9+\\-/*.() ]+$/` used to swallow the whole config as a comment,
        after which the resolver confidently answered 'no filters'."""
        js = """
function is_numeric(v) { return /^[0-9+\\-/*.() ]+$/.test(v); }
frappe.query_reports["Silent"] = { filters: [
	{ fieldname: "company", fieldtype: "Link", reqd: 1 },
	{ fieldname: "from_date", fieldtype: "Date", reqd: 1 }
] };
"""
        result = self._bounded(resolve_filters, js, "Silent")
        self.assertEqual(result.status, "resolved")
        self.assertEqual([f["fieldname"] for f in result.filters], ["company", "from_date"])

    def test_quote_inside_a_regex_does_not_invert_the_views(self):
        js = """
function esc(v) { return v.replace(/'/g, ""); }
frappe.query_reports["G"] = { filters: [
	{ fieldname: "company", fieldtype: "Link", default: "RIGHT CO" }
] };
"""
        result = self._bounded(resolve_filters, js, "G")
        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.filters[0]["default"], "RIGHT CO")

    def test_nested_template_literal_keeps_following_keys(self):
        js = 'frappe.query_reports["X"] = { filters: [{ label: `a${ `]` }b`, fieldname: "f" }] };'
        result = self._bounded(resolve_filters, js, "X")
        self.assertEqual([f["fieldname"] for f in result.filters], ["f"])


class TestNeverClaimsNoFiltersWrongly(unittest.TestCase):
    """`no_filters_declared` is a positive assertion and must be earned."""

    def test_array_of_factory_calls_is_unresolved_not_empty(self):
        js = (
            'function cf(){return {fieldname:"company",reqd:1};}\n'
            'frappe.query_reports["F"] = { filters: [cf(), cf()] };'
        )
        result = resolve_filters(js, report_name="F")
        self.assertEqual(result.status, "unresolved")

    def test_unresolvable_namespace_is_unresolved_not_empty(self):
        js = 'frappe.query_reports["Stock Analytics"] = $.extend({}, erpnext.stock_analytics);'
        result = resolve_filters(js, report_name="Other Name", load_shared=lambda ns: None)
        self.assertEqual(result.status, "unresolved")

    def test_filters_assigned_after_registration(self):
        js = (
            'frappe.query_reports["L"] = { onload: function(){} };\n'
            'frappe.query_reports["L"].filters = [{ fieldname: "company", fieldtype: "Link", reqd: 1 }];'
        )
        result = resolve_filters(js, report_name="L")
        self.assertEqual(result.status, "resolved")
        self.assertEqual([f["fieldname"] for f in result.filters], ["company"])

    def test_filters_assigned_via_bracket_notation(self):
        js = (
            'frappe.query_reports["L"] = {};\n'
            'frappe.query_reports["L"]["filters"] = [{ fieldname: "co", fieldtype: "Link" }];'
        )
        result = resolve_filters(js, report_name="L")
        self.assertEqual([f["fieldname"] for f in result.filters], ["co"])


class TestMutationAttribution(unittest.TestCase):
    NS = 'erpnext.ns = { filters: [{fieldname:"company",reqd:1},{fieldname:"fiscal_year"}] };'

    def _loader(self, ns):
        return self.NS if ns == "erpnext.ns" else None

    def test_push_wrapped_onto_a_continuation_line_is_applied(self):
        js = (
            'frappe.query_reports["I"] = { filters: [{ fieldname: "company", fieldtype: "Link" }] };\n'
            'frappe.query_reports["I"]\n\t.filters.push({ fieldname: "warehouse", reqd: 1 });'
        )
        result = resolve_filters(js, report_name="I")
        self.assertEqual([f["fieldname"] for f in result.filters], ["company", "warehouse"])

    def test_a_report_does_not_steal_a_longer_named_siblings_push(self):
        js = (
            'frappe.query_reports["Sales Register"] = { filters: [{ fieldname: "company" }] };\n'
            'frappe.query_reports["Sales Register Detail"] = { filters: [{ fieldname: "company" }] };\n'
            'frappe.query_reports["Sales Register Detail"].filters.push({ fieldname: "item_code" });'
        )
        self.assertEqual(
            [f["fieldname"] for f in resolve_filters(js, report_name="Sales Register").filters],
            ["company"],
        )
        self.assertEqual(
            [f["fieldname"] for f in resolve_filters(js, report_name="Sales Register Detail").filters],
            ["company", "item_code"],
        )

    def test_a_comment_cannot_redirect_a_push(self):
        js = (
            'frappe.query_reports["Report A"] = { filters: [{ fieldname: "company" }] };\n'
            'frappe.query_reports["Report B"] = { filters: [{ fieldname: "company" }] };\n'
            "/* keep in sync with Report A */ "
            'frappe.query_reports["Report B"].filters.push({ fieldname: "b_only" });'
        )
        result = resolve_filters(js, report_name="Report A")
        self.assertEqual([f["fieldname"] for f in result.filters], ["company"])

    def test_later_extend_argument_wins(self):
        js = 'frappe.query_reports["P"] = $.extend({ filters: [{ fieldname: "local_only" }] }, erpnext.ns);'
        result = resolve_filters(js, report_name="P", load_shared=self._loader)
        self.assertEqual([f["fieldname"] for f in result.filters], ["company", "fiscal_year"])

    def test_chained_concat_is_not_silently_dropped(self):
        js = (
            'function base(){return [{ fieldname: "company" }];}\n'
            'frappe.query_reports["C"] = { filters: base().concat([{ fieldname: "extra", reqd: 1 }]) };'
        )
        result = resolve_filters(js, report_name="C")
        self.assertEqual(result.status, "unresolved")
        self.assertTrue(result.failed)

    def test_direct_namespace_assignment_resolves(self):
        js = 'frappe.query_reports["D"] = erpnext.ns;\n'
        result = resolve_filters(js, report_name="D", load_shared=self._loader)
        self.assertEqual([f["fieldname"] for f in result.filters], ["company", "fiscal_year"])


class TestEscapesAndNumbers(unittest.TestCase):
    def test_hex_escape_in_a_label(self):
        js = 'frappe.query_reports["X"] = { filters: [{ fieldname: "c", label: "Compan\\x79" }] };'
        self.assertEqual(resolve_filters(js, report_name="X").filters[0]["label"], "Company")

    def test_surrogate_pair_is_joined_and_encodable(self):
        js = 'frappe.query_reports["X"] = { filters: [{ fieldname: "c", label: "\\uD83D\\uDE00" }] };'
        label = resolve_filters(js, report_name="X").filters[0]["label"]
        self.assertEqual(label, "\U0001f600")
        label.encode("utf-8")  # must not raise

    def test_hex_number_default(self):
        js = 'frappe.query_reports["X"] = { filters: [{ fieldname: "c", default: 0xE1 }] };'
        self.assertEqual(resolve_filters(js, report_name="X").filters[0]["default"], 225)

    def test_numeric_separator_is_not_truncated(self):
        """`1_000` must never come back as 1."""
        js = 'frappe.query_reports["X"] = { filters: [{ fieldname: "c", default: 1_000 }] };'
        got = resolve_filters(js, report_name="X").filters[0]
        self.assertNotEqual(got.get("default"), 1)
        self.assertEqual(got.get("default_source"), "runtime")


class TestBuilderMutationAttribution(unittest.TestCase):
    def test_only_the_assigned_field_is_flagged(self):
        js = (
            "function get_filters(){\n"
            '\tlet f = [{fieldname:"company"},{fieldname:"from_date"},{fieldname:"to_date"}];\n'
            '\tlet t = ["to_date"].includes("x");\n'
            "\tf[2].default = frappe.datetime.get_today();\n"
            "\tfrappe.msgprint(__(\"Please pick a 'from_date'\"));\n"
            "\treturn f;\n}\n"
            'frappe.query_reports["B"] = { filters: get_filters() };'
        )
        result = resolve_filters(js, report_name="B")
        by_name = {f["fieldname"]: f for f in result.filters}
        self.assertEqual(by_name["to_date"].get("default_source"), "runtime")
        self.assertIsNone(by_name["from_date"].get("default_source"))
