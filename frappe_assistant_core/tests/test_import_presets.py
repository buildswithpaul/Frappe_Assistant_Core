# frappe_assistant_core/tests/test_import_presets.py
"""
Import presets (#34000): recognising a source system's export by its headers and cleaning it.
This file covers the pure module: parsers, loading, matching and cleaning. The tool is tested in
test_apply_import_preset.py.
"""

import io
import json
import os
import shutil
import tempfile
from unittest.mock import patch

import frappe
from openpyxl import Workbook

from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils import import_opening_stock as opening_stock
from frappe_assistant_core.utils import import_presets as presets
from frappe_assistant_core.utils.import_presets import Sheet
from frappe_assistant_core.utils.import_session import FileProblem


class TestNormalise(BaseAssistantTest):
    def test_dashes_dots_case_and_spaces_are_one_form(self):
        self.assertEqual(presets.normalise("Ledger – Opening Balance"), "ledger opening balance")
        self.assertEqual(presets.normalise("  Ledger - Opening  Balance "), "ledger opening balance")
        self.assertEqual(presets.normalise("Ref. No."), "ref no")
        self.assertEqual(presets.normalise("Party's Name"), presets.normalise("Party’s Name"))
        self.assertEqual(presets.normalise(None), "")


class TestParse(BaseAssistantTest):
    def p(self, value, kind, **spec):
        return presets.parse(value, {"parse": kind, **spec})

    def test_amounts(self):
        cases = {
            "₹ 1,23,456.00": "123456",
            '"2,306,233.08"'.strip('"'): "2306233.08",
            "-$175,804.25": "-175804.25",
            "(1,250)": "-1250",
            "(-)1,250": "-1250",
            "INR 100.00": "100",
            "8,45,000 Dr": "845000",
            "1,25,000.00 Cr": "-125000",
            "1000Cr": "-1000",
            "596.25": "596.25",
            "0.00": "0",
        }
        for value, expected in cases.items():
            self.assertEqual(self.p(value, "amount"), expected, value)

    def test_numbers_are_read_by_the_sites_number_format(self):
        # An export saved where decimals follow a comma: the comma isn't dropped as a thousands mark
        with patch.object(opening_stock, "decimal_comma", return_value=True):
            cases = {
                "1500,50": "1500.5",
                "1.500,00": "1500",
                "12.345,67": "12345.67",
                "-175.804,25": "-175804.25",
                "8.45.000 Dr": "845000",
                "1.250,00 Cr": "-1250",
            }
            for value, expected in cases.items():
                self.assertEqual(self.p(value, "amount"), expected, value)
            self.assertEqual(self.p("2,125 Kg", "quantity"), "2.125")
            self.assertEqual(self.p("2,125 Kg", "unit"), "Kg")
            self.assertEqual(self.p("1.500,50/Kg", "rate"), "1500.5")
            self.assertEqual(self.p("18,5%", "percent"), "18.5")
        with patch.object(opening_stock, "decimal_comma", return_value=False):
            # Neither thousands nor this site's decimals: kept, so the dry run reports it
            for kind in ("amount", "quantity", "rate", "percent"):
                self.assertEqual(self.p("12,5", kind), "12,5", kind)
            self.assertEqual(self.p("1E+5", "amount"), "1E+5")

    def test_a_csv_cell_is_read_as_typed(self):
        # '1.500' typed in a CSV where the site writes 1.500,00 is fifteen hundred, not 1.5
        with patch.object(opening_stock, "decimal_comma", return_value=True):
            self.assertEqual(self.p(opening_stock.Typed("1.500"), "amount"), "1.500")
            self.assertEqual(self.p("1.500", "amount"), "1.5")  # a workbook's number, as Python writes it

    def test_amount_blank_stays_blank_and_text_stays_text(self):
        self.assertEqual(self.p("", "amount"), "")
        for text in ("n/a", "-", "Nil", "12abc"):
            self.assertEqual(self.p(text, "amount"), text)

    def test_credit_positive_flips_the_sign(self):
        self.assertEqual(self.p("5,000 Cr", "amount", sign="credit_positive"), "5000")
        self.assertEqual(self.p("5,000 Dr", "amount", sign="credit_positive"), "-5000")

    def test_credit_positive_leaves_a_plain_number_as_written(self):
        self.assertEqual(self.p("500.00", "amount", sign="credit_positive"), "500")
        self.assertEqual(self.p("-500.00", "amount", sign="credit_positive"), "-500")

    def test_debit_and_credit_split_one_dr_cr_column(self):
        self.assertEqual(self.p("8,45,000 Dr", "debit"), "845000")
        self.assertEqual(self.p("8,45,000 Dr", "credit"), "")
        self.assertEqual(self.p("1,250 Cr", "debit"), "")
        self.assertEqual(self.p("1,250 Cr", "credit"), "1250")

    def test_quantity_unit_and_rate(self):
        self.assertEqual(self.p("10 Nos", "quantity"), "10")
        self.assertEqual(self.p("1,250.000 Kgs", "quantity"), "1250")
        self.assertEqual(self.p("(-)10 Nos", "quantity"), "-10")
        self.assertEqual(self.p("10 Nos", "unit"), "Nos")
        self.assertEqual(self.p("1,250.000 Kgs", "unit"), "Kgs")
        self.assertEqual(self.p("12", "unit"), "")
        self.assertEqual(self.p("100.00/Nos", "rate"), "100")
        self.assertEqual(self.p("lots", "quantity"), "lots")

    def test_quantity_and_unit_keep_text_that_is_not_a_quantity(self):
        for text in ("1.2.3", "2024-04-01", "10-20"):
            self.assertEqual(self.p(text, "quantity"), text, text)
            self.assertEqual(self.p(text, "unit"), text, text)

    def test_amount_edge_cases(self):
        self.assertEqual(self.p("Dr", "amount"), "Dr")
        self.assertEqual(self.p("(  )", "amount"), "(  )")
        self.assertEqual(self.p("1.2.3", "amount"), "1.2.3")
        self.assertEqual(self.p("-", "amount"), "-")
        self.assertEqual(self.p("1,000.50 Dr.", "amount"), "1000.5")

    def test_dates(self):
        formats = ["d-MMM-yy", "d-MMM-yyyy", "dd/MM/yyyy"]
        self.assertEqual(self.p("1-Apr-24", "date", formats=formats), "2024-04-01")
        self.assertEqual(self.p("31-Mar-2025", "date", formats=formats), "2025-03-31")
        self.assertEqual(self.p("05/04/2024", "date", formats=formats), "2024-04-05")
        self.assertEqual(self.p("04/05/2024", "date", formats=["MM/dd/yyyy"]), "2024-04-05")
        self.assertEqual(self.p("2024-04-01", "date", formats=formats), "2024-04-01")
        self.assertEqual(self.p("someday", "date", formats=formats), "someday")

    def test_percent_and_segments(self):
        self.assertEqual(self.p("18%", "percent"), "18")
        self.assertEqual(self.p("GST 18%", "percent"), "18")
        self.assertEqual(self.p("IGST12.5", "percent"), "12.5")
        self.assertEqual(self.p("Truck:Depreciation", "last_segment"), "Depreciation")
        self.assertEqual(self.p("A:B:C", "parent_segment"), "B")
        self.assertEqual(self.p("Checking", "parent_segment"), "")
        self.assertEqual(self.p("1000 · Checking", "strip_number"), "Checking")
        self.assertEqual(self.p("1000 · Checking", "strip_number", keep="number"), "1000")
        self.assertEqual(self.p("Checking", "strip_number", keep="number"), "")

    def test_map_and_default(self):
        spec = {"values": {"Active": "0", "Inactive": "1"}}
        self.assertEqual(self.p("inactive", "map", **spec), "1")
        self.assertEqual(self.p("Archived", "map", **spec), "Archived")
        self.assertEqual(self.p("Archived", "map", default="0", **spec), "0")
        self.assertEqual(presets.parse("", {"default": "Nos"}), "Nos")
        self.assertEqual(presets.parse(" Kgs ", {"default": "Nos"}), "Kgs")

    def test_a_list_of_parsers_runs_in_order(self):
        spec = {"parse": ["last_segment", "strip_number"]}
        self.assertEqual(presets.parse("1000 · Assets:1010 · Checking", spec), "Checking")


