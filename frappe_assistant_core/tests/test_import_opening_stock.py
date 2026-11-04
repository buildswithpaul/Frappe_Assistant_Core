"""
Opening stock (#33996): the old system's closing stock becomes an Opening Stock Stock
Reconciliation at the cut-off date. Every row is checked first; nothing is written until the
user approves; totals per warehouse are compared with the file's after.
"""

import unittest

import frappe
from frappe.utils import nowdate

from frappe_assistant_core.assistant_core.doctype.fac_import_session.fac_import_session import engine_session
from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.tests.base_test import BaseAssistantTest, item_hsn_fields
from frappe_assistant_core.utils import import_opening_stock as opening_stock

HEADER = "Item,Warehouse,Qty,Rate"


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Stock Reconciliation")
class OpeningStockCase(BaseAssistantTest):
    """A company, two warehouses and items of every kind, made for each test."""

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.registry = get_tool_registry()
        self.tag = frappe.generate_hash(length=6)
        self.company = frappe.get_all("Company", pluck="name", order_by="creation", limit=1)[0]
        self.abbr = frappe.db.get_value("Company", self.company, "abbr")
        self.track_test_files()
        self.temporary = self._temporary_account()
        self.stores = self._warehouse(f"OS Stores {self.tag}")
        self.shop = self._warehouse(f"OS Shop {self.tag}")
        self.item = self._item(f"OS-ITEM-{self.tag}")
        self.item2 = self._item(f"OS-ITEM2-{self.tag}")
        self.date = nowdate()

    def tearDown(self):
        frappe.set_user("Administrator")
        self.delete_test_files()
        super().tearDown()

    # -- fixtures ------------------------------------------------------------------------

    def _temporary_account(self):
        name = frappe.db.get_value(
            "Account", {"company": self.company, "account_type": "Temporary", "is_group": 0}
        )
        if name:
            return name
        parent = frappe.db.get_value(
            "Account", {"company": self.company, "root_type": "Asset", "is_group": 1}, order_by="lft"
        )
        return (
            frappe.get_doc(
                {
                    "doctype": "Account",
                    "account_name": "Temporary Opening",
                    "company": self.company,
                    "parent_account": parent,
                    "account_type": "Temporary",
                    "is_group": 0,
                }
            )
            .insert()
            .name
        )

    def _warehouse(self, name, is_group=0):
        return (
            frappe.get_doc(
                {
                    "doctype": "Warehouse",
                    "warehouse_name": name,
                    "company": self.company,
                    "is_group": is_group,
                }
            )
            .insert()
            .name
        )

    def _allow_batch_and_serial_items(self):
        """ERPNext v16 refuses an Item with Has Batch No / Has Serial No while Stock Settings'
        "Activate Serial / Batch No for Item" is off, and a fresh site has it off. That is only
        needed to make such an Item here (the import never makes Items), so turn it on for the
        test and put it back after. v15 has no such setting."""
        field = "enable_serial_and_batch_no_for_item"
        if not frappe.get_meta("Stock Settings").has_field(field):
            return
        old = frappe.db.get_single_value("Stock Settings", field)
        if not old:
            frappe.db.set_single_value("Stock Settings", field, 1)
            self.addCleanup(frappe.db.set_single_value, "Stock Settings", field, old)

    def _item(self, code, **flags):
        if flags.get("has_batch_no") or flags.get("has_serial_no"):
            self._allow_batch_and_serial_items()
        doc = {
            "doctype": "Item",
            "item_code": code,
            "item_name": code,
            "item_group": frappe.db.get_value("Item Group", {"is_group": 0}) or "All Item Groups",
            "stock_uom": "Nos",
            "is_stock_item": 1,
            **item_hsn_fields(),
            **flags,
        }
        return frappe.get_doc(doc).insert().name

    def _run(self, tool_name, arguments):
        return self.registry.get_tool(tool_name)._safe_execute(arguments)

    def _file(self, lines, header=HEADER):
        content = ("\n".join([header, *lines]) + "\n").encode()
        return frappe.get_doc(
            {"doctype": "File", "file_name": f"stock-{self.tag}.csv", "content": content, "is_private": 1}
        ).insert()

    def _session(self, lines, header=HEADER):
        started = self._run("start_import_session", {"file_id": self._file(lines, header).name})
        self.assertTrue(started["success"], started)
        return started["result"]["session_id"]

    def _setup(self, session, **changes):
        arguments = {
            "session": session,
            "company": self.company,
            "posting_date": self.date,
            "columns": {
                "Item": "item_code",
                "Warehouse": "warehouse",
                "Qty": "qty",
                "Rate": "valuation_rate",
            },
            **changes,
        }
        return self._run("set_opening_stock", arguments)

    def _doc(self, session):
        # The session as the import tools hold it (load_session): the engine's own copy, so a
        # test can set up what an earlier step writes (#34400).
        return engine_session(session)

    def _ready(self, lines):
        """A session whose sheet passed the check, with that check's reply."""
        session = self._session(lines)
        self._setup(session)
        result = self._run("dry_run_import", {"session": session})["result"]
        return session, result

    def _card(self, session, result, **changes):
        """The values the approval card shows: what the last check reported."""
        totals = result["opening_stock"]
        return {
            "session": session,
            "company": self.company,
            "posting_date": self.date,
            "rows": result["ready"],
            "total_qty": totals["total_qty"],
            "total_value": totals["total_value"],
            **changes,
        }

    def _qty(self, item, warehouse):
        return frappe.db.get_value("Bin", {"item_code": item, "warehouse": warehouse}, "actual_qty")


class TestOpeningStockSetup(OpeningStockCase):
    def test_tool_is_registered_and_raises_no_approval_card(self):
        from frappe_assistant_core.plugins.migration.plugin import MigrationPlugin
        from frappe_assistant_core.utils.tool_category_detector import detect_tool_category

        self.assertIn("set_opening_stock", MigrationPlugin().get_tools())
        self.assertEqual(detect_tool_category(self.registry.get_tool("set_opening_stock")), "read_only")

    def test_setup_stores_the_settings_and_maps_the_columns(self):
        session = self._session([f"{self.item},{self.stores},5,10"])

        response = self._setup(session)

        self.assertTrue(response["success"], response)
        doc = self._doc(session)
        self.assertEqual((doc.status, doc.target_doctype), ("Mapped", "Stock Reconciliation"))
        options = frappe.parse_json(doc.template_options)
        self.assertEqual(
            options["column_to_field_map"],
            {"0": "items.item_code", "1": "items.warehouse", "2": "items.qty", "3": "items.valuation_rate"},
        )
        stock = options["opening_stock"]
        self.assertEqual(
            (stock["company"], stock["posting_date"], stock["posting_time"], stock["difference_account"]),
            (self.company, self.date, "23:59:59", self.temporary),
        )

    def test_a_date_outside_every_fiscal_year_is_refused(self):
        session = self._session([f"{self.item},{self.stores},5,10"])

        response = self._setup(session, posting_date="1901-01-01")

        self.assertFalse(response["success"], response)
        self.assertIn("fiscal year", frappe.as_json(response))
        self.assertEqual(self._doc(session).status, "File Read")

    def test_a_profit_and_loss_difference_account_is_refused(self):
        session = self._session([f"{self.item},{self.stores},5,10"])
        expense = frappe.db.get_value(
            "Account", {"company": self.company, "root_type": "Expense", "is_group": 0}
        )

        response = self._setup(session, difference_account=expense)

        self.assertFalse(response["success"], response)
        self.assertIn("Balance Sheet", frappe.as_json(response))

    def test_an_unknown_column_or_field_is_refused(self):
        session = self._session([f"{self.item},{self.stores},5,10"])

        response = self._setup(session, columns={"Item": "item_code", "Nope": "qty", "Qty": "price"})

        text = frappe.as_json(response)
        self.assertIn("Nope", text)
        self.assertIn("price", text)

    def test_item_warehouse_and_qty_columns_are_required(self):
        session = self._session([f"{self.item},{self.stores},5,10"])

        response = self._setup(session, columns={"Item": "item_code", "Qty": "qty"})

        self.assertIn("warehouse", frappe.as_json(response))

    def test_a_user_who_cannot_submit_stock_reconciliation_is_refused(self):
        frappe.set_user(self.make_throwaway_user("clerk", roles=("Sales User",)))

        problem = opening_stock.setup_problem(self.company, self.date, self.temporary)

        self.assertIn("can't do both", problem)
        frappe.set_user("Administrator")
        self.assertIsNone(opening_stock.setup_problem(self.company, self.date, self.temporary))


