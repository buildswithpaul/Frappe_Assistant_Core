# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""The Account Category of each account of the client's chart (ERPNext v16): the Schedule III and IFRS
statements place an account by its category, and read it from ledgers only. Live, 2026-11-19: none of a
client's 1,043 imported accounts had one, so those statements left them out."""

import unittest

import frappe

from frappe_assistant_core.tests.chart_case import ACCOUNT_MAPPING, ChartCase
from frappe_assistant_core.utils import compat, import_chart

HEADER = "Name,Number,Parent,Type,Root,Group,Category"
MAPPING = {**ACCOUNT_MAPPING, "Category": "account_category"}

#: A client's chart as the live one has it: fixed deposits typed "Fixed Asset", banks with no type
CHART = [
    "Assets,,,,Asset,1,",
    "Current Assets,2210100,Assets,,Asset,1,",
    "Current Investments,2210200,Current Assets,,Asset,1,",
    "Fixed Deposit - Punjab National Bank,2210210,Current Investments,Fixed Asset,Asset,0,",
    "FD Sweep Account,2210211,Current Investments,Current Asset,Asset,0,",
    "Interest Accrued But Not Due On Fixed Deposit,2210300,Current Assets,Fixed Asset,Asset,0,",
    "Bank Account,2230100,Current Assets,,Asset,1,",
    "Axis_3537_LS,2230110,Bank Account,,Asset,0,",
    "Advance Tax,2290100,Current Assets,,Asset,0,",
    "Odd Asset 77,2299100,Current Assets,,Asset,0,",
    "Non-Current Assets,2350100,Assets,,Asset,1,",
    "Investment in Fixed Deposit greater than 1 year,2350200,Non-Current Assets,Fixed Asset,Asset,0,",
    "Laptops,2350300,Non-Current Assets,Fixed Asset,Asset,0,",
    "Liabilities,,,,Liability,1,",
    "Short Term Borrowings,3100100,Liabilities,,Liability,1,",
    "HDFC OD,3100110,Short Term Borrowings,Bank,Liability,0,",
    "Sundry Creditors,3200100,Liabilities,,Liability,1,",
    "Acme Supplies,3200110,Sundry Creditors,Payable,Liability,0,",
    "GST Payable,3300100,Liabilities,Tax,Liability,0,",
    "Equity,,,,Equity,1,",
    "Share Capital,4100100,Equity,,Equity,0,",
    "Income,,,,Income,1,",
    "Consulting Fees,5100100,Income,Direct Income,Income,0,",
    "Interest on FD,5100200,Income,,Income,0,",
    "Expenses,,,,Expense,1,",
    "Staff Costs,6100100,Expenses,,Expense,1,",
    "Salaries,6100110,Staff Costs,Expense Account,Expense,0,",
    "Bank Interest,6100200,Expenses,,Expense,0,",
]


