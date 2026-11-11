# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Opening stock and invoices in a migration plan (#34351): checked knowing the records the
plan's earlier files bring, and run after the user gave the cut-off date."""

import unittest

import frappe

from frappe_assistant_core.tests.base_test import item_hsn_fields
from frappe_assistant_core.tests.test_import_opening_invoices import OpeningInvoicesCase
from frappe_assistant_core.tests.test_import_opening_stock import OpeningStockCase
from frappe_assistant_core.tests.test_import_run import ImportRunCase
from frappe_assistant_core.utils import import_plan

SESSION = "FAC Import Session"


class PlanFiles:
    """A master file of the plan, opened and mapped as FACO does."""

    def _master_file(self, file_name, header, rows, doctype, mapping):
        content = ("\n".join([",".join(header), *(",".join(row) for row in rows)]) + "\n").encode()
        file_doc = frappe.get_doc(
            {"doctype": "File", "file_name": file_name, "content": content, "is_private": 1}
        ).insert()
        session = self._run("start_import_session", {"file_id": file_doc.name})["result"]["session_id"]
        mapped = self._run("set_column_mapping", {"session": session, "mapping": mapping, "doctype": doctype})
        self.assertTrue(mapped["success"], mapped)
        return session

    def _plan(self, sessions):
        response = self._run("plan_migration", {"sessions": sessions})
        self.assertTrue(response["success"], response)
        return response["result"]["plan"]

    def _check(self, session):
        response = self._run("dry_run_import", {"session": session})
        self.assertTrue(response["success"], response)
        return response["result"]

    def _rows(self, session):
        content = frappe.get_doc(
            "File", {"file_url": frappe.db.get_value(SESSION, session, "validation_results")}
        )
        return {row["row"]: row for row in frappe.parse_json(content.get_content())["rows"]}


class StockPlanCase(PlanFiles, OpeningStockCase):
    def _items(self, *codes):
        group = frappe.db.get_value("Item Group", {"is_group": 0})
        # with India Compliance an items file carries the HSN code every Item needs there
        hsn = list(item_hsn_fields().values())
        return self._master_file(
            "items.csv",
            ["Code", "Name", "Group", "UOM"] + ["HSN"] * len(hsn),
            [[code, code, group, "Nos", *hsn] for code in codes],
            "Item",
            {
                "Code": "item_code",
                "Name": "item_name",
                "Group": "item_group",
                "UOM": "stock_uom",
                **({"HSN": "gst_hsn_code"} if hsn else {}),
            },
        )

    def _stock(self, lines):
        session = self._session(lines)
        self.assertTrue(self._setup(session)["success"])
        return session