class TestReadingLines(OpeningStockCase):
    def test_numbers_are_read_the_accountants_way(self):
        self.assertEqual(opening_stock.number("1,250.50"), 1250.5)
        self.assertEqual(opening_stock.number("(12)"), -12)
        self.assertEqual(opening_stock.number(" 7 "), 7)
        self.assertIsNone(opening_stock.number(""))
        with self.assertRaises(ValueError):
            opening_stock.number("ten")

    def test_a_totals_row_is_recognised(self):
        self.assertTrue(opening_stock.is_totals_row({"item_code": "Grand Total", "qty": "40"}))
        self.assertTrue(opening_stock.is_totals_row({"item_code": "", "qty": "40"}))
        self.assertTrue(opening_stock.is_totals_row({"item_code": "Sub-total", "qty": "4"}))
        self.assertFalse(opening_stock.is_totals_row({"item_code": "Total Care Kit", "qty": "4"}))
        self.assertFalse(opening_stock.is_totals_row({"item_code": "", "qty": ""}))

    def test_lines_keep_the_spreadsheet_row_numbers_and_skip_blank_lines(self):
        session = self._session([f"{self.item},{self.stores},5,10", ",,,", f"{self.item2},{self.shop},3,4"])
        self._setup(session)

        lines = opening_stock.read_lines(self._doc(session))

        self.assertEqual([line.row for line in lines], [2, 4])
        self.assertEqual(lines[1].cells["item_code"], self.item2)
        self.assertEqual(lines[1].cells["qty"], "3")


class TestOpeningStockCheck(OpeningStockCase):
    def _check(self, session, **arguments):
        response = self._run("dry_run_import", {"session": session, **arguments})
        self.assertTrue(response["success"], response)
        return response["result"]

    def _causes(self, result):
        return {g["cause"]: g for g in result["groups"]}

    def test_a_clean_sheet_is_ready_with_totals_per_warehouse(self):
        session = self._session([f"{self.item},{self.stores},5,10", f"{self.item2},{self.shop},2,7.5"])
        self._setup(session)
        before = frappe.db.count("Stock Reconciliation")

        result = self._check(session)

        self.assertEqual((result["ready"], result["failed"], result["status"]), (2, 0, "Ready to Import"))
        totals = result["opening_stock"]
        self.assertEqual((totals["total_qty"], totals["total_value"]), (7, 65))
        self.assertEqual(
            totals["warehouses"][self.stores], {"qty": 5, "value": 50, "file_value": 50, "rows": 1}
        )
        self.assertEqual(frappe.db.count("Stock Reconciliation"), before)  # nothing written

    def test_each_problem_is_its_own_group(self):
        batch_item = self._item(f"OS-BATCH-{self.tag}", has_batch_no=1, create_new_batch=0)
        disabled = self._item(f"OS-OFF-{self.tag}", disabled=1)
        service = self._item(f"OS-SVC-{self.tag}", is_stock_item=0)
        session = self._session(
            [
                f"{self.item},{self.stores},5,10",  # 2 ready
                f"NOPE-{self.tag},{self.stores},1,1",  # 3 missing item
                f"{disabled},{self.stores},1,1",  # 4 can't hold stock
                f"{service},{self.stores},1,1",  # 5 can't hold stock
                f"{self.item2},{self.stores},-3,1",  # 6 negative
                f"{self.item2},{self.shop},0,1",  # 7 zero
                f"{self.item2},{self.stores},4,",  # 8 no rate
                f"{batch_item},{self.stores},2,3",  # 9 batch needed
                f"{self.item},{self.stores},1,10",  # 10 same item and warehouse as row 2
                "Grand Total,,40,",  # 11 totals row
            ]
        )
        self._setup(session)

        causes = self._causes(self._check(session))

        self.assertEqual([e["row"] for e in causes["Missing link"]["examples"]], [3])
        self.assertEqual(causes["Can't hold stock"]["count"], 2)
        self.assertEqual(causes["Negative quantity"]["count"], 1)
        self.assertEqual(causes["Zero quantity"]["count"], 1)
        self.assertEqual(causes["No valuation rate"]["count"], 1)
        self.assertEqual(causes["Batch needed"]["count"], 1)
        self.assertEqual(causes["Same item and warehouse"]["count"], 1)
        self.assertEqual(causes["Totals row"]["count"], 1)

    def test_the_rate_is_worked_out_from_the_value(self):
        session = self._session([f"{self.item},{self.stores},4,100"], header="Item,Warehouse,Qty,Value")
        self._setup(
            session,
            columns={"Item": "item_code", "Warehouse": "warehouse", "Qty": "qty", "Value": "amount"},
        )

        result = self._check(session)

        self.assertEqual(result["ready"], 1)
        self.assertEqual(result["opening_stock"]["total_value"], 100)

    def _valued(self, qty, value):
        session = self._session(
            [f"{self.item},{self.stores},{qty},{value}"], header="Item,Warehouse,Qty,Value"
        )
        self._setup(
            session,
            columns={"Item": "item_code", "Warehouse": "warehouse", "Qty": "qty", "Value": "amount"},
        )
        return self._check(session)

    def test_the_totals_are_what_erpnext_will_post(self):
        # ERPNext keeps the valuation rate to its field's precision (2 here): 100 / 3 is posted
        # as 3 x 33.33.
        result = self._valued(3, 100)

        self.assertEqual(result["ready"], 1, result)
        self.assertEqual(result["opening_stock"]["total_value"], 99.99)

    def test_a_value_that_rounding_the_rate_would_change_is_its_own_group(self):
        # 12,345.67 / 10,000 = 1.234567, kept as 1.23: ERPNext would post 12,300.00.
        result = self._valued(10000, 12345.67)

        self.assertEqual((result["ready"], result["failed"]), (0, 1), result)
        group = self._causes(result)[opening_stock.CAUSE_ROUNDED_RATE]
        self.assertIn("12300", group["message"].replace(",", ""))

    def test_the_rounding_allowed_follows_the_currencys_decimals(self):
        # A hundred of the currency's smallest unit: 1.00 at 2 decimals, 0.100 at 3 (#34435).
        from unittest.mock import patch

        with patch.object(opening_stock, "_currency_precision", return_value=3):
            # 100 / 3 at 2 rate decimals is posted as 99.99: 0.01 off, within 0.1
            self.assertEqual(self._valued(3, 100)["ready"], 1)
        # 100.40 / 100 kept as 1.00 posts 100.00: 0.40 off, rounding at 2 decimals, not at 3
        self.assertEqual(self._valued(100, 100.4)["ready"], 1)
        with patch.object(opening_stock, "_currency_precision", return_value=3):
            result = self._valued(100, 100.4)
        self.assertIn(opening_stock.CAUSE_ROUNDED_RATE, self._causes(result))
        self.assertEqual((opening_stock.rounding_allowed(2), opening_stock.rounding_allowed(3)), (1, 0.1))

    def _rate_and_value(self, qty, rate, value):
        # The Tally preset maps both: its Rate is shown rounded, its Value is qty x the exact rate
        session = self._session(
            [f"{self.item},{self.stores},{qty},{rate},{value}"], header="Item,Warehouse,Qty,Rate,Value"
        )
        self._setup(
            session,
            columns={
                "Item": "item_code",
                "Warehouse": "warehouse",
                "Qty": "qty",
                "Rate": "valuation_rate",
                "Value": "amount",
            },
        )
        return self._check(session)

    def test_with_a_rate_and_a_value_the_value_is_what_must_be_posted(self):
        # 10,000 x 12.35 is 1,23,500, but the file's Value is 1,23,456: the books must say 1,23,456
        result = self._rate_and_value(10000, 12.35, 123456)

        self.assertEqual((result["ready"], result["failed"]), (0, 1), result)
        group = self._causes(result)[opening_stock.CAUSE_ROUNDED_RATE]
        self.assertIn("123456", group["message"].replace(",", ""))

    def test_a_value_the_rate_posts_is_taken(self):
        result = self._rate_and_value(4, 25, 100)

        self.assertEqual(result["ready"], 1, result)
        self.assertEqual(result["opening_stock"]["total_value"], 100)

    def test_a_warehouse_without_the_company_suffix_is_found_by_its_name(self):
        session = self._session([f"{self.item},OS Stores {self.tag},5,10"])
        self._setup(session)

        self.assertEqual(self._check(session)["ready"], 1)

    def test_a_group_warehouse_is_refused(self):
        group = self._warehouse(f"OS Group {self.tag}", is_group=1)
        session = self._session([f"{self.item},{group},5,10"])
        self._setup(session)

        self.assertIn("Group warehouse", self._causes(self._check(session)))

    def test_an_item_that_already_has_stock_is_refused(self):
        frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Receipt",
                "company": self.company,
                "items": [{"item_code": self.item, "t_warehouse": self.stores, "qty": 1, "basic_rate": 5}],
            }
        ).insert().submit()
        session = self._session([f"{self.item},{self.stores},5,10"])
        self._setup(session)

        self.assertIn("Already has stock", self._causes(self._check(session)))

    def test_a_unit_is_converted_to_the_stock_unit(self):
        if not frappe.db.exists("UOM", "Box"):
            frappe.get_doc({"doctype": "UOM", "uom_name": "Box"}).insert()
        item = frappe.get_doc("Item", self.item)
        item.append("uoms", {"uom": "Box", "conversion_factor": 10})
        item.save()
        session = self._session(
            [f"{self.item},{self.stores},2,100,Box"], header="Item,Warehouse,Qty,Rate,Unit"
        )
        self._setup(
            session,
            columns={
                "Item": "item_code",
                "Warehouse": "warehouse",
                "Qty": "qty",
                "Rate": "valuation_rate",
                "Unit": "uom",
            },
        )

        result = self._check(session)

        self.assertEqual(result["opening_stock"]["total_qty"], 20)  # 2 boxes of 10
        self.assertEqual(result["opening_stock"]["total_value"], 200)  # 100 a box is 10 a unit

    def test_stock_reconciliation_can_not_go_through_data_import(self):
        # Why opening stock has its own route: Allow Import is off for Stock Reconciliation.
        from frappe_assistant_core.utils.import_session import import_target_problem

        session = self._session([f"{self.item},{self.stores},5,10"])

        self.assertFalse(opening_stock.is_opening_stock(self._doc(session)))
        self.assertIn("Allow Import", import_target_problem("Stock Reconciliation"))


