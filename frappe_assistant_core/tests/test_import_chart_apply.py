# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Putting the client's chart on a company: map, add, replace, and finding its accounts by the client's names
(#34422 P4.2 and P4.3, CA-3 to CA-7, C-D2, C-D5)."""

import unittest
from unittest.mock import patch

import frappe

from frappe_assistant_core.tests.chart_case import ChartCase
from frappe_assistant_core.utils import compat, import_chart
from frappe_assistant_core.utils import import_keys as keys
from frappe_assistant_core.utils import import_opening_balances as balances


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Account and Company")
class TestImportChart(ChartCase):
    def _import(self, session, mode="add", **extra):
        return self._run(
            "import_chart_of_accounts",
            {
                "session": session,
                "company": self.company,
                "mode": mode,
                "source_system": self.system,
                **extra,
            },
        )

    def _added(self, rows=None, **extra):
        session = self._chart(rows)
        done = self._import(session, "add", **extra)
        self.assertTrue(done["success"], done)
        return session, done["result"]

    # -- add (CA-6) ----------------------------------------------------------------------------------------

    def test_add_creates_the_accounts_under_the_right_parents(self):
        _session, result = self._added()

        # Office Rent is in the standard chart too: the company's own account is kept
        self.assertEqual(len(result["created"]), 12)
        self.assertEqual(self._account("Office Rent").parent_account.startswith("Indirect Expenses"), True)
        banks = self._account("Client Banks")
        hdfc = self._account("HDFC Current")
        self.assertEqual(
            (hdfc.parent_account, hdfc.root_type, hdfc.account_type), (banks.name, "Asset", "Bank")
        )
        self.assertEqual((hdfc.is_group, hdfc.account_number), (0, "1010"))
        self.assertEqual(self._account("Vendor Pool").account_type, "Payable")

    def test_an_unknown_mode_is_refused_and_writes_nothing(self):
        session = self._chart()
        before = frappe.db.count("Account", {"company": self.company})
        refused = self._import(session, "neither")
        self.assertFalse(refused["success"])
        self.assertEqual(frappe.db.count("Account", {"company": self.company}), before)

    def test_a_root_of_the_client_goes_under_the_companys_root_for_its_type(self):
        self._added()

        root = frappe.db.get_value(
            "Account",
            {
                "company": self.company,
                "root_type": "Asset",
                "is_group": 1,
                "parent_account": ["is", "not set"],
            },
        )
        self.assertEqual(self._account("Client Assets").parent_account, root)

    def test_parents_are_created_before_their_children_whatever_the_order_in_the_file(self):
        rows = [
            "Deep Ledger,,Mid Group,,,",
            "Mid Group,,Top Assets,,,",
            "Top Assets,,,,Asset,",
        ]
        session = self._chart(rows)

        done = self._import(session, "add")

        self.assertTrue(done["success"], done)
        self.assertEqual(self._account("Deep Ledger").parent_account, self._account("Mid Group").name)
        self.assertEqual(self._account("Mid Group").parent_account, self._account("Top Assets").name)

    def test_an_account_the_company_already_has_is_kept_not_made_again(self):
        rows = ["Application of Funds (Assets),,,,,", "Client Cash Box,,Application of Funds (Assets),,,"]
        session = self._chart(rows)
        before = frappe.db.count("Account", {"company": self.company})

        done = self._import(session, "add")

        self.assertTrue(done["success"], done)
        self.assertEqual(frappe.db.count("Account", {"company": self.company}), before + 1)
        self.assertEqual(done["result"]["created"], [self._account("Client Cash Box").name])

    def test_adding_twice_creates_nothing_the_second_time(self):
        session, _result = self._added()

        again = self._import(session, "add")

        self.assertTrue(again["success"])
        self.assertEqual(again["result"]["created"], [])

    def test_a_parent_the_file_names_that_the_company_has_is_used(self):
        cash = frappe.db.get_value(
            "Account", {"company": self.company, "account_type": "Cash", "is_group": 1}
        )
        name = frappe.db.get_value("Account", cash, "account_name")
        session = self._chart([f"Till One,,{name},,,"])

        done = self._import(session, "add")

        self.assertTrue(done["success"], done)
        self.assertEqual(self._account("Till One").parent_account, cash)

    def test_a_parent_that_is_nowhere_is_refused_and_nothing_is_created(self):
        session = self._chart(["Orphan Cash,,No Such Group,,Asset,"])
        before = frappe.db.count("Account", {"company": self.company})

        refused = self._import(session, "add")

        self.assertFalse(refused["success"])
        self.assertIn("No Such Group", refused["error"])
        self.assertEqual(frappe.db.count("Account", {"company": self.company}), before)

    def test_a_failure_part_way_puts_back_what_was_created(self):
        session = self._chart(["First Group,,,,Asset,", "Second Group,,First Group,,,"])
        before = frappe.db.count("Account", {"company": self.company})
        real = import_chart._insert
        calls = []

        def fail_on_the_second(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise frappe.ValidationError("boom")
            return real(*args, **kwargs)

        with patch.object(import_chart, "_insert", side_effect=fail_on_the_second):
            refused = self._import(session, "add")

        self.assertFalse(refused["success"])
        self.assertEqual(frappe.db.count("Account", {"company": self.company}), before)

    def test_an_account_no_rule_can_place_is_refused_until_the_user_answers(self):
        session = self._chart(["Mystery One,,,,,"])

        refused = self._import(session, "add")

        self.assertFalse(refused["success"])
        self.assertIn("Mystery One", refused["error"])
        done = self._import(session, "add", classifications={"Mystery One": {"root_type": "Asset"}})
        self.assertTrue(done["success"], done)
        self.assertEqual(self._account("Mystery One").root_type, "Asset")

    def test_a_chart_with_problems_is_refused_with_them(self):
        session = self._chart(["Rent,,,,,", "Rent,,,,,"])

        refused = self._import(session, "add")

        self.assertFalse(refused["success"])
        self.assertIn("twice", refused["error"])

    def test_a_user_who_cannot_create_accounts_is_refused(self):
        session = self._chart()
        frappe.set_user(self.make_desk_user("nochart"))

        refused = self._import(session, "add")

        self.assertFalse(refused["success"])
        self.assertEqual(
            frappe.db.count("Account", {"company": self.company, "account_name": "Client Assets"}), 0
        )

    # -- old IDs (C-D5) --------------------------------------------------------------------------------------

    def test_the_clients_numbers_and_names_are_kept_as_old_ids(self):
        _session, result = self._added()

        hdfc = self._account("HDFC Current").name
        self.assertEqual(
            keys.resolve("Account", self.system, ["1010", "HDFC Current"]),
            {"1010": hdfc, "HDFC Current": hdfc},
        )
        self.assertGreaterEqual(result["old_ids_kept"], 13)

    def test_a_second_company_of_the_client_keeps_its_old_ids_too(self):
        self._added()
        abbr = "S" + frappe.generate_hash(length=4).upper()
        second = frappe.get_doc(
            {
                "doctype": "Company",
                "company_name": f"Second Co {self.tag}",
                "abbr": abbr,
                "default_currency": "JPY",
                "country": "Japan",
                "create_chart_of_accounts_based_on": "Standard Template",
                "chart_of_accounts": "Standard",
            }
        ).insert()
        self.company, self.abbr = second.name, abbr

        _session, result = self._added()  # the same chart: the same names and numbers

        own = f"{self.system} {abbr.lower()}"
        hdfc = self._account("HDFC Current").name
        self.assertGreaterEqual(result["old_ids_kept"], 13)
        self.assertEqual(result["old_id_systems"], [own])
        self.assertIn(own, result["message"])
        self.assertEqual(keys.resolve("Account", own, ["1010"]), {"1010": hdfc})

    def test_the_opening_balances_find_an_account_by_the_clients_number_or_name(self):
        self._added()
        hdfc = self._account("HDFC Current").name

        by_number = balances.find_account(self.company, self.abbr, "1010")
        by_name = balances.find_account(self.company, self.abbr, "HDFC Current")

        self.assertEqual((by_number.name, by_name.name), (hdfc, hdfc))

    def test_an_account_of_another_company_is_not_found_by_the_clients_id(self):
        self._added()

        self.assertIsNone(balances.find_account("Some Other Company", "OTH", "1010"))

    def test_an_id_nobody_kept_is_still_not_found(self):
        self._added()

        self.assertIsNone(balances.find_account(self.company, self.abbr, "9999"))

    def test_the_standard_lookups_still_come_first(self):
        self._added()
        cash = frappe.db.get_value(
            "Account", {"company": self.company, "account_type": "Cash", "is_group": 0}, ["name"]
        )

        self.assertEqual(balances.find_account(self.company, self.abbr, cash).name, cash)

    # -- map (CA-5) ---------------------------------------------------------------------------------------------

    def _standard_names(self):
        return {
            "cash": frappe.db.get_value(
                "Account", {"company": self.company, "account_type": "Cash", "is_group": 0}, "account_name"
            ),
            "number": frappe.db.get_value(
                "Account",
                {"company": self.company, "is_group": 0, "account_number": ["is", "set"]},
                ["account_name", "account_number"],
                as_dict=True,
            ),
        }

    def test_map_matches_the_clients_accounts_to_the_companys_and_creates_nothing(self):
        cash = self._standard_names()["cash"]
        session = self._chart(
            [
                "Application of Funds (Assets),,,,,",
                f"{cash},,Application of Funds (Assets),,,",
                "Strange Ledger,,Application of Funds (Assets),,,",
            ]
        )
        before = frappe.db.count("Account", {"company": self.company})

        done = self._import(session, "map")

        self.assertTrue(done["success"], done)
        self.assertEqual(frappe.db.count("Account", {"company": self.company}), before)
        self.assertEqual(done["result"]["created"], [])
        self.assertEqual([u["account"] for u in done["result"]["unmatched"]], ["Strange Ledger"])
        cash_account = frappe.db.get_value("Account", {"company": self.company, "account_name": cash})
        self.assertEqual(keys.resolve("Account", self.system, [cash]), {cash: cash_account})

    def test_map_falls_back_to_the_number_then_to_the_one_ledger_of_that_type(self):
        sample = frappe.db.get_value(
            "Account",
            {"company": self.company, "is_group": 0, "account_type": "Receivable"},
            ["name", "account_name"],
            as_dict=True,
        )
        session = self._chart(["Their Debtors,,,Receivable,,No"])

        proposal = import_chart.map_proposal(*self._classified(session), self.company)

        self.assertEqual(
            [(m["account"], m["matches"], m["how"]) for m in proposal["matched"]],
            [("Their Debtors", sample.name, "type")],
        )

    def _classified(self, session):
        nodes = import_chart.read_chart(frappe.get_doc("FAC Import Session", session))
        return nodes, import_chart.classify(nodes)

    def test_map_check_shows_what_matched_and_what_did_not(self):
        cash = self._standard_names()["cash"]
        session = self._chart([f"{cash},,,,Asset,No", "Strange Ledger,,,,Asset,No"])

        checked = self._check(session, company=self.company, root_type_column="Root")

        self.assertEqual((checked["map"]["matched"], checked["map"]["unmatched"]), (1, 1))

    def test_add_unmatched_adds_what_matched_nothing_under_its_parents_account(self):
        cash = self._standard_names()["cash"]
        cash_account = frappe.db.get_value("Account", {"company": self.company, "account_name": cash})
        session = self._chart([f"{cash},,,,Asset,No", "Strange Ledger,,,,Asset,No"])

        done = self._import(session, "map", add_unmatched=True, root_type_column="Root")

        self.assertTrue(done["success"], done)
        self.assertEqual(done["result"]["unmatched"], [])
        self.assertEqual(len(done["result"]["created"]), 1)
        self.assertTrue(self._account("Strange Ledger"))
        self.assertEqual(keys.resolve("Account", self.system, [cash]), {cash: cash_account})

    def test_map_works_on_a_company_with_transactions(self):
        self._make_a_ledger_entry()
        cash = self._standard_names()["cash"]
        session = self._chart([f"{cash},,,,Asset,No"])

        done = self._import(session, "map", root_type_column="Root")

        self.assertTrue(done["success"], done)

    # -- replace (CA-4, C-D2) -------------------------------------------------------------------------------------

    def _replace(self, session, clear=True, **extra):
        if clear:
            self._clear_references()
        figures = import_chart.replace_figures(
            self.company, import_chart.read_chart(frappe.get_doc("FAC Import Session", session))
        )
        return self._run(
            "replace_chart_of_accounts",
            {
                "session": session,
                "company": self.company,
                "accounts_removed": figures["accounts_removed"],
                "accounts_created": figures["accounts_created"],
                "source_system": self.system,
                **extra,
            },
        )

    def test_replace_removes_the_standard_chart_and_creates_the_clients(self):
        session = self._chart()
        standard = frappe.db.count("Account", {"company": self.company})

        done = self._replace(session)

        self.assertTrue(done["success"], done)
        self.assertEqual((done["result"]["removed"], done["result"]["created"]), (standard, 13))
        self.assertEqual(frappe.db.count("Account", {"company": self.company}), 13)
        self.assertEqual(self._account("HDFC Current").account_type, "Bank")
        self.assertEqual(self._account("Client Assets").parent_account, None)

    def test_replace_creates_two_sibling_accounts_of_one_name(self):
        # ERPNext's tree is keyed by name: two accounts of one name under one parent, told apart by their
        # numbers, became one, and its sub-accounts went with the other (3 of 1,043 lost, live test 2026-11-17)
        from frappe_assistant_core.tests.chart_case import CLIENT_CHART

        rows = [
            *CLIENT_CHART,
            "Service Fee,4100,Client Income,,,Yes",
            "Service Fee Retail,4110,Service Fee,,,",
            "Service Fee,4200,Client Income,,,",
        ]
        session = self._chart(rows)

        done = self._replace(session)

        self.assertTrue(done["success"], done)
        self.assertEqual(done["result"]["created"], len(rows))
        fees = frappe.get_all(
            "Account",
            filters={"company": self.company, "account_name": "Service Fee"},
            pluck="account_number",
            order_by="account_number",
        )
        self.assertEqual(fees, ["4100", "4200"])
        retail = self._account("Service Fee Retail")
        self.assertEqual(frappe.db.get_value("Account", retail.parent_account, "account_number"), "4100")

    def test_replace_sets_the_default_accounts_again_and_lists_the_ones_left_empty(self):
        done = self._replace(self._chart())["result"]

        self.assertIsInstance(done["defaults_left_empty"], list)
        receivable = frappe.db.get_value("Company", self.company, "default_receivable_account")
        self.assertEqual(receivable, self._account("Acme Customers").name)

    def test_replacing_again_with_the_same_chart_changes_nothing(self):
        # The chat called replace again after the first one had finished (live, 2026-11-18): the
        # second call deleted the 1,043 accounts the first one made and made them again.
        session = self._chart()
        self._replace(session)
        before = frappe.get_all(
            "Account", filters={"company": self.company}, fields=["name", "creation"], order_by="name"
        )

        again = self._replace(session, clear=False)

        self.assertTrue(again["success"], again)
        self.assertTrue(again["result"]["already_in_place"])
        self.assertEqual((again["result"]["removed"], again["result"]["created"]), (0, 0))
        self.assertIsInstance(again["result"]["defaults_left_empty"], list)
        after = frappe.get_all(
            "Account", filters={"company": self.company}, fields=["name", "creation"], order_by="name"
        )
        self.assertEqual(after, before)

    def test_replace_keeps_the_clients_ids(self):
        self._replace(self._chart())

        self.assertEqual(
            keys.resolve("Account", self.system, ["1010"]), {"1010": self._account("HDFC Current").name}
        )

    def test_replace_without_the_figures_is_refused_with_them(self):
        session = self._chart()
        self._clear_references()

        refused = self._run(
            "replace_chart_of_accounts",
            {"session": session, "company": self.company, "accounts_removed": 1, "accounts_created": 1},
        )

        self.assertFalse(refused["success"])
        self.assertEqual(refused["result"]["approval"]["accounts_created"], 13)
        # The skill has the first call leave the figures out to learn them: it must reach the tool.
        asked = self._run("replace_chart_of_accounts", {"session": session, "company": self.company})
        self.assertEqual(asked["result"]["approval"]["accounts_created"], 13, asked)
        self.assertTrue(
            frappe.db.exists("Account", {"company": self.company, "account_name": "Cash"})
            or frappe.db.count("Account", {"company": self.company}) > 13
        )

    def test_replace_is_refused_on_a_company_with_transactions_and_nothing_is_deleted(self):
        self._make_a_ledger_entry()
        before = frappe.db.count("Account", {"company": self.company})

        refused = self._replace(self._chart())

        self.assertFalse(refused["success"])
        self.assertIn("map or add instead", refused["error"])
        self.assertEqual(frappe.db.count("Account", {"company": self.company}), before)

    def test_replace_on_a_company_as_erpnext_made_it(self):
        # ERPNext gives every new company a row on a Cash mode of payment for its default cash account
        # (Company.set_mode_of_payment_account): a fresh company always has it, so it can't block a replace.
        old_cash = frappe.db.get_value("Company", self.company, "default_cash_account")
        modes = frappe.get_all(
            "Mode of Payment Account",
            filters={"company": self.company, "default_account": old_cash},
            pluck="parent",
        )
        self.assertTrue(modes)
        self._clear_references(modes_of_payment=False)

        done = self._replace(self._chart(), clear=False)

        self.assertTrue(done["success"], done)
        # the modes of payment follow the cash account to the new chart, never left on a deleted account
        new_cash = frappe.db.get_value("Company", self.company, "default_cash_account")
        linked = frappe.get_all(
            "Mode of Payment Account",
            filters={"company": self.company, "parent": ["in", modes]},
            pluck="default_account",
        )
        self.assertEqual(linked, [new_cash] * len(modes) if new_cash else [])
        self.assertEqual(done["result"]["cash_mode_of_payment_account"], new_cash)
        for account in linked:
            self.assertEqual(frappe.db.get_value("Account", account, "company"), self.company)

    def test_replace_is_refused_while_a_mode_of_payment_points_at_an_account(self):
        # A row on any account but the default cash one is the user's setup: where it goes is their call.
        # ERPNext 16 takes only a Bank, Cash or Receivable ledger on a mode of payment: the debtors one.
        self._clear_references()
        account = frappe.db.get_value(
            "Account", {"company": self.company, "is_group": 0, "account_type": "Receivable"}
        )
        self.assertNotEqual(account, frappe.db.get_value("Company", self.company, "default_cash_account"))
        frappe.get_doc(
            {
                "doctype": "Mode of Payment",
                "mode_of_payment": f"Till {self.tag}",
                "type": "Bank",
                "accounts": [{"company": self.company, "default_account": account}],
            }
        ).insert()
        before = frappe.db.count("Account", {"company": self.company})

        refused = self._replace(self._chart(), clear=False)

        self.assertFalse(refused["success"])
        self.assertIn(f"Till {self.tag}", refused["error"])
        self.assertEqual(frappe.db.count("Account", {"company": self.company}), before)

    def test_replace_that_fails_part_way_puts_the_old_chart_back(self):
        session = self._chart()
        before = frappe.db.count("Account", {"company": self.company})

        with patch.object(compat, "create_charts", side_effect=frappe.ValidationError("boom")):
            refused = self._replace(session)

        self.assertFalse(refused["success"])
        self.assertEqual(frappe.db.count("Account", {"company": self.company}), before)
        self.assertTrue(frappe.db.get_value("Company", self.company, "default_receivable_account"))

    def test_replace_needs_a_chart_whose_top_accounts_are_groups_with_a_root_type(self):
        session = self._chart(["Lone Ledger,,,,,No"])

        refused = self._replace(session)

        self.assertFalse(refused["success"])
        self.assertIn("root type", refused["error"])

    def test_replace_for_a_user_who_may_not_delete_accounts_is_refused(self):
        session = self._chart()
        self._clear_references()
        figures = import_chart.replace_figures(
            self.company, import_chart.read_chart(frappe.get_doc("FAC Import Session", session))
        )
        user = self.make_desk_user("nodelete")
        frappe.set_user(user)

        refused = self._run(
            "replace_chart_of_accounts",
            {
                "session": session,
                "company": self.company,
                "accounts_removed": figures["accounts_removed"],
                "accounts_created": figures["accounts_created"],
            },
        )

        self.assertFalse(refused["success"])
        self.assertTrue(frappe.db.count("Account", {"company": self.company}) > 13)

    def test_who_may_not_delete_accounts_is_not_told_what_points_at_them(self):
        # the company's own tax templates point at its accounts, as ERPNext sets them up for a new company
        user = self.make_desk_user("nodelete")
        frappe.set_user(user)

        problem = import_chart.replace_problem(self.company)

        self.assertIn("Accounts Manager", problem)
        self.assertNotIn("tax template", problem)

    def test_a_draft_documents_tax_row_on_an_account_blocks_a_replace(self):
        # A draft quotation's tax row, as the Quotation form saves it: the same child table as a tax
        # template's, under another parent, which the tax template check doesn't look at.
        self._clear_references()
        account = frappe.get_all(
            "Account", filters={"company": self.company, "is_group": 0}, pluck="name", limit=1
        )[0]
        row = frappe.get_doc(
            {
                "doctype": "Sales Taxes and Charges",
                "parenttype": "Quotation",
                "parentfield": "taxes",
                "parent": f"SAL-QTN-{self.tag}",
                "charge_type": "Actual",
                "account_head": account,
                "description": "Freight",
            }
        )
        row.db_insert()

        refs = import_chart.blocking_references(self.company)

        self.assertTrue(any(f"SAL-QTN-{self.tag}" in ref or "Quotation" in ref for ref in refs), refs)

    def test_replace_is_refused_while_any_record_points_at_an_account_and_says_which(self):
        # A user sets a warehouse's account in the form; ERPNext refuses to delete an account any record links
        # to, so the replace names it before deleting anything, whatever the doctype, not a listed few.
        session = self._chart()
        account = frappe.get_all(  # ERPNext 16 takes only a Stock ledger for a warehouse
            "Account",
            filters={"company": self.company, "is_group": 0, "account_type": "Stock"},
            pluck="name",
            limit=1,
        )[0]
        warehouse = frappe.get_doc(
            {
                "doctype": "Warehouse",
                "warehouse_name": f"Linked {self.tag}",
                "company": self.company,
                "account": account,
            }
        ).insert()
        before = frappe.db.count("Account", {"company": self.company})

        refused = self._replace(session)

        self.assertFalse(refused["success"])
        self.assertIn(warehouse.name, refused["error"])
        self.assertEqual(frappe.db.count("Account", {"company": self.company}), before)

    def test_replace_is_refused_while_a_tax_template_points_at_an_account_and_says_which(self):
        session = self._chart()
        before = frappe.db.count("Account", {"company": self.company})

        refused = self._replace(session, clear=False)

        self.assertFalse(refused["success"])
        self.assertIn("tax template", refused["error"])
        self.assertEqual(frappe.db.count("Account", {"company": self.company}), before)