@unittest.skipUnless(
    "erpnext" in frappe.get_installed_apps(), "needs ERPNext's Item and Stock Reconciliation"
)
class TestStockInAPlan(StockPlanCase):
    def test_stock_of_an_item_an_earlier_file_brings_is_ready(self):
        code = f"NEW-{self.tag}"
        items, stock = self._items(code), self._stock([f"{code},{self.stores},10,5"])
        self._plan([stock, items])
        self._check(items)  # the plan checks its files in order: what items.csv brings is known

        result = self._check(stock)

        self.assertEqual((result["ready"], result["failed"]), (1, 0), result.get("groups"))
        self.assertEqual(result["opening_stock"]["total_value"], 50)
        self.assertEqual(self._rows(stock)[2].get("after_files"), ["items.csv"])
        self.assertFalse(frappe.db.exists("Item", code))  # nothing was written

    def test_its_other_checks_still_run(self):
        code = f"NEW-{self.tag}"
        items, stock = self._items(code), self._stock([f"{code},Nowhere {self.tag},10,5"])
        self._plan([stock, items])
        self._check(items)

        result = self._check(stock)

        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["groups"][0]["message"], f"Warehouse 'Nowhere {self.tag}' doesn't exist.")

    def test_outside_a_plan_the_item_is_still_missing(self):
        code = f"NEW-{self.tag}"
        self._items(code)
        stock = self._stock([f"{code},{self.stores},10,5"])

        result = self._check(stock)

        self.assertEqual(result["groups"][0]["message"], f"Item '{code}' doesn't exist.")


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer and Sales Invoice")
class TestInvoicesInAPlan(PlanFiles, OpeningInvoicesCase):
    def _parties(self, doctype, *names):
        field, group_field, group_doctype = {
            "Customer": ("customer_name", "customer_group", "Customer Group"),
            "Supplier": ("supplier_name", "supplier_group", "Supplier Group"),
        }[doctype]
        group = frappe.db.get_value(group_doctype, {"is_group": 0})
        return self._master_file(
            f"{doctype.lower()}s.csv",
            ["Party", "Group"],
            [[name, group] for name in names],
            doctype,
            {"Party": field, "Group": group_field},
        )

    def test_an_invoice_of_a_customer_an_earlier_file_brings_is_ready(self):
        name = f"Planned Customer {self.tag}"
        customers = self._parties("Customer", name)
        invoices = self._session([f"{name},{self._number(1)},{self.date},{self.date},1500"])
        self.assertTrue(self._setup(invoices)["success"])
        self._plan([invoices, customers])
        self._check(customers)

        result = self._check(invoices)

        self.assertEqual((result["ready"], result["failed"]), (1, 0), result.get("groups"))
        self.assertEqual(result["opening_invoices"]["total_amount"], 1500)
        self.assertEqual(self._rows(invoices)[2].get("after_files"), ["customers.csv"])

    def test_an_invoice_of_a_customer_whose_own_row_still_fails_is_ready(self):
        # The customer file's row waits for an answer (its group is missing): the customer is still
        # what that file creates, by the name ERPNext gives it (Selling Settings: by Customer Name).
        if frappe.db.get_single_value("Selling Settings", "cust_master_name") != "Customer Name":
            self.skipTest("customers are named by a series on this site")
        name = f"Planned Customer {self.tag}"
        customers = self._master_file(
            "customers.csv",
            ["Party", "Group"],
            [[name, f"Nowhere {self.tag}"]],
            "Customer",
            {"Party": "customer_name", "Group": "customer_group"},
        )
        invoices = self._session([f"{name},{self._number(1)},{self.date},{self.date},1500"])
        self.assertTrue(self._setup(invoices)["success"])
        self._plan([invoices, customers])
        self.assertEqual(self._check(customers)["failed"], 1)

        result = self._check(invoices)

        self.assertEqual((result["ready"], result["failed"]), (1, 0), result.get("groups"))

    def test_a_bill_of_a_supplier_whose_own_row_still_fails_is_ready(self):
        if frappe.db.get_single_value("Buying Settings", "supp_master_name") != "Supplier Name":
            self.skipTest("suppliers are named by a series on this site")
        name = f"Planned Supplier {self.tag}"
        suppliers = self._master_file(
            "suppliers.csv",
            ["Party", "Group"],
            [[name, f"Nowhere {self.tag}"]],
            "Supplier",
            {"Party": "supplier_name", "Group": "supplier_group"},
        )
        bills = self._session([f"{name},{self._number(1)},{self.date},{self.date},700"])
        self.assertTrue(self._setup(bills, invoice_type="Purchase")["success"])
        self._plan([bills, suppliers])
        self.assertEqual(self._check(suppliers)["failed"], 1)

        result = self._check(bills)

        self.assertEqual((result["ready"], result["failed"]), (1, 0), result.get("groups"))

    def test_a_customer_no_file_brings_is_not_offered_to_create_in_a_plan(self):
        # The plan can't create a customer when it runs (ERPNext names it in code): offering it led
        # to an approved plan that refused to run.
        name = f"Unknown Customer {self.tag}"
        customers = self._parties("Customer", f"Planned Customer {self.tag}")
        invoices = self._session([f"{name},{self._number(1)},{self.date},{self.date},1500"])
        self.assertTrue(self._setup(invoices)["success"])
        plan = self._plan([invoices, customers])

        questions = self._run("dry_run_import", {"plan": plan})["result"]["questions"]

        fix = next(q for q in questions if q["kind"] == "fix" and q["session"] == invoices)
        self.assertNotIn("create", [f["action"] for f in fix["fixes"]])
        self.assertIn("leave_out", [f["action"] for f in fix["fixes"]])

    def test_leaving_out_a_customer_a_later_invoice_needs_says_so(self):
        # A customer row with a problem of its own: leaving it out leaves its invoice without it.
        name = f"Planned Customer {self.tag}"
        customers = self._master_file(
            "customers.csv",
            ["Party", "Group"],
            [[name, f"Nowhere {self.tag}"]],
            "Customer",
            {"Party": "customer_name", "Group": "customer_group"},
        )
        invoices = self._session([f"{name},{self._number(1)},{self.date},{self.date},1500"])
        self.assertTrue(self._setup(invoices)["success"])
        plan = self._plan([invoices, customers])

        questions = self._run("dry_run_import", {"plan": plan})["result"]["questions"]

        fix = next(q for q in questions if q["kind"] == "fix" and q["session"] == customers)
        self.assertEqual(fix["needed_by"], [f"open-{self.tag}.csv row 2 ({name})"])

    def test_a_file_of_an_open_plan_isnt_imported_on_its_own(self):
        customers = self._parties("Customer", f"Planned Customer {self.tag}")
        self._plan([customers])
        self._check(customers)

        response = self._run(
            "start_import",
            {"session": customers, "doctype": "Customer", "rows": 1, "import_type": "Insert New Records"},
        )

        self.assertFalse(response["success"], response)
        self.assertIn("run_migration_plan", response["result"]["error"])
        self.assertFalse(frappe.db.exists("Customer", f"Planned Customer {self.tag}"))

    def test_a_bill_of_a_supplier_an_earlier_file_brings_is_ready(self):
        name = f"Planned Supplier {self.tag}"
        suppliers = self._parties("Supplier", name)
        bills = self._session([f"{name},{self._number(1)},{self.date},{self.date},700"])
        self.assertTrue(self._setup(bills, invoice_type="Purchase")["success"])
        self._plan([bills, suppliers])
        self._check(suppliers)

        result = self._check(bills)

        self.assertEqual((result["ready"], result["failed"]), (1, 0), result.get("groups"))

    def test_an_invoice_after_the_cut_off_still_fails(self):
        name = f"Planned Customer {self.tag}"
        later = frappe.utils.add_days(self.date, 5)
        customers = self._parties("Customer", name)
        invoices = self._session([f"{name},{self._number(1)},{later},{later},1500"])
        self.assertTrue(self._setup(invoices)["success"])
        self._plan([invoices, customers])
        self._check(customers)

        result = self._check(invoices)

        self.assertEqual(result["failed"], 1)
        self.assertIn("after the cut-off", result["groups"][0]["message"])