class TestErpnextValidation(OpeningStockCase):
    def _check(self, session):
        response = self._run("dry_run_import", {"session": session})
        self.assertTrue(response["success"], response)
        return response["result"]

    def test_the_draft_is_checked_by_erpnext_and_nothing_is_left_behind(self):
        session = self._session([f"{self.item},{self.stores},5,10"])
        self._setup(session)
        tables = ("Stock Reconciliation", "Serial and Batch Bundle", "Batch", "Stock Ledger Entry")
        before = {dt: frappe.db.count(dt) for dt in tables}

        result = self._check(session)

        self.assertEqual(result["ready"], 1)
        self.assertEqual({dt: frappe.db.count(dt) for dt in tables}, before)

    def test_a_row_erpnext_refuses_is_grouped_as_rejected(self):
        from unittest.mock import patch

        from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import StockReconciliation

        session = self._session([f"{self.item},{self.stores},5,10"])
        self._setup(session)

        with patch.object(
            StockReconciliation, "validate", side_effect=frappe.ValidationError("Row 1: refused for a test")
        ):
            result = self._check(session)

        rejected = next(g for g in result["groups"] if g["cause"] == "Rejected by ERPNext")
        self.assertEqual(rejected["count"], 1)
        self.assertEqual(result["status"], "Dry Run Failed")

    def test_a_refusal_erpnext_gives_only_on_submit_fails_the_check(self):
        # #34435: ERPNext checks some things only when the document is submitted.
        from unittest.mock import patch

        from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import StockReconciliation

        session = self._session([f"{self.item},{self.stores},5,10"])
        self._setup(session)

        with patch.object(
            StockReconciliation,
            "on_submit",
            side_effect=frappe.ValidationError("Refused on submit for a test"),
        ):
            result = self._check(session)

        rejected = next(g for g in result["groups"] if g["cause"] == "Rejected by ERPNext")
        self.assertIn("Refused on submit", rejected["message"])
        self.assertEqual(result["status"], "Dry Run Failed")

    def test_the_submit_the_check_tries_leaves_nothing_behind(self):
        session = self._session([f"{self.item},{self.stores},5,10"])
        self._setup(session)
        tables = ("Stock Reconciliation", "Stock Ledger Entry", "GL Entry", "Repost Item Valuation", "Bin")
        before = {dt: frappe.db.count(dt) for dt in tables}

        result = self._check(session)

        self.assertEqual(result["ready"], 1, result)
        self.assertEqual({dt: frappe.db.count(dt) for dt in tables}, before)

    def test_a_large_sheet_is_split_into_documents_of_a_thousand_rows(self):
        lines = [opening_stock.Ready(n, f"X{n:05}", "W", 1, 1) for n in range(2, 2502)]

        self.assertEqual([len(c) for c in opening_stock.chunks(lines)], [1000, 1000, 500])

    def test_a_batch_item_with_a_new_batch_and_a_serial_item_pass(self):
        batch_item = self._item(f"OS-B-{self.tag}", has_batch_no=1, create_new_batch=0)
        serial_item = self._item(f"OS-S-{self.tag}", has_serial_no=1)
        session = self._session(
            [
                f"{batch_item},{self.stores},3,2,B-{self.tag},",
                f"{serial_item},{self.stores},2,9,,S1-{self.tag} S2-{self.tag}",
            ],
            header="Item,Warehouse,Qty,Rate,Batch,Serial",
        )
        self._setup(
            session,
            columns={
                "Item": "item_code",
                "Warehouse": "warehouse",
                "Qty": "qty",
                "Rate": "valuation_rate",
                "Batch": "batch_no",
                "Serial": "serial_no",
            },
        )

        result = self._check(session)

        self.assertEqual((result["ready"], result["failed"]), (2, 0), result["groups"])
        self.assertFalse(frappe.db.exists("Batch", f"B-{self.tag}"))  # rolled back

    def test_batch_and_serial_rows_pass_with_the_use_serial_batch_fields_setting_off(self):
        # A fresh v16 site has "Use Serial / Batch Fields" off (#34428); the import must not need it.
        old = frappe.db.get_single_value("Stock Settings", "use_serial_batch_fields")
        frappe.db.set_single_value("Stock Settings", "use_serial_batch_fields", 0)
        self.addCleanup(frappe.db.set_single_value, "Stock Settings", "use_serial_batch_fields", old)
        batch_item = self._item(f"OS-B0-{self.tag}", has_batch_no=1, create_new_batch=0)
        serial_item = self._item(f"OS-S0-{self.tag}", has_serial_no=1)
        session = self._session(
            [
                f"{self.item},{self.stores},1,5,,",
                f"{batch_item},{self.stores},3,2,B0-{self.tag},",
                f"{serial_item},{self.stores},2,9,,S1-{self.tag} S2-{self.tag}",
            ],
            header="Item,Warehouse,Qty,Rate,Batch,Serial",
        )
        self._setup(
            session,
            columns={
                "Item": "item_code",
                "Warehouse": "warehouse",
                "Qty": "qty",
                "Rate": "valuation_rate",
                "Batch": "batch_no",
                "Serial": "serial_no",
            },
        )

        result = self._check(session)

        self.assertEqual((result["ready"], result["failed"]), (3, 0), result["groups"])

    def test_a_row_named_with_a_space_after_the_hash_fails_alone(self):
        from unittest.mock import patch

        from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import StockReconciliation

        def refuse_the_second_item(doc, *args, **kwargs):
            for index, row in enumerate(doc.items, start=1):
                if row.item_code == self.item2:
                    frappe.throw(f"Row # {index}: refused for a test")  # ERPNext's wording

        session = self._session(
            [
                f"{self.item},{self.stores},5,10",
                f"{self.item2},{self.stores},2,7",
                f"{self.item},{self.shop},1,3",
            ]
        )
        self._setup(session)

        with patch.object(StockReconciliation, "validate", refuse_the_second_item):
            result = self._check(session)

        self.assertEqual((result["ready"], result["failed"]), (2, 1), result["groups"])
        rejected = next(g for g in result["groups"] if g["cause"] == "Rejected by ERPNext")
        self.assertEqual([e["row"] for e in rejected["examples"]], [3])