MINIMAL = {
    "id": "test.customers",
    "system": "Test System",
    "export": "Customers",
    "signature": {"required": [["Client"], ["Client Code"]]},
    "columns": {"Client": {"from": ["Client"]}, "Code": {"from": ["Client Code"]}},
    "targets": [{"name": "Customers", "doctype": "Customer", "mapping": {"Client": "customer_name"}}],
}


def preset(**changes):
    out = json.loads(json.dumps(MINIMAL))
    out.update(changes)
    return out


class TestValidate(BaseAssistantTest):
    def test_a_minimal_preset_is_valid(self):
        self.assertIsNone(presets.validate_preset(preset()))

    def test_problems_are_named(self):
        cases = [
            (preset(id=""), "'id'"),
            (preset(signature={"required": []}), "signature.required"),
            (preset(header={"rows": 3}), "header.rows"),
            (preset(columns={"Client": {"from": ["Client"], "parse": "magic"}}), "unknown parse 'magic'"),
            (preset(targets=[]), "targets"),
            (
                preset(targets=[{"name": "X", "doctype": "Customer", "engine": "opening_stock"}]),
                "exactly one",
            ),
            (preset(targets=[{"name": "X", "engine": "teleport", "columns": {}}]), "unknown engine"),
            (
                preset(targets=[{"name": "X", "engine": "opening_invoices", "columns": {"Client": "party"}}]),
                "invoice_type",
            ),
            (
                preset(targets=[{"name": "X", "engine": "opening_stock", "columns": {"Client": "colour"}}]),
                "'colour'",
            ),
            (
                preset(targets=[{"name": "X", "doctype": "Customer", "mapping": {"Nope": "customer_name"}}]),
                "unknown column 'Nope'",
            ),
            (
                preset(
                    targets=[
                        {"name": "X", "doctype": "Customer", "when": {"column": "Client"}, "mapping": {}}
                    ]
                ),
                "when",
            ),
            (preset(groups={"method": "telepathy", "column": "Client"}), "groups.method"),
            (preset(distinct_by=["Missing"]), "distinct_by"),
            (preset(columns={"Client": {"from": ["Client"], "join": ["Nope"]}}), "column 'Client': join"),
            (preset(columns={"Client": {"from": [], "join": []}}), "column 'Client': join"),
            (
                preset(group_flag={"column": "Client", "name": "Client", "parent": "Nope"}),
                "group_flag",
            ),
            (preset(group_flag={"column": "Client"}), "group_flag"),
        ]
        for bad, text in cases:
            problem = presets.validate_preset(bad)
            self.assertIsNotNone(problem, bad)
            self.assertIn(text, problem)

    def test_shapes_that_matching_would_crash_on_are_named(self):
        cases = [
            (preset(columns={"Client": {"from": "Client"}}), "column 'Client': from"),
            (preset(columns={"Client": {"from": [""]}}), "column 'Client': from"),
            (
                preset(columns={"Client": {"from": ["Client"], "from_index": "3"}}),
                "column 'Client': from_index",
            ),
            (
                preset(columns={"Client": {"from": ["Client"], "from_index": [1, "2"]}}),
                "column 'Client': from_index",
            ),
            (preset(header={"search_rows": 0}), "header.search_rows"),
            (preset(header={"search_rows": "5"}), "header.search_rows"),
            (
                preset(signature={"required": [["Client"]], "min_optional": -1}),
                "signature.min_optional must be a non-negative integer",
            ),
            (
                preset(signature={"required": [["Client"]], "min_optional": "1"}),
                "signature.min_optional must be a non-negative integer",
            ),
            (
                preset(signature={"required": [["Client"]], "min_optional": True}),
                "signature.min_optional must be a non-negative integer",
            ),
            (
                preset(
                    targets=[
                        {
                            "name": "X",
                            "doctype": "Customer",
                            "when": {"column": "Client", "in": "Group"},
                            "mapping": {},
                        }
                    ]
                ),
                "when 'in'",
            ),
            (
                preset(
                    targets=[
                        {
                            "name": "X",
                            "doctype": "Customer",
                            "when": {"column": "Client", "not_in": [1]},
                            "mapping": {},
                        }
                    ]
                ),
                "when 'not_in'",
            ),
            (
                preset(targets=[{"name": "X", "doctype": "Customer", "mapping": {"Client": 5}}]),
                "'Client' must map to a field",
            ),
            (
                preset(targets=[{"name": "X", "doctype": "Customer", "mapping": {"Client": []}}]),
                "'Client' must map to a field",
            ),
            (
                preset(targets=[{"name": "X", "engine": "opening_stock", "columns": {"Client": ["qty", 3]}}]),
                "is not a field of opening_stock",
            ),
            (
                preset(targets=[{"name": "X", "engine": "opening_stock", "columns": {"Client": ["qty"]}}]),
                "is not a field of opening_stock",
            ),
            (
                preset(targets=[{"name": "X", "engine": "opening_stock", "columns": {"Client": 5}}]),
                "is not a field of opening_stock",
            ),
            (
                preset(
                    targets=[
                        {
                            "name": "X",
                            "engine": "opening_stock",
                            "columns": {"Client": "qty"},
                            "constants": [{"column": "Kind", "field": "colour", "value": "x"}],
                        }
                    ]
                ),
                "'colour' is not a field of opening_stock",
            ),
            (preset(groups={"method": "indent", "column": "Client", "names": "Group"}), "groups.names"),
            (preset(skip={"totals": "Total"}), "skip.totals"),
            (preset(skip={"footer": [1]}), "skip.footer"),
            (preset(distinct_by="Client"), "distinct_by must be a list"),
            (
                preset(
                    targets=[
                        {
                            "name": "X",
                            "doctype": "Customer",
                            "mapping": {"Client": "customer_name"},
                            "constants": [{"column": "Client", "field": "customer_type", "value": "x"}],
                        }
                    ]
                ),
                "target 'X': column 'Client' appears twice",
            ),
            (
                preset(
                    targets=[
                        {
                            "name": "X",
                            "doctype": "Customer",
                            "mapping": {"Client": "customer_name"},
                            "constants": [{"column": "Kind", "field": "customer_type", "value": "x"}],
                            "inputs": [{"name": "k", "column": "Kind", "field": "territory", "ask": "?"}],
                        }
                    ]
                ),
                "target 'X': column 'Kind' appears twice",
            ),
        ]
        for bad, text in cases:
            problem = presets.validate_preset(bad)
            self.assertIsNotNone(problem, bad)
            self.assertIn(text, problem)

    def test_the_shapes_matching_accepts_are_valid(self):
        full = preset(
            header={"search_rows": 5},
            columns={
                "Client": {"from": [], "from_index": [1, 2]},
                "Code": {"from": ["Client Code"], "from_index": 0},
            },
            targets=[
                {
                    "name": "Customers",
                    "doctype": "Customer",
                    "when": {"column": "Client", "in": ["Group"]},
                    "mapping": {"Client": ["customer_name", "name"]},
                }
            ],
            groups={"method": "indent", "column": "Client", "names": ["Group"]},
            skip={"totals": ["Total"], "footer": []},
            distinct_by=["Client"],
        )
        self.assertIsNone(presets.validate_preset(full))
        engine = preset(
            targets=[
                {
                    "name": "Stock",
                    "engine": "opening_stock",
                    "columns": {"Client": "qty"},
                    "constants": [{"column": "Unit", "field": "uom", "value": "Nos"}],
                }
            ]
        )
        self.assertIsNone(presets.validate_preset(engine))

    def test_target_mapping_adds_constants_and_inputs(self):
        target = {
            "name": "Accounts",
            "doctype": "Account",
            "mapping": {"Client": "account_name"},
            "constants": [{"column": "Kind", "field": "account_type", "value": "Bank"}],
            "inputs": [{"name": "company", "column": "Company", "field": "company", "ask": "Which company?"}],
        }
        self.assertEqual(
            presets.target_mapping(target),
            {"Client": "account_name", "Kind": "account_type", "Company": "company"},
        )

    def test_engine_doctype(self):
        self.assertEqual(presets.engine_doctype({"engine": "opening_stock"}), "Stock Reconciliation")
        self.assertEqual(presets.engine_doctype({"engine": "opening_balances"}), "Journal Entry")
        self.assertEqual(
            presets.engine_doctype({"engine": "opening_invoices", "invoice_type": "Purchase"}),
            "Purchase Invoice",
        )