@unittest.skipUnless(
    "erpnext" in frappe.get_installed_apps(), "needs ERPNext's Item and Stock Reconciliation"
)
class TestTheCutOffQuestion(StockPlanCase):
    def _planned(self):
        code = f"NEW-{self.tag}"
        self.code = code
        items, stock = self._items(code), self._stock([f"{code},{self.stores},10,5"])
        return self._plan([stock, items]), items, stock

    def _questions(self, plan, answers=None):
        response = self._run("dry_run_import", {"plan": plan, **({"answers": answers} if answers else {})})
        return response

    def test_the_plan_asks_the_cut_off_date(self):
        plan, _items, _stock = self._planned()

        questions = self._questions(plan)["result"]["questions"]

        asked = next(q for q in questions if q["kind"] == "cut_off")
        self.assertEqual(list(asked["dates"].values()), [self.date])
        self.assertNotIn("suggested", asked)  # the user says it: never a file name or today
        # a choice card: the date the files are set to, or another the user gives
        self.assertEqual(asked["choices"], [self.date, "another_date"])

    def test_a_date_other_than_the_files_is_refused(self):
        plan, _items, _stock = self._planned()
        other = frappe.utils.add_days(self.date, -1)

        response = self._questions(
            plan,
            [{"id": "plan:cut_off", "date": other}, {"id": "plan:failure_rule", "rule": "stop"}],
        )

        self.assertFalse(response["success"], response)
        self.assertIn("set_opening_stock", response["result"]["error"])
        self.assertEqual(import_plan.get_plan(plan).failure_rule, "leave_out")  # nothing applied

    def test_the_users_date_answers_it(self):
        plan, _items, _stock = self._planned()

        response = self._questions(
            plan,
            [{"id": "plan:cut_off", "date": self.date}, {"id": "plan:failure_rule", "rule": "leave_out"}],
        )

        self.assertTrue(response["success"], response)
        self.assertEqual(response["result"]["questions"], [])
        self.assertTrue(response["result"]["ready"])

    def _answered(self, plan, *more):
        ready = self._questions(
            plan,
            [
                {"id": "plan:cut_off", "date": self.date},
                {"id": "plan:failure_rule", "rule": "leave_out"},
                *more,
            ],
        )["result"]
        self.assertTrue(ready["ready"], ready)
        return ready

    def test_the_approval_card_shows_the_cut_off_and_every_decision(self):
        code, shop = f"NEW-{self.tag}", f"Godown {self.tag}"
        self.code = code
        items = self._items(code)
        stock = self._stock([f"{code},{shop},10,5"])
        plan = self._plan([stock, items])
        fix = next(q for q in self._questions(plan)["result"]["questions"] if q["kind"] == "fix")

        approval = self._answered(plan, {"id": fix["id"], "action": "map", "to": self.stores})["approval"]

        self.assertEqual((approval["files"], approval["rows"], approval["cut_off"]), (2, 2, self.date))
        self.assertIn(f"stock-{self.tag}.csv: Warehouse '{shop}' → '{self.stores}'.", approval["decisions"])
        self.assertIn(
            "Rows that still fail when their file comes up: left out, with their reason.",
            approval["decisions"],
        )

    def test_a_run_whose_card_doesnt_show_the_decisions_is_refused(self):
        plan, _items, _stock = self._planned()
        approval = self._answered(plan)["approval"]

        with ImportRunCase._each_row_commits(self):
            response = self._run(
                "run_migration_plan",
                {"plan": plan, **approval, "decisions": []},  # the card without the decisions
            )

        self.assertFalse(response["success"], response)
        self.assertEqual(response["result"]["approval"], approval)  # what to pass, to copy
        self.assertFalse(frappe.db.exists("Item", self.code))

    def test_a_file_name_with_another_date_is_shown_on_the_question_and_the_card(self):
        code = f"NEW-{self.tag}"
        self.code = code
        items = self._items(code)
        content = f"Item,Warehouse,Qty,Rate\n{code},{self.stores},10,5\n".encode()
        named = frappe.get_doc(
            {"doctype": "File", "file_name": "Closing Stock 30-Sep.csv", "content": content, "is_private": 1}
        ).insert()
        stock = self._run("start_import_session", {"file_id": named.name})["result"]["session_id"]
        self.assertTrue(self._setup(stock, posting_date="2026-10-01")["success"])
        self.date = "2026-10-01"
        plan = self._plan([stock, items])

        asked = next(q for q in self._questions(plan)["result"]["questions"] if q["kind"] == "cut_off")
        approval = self._answered(plan)["approval"]

        self.assertEqual(asked["file_names_say"], {"Closing Stock 30-Sep.csv": "30-Sep"})
        self.assertTrue(any("30-Sep" in line and "2026-10-01" in line for line in approval["decisions"]))

    def test_one_approval_imports_the_items_then_their_stock(self):
        plan, items, stock = self._planned()
        approval = self._answered(plan)["approval"]

        with ImportRunCase._each_row_commits(self):
            response = self._run("run_migration_plan", {"plan": plan, **approval})

        self.assertTrue(response["success"], response)
        self.assertEqual(import_plan.get_plan(plan).status, "Completed", import_plan.get_plan(plan).steps)
        self.assertTrue(frappe.db.exists("Item", self.code))
        self.assertEqual(
            frappe.db.get_value(
                "Stock Reconciliation Item",
                {"item_code": self.code, "docstatus": 1},
                ["qty", "valuation_rate"],
            ),
            (10, 5),
        )