class TestOpeningStockFixes(OpeningStockCase):
    def _check(self, session, **arguments):
        response = self._run("dry_run_import", {"session": session, **arguments})
        self.assertTrue(response["success"], response)
        return response["result"]

    def test_every_new_cause_comes_with_a_plain_explanation(self):
        session = self._session([f"{self.item},{self.stores},4,", f"{self.item2},{self.stores},-1,3"])
        self._setup(session)

        groups = self._check(session)["groups"]

        self.assertEqual(len(groups), 2)
        for group in groups:
            self.assertTrue(group["explanation"], group)
            self.assertIn("leave_out", [f["action"] for f in group["fixes"]])
        no_rate = next(g for g in groups if g["cause"] == "No valuation rate")
        self.assertIn("allow_zero_rate", [f["action"] for f in no_rate["fixes"]])

    def test_allowing_a_zero_rate_makes_the_row_ready_at_zero_value(self):
        session = self._session([f"{self.item},{self.stores},4,"])
        self._setup(session)
        group = next(g for g in self._check(session)["groups"] if g["cause"] == "No valuation rate")

        result = self._check(session, fixes=[{"group": group["id"], "action": "allow_zero_rate"}])

        self.assertEqual((result["ready"], result["opening_stock"]["total_value"]), (1, 0))

    def test_a_missing_warehouse_is_mapped_to_an_existing_one(self):
        session = self._session([f"{self.item},Godown {self.tag},4,2"])
        self._setup(session)
        group = next(g for g in self._check(session)["groups"] if g["cause"] == "Missing link")

        result = self._check(session, fixes=[{"group": group["id"], "action": "map", "to": self.stores}])

        self.assertEqual(result["ready"], 1)

    def test_a_group_warehouse_is_mapped_to_a_real_one(self):
        group_warehouse = self._warehouse(f"OS Group {self.tag}", is_group=1)
        session = self._session([f"{self.item},{group_warehouse},4,2"])
        self._setup(session)
        group = next(g for g in self._check(session)["groups"] if g["cause"] == "Group warehouse")

        result = self._check(session, fixes=[{"group": group["id"], "action": "map", "to": self.stores}])

        self.assertEqual(result["ready"], 1)

    def test_allow_zero_rate_is_refused_for_other_groups(self):
        session = self._session([f"{self.item},{self.stores},-1,3"])
        self._setup(session)
        group = self._check(session)["groups"][0]

        response = self._run(
            "dry_run_import",
            {"session": session, "fixes": [{"group": group["id"], "action": "allow_zero_rate"}]},
        )

        self.assertFalse(response["success"], response)
        self.assertIn("zero rate", frappe.as_json(response))


class TestCreatingOpeningStock(OpeningStockCase):
    def test_tool_needs_approval(self):
        from frappe_assistant_core.plugins.migration.plugin import MigrationPlugin
        from frappe_assistant_core.utils.tool_category_detector import detect_tool_category

        self.assertIn("import_opening_stock", MigrationPlugin().get_tools())
        self.assertNotEqual(detect_tool_category(self.registry.get_tool("import_opening_stock")), "read_only")

    def test_an_approved_sheet_becomes_a_submitted_opening_stock_reconciliation(self):
        session, result = self._ready([f"{self.item},{self.stores},5,10", f"{self.item2},{self.shop},2,7.5"])

        response = self._run("import_opening_stock", self._card(session, result))

        self.assertTrue(response["success"], response)
        name = response["result"]["documents"][0]
        doc = frappe.get_doc("Stock Reconciliation", name)
        self.assertEqual(
            (doc.docstatus, doc.purpose, doc.expense_account), (1, "Opening Stock", self.temporary)
        )
        self.assertEqual(str(doc.posting_date), self.date)
        self.assertEqual(str(doc.posting_time), "23:59:59")
        self.assertEqual(self._qty(self.item, self.stores), 5)
        session_doc = self._doc(session)
        self.assertEqual(session_doc.status, "Completed")
        self.assertEqual([r.record_name for r in session_doc.created_records], [name])

    def test_card_values_that_differ_from_the_check_are_refused(self):
        session, result = self._ready([f"{self.item},{self.stores},5,10"])

        response = self._run("import_opening_stock", self._card(session, result, total_value=999))

        self.assertFalse(response["success"], response)
        self.assertFalse(self._doc(session).created_records)

    def test_a_sheet_changed_since_its_check_is_refused(self):
        session, result = self._ready([f"{self.item},{self.stores},5,10"])
        doc = self._doc(session)
        doc.transformation_rules = frappe.as_json({"zero_rate_items": ["X"]})  # a fix since the check
        doc.save()

        response = self._run("import_opening_stock", self._card(session, result))

        self.assertFalse(response["success"], response)
        self.assertIn("last check", frappe.as_json(response))
        self.assertFalse(self._doc(session).created_records)

    def test_stock_that_moved_since_the_check_stops_the_import(self):
        session, result = self._ready([f"{self.item},{self.stores},5,10"])
        frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Receipt",
                "company": self.company,
                "items": [{"item_code": self.item, "t_warehouse": self.stores, "qty": 1, "basic_rate": 5}],
            }
        ).insert().submit()

        response = self._run("import_opening_stock", self._card(session, result))

        self.assertFalse(response["success"], response)
        self.assertIn("changed", frappe.as_json(response))
        self.assertFalse(self._doc(session).created_records)

    def test_calling_again_creates_nothing_more(self):
        session, result = self._ready([f"{self.item},{self.stores},5,10"])
        first = self._run("import_opening_stock", self._card(session, result))

        second = self._run("import_opening_stock", self._card(session, result))

        self.assertTrue(second["success"], second)
        self.assertEqual(second["result"]["documents"], first["result"]["documents"])
        self.assertEqual(len(self._doc(session).created_records), 1)
        self.assertEqual(self._qty(self.item, self.stores), 5)

    def test_a_chunk_that_fails_rolls_back_whole_and_the_session_says_so(self):
        from unittest.mock import patch

        from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import StockReconciliation

        session, result = self._ready([f"{self.item},{self.stores},5,10"])

        with patch.object(StockReconciliation, "on_submit", side_effect=frappe.ValidationError("refused")):
            response = self._run("import_opening_stock", self._card(session, result))

        self.assertFalse(response["success"], response)
        self.assertEqual(self._doc(session).status, "Failed")
        self.assertFalse(self._qty(self.item, self.stores))

    def test_after_a_later_chunk_fails_only_the_rest_is_checked_and_imported(self):
        from unittest.mock import patch

        from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import StockReconciliation

        real_on_submit, calls = StockReconciliation.on_submit, []

        def second_fails(doc):
            calls.append(doc.name)
            if len(calls) == 2:
                raise frappe.ValidationError("refused")
            return real_on_submit(doc)

        with patch.object(opening_stock, "CHUNK_ROWS", 1):
            session, result = self._ready(
                [f"{self.item},{self.stores},5,10", f"{self.item2},{self.shop},2,7.5"]
            )
            with patch.object(StockReconciliation, "on_submit", second_fails):
                self._run("import_opening_stock", self._card(session, result))
            self.assertEqual(self._doc(session).status, "Partially Completed")

            again = self._run("dry_run_import", {"session": session})["result"]
            self.assertEqual((again["imported"], again["ready"]), (1, 1))
            response = self._run("import_opening_stock", self._card(session, again))

        self.assertTrue(response["success"], response)
        self.assertEqual(len(self._doc(session).created_records), 2)
        self.assertEqual(self._qty(self.item, self.stores), 5)
        self.assertEqual(self._qty(self.item2, self.shop), 2)

    def test_a_document_erpnext_is_still_submitting_keeps_the_session_importing(self):
        from unittest.mock import patch

        from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import StockReconciliation

        session, result = self._ready([f"{self.item},{self.stores},5,10"])

        with patch.object(StockReconciliation, "submit", lambda doc: None):  # as when queued
            response = self._run("import_opening_stock", self._card(session, result))

        self.assertTrue(response["success"], response)
        self.assertEqual(self._doc(session).status, "Importing")
        self.assertEqual(response["result"]["pending"], response["result"]["documents"])