@unittest.skipUnless(
    "erpnext" in frappe.get_installed_apps() and compat.has_field("Account", "account_category"),
    "Account Category is ERPNext v16's",
)
class TestChartCategories(ChartCase):
    def _session(self, rows=None):
        return self._chart(CHART if rows is None else rows, header=HEADER, mapping=MAPPING)

    def _classes(self, rows=None, answers=None):
        nodes = import_chart.read_chart(frappe.get_doc("FAC Import Session", self._session(rows)), "Root")
        import_chart.apply_answers(nodes, answers)
        return {n["name"]: c for n, c in zip(nodes, import_chart.classify(nodes))}

    def _category(self, classes, name):
        return (classes[name]["account_category"], classes[name]["category_from"])

    # -- where a category comes from ----------------------------------------------------------------

    def test_the_files_own_category_column_comes_first(self):
        rows = [*CHART[:7], "Axis_3537_LS,2230110,Bank Account,,Asset,0,Other Current Assets"]
        classes = self._classes(rows)

        self.assertEqual(self._category(classes, "Axis_3537_LS"), ("Other Current Assets", "column"))

    def test_a_category_the_site_does_not_have_is_listed_and_not_used(self):
        rows = [*CHART[:7], "Axis_3537_LS,2230110,Bank Account,,Asset,0,Moon Money"]
        checked = self._check(self._session(rows), root_type_column="Root")

        self.assertEqual(
            [(c["account"], c["value"]) for c in checked["categories_not_found"]],
            [("Axis_3537_LS", "Moon Money")],
        )
        classes = self._classes(rows)
        self.assertEqual(classes["Axis_3537_LS"]["account_category"], "Cash and Cash Equivalents")

    def test_a_fixed_deposit_is_an_investment_not_a_tangible_asset_whatever_its_type_says(self):
        classes = self._classes()

        self.assertEqual(
            classes["Fixed Deposit - Punjab National Bank"]["account_category"], "Short-term Investments"
        )
        self.assertEqual(
            classes["Investment in Fixed Deposit greater than 1 year"]["account_category"],
            "Long-term Investments",
        )
        self.assertEqual(
            classes["Interest Accrued But Not Due On Fixed Deposit"]["account_category"],
            "Other Current Assets",
        )
        self.assertEqual(classes["Laptops"]["account_category"], "Tangible Assets")

    def test_a_ledger_takes_its_groups_category(self):
        classes = self._classes()

        self.assertEqual(self._category(classes, "Bank Account"), ("Cash and Cash Equivalents", "name"))
        self.assertEqual(self._category(classes, "Axis_3537_LS"), ("Cash and Cash Equivalents", "parent"))
        self.assertEqual(self._category(classes, "FD Sweep Account"), ("Short-term Investments", "parent"))

    def test_an_overdraft_under_borrowings_is_a_borrowing_not_cash(self):
        classes = self._classes()

        self.assertEqual(classes["HDFC OD"]["account_category"], "Short-term Borrowings")

    def test_the_account_type_places_a_ledger_whose_names_say_nothing(self):
        classes = self._classes()

        self.assertEqual(self._category(classes, "Salaries"), ("Operating Expenses", "account type"))
        self.assertEqual(
            self._category(classes, "Consulting Fees"), ("Revenue from Operations", "account type")
        )
        self.assertEqual(classes["Acme Supplies"]["account_category"], "Trade Payables")

    def test_words_place_each_root_type_on_its_own_lines(self):
        classes = self._classes()

        self.assertEqual(classes["Advance Tax"]["account_category"], "Other Current Assets")
        self.assertEqual(classes["GST Payable"]["account_category"], "Current Tax Liabilities")
        self.assertEqual(classes["Share Capital"]["account_category"], "Share Capital")
        self.assertEqual(classes["Interest on FD"]["account_category"], "Investment Income")
        self.assertEqual(classes["Bank Interest"]["account_category"], "Finance Costs")

    def test_what_no_rule_places_gets_its_root_types_usual_line_and_is_listed_to_check(self):
        classes = self._classes()
        self.assertEqual(self._category(classes, "Odd Asset 77"), ("Other Current Assets", "fallback"))

        checked = self._check(self._session(), root_type_column="Root")
        self.assertEqual(
            [(c["account"], c["account_category"]) for c in checked["categories_to_check"]],
            [("Odd Asset 77", "Other Current Assets")],
        )
        self.assertEqual(checked["by_category"]["Cash and Cash Equivalents"], 1)

    def test_a_group_gets_no_fallback_category(self):
        classes = self._classes()

        # ERPNext reads the category of ledgers only: a guess on a group would be one more line to check
        self.assertEqual(self._category(classes, "Assets"), ("", ""))
        self.assertEqual(self._category(classes, "Staff Costs"), ("", ""))

    def test_an_answer_sets_the_category(self):
        classes = self._classes(answers={"Odd Asset 77": {"account_category": "Other Non-current Assets"}})

        self.assertEqual(self._category(classes, "Odd Asset 77"), ("Other Non-current Assets", "column"))
        self.assertEqual(classes["Odd Asset 77"]["root_type"], "Asset")

    def test_an_answer_with_a_category_the_site_does_not_have_is_refused(self):
        with self.assertRaises(import_chart.ChartProblem):
            self._classes(answers={"Odd Asset 77": {"account_category": "Moon Money"}})

    # -- what is written -----------------------------------------------------------------------------

    def test_add_puts_the_categories_on_the_accounts(self):
        done = self._run(
            "import_chart_of_accounts",
            {
                "session": self._session(),
                "company": self.company,
                "mode": "add",
                "root_type_column": "Root",
                "source_system": self.system,
            },
        )
        self.assertTrue(done["success"], done)

        def category(name):
            return frappe.db.get_value(
                "Account", {"company": self.company, "account_name": name}, "account_category"
            )

        self.assertEqual(category("Fixed Deposit - Punjab National Bank"), "Short-term Investments")
        self.assertEqual(category("Axis_3537_LS"), "Cash and Cash Equivalents")
        self.assertEqual(category("Salaries"), "Operating Expenses")

    def test_replace_puts_the_categories_on_the_accounts(self):
        session = self._session()
        self._clear_references()
        nodes = import_chart.read_chart(frappe.get_doc("FAC Import Session", session), "Root")
        figures = import_chart.replace_figures(self.company, nodes)
        done = self._run(
            "replace_chart_of_accounts",
            {
                "session": session,
                "company": self.company,
                "root_type_column": "Root",
                "accounts_removed": figures["accounts_removed"],
                "accounts_created": figures["accounts_created"],
                "tax_setup_removed": figures["tax_setup_removed"],
                "source_system": self.system,
            },
        )
        self.assertTrue(done["success"], done)

        ledgers = frappe.get_all(
            "Account",
            filters={"company": self.company, "is_group": 0},
            fields=["account_name", "account_category"],
        )
        self.assertEqual([a.account_name for a in ledgers if not a.account_category], [])
        self.assertEqual(
            frappe.db.get_value(
                "Account", {"company": self.company, "account_name": "HDFC OD"}, "account_category"
            ),
            "Short-term Borrowings",
        )

    def test_categories_mode_fills_the_empty_categories_of_a_companys_accounts(self):
        frappe.db.set_value("Account", {"company": self.company}, "account_category", None)
        cash = frappe.db.get_value(
            "Account", {"company": self.company, "account_type": "Cash", "is_group": 0}
        )
        frappe.db.set_value("Account", cash, "account_category", "Other Current Assets")  # the user's own

        done = self._run("import_chart_of_accounts", {"company": self.company, "mode": "categories"})

        self.assertTrue(done["success"], done)
        result = done["result"]
        self.assertGreater(result["categories_set"], 0)
        self.assertEqual(frappe.db.get_value("Account", cash, "account_category"), "Other Current Assets")
        debtors = frappe.db.get_value(
            "Account", {"company": self.company, "account_type": "Receivable", "is_group": 0}
        )
        self.assertEqual(frappe.db.get_value("Account", debtors, "account_category"), "Trade Receivables")
        left = frappe.get_all(
            "Account", filters={"company": self.company, "is_group": 0, "account_category": ["is", "not set"]}
        )
        self.assertEqual(left, [])

    def test_categories_mode_again_sets_nothing(self):
        self._run("import_chart_of_accounts", {"company": self.company, "mode": "categories"})

        again = self._run("import_chart_of_accounts", {"company": self.company, "mode": "categories"})

        self.assertTrue(again["success"], again)
        self.assertEqual(again["result"]["categories_set"], 0)


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Account and Company")
class TestChartWithoutCategories(ChartCase):
    """On ERPNext v15 there are no categories: nothing about them is shown, asked or written."""

    def test_the_check_names_categories_only_where_the_site_has_them(self):
        checked = self._check(self._chart())

        has = compat.has_field("Account", "account_category")
        self.assertEqual("by_category" in checked, has)
        self.assertEqual("categories_to_check" in checked, has)

    def test_categories_mode_on_a_site_without_them_is_refused(self):
        if compat.has_field("Account", "account_category"):
            self.skipTest("this site has Account Category")
        done = self._run("import_chart_of_accounts", {"company": self.company, "mode": "categories"})

        self.assertFalse(done["success"])