@unittest.skipUnless(
    "erpnext" in frappe.get_installed_apps(), "needs ERPNext's Item and Stock Reconciliation"
)
class TestTheStartQuestions(StockPlanCase):
    """The company and the cut-off are asked once, at the start, on one choice card: not as text,
    and not again file by file or in the plan's questions."""

    def _planned(self):
        self.code = f"NEW-{self.tag}"
        items, stock = self._items(self.code), self._stock([f"{self.code},{self.stores},10,5"])
        response = self._run("plan_migration", {"sessions": [stock, items]})
        self.assertTrue(response["success"], response)
        return response["result"]

    def test_the_plan_offers_the_company_and_dates_to_pick(self):
        setup = self._planned()["opening_setup"]

        companies = frappe.get_all("Company", pluck="name")
        if len(companies) == 1:
            self.assertEqual(setup["company"], companies[0])  # nothing to ask
        else:
            self.assertIn(self.company, setup["companies"])
        choices = setup["cut_off_choices"]
        self.assertEqual(choices[-1], "another_date")
        last_month_end = str(frappe.utils.get_last_day(frappe.utils.add_months(frappe.utils.today(), -1)))
        self.assertIn(last_month_end, choices)
        self.assertEqual(choices[:-1], sorted(choices[:-1], reverse=True))

    def test_the_picked_cut_off_isnt_asked_again(self):
        plan = self._planned()["plan"]

        response = self._run("plan_migration", {"sessions": [], "plan": plan, "cut_off": self.date})
        questions = self._run("dry_run_import", {"plan": plan})["result"]["questions"]

        self.assertTrue(response["success"], response)
        self.assertEqual(response["result"]["opening_setup"]["cut_off"], self.date)
        self.assertNotIn("cut_off", [q["kind"] for q in questions])

    def test_a_picked_date_the_files_dont_have_is_still_asked(self):
        plan = self._planned()["plan"]
        other = frappe.utils.add_days(self.date, -1)

        self._run("plan_migration", {"sessions": [], "plan": plan, "cut_off": other})
        questions = self._run("dry_run_import", {"plan": plan})["result"]["questions"]

        self.assertIn("cut_off", [q["kind"] for q in questions])  # the stock file has another date

    def test_a_cut_off_that_isnt_a_date_is_refused(self):
        plan = self._planned()["plan"]

        response = self._run("plan_migration", {"sessions": [], "plan": plan, "cut_off": "30 Sept"})

        self.assertFalse(response["success"], response)
        self.assertIn("YYYY-MM-DD", response["result"]["error"])

    def test_after_apply_all_the_plan_runs_without_another_card(self):
        plan = self._planned()["plan"]
        asked = self._run("dry_run_import", {"plan": plan})["result"]

        answered = self._run(
            "dry_run_import",
            {
                "plan": plan,
                "answers": [
                    {"id": "plan:cut_off", "date": self.date},
                    {"id": "plan:failure_rule", "rule": "leave_out"},
                ],
            },
        )["result"]

        self.assertIn("ONE ask_user single_select", asked["next"])
        self.assertTrue(answered["ready"], answered)
        self.assertIn("call run_migration_plan now", answered["next"])