class TestOpeningStockReport(OpeningStockCase):
    def _imported(self, lines):
        session, result = self._ready(lines)
        response = self._run("import_opening_stock", self._card(session, result))
        self.assertTrue(response["success"], response)
        return session, response["result"]

    def test_the_report_puts_erpnext_totals_next_to_the_files(self):
        _session, report = self._imported(
            [f"{self.item},{self.stores},5,10", f"{self.item2},{self.shop},2,7.5"]
        )

        stores = report["warehouses"][self.stores]
        self.assertEqual((stores["file_qty"], stores["erpnext_qty"]), (5, 5))
        self.assertEqual((stores["file_value"], stores["erpnext_value"]), (50, 50))
        self.assertEqual(report["differences"], [])
        self.assertEqual(report["status"], "Completed")
        self.assertIn("matches", report["message"])

    def test_the_report_shows_what_rounding_the_rate_changed(self):
        # 100 / 3 is posted as 3 x 33.33: the books hold 99.99, the file said 100 (#34435).
        session = self._session([f"{self.item},{self.stores},3,100"], header="Item,Warehouse,Qty,Value")
        self._setup(
            session,
            columns={"Item": "item_code", "Warehouse": "warehouse", "Qty": "qty", "Value": "amount"},
        )
        result = self._run("dry_run_import", {"session": session})["result"]
        self.assertEqual(result["ready"], 1, result)
        self.assertTrue(self._run("import_opening_stock", self._card(session, result))["success"])

        report = opening_stock.report(self._doc(session))

        stores = report["warehouses"][self.stores]
        self.assertEqual((stores["file_value"], stores["erpnext_value"]), (100, 99.99))
        self.assertEqual(stores["difference_value"], -0.01)
        self.assertEqual(report["differences"], [self.stores])

    def test_a_difference_is_listed(self):
        session, _report = self._imported([f"{self.item},{self.stores},5,10"])
        doc = self._doc(session)
        options = frappe.parse_json(doc.template_options)
        held = options["opening_stock"]["created"][doc.created_records[0].record_name]
        held[self.stores]["file_value"] = 60  # the file said 60
        doc.db_set("template_options", frappe.as_json(options))

        report = opening_stock.report(self._doc(session))

        self.assertEqual(report["differences"], [self.stores])
        self.assertEqual(report["warehouses"][self.stores]["difference_value"], -10)

    def test_pending_reposting_is_reported(self):
        session, _report = self._imported([f"{self.item},{self.stores},5,10"])
        name = self._doc(session).created_records[0].record_name
        frappe.get_doc(
            {
                "doctype": "Repost Item Valuation",
                "based_on": "Transaction",
                "voucher_type": "Stock Reconciliation",
                "voucher_no": name,
                "company": self.company,
                "posting_date": self.date,
                "status": "Queued",
            }
        ).insert(ignore_permissions=True)

        report = opening_stock.report(self._doc(session))

        self.assertTrue(report["reposting"])
        self.assertIn("reposting", report["message"])

    def test_the_accounting_sentence_says_which_account_or_that_none_was_posted(self):
        session, report = self._imported([f"{self.item},{self.stores},5,10"])

        perpetual = opening_stock.settings(self._doc(session))["perpetual"]

        self.assertEqual(self.temporary in report["accounting"], perpetual)
        self.assertEqual("no accounting entries" in report["accounting"], not perpetual)