class TestLoad(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.folder = tempfile.mkdtemp()
        presets.clear_cache()

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)
        presets.clear_cache()
        super().tearDown()

    def _write(self, name, content):
        path = os.path.join(self.folder, name)
        with open(path, "w") as f:
            f.write(content if isinstance(content, str) else json.dumps(content))
        return path

    def _hooks(self, entries):
        real = frappe.get_hooks

        def fake(hook=None, *args, **kwargs):
            if hook == presets.HOOK:
                return entries
            return real(hook, *args, **kwargs)

        return patch("frappe.get_hooks", side_effect=fake), patch(
            "frappe.get_app_path", side_effect=lambda app, *parts: os.path.join(self.folder, *parts)
        )

    def test_shipped_presets_all_validate(self):
        for name in sorted(os.listdir(presets.PRESET_DIR)):
            with open(os.path.join(presets.PRESET_DIR, name)) as f:
                content = json.load(f)
            for item in content:
                self.assertIsNone(presets.validate_preset(item), f"{name}: {item.get('id')}")

    def test_every_shipped_preset_without_a_title_needs_an_optional_column(self):
        for item in presets.load_presets():
            if not item["signature"].get("title"):
                self.assertGreaterEqual(item["signature"].get("min_optional", 0), 1, item["id"])

    def test_a_hook_folder_adds_presets_and_a_hook_id_replaces_one(self):
        os.mkdir(os.path.join(self.folder, "presets"))
        self._write("presets/a.json", [preset(id="partner.customers")])
        self._write("presets/b.json", [preset(export="Customers, partner edition")])
        # FAC's own folder is replaced by an empty one; MINIMAL is loaded first through the first hook entry.
        self._write("base.json", [preset()])
        hooks, app_path = self._hooks(
            [{"app": "fac_test", "path": "base.json"}, {"app": "partner_app", "path": "presets"}]
        )
        with hooks, app_path, patch.object(presets, "PRESET_DIR", os.path.join(self.folder, "none")):
            loaded = {p["id"]: p for p in presets.load_presets()}
        self.assertIn("partner.customers", loaded)
        self.assertEqual(loaded["test.customers"]["export"], "Customers, partner edition")

    def test_an_invalid_hook_preset_is_skipped_and_logged(self):
        self._write("bad.json", [preset(id="bad.one", targets=[]), preset(id="good.one")])
        hooks, app_path = self._hooks([{"app": "partner_app", "path": "bad.json"}])
        with hooks, app_path, patch.object(presets, "PRESET_DIR", os.path.join(self.folder, "none")), patch(
            "frappe.log_error"
        ) as log:
            ids = [p["id"] for p in presets.load_presets()]
        self.assertEqual(ids, ["good.one"])
        self.assertIn("bad.one", frappe.as_json(log.call_args))

    def test_a_broken_json_file_is_skipped_and_logged(self):
        self._write("broken.json", "{not json")
        hooks, app_path = self._hooks([{"app": "partner_app", "path": "broken.json"}])
        with hooks, app_path, patch.object(presets, "PRESET_DIR", os.path.join(self.folder, "none")), patch(
            "frappe.log_error"
        ) as log:
            self.assertEqual(presets.load_presets(), [])
        self.assertTrue(log.called)

    def test_loading_is_cached_for_the_request(self):
        first = presets.load_presets()
        with patch.object(presets, "_preset_files", side_effect=AssertionError("read again")):
            self.assertIs(presets.load_presets(), first)

    def test_a_preset_with_the_wrong_shape_is_skipped_and_the_others_load(self):
        self._write(
            "odd.json",
            [
                preset(id="odd.one", header="not a dict"),
                preset(
                    id="odd.two",
                    targets=[{"name": "X", "doctype": "Customer", "when": "Group"}],
                ),
                preset(id="good.one"),
            ],
        )
        hooks, app_path = self._hooks([{"app": "partner_app", "path": "odd.json"}])
        with hooks, app_path, patch.object(presets, "PRESET_DIR", os.path.join(self.folder, "none")), patch(
            "frappe.log_error"
        ) as log:
            ids = [p["id"] for p in presets.load_presets()]
        self.assertEqual(ids, ["good.one"])
        logged = frappe.as_json([c.kwargs["message"] for c in log.call_args_list])
        self.assertIn("odd.one", logged)
        self.assertIn("odd.two", logged)
        self.assertEqual(log.call_count, 2)