class TestCutOffChoices(unittest.TestCase):
    def _choices(self, file_name, on):
        return import_plan.cut_off_choices([frappe._dict(file_name=file_name)], on)

    def test_a_day_the_file_name_gives_is_offered_with_its_year(self):
        choices = self._choices("Closing_Stock_30-Sep.xlsx", "2026-11-05")

        self.assertIn("2026-09-30", choices)
        self.assertIn("2026-10-31", choices)  # the last month end
        self.assertTrue(all(date <= "2026-11-05" for date in choices))

    def test_a_day_not_come_yet_this_year_is_last_years(self):
        choices = self._choices("Closing_Stock_30-Sep.xlsx", "2026-09-15")

        self.assertIn("2025-09-30", choices)
        self.assertNotIn("2026-09-30", choices)

    def test_only_a_months_own_name_is_a_date(self):
        self.assertNotIn("2026-09-30", self._choices("Stock_30-Sepac.xlsx", "2026-11-05"))
        self.assertIn("2026-09-30", self._choices("Stock 30 September.xlsx", "2026-11-05"))

    def test_a_day_the_month_doesnt_have_is_skipped(self):
        self.assertEqual(
            self._choices("Stock_31-Sep.xlsx", "2026-11-05"), self._choices("Stock.xlsx", "2026-11-05")
        )