class TestFinalReviewFixes(OpeningStockCase):
    """Findings of the whole-branch review, each pinned by a test that failed first."""

    def _check(self, session, **arguments):
        response = self._run("dry_run_import", {"session": session, **arguments})
        self.assertTrue(response["success"], response)
        return response["result"]

    def _partly_imported(self, lines):
        """One chunk per line; ERPNext refuses the second: the first is in, Partially Completed."""
        from unittest.mock import patch

        from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import StockReconciliation

        real_on_submit, calls = StockReconciliation.on_submit, []

        def second_fails(doc):
            calls.append(doc.name)
            if len(calls) == 2:
                raise frappe.ValidationError("refused")
            return real_on_submit(doc)

        with patch.object(opening_stock, "CHUNK_ROWS", 1):
            session, result = self._ready(lines)
            with patch.object(StockReconciliation, "on_submit", second_fails):
                self._run("import_opening_stock", self._card(session, result))
        self.assertEqual(self._doc(session).status, "Partially Completed")
        return session

    # -- the rows already in are remembered whatever is checked or uploaded later ------------

    def test_the_rows_already_in_survive_every_later_check(self):
        session = self._partly_imported(
            [f"{self.item},{self.stores},5,10", f"{self.item2},{self.shop},2,7.5"]
        )

        self._check(session)
        second = self._check(session)

        self.assertEqual((second["imported"], second["ready"], second["failed"]), (1, 1, 0), second)

    def test_a_corrected_file_with_a_row_inserted_above_still_skips_what_is_in(self):
        session = self._partly_imported(
            [f"{self.item},{self.stores},5,10", f"{self.item2},{self.shop},2,7.5"]
        )
        item3 = self._item(f"OS-ITEM3-{self.tag}")
        corrected = self._file(
            [f"{item3},{self.shop},1,3", f"{self.item},{self.stores},5,10", f"{self.item2},{self.shop},2,7.5"]
        )

        result = self._check(session, file_id=corrected.name)

        self.assertEqual((result["imported"], result["ready"], result["failed"]), (1, 2, 0), result)

    def test_an_item_and_warehouse_are_never_split_across_documents(self):
        from unittest.mock import patch

        lines = [opening_stock.Ready(n, "A", "W", 1, 1, batch_no=f"B{n}") for n in (2, 3, 4)]
        lines.append(opening_stock.Ready(5, "B", "W", 1, 1))

        with patch.object(opening_stock, "CHUNK_ROWS", 2):
            sizes = [len(c) for c in opening_stock.chunks(lines)]

        self.assertEqual(sizes, [3, 1])

    # -- the report covers every chunk and counts a batch once -------------------------------

    def test_the_report_after_a_resumed_import_covers_every_chunk(self):
        session = self._partly_imported(
            [f"{self.item},{self.stores},5,10", f"{self.item2},{self.stores},2,7.5"]
        )
        again = self._check(session)

        response = self._run("import_opening_stock", self._card(session, again))

        self.assertTrue(response["success"], response)
        report = response["result"]
        self.assertEqual(report["differences"], [], report)
        stores = report["warehouses"][self.stores]
        self.assertEqual((stores["file_qty"], stores["erpnext_qty"]), (7, 7))

    def test_two_batches_of_one_item_in_a_warehouse_are_not_counted_twice(self):
        batch_item = self._item(f"OS-BB-{self.tag}", has_batch_no=1, create_new_batch=0)
        session = self._session(
            [
                f"{batch_item},{self.stores},10,2,B1-{self.tag}",
                f"{batch_item},{self.stores},5,2,B2-{self.tag}",
            ],
            header="Item,Warehouse,Qty,Rate,Batch",
        )
        self._setup(
            session,
            columns={
                "Item": "item_code",
                "Warehouse": "warehouse",
                "Qty": "qty",
                "Rate": "valuation_rate",
                "Batch": "batch_no",
            },
        )
        result = self._check(session)

        response = self._run("import_opening_stock", self._card(session, result))

        self.assertTrue(response["success"], response)
        report = response["result"]
        stores = report["warehouses"][self.stores]
        self.assertEqual((stores["file_qty"], stores["erpnext_qty"]), (15, 15), report)
        self.assertEqual(report["differences"], [])

    # -- one bad row fails alone ------------------------------------------------------------

    def test_a_negative_rate_fails_its_own_row_not_the_chunk(self):
        session = self._session([f"{self.item},{self.stores},5,(10)", f"{self.item2},{self.shop},2,7.5"])
        self._setup(session)

        result = self._check(session)

        self.assertEqual((result["ready"], result["failed"]), (1, 1), result)

    def test_one_row_erpnext_refuses_fails_alone_and_names_its_sheet_row(self):
        from unittest.mock import patch

        from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import StockReconciliation

        bad = self._item(f"OS-BAD-{self.tag}")
        real_validate = StockReconciliation.validate

        def refuse_bad(doc):
            for row in doc.items:
                if row.item_code == bad:
                    raise frappe.ValidationError(f"Row #{row.idx}: refused for a test")
            return real_validate(doc)

        session = self._session(
            [f"{self.item},{self.stores},5,10", f"{bad},{self.stores},1,1", f"{self.item2},{self.shop},2,7.5"]
        )
        self._setup(session)

        with patch.object(StockReconciliation, "validate", refuse_bad):
            result = self._check(session)

        self.assertEqual((result["ready"], result["failed"]), (2, 1), result)
        rejected = next(g for g in result["groups"] if g["cause"] == "Rejected by ERPNext")
        self.assertEqual([e["row"] for e in rejected["examples"]], [3])
        self.assertIn("Row 3", rejected["message"])

    # -- a background submit that never finishes is reported, not waited for forever ---------

    def test_a_draft_erpnext_never_submitted_is_reported_failed_not_pending_forever(self):
        from unittest.mock import patch

        from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import StockReconciliation

        session, result = self._ready([f"{self.item},{self.stores},5,10"])
        with patch.object(StockReconciliation, "submit", lambda doc: None):  # as when queued
            response = self._run("import_opening_stock", self._card(session, result))
        name = response["result"]["documents"][0]
        self.assertEqual(self._doc(session).status, "Importing")
        long_ago = frappe.utils.add_to_date(None, seconds=-(opening_stock.STALL_SECONDS + 60))
        frappe.db.set_value("Stock Reconciliation", name, "modified", long_ago, update_modified=False)

        report = opening_stock.report(self._doc(session))

        self.assertEqual(report["failed_documents"], [name])
        self.assertEqual(report["pending"], [])
        self.assertEqual(self._doc(session).status, "Failed")
        self.assertIn("couldn't submit", report["message"])


class TestSecondReview(OpeningStockCase):
    def _stalled_draft(self):
        """A session whose document ERPNext never submitted, reported Failed, then checked again."""
        from unittest.mock import patch

        from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import StockReconciliation

        session, result = self._ready([f"{self.item},{self.stores},5,10"])
        with patch.object(StockReconciliation, "submit", lambda doc: None):  # as when queued
            name = self._run("import_opening_stock", self._card(session, result))["result"]["documents"][0]
        long_ago = frappe.utils.add_to_date(None, seconds=-(opening_stock.STALL_SECONDS + 60))
        frappe.db.set_value("Stock Reconciliation", name, "modified", long_ago, update_modified=False)
        opening_stock.report(self._doc(session))  # the session becomes Failed
        again = self._run("dry_run_import", {"session": session})["result"]
        self.assertEqual(again["ready"], 1)
        return session, again, name

    def test_importing_again_deletes_the_draft_erpnext_never_submitted_first(self):
        # A slow background job could still submit the old draft: it must be gone before the stock
        # is brought in again, or it would be posted twice.
        session, again, name = self._stalled_draft()

        response = self._run("import_opening_stock", self._card(session, again))

        self.assertTrue(response["success"], response)
        # One document holds this stock, submitted: the old draft is gone. (Frappe gives the new
        # document the deleted draft's name back, as it was the last of its series.)
        parents = set(frappe.get_all("Stock Reconciliation Item", {"item_code": self.item}, pluck="parent"))
        self.assertEqual(len(parents), 1)
        self.assertEqual(frappe.db.get_value("Stock Reconciliation", parents.pop(), "docstatus"), 1)
        self.assertEqual(self._qty(self.item, self.stores), 5)
        self.assertIn(f"Deleted {name}", " ".join(step.message for step in self._doc(session).steps))

    def test_a_draft_still_being_submitted_stops_a_new_import(self):
        session, again, name = self._stalled_draft()
        frappe.db.set_value("Stock Reconciliation", name, "modified", frappe.utils.now_datetime())

        response = self._run("import_opening_stock", self._card(session, again))

        self.assertFalse(response["success"], response)
        self.assertIn(name, response["error"])
        self.assertTrue(frappe.db.exists("Stock Reconciliation", name))
        self.assertFalse(self._qty(self.item, self.stores))