#: A chart exported from another ERPNext company (abbreviation CCBF), as its tree shows it
CCBF_CHART = [
    "1000 - Assets - CCBF,,,,Asset,1",
    "1100 - CCBF Bank Group - CCBF,,1000 - Assets - CCBF,,Asset,1",
    "141600 - State Bank of India - Saving account - CCBF,,1100 - CCBF Bank Group - CCBF,Bank,Asset,0",
    "141601 - Bharat Kosh - CCBF,,1100 - CCBF Bank Group - CCBF,Bank,Asset,0",
    "2000 - Liabilities - CCBF,,,,Liability,1",
    "2100 - Creditors - CCBF,,2000 - Liabilities - CCBF,Payable,Liability,0",
]
#: Numbered names with no abbreviation (live, Sambhav: "2210100 - Current Assets")
NUMBERED_CHART = [
    "Application of Funds (Assets),,,,Asset,1",
    "2210100 - Sambhav Current Assets,,Application of Funds (Assets),,Asset,1",
    "2220100 - Sambhav Cash Box,,2210100 - Sambhav Current Assets,Cash,Asset,0",
    "2230100 - Sambhav Bank,,2210100 - Sambhav Current Assets,Bank,Asset,0",
]


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Account and Company")
class TestChartNamesFromAnotherCompany(ChartCase):
    """A file whose names carry another ERPNext company's account numbers and abbreviation: ERPNext adds
    this company's own, so kept as they are they would be doubled. The user decides."""

    def _add(self, session, **extra):
        return self._run(
            "import_chart_of_accounts",
            {
                "session": session,
                "company": self.company,
                "mode": "add",
                "root_type_column": "Root",
                "source_system": self.system,
                **extra,
            },
        )

    def test_the_check_reports_the_numbers_and_the_abbreviation_and_asks(self):
        checked = self._check(self._chart(CCBF_CHART), root_type_column="Root")

        found = checked["names_from_another_company"]
        self.assertEqual(
            (
                found["abbreviation"],
                found["names_with_abbreviation"],
                found["names_with_number"],
                found["cleaned"],
            ),
            ("CCBF", 6, 6, False),
        )
        self.assertIn({"in_the_file": "1000 - Assets - CCBF", "cleaned": "Assets"}, found["examples"])
        self.assertIn("clean_names", checked["names_question"])

    def test_numbers_alone_are_reported_too(self):
        checked = self._check(self._chart(NUMBERED_CHART), root_type_column="Root")

        found = checked["names_from_another_company"]
        self.assertEqual((found["abbreviation"], found["names_with_number"]), (None, 3))

    def test_plain_names_are_not_reported(self):
        checked = self._check(self._chart())

        self.assertNotIn("names_from_another_company", checked)

    def test_putting_the_chart_on_waits_for_the_users_answer(self):
        done = self._add(self._chart(CCBF_CHART))

        self.assertFalse(done["success"])
        self.assertIn("clean_names", done["error"])
        self.assertFalse(
            frappe.db.exists("Account", {"company": self.company, "account_name": ["like", "%CCBF%"]})
        )

    def test_cleaned_names_lose_the_other_companys_number_and_abbreviation(self):
        done = self._add(self._chart(CCBF_CHART), clean_names=True)

        self.assertTrue(done["success"], done)
        sbi = self._account("State Bank of India - Saving account")
        banks = self._account("CCBF Bank Group")
        self.assertEqual((sbi.account_number, sbi.parent_account), ("141600", banks.name))
        self.assertEqual(sbi.name, f"141600 - State Bank of India - Saving account - {self.abbr}")
        self.assertEqual(banks.account_number, "1100")

    def test_kept_names_stay_as_the_file_has_them(self):
        done = self._add(self._chart(CCBF_CHART), clean_names=False)

        self.assertTrue(done["success"], done)
        self.assertTrue(self._account("141601 - Bharat Kosh - CCBF"))

    def test_numbered_names_without_an_abbreviation_are_cleaned_too(self):
        done = self._add(self._chart(NUMBERED_CHART), clean_names=True)

        self.assertTrue(done["success"], done)
        cash = self._account("Sambhav Cash Box")
        self.assertEqual(
            (cash.account_number, cash.parent_account),
            ("2220100", self._account("Sambhav Current Assets").name),
        )

    def test_a_cleaned_name_finds_the_companys_own_account_of_that_name(self):
        # "2220100 - Cash" is the company's own Cash once its number is off: add keeps that one
        rows = [*NUMBERED_CHART, "2220200 - Cash,,2210100 - Sambhav Current Assets,Cash,Asset,0"]
        cash = frappe.db.get_value(
            "Account", {"company": self.company, "account_name": "Cash", "is_group": 0}
        )

        done = self._add(self._chart(rows), clean_names=True)

        self.assertTrue(done["success"], done)
        self.assertNotIn("2220200 - Cash - " + self.abbr, done["result"]["created"])
        self.assertEqual(frappe.db.count("Account", {"company": self.company, "account_name": "Cash"}), 1)
        self.assertTrue(cash)