LEDGERS = {
    "id": "test.ledgers",
    "system": "Test",
    "export": "Ledgers",
    "signature": {"required": [["Name"], ["Under", "Group Name"]], "optional": [["GSTIN"], ["Missing"]]},
    "skip": {"totals": ["Grand Total"], "footer": ["* GMT*"]},
    "columns": {
        "Name": {"from": ["Name"]},
        "Group": {"from": ["Under", "Group Name"]},
        "GSTIN": {"from": ["GSTIN"]},
        "Opening": {"from": ["Opening Balance"], "parse": "amount"},
    },
    "targets": [
        {
            "name": "Customers",
            "when": {"column": "Group", "in": ["Sundry Debtors"]},
            "doctype": "Customer",
            "mapping": {"Name": "customer_name"},
            "constants": [{"column": "Customer Type", "field": "customer_type", "value": "Company"}],
        },
        {
            "name": "Suppliers",
            "when": {"column": "Group", "in": ["sundry creditors"]},
            "doctype": "Supplier",
            "mapping": {"Name": "supplier_name"},
        },
        {
            "name": "Accounts",
            "when": {"column": "Group", "not_in": ["Sundry Debtors", "Sundry Creditors"]},
            "doctype": "Account",
            "mapping": {"Name": "account_name"},
            "inputs": [{"name": "company", "column": "Company", "field": "company", "ask": "Which company?"}],
        },
    ],
}

TB = {
    "id": "test.tb",
    "system": "Test",
    "export": "Trial balance",
    "signature": {"required": [["Debit"], ["Credit"]], "title": ["*trial balance*"]},
    "skip": {"totals": ["Grand Total", "Total for *"]},
    "groups": {"method": ["indent", "known_names"], "column": "Account", "names": ["Current Assets"]},
    "columns": {
        "Account": {"from": ["Particulars"], "from_index": [0, 1]},
        "Debit": {"from": ["Debit"], "parse": "amount"},
        "Credit": {"from": ["Credit"], "parse": "amount"},
    },
    "targets": [
        {
            "name": "Trial balance",
            "engine": "opening_balances",
            "columns": {"Account": "account", "Debit": "debit", "Credit": "credit"},
        }
    ],
}