class TestSessionIsOneKind(OpeningStockCase):
    def _with_invoices(self, session, **kept):
        doc = self._doc(session)
        options = frappe.parse_json(doc.template_options or "{}") or {}
        options["opening_invoices"] = {"company": self.company, **kept}
        doc.db_set("template_options", frappe.as_json(options))

    def test_a_stale_invoices_setting_is_dropped(self):
        session = self._session([f"{self.item},{self.stores},5,10"])
        self._with_invoices(session)
        self.assertTrue(self._setup(session)["success"])
        options = frappe.parse_json(self._doc(session).template_options)
        self.assertNotIn("opening_invoices", options)
        self.assertIn("opening_stock", options)

    def test_invoices_already_made_refuse_the_stock_setup(self):
        session = self._session([f"{self.item},{self.stores},5,10"])
        self._with_invoices(session, created={"SINV-1": {"row": 2, "amount": 10}})
        before = self._doc(session).template_options
        reply = self._setup(session)
        self.assertFalse(reply["success"], reply)
        self.assertIn("Start a new session for the stock", reply["error"])
        self.assertEqual(self._doc(session).template_options, before)

    def _with_balances(self, session, **kept):
        doc = self._doc(session)
        options = frappe.parse_json(doc.template_options or "{}") or {}
        options["opening_balances"] = {"company": self.company, **kept}
        doc.db_set("template_options", frappe.as_json(options))

    def test_a_stale_balances_setting_is_dropped(self):
        session = self._session([f"{self.item},{self.stores},5,10"])
        self._with_balances(session)
        self.assertTrue(self._setup(session)["success"])
        options = frappe.parse_json(self._doc(session).template_options)
        self.assertNotIn("opening_balances", options)
        self.assertIn("opening_stock", options)

    def test_balances_already_made_refuse_the_stock_setup(self):
        session = self._session([f"{self.item},{self.stores},5,10"])
        self._with_balances(session, created={"ACC-JV-1": {}})
        before = self._doc(session).template_options
        reply = self._setup(session)
        self.assertFalse(reply["success"], reply)
        self.assertIn("opening balances", reply["error"])
        self.assertEqual(self._doc(session).template_options, before)


def refuse_sql_functions(real_get_all):
    """frappe.get_all as Frappe v16 has it: SQL functions in fields are refused. v15 accepts
    them, so code tested on v15 only would pass here and break on v16."""

    def get_all(doctype, *args, **kwargs):
        fields = kwargs.get("fields") or (args[1] if len(args) > 1 else None) or []
        for field in [fields] if isinstance(fields, str) else fields:
            if isinstance(field, str) and "(" in field:
                raise frappe.ValidationError(f"SQL functions are not allowed as strings in SELECT: {field}")
        return real_get_all(doctype, *args, **kwargs)

    return get_all


class TestSignoffReviewFixes(OpeningStockCase):
    """The review's findings on opening stock (#33999), each pinned by a test that failed first."""

    def _imported(self, lines):
        session, result = self._ready(lines)
        response = self._run("import_opening_stock", self._card(session, result))
        self.assertTrue(response["success"], response)
        return session, response["result"]

    # -- the report works on Frappe v16 ----------------------------------------------------------

    def test_the_report_asks_get_all_for_no_sql_function(self):
        from unittest.mock import patch

        session, _report = self._imported([f"{self.item},{self.stores},5,10"])

        with patch("frappe.get_all", refuse_sql_functions(frappe.get_all)):
            report = opening_stock.report(self._doc(session))

        self.assertEqual(report["warehouses"][self.stores]["erpnext_value"], 50)

    def test_a_row_imported_stays_imported_when_its_item_or_warehouse_is_retired(self):
        # After go-live an item or warehouse is disabled, as ERPNext allows with stock in it:
        # its opening stock is still in the books, so sign-off must not call the row failed.
        session, _report = self._imported([f"{self.item},{self.stores},5,10"])
        for doctype, name in (("Item", self.item), ("Warehouse", self.stores)):
            frappe.db.set_value(doctype, name, "disabled", 1)
            self.addCleanup(frappe.db.set_value, doctype, name, "disabled", 0)

            [row] = [o for o in opening_stock.outcomes(self._doc(session)) if not o["totals_row"]]

            self.assertEqual(row["status"], "imported", (doctype, row))

    # -- numbers as the file writes them ------------------------------------------------------

    def test_numbers_with_both_separators_take_the_last_as_the_decimal_point(self):
        self.assertEqual(opening_stock.number("1,234.56"), 1234.56)
        self.assertEqual(opening_stock.number("1.234,56"), 1234.56)
        self.assertEqual(opening_stock.number("1 234,56"), 1234.56)
        self.assertEqual(opening_stock.number("(1.234,50)"), -1234.5)
        self.assertEqual(opening_stock.number("1.234.567"), 1234567)

    def test_a_comma_is_read_by_the_sites_number_format(self):
        from unittest.mock import patch

        with patch.object(opening_stock, "decimal_comma", return_value=False):
            self.assertEqual(opening_stock.number("1,234"), 1234)
            with self.assertRaises(ValueError):  # not 125: it isn't thousands
                opening_stock.number("12,5")
        with patch.object(opening_stock, "decimal_comma", return_value=True):
            self.assertEqual(opening_stock.number("12,5"), 12.5)
            self.assertEqual(opening_stock.number("1,234"), 1.234)
        self.assertEqual(opening_stock.number("1234.5"), 1234.5)  # a workbook's number, either way

    def test_a_lone_point_before_three_digits_typed_in_a_csv_is_not_guessed(self):
        from unittest.mock import patch

        typed = opening_stock.Typed
        with patch.object(opening_stock, "decimal_comma", return_value=True):
            for text in ("1.500", "12.345", "-1.000"):  # a thousand and five hundred, or 1.5?
                with self.subTest(text), self.assertRaises(ValueError):
                    opening_stock.number(typed(text))
            self.assertEqual(opening_stock.number(typed("1.5")), 1.5)
            self.assertEqual(opening_stock.number(typed("1.234.567")), 1234567)
            self.assertEqual(opening_stock.number(typed("1.234,56")), 1234.56)
            # A workbook's number reaches us as Python writes it, so its point is the decimal one.
            self.assertEqual(opening_stock.number("2.125"), 2.125)
        with patch.object(opening_stock, "decimal_comma", return_value=False):
            self.assertEqual(opening_stock.number(typed("1.500")), 1.5)

    def test_a_csv_amount_on_a_decimal_comma_site_is_not_read_a_thousand_times_too_small(self):
        from unittest.mock import patch

        session = self._session([f"{self.item},{self.stores},1.500,10"])
        self._setup(session)

        with patch.object(opening_stock, "decimal_comma", return_value=True):
            response = self._run("dry_run_import", {"session": session})

        self.assertTrue(response["success"], response)
        result = response["result"]
        self.assertEqual((result["ready"], result["failed"]), (0, 1), result)

    def test_the_decimal_point_comes_from_system_settings(self):
        from unittest.mock import patch

        for fmt, comma in (("#,###.##", False), ("#.###,##", True), ("# ###,##", True), ("#.###", True)):
            with patch.object(frappe.db, "get_default", return_value=fmt):
                self.assertEqual(opening_stock.decimal_comma(), comma, fmt)

    def test_indian_grouping_is_read_as_thousands(self):
        self.assertEqual(opening_stock.number("1,00,000"), 100000)
        self.assertEqual(opening_stock.number("12,34,567.50"), 1234567.5)
        self.assertEqual(opening_stock.number("(2,50,000)"), -250000)
        with self.assertRaises(ValueError):  # neither way of grouping
            opening_stock.number("1,0,0")

    def test_nan_and_inf_are_not_numbers(self):
        for text in ("nan", "inf", "-inf"):
            with self.assertRaises(ValueError):
                opening_stock.number(text)

    # -- a draft is failed when ERPNext says so, and pending while queued ----------------------

    def _queued_draft(self):
        from unittest.mock import patch

        from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import StockReconciliation

        session, result = self._ready([f"{self.item},{self.stores},5,10"])
        with patch.object(StockReconciliation, "submit", lambda doc: None):  # as when queued
            name = self._run("import_opening_stock", self._card(session, result))["result"]["documents"][0]
        return session, name

    def test_a_draft_whose_queued_submit_failed_is_failed_at_once(self):
        session, name = self._queued_draft()
        # Production: Frappe's execute_action adds this comment when the queued submit raises.
        frappe.get_doc("Stock Reconciliation", name).add_comment("Comment", "Action Failed<br><br>No stock")

        report = opening_stock.report(self._doc(session))

        self.assertEqual(report["failed_documents"], [name])
        self.assertEqual(self._doc(session).status, "Failed")

    def test_a_draft_still_waiting_in_the_queue_is_pending_however_old(self):
        session, name = self._queued_draft()
        long_ago = frappe.utils.add_to_date(None, seconds=-(opening_stock.STALL_SECONDS + 60))
        frappe.db.set_value("Stock Reconciliation", name, "modified", long_ago, update_modified=False)
        doc = frappe.get_doc("Stock Reconciliation", name)
        doc.lock()  # Production: queue_action locks the document until its job starts
        try:
            report = opening_stock.report(self._doc(session))
        finally:
            doc.unlock()

        self.assertEqual((report["pending"], report["failed_documents"]), ([name], []))
        self.assertEqual(self._doc(session).status, "Importing")

    def test_a_draft_out_of_the_queue_is_not_failed_within_the_jobs_time(self):
        session, name = self._queued_draft()
        ten_minutes_ago = frappe.utils.add_to_date(None, minutes=-11)
        frappe.db.set_value("Stock Reconciliation", name, "modified", ten_minutes_ago, update_modified=False)

        report = opening_stock.report(self._doc(session))

        self.assertEqual((report["pending"], report["failed_documents"]), ([name], []))

    # -- a sheet of several documents is made in the background -------------------------------

    def test_several_documents_are_made_by_a_background_job(self):
        from unittest.mock import patch

        session, result = self._ready([f"{self.item},{self.stores},5,10", f"{self.item2},{self.shop},2,7.5"])
        with patch.object(opening_stock, "CHUNK_ROWS", 1):
            with patch("frappe.enqueue", wraps=frappe.enqueue) as enqueue:
                response = self._run("import_opening_stock", self._card(session, result))

        self.assertTrue(response["success"], response)
        self.assertEqual(enqueue.call_args.args[0], f"{opening_stock.__name__}.create_job")
        self.assertEqual(enqueue.call_args.kwargs["job_id"], f"fac_opening_stock::{session}")
        self.assertEqual(len(response["result"]["documents"]), 2)
        self.assertEqual(self._doc(session).status, "Completed")

    def test_one_document_is_made_in_the_request(self):
        from unittest.mock import patch

        session, result = self._ready([f"{self.item},{self.stores},5,10"])
        with patch("frappe.enqueue", wraps=frappe.enqueue) as enqueue:
            response = self._run("import_opening_stock", self._card(session, result))

        self.assertTrue(response["success"], response)
        self.assertFalse([c for c in enqueue.call_args_list if c.args and "create_job" in c.args[0]])

    def test_while_the_job_runs_the_report_says_so_and_waits(self):
        from unittest.mock import patch

        session, _report = self._imported([f"{self.item},{self.stores},5,10"])
        doc = self._doc(session)
        doc.db_set("status", "Importing")
        doc.db_set("progress", opening_stock._progress("queued"))

        with patch.object(opening_stock, "_job_running", return_value=True):
            report = opening_stock.report(self._doc(session))

        self.assertEqual(report["status"], "Importing")
        self.assertIn("in the background", report["message"])

    def test_a_job_that_stopped_before_its_end_is_marked_so(self):
        from unittest.mock import patch

        session, _report = self._imported([f"{self.item},{self.stores},5,10"])
        doc = self._doc(session)
        doc.db_set("status", "Importing")
        doc.db_set("progress", opening_stock._progress("queued"))

        with patch.object(opening_stock, "_job_running", return_value=False):
            report = opening_stock.report(self._doc(session))

        self.assertEqual(report["status"], "Partially Completed")
        self.assertIn("stopped", self._doc(session).steps[-1].message)

    # -- every row, for the sign-off report --------------------------------------------------

    def test_the_summary_counts_every_row_and_values_them_as_the_file_does(self):
        session, result = self._ready(
            [
                f"{self.item},{self.stores},5,10",
                f"{self.item2},{self.shop},2,7.5",
                f"NO-SUCH-{self.tag},{self.stores},1,1",
                "Total,,8,",
            ]
        )
        groups = {g["cause"]: g for g in result["groups"]}
        result = self._run(
            "dry_run_import",
            {
                "session": session,
                "fixes": [{"group": groups["Totals row"]["id"], "action": "leave_out", "reason": "Totals"}],
            },
        )["result"]

        summary = opening_stock.summary(self._doc(session))

        self.assertEqual(
            summary["rows"],
            {"source": 4, "imported": 0, "unchanged": 0, "excluded": 1, "failed": 1, "not_imported": 2},
        )
        self.assertEqual(summary["excluded"], [{"reason": "Totals", "count": 1, "rows": "5"}])
        self.assertEqual(summary["value"]["source"], 66)  # the totals row isn't a row of stock
        self.assertEqual(summary["value"]["failed"], 1)
        self.assertEqual(summary["erpnext"]["total"], 0)


