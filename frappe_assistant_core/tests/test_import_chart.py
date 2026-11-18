# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Reading and classifying the client's chart, its problems, and the modes (#34422 P4.1, CA-1 to CA-3, CA-8)."""

import unittest
from unittest.mock import patch

import frappe

from frappe_assistant_core.tests.chart_case import CLIENT_CHART, ChartCase
from frappe_assistant_core.utils import import_chart
from frappe_assistant_core.utils.tool_category_detector import PRIVILEGED_TOOLS, READ_ONLY_TOOLS, WRITE_TOOLS


def outline(checked):
    return {row["account"]: row for row in checked["outline"]}


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Account and Company")
class TestReadChart(ChartCase):
    def _nodes(self, session):
        return import_chart.read_chart(frappe.get_doc("FAC Import Session", session))

    # -- the tree ----------------------------------------------------------------------------------

    def test_the_tree_is_shown_with_its_counts(self):
        checked = self._check(self._chart())

        self.assertEqual((checked["accounts"], checked["groups"], checked["ledgers"]), (13, 7, 6))
        self.assertEqual(checked["by_root_type"], {"Asset": 6, "Liability": 3, "Income": 2, "Expense": 2})

    def test_a_group_is_an_account_with_accounts_under_it(self):
        nodes = self._nodes(self._chart())

        by_name = {n["name"]: n for n in nodes}
        self.assertTrue(by_name["Client Banks"]["is_group"])
        self.assertFalse(by_name["HDFC Current"]["is_group"])

    def test_an_is_group_column_decides_when_the_file_has_one(self):
        nodes = self._nodes(self._chart(["Pool,,,,,Yes", "Empty Group,,Pool,,,Yes", "Leaf,,Pool,,,No"]))

        by_name = {n["name"]: n for n in nodes}
        self.assertTrue(by_name["Empty Group"]["is_group"])  # no accounts under it yet, still a group
        self.assertFalse(by_name["Leaf"]["is_group"])

    def test_only_the_top_levels_are_outlined(self):
        outlined = outline(self._check(self._chart()))

        self.assertIn("Client Banks", outlined)
        self.assertNotIn("HDFC Current", outlined)

    def test_a_file_with_no_account_name_column_is_refused(self):
        session = self._chart(mapping={"Number": "account_number"})

        checked = self._run("dry_run_import", {"session": session, "chart": {}})

        self.assertFalse(checked["success"])
        self.assertIn("Account Name", checked["error"])

    def test_a_session_that_does_not_exist_is_refused(self):
        self.assertFalse(self._run("dry_run_import", {"session": "IMP-0000-00000", "chart": {}})["success"])

    # -- classification (C-D3) -------------------------------------------------------------------------

    def test_words_in_the_name_place_an_account_and_a_ledger_follows_its_group(self):
        outlined = outline(self._check(self._chart()))
        nodes = {n["name"]: c for n, c in zip(*self._classified())}

        self.assertEqual(
            (outlined["Client Assets"]["root_type"], outlined["Client Assets"]["from"]), ("Asset", "name")
        )
        self.assertEqual(
            (nodes["HDFC Current"]["root_type"], nodes["HDFC Current"]["account_type"]), ("Asset", "Bank")
        )
        self.assertEqual(nodes["Acme Customers"]["account_type"], "Receivable")
        self.assertEqual(nodes["Vendor Pool"]["account_type"], "Payable")
        self.assertEqual(nodes["Vendor Pool"]["root_type"], "Liability")

    def test_a_word_in_the_name_does_not_outrank_the_parents_root_type(self):
        names, classes = self._classified([*CLIENT_CHART, "Bank Fees,5100,Client Expenses,,,"])
        by_name = dict(zip([n["name"] for n in names], classes))

        self.assertEqual(
            (by_name["Bank Fees"]["root_type"], by_name["Bank Fees"]["account_type"]), ("Expense", "")
        )
        self.assertEqual(by_name["HDFC Current"]["account_type"], "Bank")  # a bank under assets still is

    def _classified(self, rows=None, root_type_column=None):
        nodes = import_chart.read_chart(
            frappe.get_doc("FAC Import Session", self._chart(rows)), root_type_column
        )
        classes = import_chart.classify(nodes)
        return [{"name": n["name"]} for n in nodes], classes

    def test_a_group_takes_no_account_type_only_its_ledgers_do(self):
        names, classes = self._classified()
        by_name = dict(zip([n["name"] for n in names], classes))

        self.assertEqual(by_name["Client Banks"]["account_type"], "")
        self.assertEqual(by_name["Client Banks"]["root_type"], "Asset")

    def test_the_files_own_columns_come_first(self):
        names, classes = self._classified(["Odd Account,,,Receivable,Liability,"], root_type_column="Root")

        self.assertEqual(
            (classes[0]["root_type"], classes[0]["account_type"], classes[0]["source"]),
            ("Liability", "Receivable", "column"),
        )

    def test_tally_primary_groups_place_the_ledgers_below_them(self):
        rows = [
            "Sundry Debtors,,,,,",
            "Rao Traders,,Sundry Debtors,,,",
            "Bank Accounts,,,,,",
            "SBI,,Bank Accounts,,,",
            "Duties & Taxes,,,,,",
            "GST Payable,,Duties & Taxes,,,",
            "Capital Account,,,,,",
            "Owner Funds,,Capital Account,,,",
        ]
        names, classes = self._classified(rows)
        by_name = dict(
            zip(
                [
                    "Sundry Debtors",
                    "Rao Traders",
                    "Bank Accounts",
                    "SBI",
                    "Duties & Taxes",
                    "GST Payable",
                    "Capital Account",
                    "Owner Funds",
                ],
                classes,
            )
        )

        self.assertEqual(
            (
                by_name["Rao Traders"]["root_type"],
                by_name["Rao Traders"]["account_type"],
                by_name["Rao Traders"]["source"],
            ),
            ("Asset", "Receivable", "tally group"),
        )
        self.assertEqual((by_name["SBI"]["root_type"], by_name["SBI"]["account_type"]), ("Asset", "Bank"))
        self.assertEqual(
            (by_name["GST Payable"]["root_type"], by_name["GST Payable"]["account_type"]),
            ("Liability", "Tax"),
        )
        self.assertEqual(by_name["Owner Funds"]["root_type"], "Equity")

    def test_a_tally_group_that_must_be_asked_is_left_unclassified(self):
        checked = self._check(self._chart(["Suspense A/c,,,,,", "Branch / Divisions,,,,,"]))

        self.assertEqual(
            [u["account"] for u in checked["unclassified"]], ["Suspense A/c", "Branch / Divisions"]
        )

    def test_every_account_that_cannot_be_classified_comes_in_one_list(self):
        checked = self._check(
            self._chart(["Mystery One,,,,,", "Mystery Two,,Mystery One,,,", "Zed Zed,,,,,", "Rent Paid,,,,,"])
        )

        listed = [u["account"] for u in checked["unclassified"]]
        self.assertEqual(
            listed, ["Mystery One", "Mystery Two", "Zed Zed"]
        )  # Rent Paid is an expense by its name
        self.assertEqual(checked["classified_from"]["unclassified"], 3)

    def test_an_answer_places_the_account_and_what_is_under_it(self):
        rows = ["Mystery One,,,,,", "Mystery Two,,Mystery One,,,"]
        session = self._chart(rows)

        checked = self._check(session, classifications={"Mystery One": {"root_type": "Equity"}})

        self.assertEqual(checked["unclassified"], [])
        self.assertEqual(checked["by_root_type"], {"Equity": 2})

    def test_an_answer_with_a_root_type_that_is_not_one_is_refused(self):
        session = self._chart(["Mystery One,,,,,"])

        refused = self._run(
            "dry_run_import",
            {"session": session, "chart": {"classifications": {"Mystery One": {"root_type": "Money"}}}},
        )

        self.assertFalse(refused["success"])
        self.assertIn("root type", refused["error"])

    def test_an_answer_for_an_account_not_in_the_file_is_refused(self):
        session = self._chart(["Mystery One,,,,,"])

        refused = self._run(
            "dry_run_import",
            {"session": session, "chart": {"classifications": {"Nope": {"root_type": "Asset"}}}},
        )

        self.assertFalse(refused["success"])

    def test_an_account_type_erpnext_does_not_have_is_dropped_from_the_proposal(self):
        names, classes = self._classified(["Odd,,,Wizardry,Asset,"], root_type_column="Root")

        self.assertEqual((classes[0]["root_type"], classes[0]["account_type"]), ("Asset", ""))

    # -- problems (CA-8) -------------------------------------------------------------------------------

    def _problems(self, rows, **kw):
        return {p["kind"]: p for p in self._check(self._chart(rows, **kw))["problems"]}

    def test_a_cycle_is_listed(self):
        found = self._problems(["Alpha Assets,,Beta Assets,,,", "Beta Assets,,Alpha Assets,,,"])

        self.assertIn("cycle", found)
        self.assertEqual(found["cycle"]["rows"], [2, 3])

    def test_an_account_under_a_ledger_is_listed(self):
        found = self._problems(["Cash Box,,,,,No", "Stray,,Cash Box,,,"])

        self.assertIn("under_ledger", found)
        self.assertIn("Cash Box", found["under_ledger"]["message"])

    def test_two_accounts_with_one_name_are_listed(self):
        found = self._problems(["Rent,,,,,", "Rent,,,,,"])

        self.assertEqual(found["duplicate_name"]["rows"], [2, 3])

    def test_two_accounts_with_one_number_are_listed(self):
        found = self._problems(["Rent,5000,,,,", "Salary,5000,,,,"])

        self.assertIn("duplicate_number", found)

    # A client's chart made for ERPNext's own Chart of Accounts Importer: a sub-account may repeat its parent's
    # name under its own number ("Advance Tax" 2290110 under "Advance Tax" 2290100), which ERPNext names
    # "2290110 - Advance Tax - ABBR", and the Parent Account Number column says which parent is meant.
    ERPNEXT_HEADER = (
        "Account Name,Parent Account,Account Number,Parent Account Number,Is Group,Account Type,Root Type"
    )
    ERPNEXT_MAPPING = {
        "Account Name": "account_name",
        "Parent Account": "parent_account",
        "Account Number": "account_number",
        "Parent Account Number": "Don't Import",
        "Is Group": "is_group",
        "Account Type": "account_type",
        "Root Type": "Don't Import",
    }

    def _erpnext_chart(self, rows):
        return self._chart(rows, header=self.ERPNEXT_HEADER, mapping=self.ERPNEXT_MAPPING)

    def test_one_name_under_two_numbers_is_two_accounts(self):
        session = self._erpnext_chart(
            [
                "Client Assets,,1000,,1,,Asset",
                "Advance Tax,Client Assets,1100,1000,1,,Asset",
                "Advance Tax,Advance Tax,1110,1100,0,,Asset",
            ]
        )

        self.assertEqual(self._check(session, root_type_column="Root Type")["problems"], [])

    def test_the_parent_number_picks_the_parent_when_names_repeat(self):
        # The ledger "Other Income" comes first in the file: by name, Misc Income would go under it
        session = self._erpnext_chart(
            [
                "Client Income,,3000,,1,,Income",
                "Other Income,Client Income,3100,3000,0,Income Account,Income",
                "Other Income,Client Income,3200,3000,1,,Income",
                "Misc Income,Other Income,3210,3200,0,Income Account,Income",
            ]
        )

        self.assertEqual(self._check(session, root_type_column="Root Type")["problems"], [])
        nodes = import_chart.read_chart(frappe.get_doc("FAC Import Session", session), "Root Type")
        misc = next(n for n in nodes if n["name"] == "Misc Income")
        self.assertEqual(nodes[misc["parent"]]["number"], "3200")

    def test_one_name_and_one_number_twice_is_still_listed(self):
        session = self._erpnext_chart(["Rent,,5000,,0,,Expense", "Rent,,5000,,0,,Expense"])

        kinds = {p["kind"] for p in self._check(session, root_type_column="Root Type")["problems"]}
        self.assertIn("duplicate_number", kinds)

    def test_a_clean_chart_has_no_problems(self):
        self.assertEqual(self._check(self._chart())["problems"], [])

    def test_a_parent_the_file_does_not_hold_is_named(self):
        checked = self._check(self._chart(["Petty Cash,,Cash In Hand,,,"]))

        self.assertEqual(checked["parents_not_in_the_file"], ["Cash In Hand"])

    def test_nothing_is_written_to_the_company(self):
        before = frappe.db.count("Account", {"company": self.company})

        self._check(self._chart(), company=self.company)

        self.assertEqual(frappe.db.count("Account", {"company": self.company}), before)

    # -- the modes (CA-3) --------------------------------------------------------------------------------

    def test_a_company_with_no_transactions_is_offered_all_three_modes_add_first(self):
        modes = self._check(self._chart(), company=self.company)["modes"]

        self.assertEqual(modes["offered"], ["map", "add", "replace"])
        self.assertEqual(modes["default"], "add")
        self.assertIsNone(modes["replace_refused"])

    def test_a_company_with_transactions_is_offered_map_and_add_and_replace_is_refused_with_the_reason(self):
        self._make_a_ledger_entry()

        modes = self._check(self._chart(), company=self.company)["modes"]

        self.assertEqual(modes["offered"], ["map", "add"])
        self.assertEqual(modes["default"], "map")
        self.assertIn("general ledger entries", modes["replace_refused"])
        self.assertNotIn("replace_figures", modes)

    def test_the_check_gives_the_replace_figures_for_one_approval_card(self):
        # Live, 2026-11-17: the first replace call left the figures out to learn them, and the user
        # approved a card without them, then a second card with them.
        session = self._chart()

        modes = self._check(session, company=self.company)["modes"]

        expected = import_chart.replace_figures(
            self.company, import_chart.read_chart(frappe.get_doc("FAC Import Session", session))
        )
        self.assertEqual(modes["replace_figures"], expected)
        self.assertEqual(expected["accounts_created"], 13)

    def test_the_company_must_exist(self):
        refused = self._run(
            "dry_run_import",
            {"session": self._chart(), "chart": {"company": "No Such Company"}},
        )

        self.assertFalse(refused["success"])

    def test_the_check_lists_accounts_whose_type_does_not_belong_under_their_root(self):
        # Live, 2026-11-18: a client's chart had 13 "Stock" accounts under Equity; ERPNext books stock to them
        session = self._chart(["Client Equity,,,,,Yes", "Share Stock,3100,Client Equity,Stock,,No"])

        checked = self._check(
            session,
            classifications={
                "Client Equity": {"root_type": "Equity"},
                "Share Stock": {"root_type": "Equity", "account_type": "Stock"},
            },
        )

        self.assertEqual(
            [
                (d["account"], d["account_type"], d["root_type"], d["expected_root_type"])
                for d in checked["doubtful"]
            ],
            [("Share Stock", "Stock", "Equity", "Asset")],
        )

    def test_a_bank_account_under_liabilities_is_not_doubtful(self):
        # an overdraft is a bank account and a liability
        session = self._chart(["Client Loans,,,,,Yes", "OD Account,2010,Client Loans,Bank,,No"])

        checked = self._check(
            session,
            classifications={
                "Client Loans": {"root_type": "Liability"},
                "OD Account": {"root_type": "Liability", "account_type": "Bank"},
            },
        )

        self.assertEqual(checked["doubtful"], [])

    def test_on_a_site_of_one_company_the_check_uses_it_unasked(self):
        # the shared test site holds a company per test: the list a one-company site returns stands in
        real = frappe.get_list

        def one_company(doctype, *args, **kwargs):
            # only the list of company names the check asks for: the replace check reads Company rows too
            if doctype == "Company" and kwargs.get("pluck") == "name":
                return [self.company]
            return real(doctype, *args, **kwargs)

        with patch.object(frappe, "get_list", side_effect=one_company):
            checked = self._check(self._chart())

        self.assertEqual(checked["company"], self.company)
        self.assertIn("modes", checked)

    def test_on_a_site_of_several_companies_the_check_names_none(self):
        self.assertGreater(len(frappe.get_all("Company", limit=2)), 1)

        checked = self._check(self._chart())

        self.assertNotIn("company", checked)

    # -- categories ----------------------------------------------------------------------------------------

    def test_the_tools_are_in_the_right_categories(self):
        self.assertIsNone(self.registry.get_tool("check_chart_of_accounts"))  # dry_run_import with chart now
        self.assertIn("import_chart_of_accounts", WRITE_TOOLS)
        self.assertIn("replace_chart_of_accounts", PRIVILEGED_TOOLS)