def ledger_rows():
    return [
        ["Acme Pvt Ltd", "", ""],
        ["Ledgers", "", ""],
        ["", "", ""],
        ["Name", "Under", "GSTIN", "Opening Balance"],
        ["Ravi Traders", "Sundry Debtors", "29ABCDE1234F1Z5", "1,000 Dr"],
        ["", "", "", ""],
        ["Mehta Supplies", "Sundry Creditors", "", "500 Cr"],
        ["Name", "Under", "GSTIN", "Opening Balance"],
        ["HDFC Bank", "Bank Accounts", "", ""],
        ["Grand Total", "", "", "500"],
        [" Wednesday, March 04, 2026 10:53 PM GMTZ"],
    ]


class TestMatch(BaseAssistantTest):
    def test_the_header_row_is_found_under_title_rows(self):
        for titles in (0, 3, 4):
            rows = [["Title"]] * titles + [["Name", "Under", "GSTIN"], ["A", "Sundry Debtors", ""]]
            found = presets.match_sheet(rows, [LEDGERS])
            self.assertEqual(found[0].header_row, titles)

    def test_score_counts_optional_groups(self):
        found = presets.match_sheet([["Name", "Under", "GSTIN"]], [LEDGERS])[0]
        self.assertAlmostEqual(found.score, 3 / 4)

    def test_min_optional_needs_that_many_optional_groups_on_the_header_row(self):
        strict = {**LEDGERS, "signature": {**LEDGERS["signature"], "min_optional": 1}}
        self.assertIsNone(presets.validate_preset(strict))
        self.assertEqual(presets.match_sheet([["Name", "Under"], ["A", "B"]], [strict]), [])
        found = presets.match_sheet([["Name", "Under"], ["Name", "Under", "GSTIN"]], [strict])
        self.assertEqual(found[0].header_row, 1)  # the row without an optional group is no candidate
        self.assertEqual(len(presets.match_sheet([["Name", "Under"]], [LEDGERS])), 1)  # default 0

    def test_no_match_without_every_required_group(self):
        self.assertEqual(presets.match_sheet([["Name", "GSTIN"], ["A", "B"]], [LEDGERS]), [])
        self.assertEqual(presets.missing_groups([["Name", "GSTIN"]], LEDGERS), [["Under", "Group Name"]])

    def test_why_not_names_the_missing_required_groups(self):
        self.assertEqual(
            presets.why_not([["Name", "GSTIN"], ["A", "B"]], LEDGERS),
            {"missing_headers": [["Under", "Group Name"]]},
        )

    def test_why_not_names_the_title_when_no_header_row_has_it_above(self):
        rows = [["Particulars", "Debit", "Credit"], ["Cash", "10", ""]]
        self.assertEqual(
            presets.why_not(rows, TB), {"missing_headers": [], "missing_title": ["*trial balance*"]}
        )
        # With the title above, nothing is missing.
        self.assertEqual(presets.why_not([["Trial Balance"], *rows], TB), {"missing_headers": []})

    def test_why_not_says_how_many_optional_groups_are_needed(self):
        strict = {**LEDGERS, "signature": {**LEDGERS["signature"], "min_optional": 1}}
        self.assertEqual(
            presets.why_not([["Name", "Under"], ["A", "B"]], strict),
            {"missing_headers": [], "needs_optional": {"min": 1, "groups": [["GSTIN"], ["Missing"]]}},
        )
        # Required groups missing: only missing_headers, no optional count.
        self.assertEqual(
            presets.why_not([["Name"], ["A"]], strict), {"missing_headers": [["Under", "Group Name"]]}
        )

    def test_a_title_pattern_is_required_above_the_header(self):
        rows = [["Particulars", "Debit", "Credit"], ["Cash", "10", ""]]
        self.assertEqual(presets.match_sheet(rows, [TB]), [])
        found = presets.match_sheet([["Acme"], ["Trial Balance"], *rows], [TB])
        self.assertEqual(found[0].header_row, 2)

    def test_header_aliases_are_compared_normalised(self):
        found = presets.match_sheet([["NAME", "Group  Name"]], [LEDGERS])
        self.assertEqual(len(found), 1)

    def test_ties_keep_load_order(self):
        twin = {**LEDGERS, "id": "test.twin"}
        found = presets.match_sheet([["Name", "Under", "GSTIN"]], [LEDGERS, twin])
        self.assertEqual([m.preset["id"] for m in found], ["test.ledgers", "test.twin"])

    def test_the_header_is_the_row_with_the_most_groups_found(self):
        tally = {
            **TB,
            "signature": {"required": [["Debit", "Closing Balance"]], "optional": [["Credit"]]},
        }
        rows = [["Co"], ["", "Closing Balance"], ["", "Debit", "Credit"], ["Cash", "10", ""]]
        self.assertEqual(presets.match_sheet(rows, [tally])[0].header_row, 2)
        # a tie goes to the earlier row
        rows = [["Co"], ["", "Debit", "Credit"], ["", "Debit", "Credit"], ["Cash", "10", ""]]
        self.assertEqual(presets.match_sheet(rows, [tally])[0].header_row, 1)
        # a row still needs every required group
        self.assertEqual(presets.match_sheet([["", "Credit"], ["Cash", "10"]], [tally]), [])

    def test_two_row_headers_join_with_the_cell_above(self):
        two = {
            **TB,
            "header": {"rows": 2},
            "signature": {"required": [["Closing Balance › Debit"], ["Closing Balance › Credit"]]},
        }
        rows = [["Particulars", "Closing Balance", ""], ["", "Debit", "Credit"], ["Cash", "10", ""]]
        found = presets.match_sheet(rows, [two])[0]
        self.assertEqual(
            found.headers, ["Particulars", "Closing Balance › Debit", "Closing Balance › Credit"]
        )