class TestCodeReviewFindings(OpeningStockCase):
    """The code review's findings on opening stock, each pinned by a test that failed first."""

    def test_a_refused_document_leaves_no_commit_work_behind(self):
        # Submitting registers work for the commit (ERPNext's queued repost, realtime events);
        # when the document is then refused and rolled back, that work must go with it.
        from unittest.mock import patch

        from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import StockReconciliation

        session, result = self._ready([f"{self.item},{self.stores},5,10"])
        queued = []

        def refuse(*args, **kwargs):
            callback = lambda: None  # noqa: E731
            queued.append(callback)
            frappe.db.after_commit.add(callback)
            raise frappe.ValidationError("refused after queuing commit work")

        with patch.object(StockReconciliation, "on_submit", side_effect=refuse):
            response = self._run("import_opening_stock", self._card(session, result))

        self.assertFalse(response["success"], response)
        self.assertTrue(queued)
        self.assertFalse([c for c in queued if c in frappe.db.after_commit._functions])

    def _approved_for_a_job(self):
        from unittest.mock import patch

        session, result = self._ready([f"{self.item},{self.stores},5,10", f"{self.item2},{self.shop},2,7.5"])
        # The job is queued and hasn't run yet: the report finds it in the queue.
        with (
            patch.object(opening_stock, "CHUNK_ROWS", 1),
            patch("frappe.enqueue"),
            patch.object(opening_stock, "_job_running", return_value=True),
        ):
            response = self._run("import_opening_stock", self._card(session, result))
        self.assertTrue(response["success"], response)
        self.assertEqual(self._doc(session).status, "Importing")
        return session

    def test_the_job_stops_when_the_sheet_changed_but_not_its_row_count(self):
        from unittest.mock import patch

        session = self._approved_for_a_job()
        doc = self._doc(session)
        # A fix saved after the approval that keeps every row ready.
        doc.transformation_rules = frappe.as_json({"zero_rate_items": ["X"]})
        doc.save()

        with patch.object(opening_stock, "CHUNK_ROWS", 1):
            opening_stock.create_job(session, "Administrator")

        self.assertFalse(self._doc(session).created_records)
        self.assertFalse(self._qty(self.item, self.stores))
        self.assertIn("check it again", self._doc(session).steps[-1].message)

    def test_the_job_still_runs_what_was_approved(self):
        from unittest.mock import patch

        session = self._approved_for_a_job()

        with patch.object(opening_stock, "CHUNK_ROWS", 1):
            opening_stock.create_job(session, "Administrator")

        self.assertEqual(len(self._doc(session).created_records), 2)
        self.assertEqual(self._qty(self.item, self.stores), 5)