class TestClean(BaseAssistantTest):
    def _clean(self, rows, preset, indents=None):
        found = presets.match_sheet(rows, [preset])[0]
        return presets.clean(Sheet("Sheet1", rows, indents), found)

    def test_rows_are_split_by_target_and_junk_is_counted(self):
        cleaned = self._clean(ledger_rows(), LEDGERS)
        by_name = {t.target["name"]: t for t in cleaned.targets}
        self.assertEqual(by_name["Customers"].header, ["Name", "Group", "GSTIN", "Opening"])
        self.assertEqual(
            by_name["Customers"].rows, [["Ravi Traders", "Sundry Debtors", "29ABCDE1234F1Z5", "1000"]]
        )
        self.assertEqual(by_name["Suppliers"].rows[0][3], "-500")
        self.assertEqual(by_name["Accounts"].rows[0][0], "HDFC Bank")
        self.assertEqual(
            {k: v for k, v in cleaned.dropped.items() if v},
            {"title": 3, "blank": 1, "repeated_header": 1, "totals": 1, "footer": 1},
        )
        self.assertEqual(cleaned.rows_read, 7)

    def test_a_row_that_fits_no_target_is_counted_with_its_value(self):
        only_customers = {**LEDGERS, "targets": LEDGERS["targets"][:1]}
        cleaned = self._clean(ledger_rows(), only_customers)
        self.assertEqual(cleaned.dropped["no_target"], 2)
        self.assertEqual(cleaned.no_target_values, {"Group": ["Sundry Creditors", "Bank Accounts"]})

    def test_known_group_names_and_indented_groups_are_dropped(self):
        rows = [
            ["Acme"],
            ["Trial Balance"],
            ["Particulars", "Debit", "Credit"],
            ["Current Assets", "1,500.00", ""],
            ["  Cash", "500.00", ""],
            ["Fixed Assets", "1,000.00", ""],
            ["   Furniture", "1,000.00", ""],
            ["Capital Account", "", "1,500.00"],
            ["Grand Total", "1,500.00", "1,500.00"],
        ]
        cleaned = self._clean(rows, TB)
        accounts = [r[0] for r in cleaned.targets[0].rows]
        self.assertEqual(accounts, ["Cash", "Furniture", "Capital Account"])
        self.assertEqual(cleaned.dropped["groups"], 2)

    def test_xlsx_cell_indents_mark_groups(self):
        rows = [
            ["Trial Balance"],
            ["Particulars", "Debit", "Credit"],
            ["Loans", "", "900"],
            ["Bank Loan", "", "900"],
        ]
        indents = [[0], [0, 0, 0], [0, 0, 0], [2, 0, 0]]
        cleaned = self._clean(rows, TB, indents)
        self.assertEqual([r[0] for r in cleaned.targets[0].rows], ["Bank Loan"])

    def test_empty_amount_groups_carry_their_name_down(self):
        aging = {
            "id": "test.aging",
            "system": "Test",
            "export": "Aging",
            "signature": {"required": [["Customer"], ["Total"]]},
            "skip": {"totals": ["TOTAL", "Total for *"]},
            "groups": {"method": "empty_amounts", "column": "Customer", "carry_to": "Parent"},
            "columns": {
                "Customer": {"from": ["Customer"]},
                "Parent": {"from": []},
                "Total": {"from": ["Total"], "parse": "amount"},
            },
            "targets": [
                {
                    "name": "Open",
                    "engine": "opening_invoices",
                    "invoice_type": "Sales",
                    "when": {"column": "Total", "nonzero": True},
                    "columns": {"Customer": "party", "Total": "outstanding_amount"},
                }
            ],
        }
        rows = [
            ["Customer", "CURRENT", "Total"],
            ["Amy's Bird Sanctuary", "239.00", "239.00"],
            ["Freeman Sporting Goods", "", ""],
            ["0969 Ocean View Road", "477.50", "477.50"],
            ["Total for Freeman Sporting Goods", "477.50", "$477.50"],
            ["Zero Co", "0.00", "0.00"],
            ["TOTAL", "", "-$716.50"],
        ]
        cleaned = self._clean(rows, aging)
        self.assertEqual(
            cleaned.targets[0].rows,
            [
                ["Amy's Bird Sanctuary", "", "239"],
                ["0969 Ocean View Road", "Freeman Sporting Goods", "477.5"],
            ],
        )
        self.assertEqual(cleaned.dropped["groups"], 1)
        self.assertEqual(cleaned.dropped["no_target"], 1)  # Zero Co: nonzero filter

    def test_nonzero_keeps_text_that_is_not_a_number_for_the_dry_run(self):
        preset = {
            "id": "test.nonzero",
            "system": "Test",
            "export": "Aging",
            "signature": {"required": [["Customer"], ["Total"]]},
            "columns": {
                "Customer": {"from": ["Customer"]},
                "Total": {"from": ["Total"], "parse": "amount"},
            },
            "targets": [
                {
                    "name": "Open",
                    "engine": "opening_invoices",
                    "invoice_type": "Sales",
                    "when": {"column": "Total", "nonzero": True},
                    "columns": {"Customer": "party", "Total": "outstanding_amount"},
                }
            ],
        }
        rows = [
            ["Customer", "Total"],
            ["Amy", "239.00"],
            ["Bob", "n/a"],
            ["Zero Co", "0.00"],
            ["Blank Co", ""],
        ]
        cleaned = self._clean(rows, preset)
        self.assertEqual(cleaned.targets[0].rows, [["Amy", "239"], ["Bob", "n/a"]])
        self.assertEqual(cleaned.dropped["no_target"], 2)  # only numeric zero and blank fail nonzero

    def test_join_builds_a_column_from_the_non_blank_values_of_others(self):
        aging = {
            "id": "test.join",
            "system": "Test",
            "export": "Aging",
            "signature": {"required": [["Customer"], ["Total"]]},
            "skip": {"totals": ["TOTAL", "Total for *"]},
            "groups": {"method": "empty_amounts", "column": "Customer", "carry_to": "Parent"},
            "columns": {
                "Customer": {"from": ["Customer"]},
                "Parent": {"from": []},
                "Party": {"from": [], "join": ["Parent", "Customer"]},
                "Total": {"from": ["Total"], "parse": "amount"},
            },
            "targets": [
                {
                    "name": "Open",
                    "engine": "opening_invoices",
                    "invoice_type": "Sales",
                    "columns": {"Party": "party", "Total": "outstanding_amount"},
                }
            ],
        }
        self.assertIsNone(presets.validate_preset(aging))
        rows = [
            ["Customer", "Total"],
            ["Amy's Bird Sanctuary", "239.00"],
            ["Freeman Sporting Goods", ""],
            ["0969 Ocean View Road", "477.50"],
            ["Total for Freeman Sporting Goods", "477.50"],
        ]
        cleaned = self._clean(rows, aging)
        self.assertEqual(
            [r[2] for r in cleaned.targets[0].rows],
            ["Amy's Bird Sanctuary", "Freeman Sporting Goods:0969 Ocean View Road"],
        )
        with_sep = {
            **aging,
            "columns": {**aging["columns"], "Party": {**aging["columns"]["Party"], "sep": " / "}},
        }
        cleaned = self._clean(rows, with_sep)
        self.assertEqual(cleaned.targets[0].rows[1][2], "Freeman Sporting Goods / 0969 Ocean View Road")

    def test_group_flag_marks_the_accounts_that_are_a_parent(self):
        accounts = {
            "id": "test.accounts",
            "system": "Test",
            "export": "Accounts",
            "signature": {"required": [["Full name"], ["Type"]]},
            "columns": {
                "Account": {"from": ["Full name"], "parse": "last_segment"},
                "Type": {"from": ["Type"]},
                "Parent": {"from": ["Full name"], "parse": "parent_segment", "fallback": "Type"},
                "Is Group": {"from": []},
            },
            "group_flag": {"column": "Is Group", "name": "Account", "parent": "Parent"},
            "targets": [
                {
                    "name": "Accounts",
                    "doctype": "Account",
                    "mapping": {
                        "Account": "account_name",
                        "Parent": "parent_account",
                        "Is Group": "is_group",
                    },
                }
            ],
        }
        self.assertIsNone(presets.validate_preset(accounts))
        rows = [
            ["Full name", "Type"],
            ["Checking", "Bank"],
            ["Truck", "Fixed Assets"],
            ["Truck:Depreciation", "Fixed Assets"],
        ]
        cleaned = self._clean(rows, accounts)
        self.assertEqual(
            {r[0]: r[3] for r in cleaned.targets[0].rows},
            {"Checking": "0", "Truck": "1", "Depreciation": "0"},
        )

    def test_distinct_by_keeps_the_first_row_of_each_document(self):
        lines = {
            "id": "test.lines",
            "system": "Test",
            "export": "Invoices",
            "signature": {"required": [["Invoice Number"], ["Balance"]]},
            "distinct_by": ["Invoice"],
            "columns": {
                "Invoice": {"from": ["Invoice Number"]},
                "Balance": {"from": ["Balance"], "parse": "amount"},
            },
            "targets": [
                {
                    "name": "Open",
                    "engine": "opening_invoices",
                    "invoice_type": "Sales",
                    "columns": {"Balance": "outstanding_amount", "Invoice": "invoice_number"},
                }
            ],
        }
        rows = [["Invoice Number", "Balance"], ["INV-1", "100"], ["INV-1", "100"], ["INV-2", "50"]]
        cleaned = self._clean(rows, lines)
        self.assertEqual(cleaned.targets[0].rows, [["INV-1", "100"], ["INV-2", "50"]])
        self.assertEqual(cleaned.dropped["merged"], 1)

    def test_fallback_and_from_index_list(self):
        spec = {
            "id": "test.fb",
            "system": "Test",
            "export": "Accounts",
            "signature": {"required": [["Type"]]},
            "columns": {
                "Account": {"from": [], "from_index": [0, 1]},
                "Type": {"from": ["Type"]},
                "Parent": {"from": ["Full"], "parse": "parent_segment", "fallback": "Type"},
            },
            "targets": [{"name": "A", "doctype": "Account", "mapping": {"Account": "account_name"}}],
        }
        rows = [
            ["", "", "Type", "Full"],
            ["", "Checking", "Bank", "Checking"],
            ["Truck", "", "Fixed", "Assets:Truck"],
        ]
        cleaned = self._clean(rows, spec)
        self.assertEqual(
            cleaned.targets[0].rows, [["Checking", "Bank", "Bank"], ["Truck", "Fixed", "Assets"]]
        )

    def test_finish_adds_constants_and_inputs(self):
        cleaned = self._clean(ledger_rows(), LEDGERS)
        accounts = next(t for t in cleaned.targets if t.target["name"] == "Accounts")
        self.assertEqual(presets.missing_inputs(accounts.target, {}), accounts.target["inputs"])
        self.assertEqual(presets.missing_inputs(accounts.target, {"company": "PBSPL"}), [])
        done = presets.finish(accounts, {"company": "PBSPL"})
        self.assertEqual(done.header[-1], "Company")
        self.assertEqual(done.rows[0][-1], "PBSPL")
        customers = presets.finish(cleaned.targets[0], {})
        self.assertEqual(customers.header[-1], "Customer Type")
        self.assertEqual(customers.rows[0][-1], "Company")


AGING = {
    "id": "test.aging2",
    "system": "Test",
    "export": "Aging",
    "signature": {"required": [["Customer"], ["Total"]]},
    "skip": {"totals": ["TOTAL", "Total for *"]},
    "groups": {"method": "empty_amounts", "column": "Customer", "carry_to": "Parent"},
    "columns": {
        "Customer": {"from": ["Customer"]},
        "Parent": {"from": []},
        "Total": {"from": ["Total"], "parse": "amount"},
    },
    "targets": [
        {
            "name": "Open",
            "engine": "opening_invoices",
            "invoice_type": "Sales",
            "columns": {"Customer": "party", "Total": "outstanding_amount"},
        }
    ],
}


class TestReadAndCarry(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self._files = []

    def tearDown(self):
        for name in self._files:
            frappe.delete_doc("File", name, force=True, ignore_permissions=True)
        super().tearDown()

    def _file(self, name, content):
        doc = frappe.get_doc(
            {"doctype": "File", "file_name": name, "content": content, "is_private": 1}
        ).insert(ignore_permissions=True)
        self._files.append(doc.name)
        return doc

    def test_head_rows_covers_the_deepest_header_search(self):
        self.assertEqual(presets.head_rows([LEDGERS]), 22)
        deep = {**LEDGERS, "header": {"search_rows": 30}}
        self.assertEqual(presets.head_rows([LEDGERS, deep]), 32)
        self.assertGreaterEqual(presets.head_rows(), 22)

    def test_read_heads_reads_only_the_top_of_each_sheet(self):
        rows = [["Name", "Under"]] + [[f"Party {i}", "Sundry Debtors"] for i in range(499)]
        limit = presets.head_rows()
        csv_doc = self._file("heads.csv", "\n".join(",".join(r) for r in rows).encode())
        workbook = Workbook()
        workbook.active.title = "One"
        second = workbook.create_sheet("Two")
        for row in rows:
            workbook["One"].append(row)
            second.append(row)
        buffer = io.BytesIO()
        workbook.save(buffer)
        xlsx_doc = self._file("heads.xlsx", buffer.getvalue())

        (csv_head,) = presets.read_heads(csv_doc)
        self.assertIsNone(csv_head.name)
        self.assertEqual(len(csv_head.rows), limit)
        self.assertEqual(csv_head.rows[:2], rows[:2])
        with patch.object(presets, "_as_text", wraps=presets._as_text) as as_text:
            xlsx_heads = presets.read_heads(xlsx_doc)
        self.assertEqual(
            as_text.call_count, 2 * limit * 2
        )  # two sheets, two cells a row: no row past the head
        self.assertEqual([s.name for s in xlsx_heads], ["One", "Two"])
        self.assertEqual([len(s.rows) for s in xlsx_heads], [limit, limit])
        self.assertEqual(xlsx_heads[1].rows[:2], rows[:2])
        self.assertEqual(len(presets.read_heads(csv_doc, rows=5)[0].rows), 5)

        self.assertEqual(len(presets.read_sheet(csv_doc, None).rows), 500)
        two = presets.read_sheet(xlsx_doc, "Two")
        self.assertEqual((two.name, len(two.rows)), ("Two", 500))
        with patch.object(presets, "MAX_PRESET_ROWS", 499):
            with self.assertRaises(FileProblem) as raised:
                presets.read_sheet(xlsx_doc, "One")
        self.assertIn("more than 499 rows", str(raised.exception))
        with self.assertRaises(FileProblem):
            presets.read_sheet(xlsx_doc, "Three")

    def test_csv_keeps_leading_spaces_so_indent_groups_are_found(self):
        content = (
            b"Acme\nTrial Balance\nParticulars,Debit,Credit\n"
            b"Loans,,900\n  Bank Loan,,900\nCapital Account,,100\n"
        )
        doc = frappe.get_doc(
            {"doctype": "File", "file_name": "tb_indent.csv", "content": content, "is_private": 1}
        ).insert(ignore_permissions=True)
        self._files.append(doc.name)
        sheet = presets.read_sheets(doc)[0]
        self.assertEqual(sheet.rows[4][0], "  Bank Loan")
        found = presets.match_sheet(sheet.rows, [TB])[0]
        cleaned = presets.clean(sheet, found)
        self.assertEqual([r[0] for r in cleaned.targets[0].rows], ["Bank Loan", "Capital Account"])
        self.assertEqual(cleaned.dropped["groups"], 1)

    def test_a_total_row_ends_the_carried_group(self):
        rows = [
            ["Customer", "Current", "Total"],
            ["Freeman Sporting Goods", "", ""],
            ["0969 Ocean View Road", "477.50", "477.50"],
            ["Total for Freeman Sporting Goods", "477.50", "477.50"],
            ["Plain Co", "10.00", "10.00"],
        ]
        found = presets.match_sheet(rows, [AGING])[0]
        cleaned = presets.clean(Sheet(None, rows), found)
        self.assertEqual(
            cleaned.targets[0].rows,
            [["0969 Ocean View Road", "Freeman Sporting Goods", "477.5"], ["Plain Co", "", "10"]],
        )

    def test_equal_scores_keep_load_order_whatever_the_hits(self):
        first = {**LEDGERS, "id": "first", "signature": {"required": [["Name"]], "optional": [["Nope"]]}}
        later = {
            **LEDGERS,
            "id": "later",
            "signature": {"required": [["Name"]], "optional": [["Under"], ["Nope"], ["Nada"]]},
        }
        found = presets.match_sheet([["Name", "Under"]], [first, later])
        self.assertEqual([m.score for m in found], [0.5, 0.5])
        self.assertEqual([m.preset["id"] for m in found], ["first", "later"])

    def test_missing_groups_finds_two_row_joined_aliases(self):
        two = {
            **TB,
            "header": {"rows": 2},
            "signature": {"required": [["Closing Balance › Debit"], ["Nope"]]},
        }
        rows = [["Particulars", "Closing Balance", ""], ["", "Debit", "Credit"]]
        self.assertEqual(presets.missing_groups(rows, two), [["Nope"]])

    def test_a_semicolon_separated_csv_reads_into_the_right_cells(self):
        doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "semi.csv",
                "content": b"Name;Under;GSTIN\nRavi Traders;Sundry Debtors;29ABCDE1234F1Z5\n",
                "is_private": 1,
            }
        ).insert(ignore_permissions=True)
        self._files.append(doc.name)
        self.assertEqual(
            presets.read_sheets(doc)[0].rows,
            [["Name", "Under", "GSTIN"], ["Ravi Traders", "Sundry Debtors", "29ABCDE1234F1Z5"]],
        )
