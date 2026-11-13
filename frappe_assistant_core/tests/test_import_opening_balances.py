# frappe_assistant_core/tests/test_import_opening_balances.py
"""
Opening account balances (#33998): the old system's closing trial balance becomes one opening
Journal Entry. This file covers the setup and its pre-checks; the row checks, the balance check,
creation and the report are added with their own tasks.
"""

import unittest
from unittest.mock import patch

import frappe
from frappe.utils import add_days, nowdate

from frappe_assistant_core.assistant_core.doctype.fac_import_session.fac_import_session import engine_session
from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils import import_dry_run as dry_run
from frappe_assistant_core.utils import import_opening_balances as opening_balances
from frappe_assistant_core.utils import import_opening_invoices as opening_invoices
from frappe_assistant_core.utils import import_opening_stock as opening_stock

HEADER = "Account,Debit,Credit,Balance"
COLUMNS = {"Account": "account", "Debit": "debit", "Credit": "credit"}


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Journal Entry")
def card_amounts(result):
    """What the approval card shows besides the totals (#34433), as the check reported it."""
    return {key: result["opening_balances"][key] for key in opening_balances.CARD_AMOUNTS}


class OpeningBalancesCase(BaseAssistantTest):
    """A company with a Temporary Opening account and a few ledger accounts, made for each test."""

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.registry = get_tool_registry()
        self.tag = frappe.generate_hash(length=6)
        self.date = nowdate()
        self.company = self._clean_company()
        if not self.company:
            self.skipTest(
                "no company with perpetual inventory is in a fiscal year today without an opening "
                "entry or a closed period"
            )
        self.abbr = frappe.get_cached_value("Company", self.company, "abbr")
        self.track_test_files()
        self.made_accounts, self.made_entries = [], []
        self.temporary = self._temporary_account()
        self.bank = self._account("Bank", "Asset", "Bank")
        self.equity_group = self._equity_group()
        self.capital = self._account("Capital", "Equity")
        self.expense = self._account("Rent", "Expense")
        self.debtors = self._account("Debtors", "Asset", "Receivable")
        self.creditors = self._account("Creditors", "Liability", "Payable")

    def tearDown(self):
        frappe.set_user("Administrator")
        for name in self.made_entries:
            if frappe.db.get_value("Journal Entry", name, "docstatus") == 1:
                frappe.get_doc("Journal Entry", name)._cancel()  # cancel() queues more than 100 lines
            frappe.delete_doc("Journal Entry", name, force=True, ignore_permissions=True)
        for name in reversed(self.made_accounts):
            try:
                frappe.delete_doc("Account", name, force=True, ignore_permissions=True)
            except Exception:
                frappe.clear_messages()
        self.delete_test_files()
        super().tearDown()

    # -- fixtures ------------------------------------------------------------------------

    def _clean_company(self):
        """The oldest company the opening-entry guard lets through today (#26): a submitted opening
        entry or Period Closing Voucher left by an earlier run or by hand would refuse every test.
        The tests count stock rows as covered by opening stock, so it has perpetual inventory."""
        import erpnext

        for company in frappe.get_all("Company", pluck="name", order_by="creation"):
            if not opening_invoices.in_fiscal_year(self.date, company):
                continue
            if not erpnext.is_perpetual_inventory_enabled(company):
                continue
            busy = {"company": company, "docstatus": 1}
            if frappe.db.exists("Period Closing Voucher", busy):
                continue
            if frappe.db.exists("Journal Entry", {**busy, "is_opening": "Yes"}):
                continue
            return company
        return None

    def _temporary_account(self):
        name = opening_invoices.temporary_account(self.company)
        if name:
            return name
        return self._account("Temporary Opening", "Asset", "Temporary")

    def _equity_group(self):
        """The company's Equity group; some charts have no Equity root, so one is made."""
        name = frappe.db.get_value(
            "Account", {"company": self.company, "root_type": "Equity", "is_group": 1}, order_by="lft"
        )
        if name:
            return name
        doc = frappe.get_doc(
            {
                "doctype": "Account",
                "account_name": f"Equity {self.tag}",
                "company": self.company,
                "is_group": 1,
                "root_type": "Equity",
                "report_type": "Balance Sheet",
            }
        ).insert(ignore_mandatory=True)
        self.made_accounts.append(doc.name)
        return doc.name

    def _account(self, title, root_type, account_type=None, **extra):
        """A ledger account of the test company: a new one named for this test run."""
        parent = frappe.db.get_value(
            "Account", {"company": self.company, "root_type": root_type, "is_group": 1}, order_by="lft"
        )
        doc = frappe.get_doc(
            {
                "doctype": "Account",
                "account_name": f"{title} {self.tag}",
                "company": self.company,
                "parent_account": parent,
                "account_type": account_type,
                "is_group": 0,
                **extra,
            }
        ).insert()
        self.made_accounts.append(doc.name)
        return doc.name

    def _run(self, tool_name, arguments):
        return self.registry.get_tool(tool_name)._safe_execute(arguments)

    def _file(self, lines, header=HEADER):
        content = ("\n".join([header, *lines]) + "\n").encode()
        return frappe.get_doc(
            {"doctype": "File", "file_name": f"balances-{self.tag}.csv", "content": content, "is_private": 1}
        ).insert()

    def _session(self, lines=None, header=HEADER):
        lines = lines if lines is not None else [f"{self.bank},100,,", f"{self.capital},,100,"]
        started = self._run("start_import_session", {"file_id": self._file(lines, header).name})
        self.assertTrue(started["success"], started)
        return started["result"]["session_id"]

    def _setup(self, session, **changes):
        arguments = {
            "session": session,
            "company": self.company,
            "cut_off": self.date,
            "columns": dict(COLUMNS),
            **changes,
        }
        return self._run("set_opening_balances", arguments)

    def _doc(self, session):
        # The session as the import tools hold it (load_session): the engine's own copy, so a
        # test can set up what an earlier step writes (#34400).
        return engine_session(session)


class TestSetup(OpeningBalancesCase):
    def test_maps_columns_and_stores_settings(self):
        session = self._session()
        reply = self._setup(session)
        self.assertTrue(reply["success"], reply)
        doc = self._doc(session)
        self.assertEqual(doc.status, "Mapped")
        self.assertEqual(doc.target_doctype, "Journal Entry")
        stored = opening_balances.settings(doc)
        self.assertEqual(stored["company"], self.company)
        self.assertEqual(stored["cut_off"], self.date)
        self.assertEqual(stored["temporary_opening_account"], self.temporary)
        self.assertEqual(
            stored["currency"], frappe.get_cached_value("Company", self.company, "default_currency")
        )
        self.assertEqual(stored["profit_and_loss"], "stop")
        self.assertEqual(stored["columns"], {})
        mapping = reply["result"]["column_to_field_map"]
        self.assertEqual(mapping["0"], "accounts.account")
        self.assertEqual(mapping["1"], "accounts.debit_in_account_currency")
        self.assertEqual(mapping["2"], "accounts.credit_in_account_currency")
        self.assertEqual(mapping["3"], "Don't Import")
        self.assertTrue(opening_balances.is_opening_balances(doc))

    def test_signed_balance_is_kept_in_settings_not_mapped(self):
        session = self._session([f"{self.bank},,,100"])
        reply = self._setup(session, columns={"Account": "account", "Balance": "balance"})
        self.assertTrue(reply["success"], reply)
        self.assertEqual(opening_balances.settings(self._doc(session))["columns"], {"balance": 3})
        mapping = reply["result"]["column_to_field_map"]
        self.assertEqual(mapping["0"], "accounts.account")
        self.assertEqual(mapping["3"], "balance")  # read by the engine, not dropped

    def test_every_wrong_column_is_listed_at_once(self):
        session = self._session()
        reply = self._setup(session, columns={"Nope": "account", "Debit": "bogus"})
        self.assertFalse(reply["success"])
        error = frappe.as_json(reply)
        self.assertIn("Nope", error)
        self.assertIn("bogus", error)
        self.assertIn("each of: account", error)

    def test_two_columns_for_one_field_are_reported_with_the_other_wrong_columns(self):
        session = self._session()
        reply = self._setup(
            session, columns={"Account": "account", "Debit": "debit", "Credit": "debit", "Balance": "bogus"}
        )
        self.assertFalse(reply["success"])
        error = frappe.as_json(reply)
        self.assertIn("Two columns are mapped to debit: Debit and Credit.", error)
        self.assertIn("bogus", error)

    def test_needs_an_amount_column(self):
        session = self._session()
        reply = self._setup(session, columns={"Account": "account"})
        self.assertFalse(reply["success"])
        self.assertIn("balance", frappe.as_json(reply))

    def test_refuses_wrong_settings(self):
        session = self._session()
        for changes, words in (
            ({"profit_and_loss": "ignore"}, "retained_earnings"),
            ({"cut_off": "soon"}, "isn't a date"),
            ({"cut_off": "1990-01-31"}, "fiscal year"),
            ({"company": "No Such Company"}, "doesn't exist"),
            ({"profit_and_loss": "retained_earnings"}, "Equity"),
            ({"profit_and_loss": "retained_earnings", "retained_earnings_account": "No Such"}, "Equity"),
            ({"profit_and_loss": "retained_earnings", "retained_earnings_account": self.expense}, "Equity"),
        ):
            reply = self._setup(session, **changes)
            self.assertFalse(reply["success"], changes)
            self.assertIn(words, frappe.as_json(reply))

    def test_retained_earnings_must_be_a_ledger_account(self):
        reply = self._setup(
            self._session(),
            profit_and_loss="retained_earnings",
            retained_earnings_account=self.equity_group,
        )
        self.assertFalse(reply["success"])
        self.assertIn("Equity", frappe.as_json(reply))

    def test_retained_earnings_account_is_stored(self):
        session = self._session()
        reply = self._setup(
            session, profit_and_loss="retained_earnings", retained_earnings_account=self.capital
        )
        self.assertTrue(reply["success"], reply)
        stored = opening_balances.settings(self._doc(session))
        self.assertEqual(stored["profit_and_loss"], "retained_earnings")
        self.assertEqual(stored["retained_earnings_account"], self.capital)

    def test_refuses_a_company_without_a_temporary_account(self):
        session = self._session()
        with patch.object(opening_balances, "temporary_account", return_value=None):
            reply = self._setup(session)
        self.assertFalse(reply["success"])
        self.assertIn("Temporary", frappe.as_json(reply))

    def test_refuses_without_create_and_submit_permission(self):
        session = self._session()
        real = frappe.has_permission

        def no_submit(doctype=None, ptype="read", *args, **kwargs):
            if doctype == "Journal Entry" and ptype == "submit":
                return False
            return real(doctype, ptype, *args, **kwargs)

        with patch.object(opening_balances.frappe, "has_permission", side_effect=no_submit):
            reply = self._setup(session)
        self.assertFalse(reply["success"])
        self.assertIn("Accounts Manager", frappe.as_json(reply))

    def test_refuses_a_company_with_a_submitted_period_closing_voucher(self):
        session = self._session()
        real = frappe.db.exists

        def closed(doctype=None, *args, **kwargs):
            if doctype == "Period Closing Voucher":
                return "PCV-0001"
            return real(doctype, *args, **kwargs)

        with patch.object(opening_balances.frappe.db, "exists", side_effect=closed):
            reply = self._setup(session)
        self.assertFalse(reply["success"])
        self.assertIn("Period Closing Voucher", frappe.as_json(reply))

    def _opening_entry(self, posting_date=None):
        entry = frappe.get_doc(
            {
                "doctype": "Journal Entry",
                "voucher_type": "Opening Entry",
                "company": self.company,
                "posting_date": posting_date or self.date,
                "accounts": [
                    {"account": self.bank, "debit_in_account_currency": 5},
                    {"account": self.capital, "credit_in_account_currency": 5},
                ],
            }
        )
        entry.insert()
        entry.submit()
        self.made_entries.append(entry.name)
        return entry

    def test_refuses_a_date_with_an_opening_entry_already(self):
        entry = self._opening_entry()
        reply = self._setup(self._session())
        self.assertFalse(reply["success"])
        error = frappe.as_json(reply)
        self.assertIn("already", error)
        self.assertIn(entry.name, error)

    def test_refuses_a_company_with_an_opening_entry_on_another_date(self):
        # #34433, Paul's review of 49da112: only one on the same date was found, so a second
        # opening entry, on another cut-off, doubled the opening balances
        earlier = add_days(self.date, -1)
        if not opening_invoices.in_fiscal_year(earlier, self.company):
            self.skipTest("yesterday is in no fiscal year of the test company")
        entry = self._opening_entry(posting_date=earlier)

        reply = self._setup(self._session())

        self.assertFalse(reply["success"])
        self.assertIn(entry.name, frappe.as_json(reply))

    def test_the_companys_own_temporary_account_is_taken_of_several(self):
        # #34433: with two Temporary accounts, either one could be posted to; the chart's own, the
        # oldest, is taken, never one that sorts first
        self._account("AAA Temporary", "Asset", "Temporary")

        self.assertEqual(opening_invoices.temporary_account(self.company), self.temporary)

    def test_the_dry_run_refuses_a_company_with_a_submitted_period_closing_voucher(self):
        session = self._session()
        self.assertTrue(self._setup(session)["success"])
        real = frappe.db.exists

        def closed(doctype=None, *args, **kwargs):
            if doctype == "Period Closing Voucher":
                return "PCV-0001"
            return real(doctype, *args, **kwargs)

        with patch.object(opening_balances.frappe.db, "exists", side_effect=closed):
            reply = self._run("dry_run_import", {"session": session})
        self.assertFalse(reply["success"], reply)
        self.assertIn("Period Closing Voucher", frappe.as_json(reply))

    def test_the_dry_run_refuses_a_date_with_an_opening_entry_already(self):
        session = self._session()
        self.assertTrue(self._setup(session)["success"])
        entry = self._opening_entry()
        reply = self._run("dry_run_import", {"session": session})
        self.assertFalse(reply["success"], reply)
        error = frappe.as_json(reply)
        self.assertIn("already", error)
        self.assertIn(entry.name, error)

    def test_this_sessions_own_entry_is_not_a_conflict(self):
        entry = self._opening_entry()
        session = self._session()
        self.assertFalse(self._setup(session)["success"])
        self.assertIsNone(
            opening_balances.setup_problem(
                self.company, self.date, "stop", None, session=self._with_created(session, entry.name)
            )
        )

    def _with_created(self, session, entry_name):
        doc = self._doc(session)
        options = frappe.parse_json(doc.template_options or "{}") or {}
        options["opening_balances"] = {"created": {entry_name: {}}}
        doc.template_options = frappe.as_json(options)
        return doc

    def test_dry_run_goes_to_this_engine(self):
        session = self._session()
        self._setup(session)
        self.assertIs(dry_run.special_engine(self._doc(session)), opening_balances)

    def test_start_import_refuses_naming_the_right_tool(self):
        session = self._session()
        self._setup(session)
        reply = self._run(
            "start_import",
            {"session": session, "doctype": "Journal Entry", "rows": 2, "import_type": "Insert New Records"},
        )
        self.assertFalse(reply["success"])
        self.assertIn("import_opening_balances", frappe.as_json(reply))

    def test_engines_name_their_own_import_tools(self):
        self.assertEqual(opening_stock.IMPORT_TOOL, "import_opening_stock")
        self.assertEqual(opening_invoices.IMPORT_TOOL, "import_opening_invoices")
        self.assertEqual(opening_balances.IMPORT_TOOL, "import_opening_balances")

    def test_setup_again_on_a_mapped_session(self):
        session = self._session()
        self.assertTrue(self._setup(session)["success"])
        again = self._setup(
            session, profit_and_loss="retained_earnings", retained_earnings_account=self.capital
        )
        self.assertTrue(again["success"], again)
        self.assertEqual(
            opening_balances.settings(self._doc(session))["profit_and_loss"], "retained_earnings"
        )

    def test_refuses_a_company_or_cut_off_change_once_created(self):
        session = self._session()
        self.assertTrue(self._setup(session)["success"])
        doc = self._with_created(session, "ACC-JV-NONE")
        stored = opening_balances.settings(self._doc(session))
        stored["created"] = {"ACC-JV-NONE": {}}
        options = frappe.parse_json(doc.template_options)
        options["opening_balances"] = stored
        doc.template_options = frappe.as_json(options)
        doc.save()
        other_date = frappe.utils.add_days(self.date, -1)
        reply = self._setup(session, cut_off=other_date)
        self.assertFalse(reply["success"])
        self.assertIn("already", frappe.as_json(reply))
        reply = self._setup(session, company="No Such Company")
        self.assertFalse(reply["success"])

    def _mark_created(self, session, **changes):
        doc = self._doc(session)
        options = frappe.parse_json(doc.template_options or "{}") or {}
        options["opening_balances"] = {
            **options["opening_balances"],
            "created": {"ACC-JV-NONE": {}},
            **changes,
        }
        doc.template_options = frappe.as_json(options)
        doc.save()

    def test_the_same_cut_off_in_another_format_is_not_a_change(self):
        session = self._session()
        self.assertTrue(self._setup(session)["success"])
        self._mark_created(session)
        same_day = self.date.replace("-", "/")
        self.assertNotEqual(same_day, self.date)
        reply = self._setup(session, cut_off=same_day)
        self.assertTrue(reply["success"], reply)
        self.assertEqual(opening_balances.settings(self._doc(session))["cut_off"], self.date)

    def test_a_different_cut_off_or_company_is_refused_once_created(self):
        session = self._session()
        self.assertTrue(self._setup(session)["success"])
        self._mark_created(session)
        reply = self._setup(session, cut_off=frappe.utils.add_days(self.date, -1))
        self.assertFalse(reply["success"])
        self.assertIn("already made the opening entry at", frappe.as_json(reply))
        self._mark_created(session, company="Some Other Company")
        reply = self._setup(session)
        self.assertFalse(reply["success"])
        self.assertIn("Some Other Company", frappe.as_json(reply))

    def test_refuses_a_session_that_made_invoices_or_stock(self):
        for key in ("opening_stock", "opening_invoices"):
            session = self._session()
            doc = self._doc(session)
            options = frappe.parse_json(doc.template_options or "{}") or {}
            options[key] = {"created": {"X": 1}}
            doc.template_options = frappe.as_json(options)
            doc.save()
            reply = self._setup(session)
            self.assertFalse(reply["success"], key)
            self.assertIn("new session", frappe.as_json(reply))


class TestReadingLines(OpeningBalancesCase):
    def test_balance_of(self):
        balance_of = opening_balances.balance_of
        self.assertEqual(balance_of({"balance": "1,250.50"}), (1250.5, 0))
        self.assertEqual(balance_of({"balance": "(12)"}), (0, 12))
        self.assertEqual(balance_of({"balance": "-5"}), (0, 5))
        self.assertEqual(balance_of({"debit": "1,000", "credit": ""}), (1000, 0))
        self.assertEqual(balance_of({"debit": "", "credit": "(7)"}), (0, -7))
        self.assertEqual(balance_of({"debit": "3", "credit": "4"}), (3, 4))  # the check reports it
        self.assertEqual(balance_of({"debit": "", "credit": "", "balance": ""}), (0, 0))
        self.assertEqual(balance_of({}), (0, 0))
        with self.assertRaises(ValueError):
            balance_of({"debit": "ten"})
        with self.assertRaises(ValueError):
            balance_of({"balance": "ten"})

    def test_totals_rows(self):
        totals = opening_balances.is_totals_row
        self.assertTrue(totals({"account": "Grand Total", "debit": "500"}))
        self.assertTrue(totals({"account": "Total", "balance": "500"}))
        self.assertTrue(totals({"account": "", "credit": "500"}))
        self.assertFalse(totals({"account": "Cash", "debit": "500"}))
        self.assertFalse(totals({"account": "Total", "debit": ""}))
        self.assertFalse(totals({"account": "", "debit": ""}))

    def test_lines_with_debit_and_credit_and_value_maps(self):
        session = self._session(['Old Bank,"1,250.50",,', ",,,", f'{self.capital},,"1,250.50",'])
        self._setup(session)
        doc = self._doc(session)
        doc.transformation_rules = frappe.as_json(
            {
                "value_maps": [
                    {
                        "parent": "Journal Entry Account",
                        "field": "account",
                        "label": "Account",
                        "from": "Old Bank",
                        "to": self.bank,
                    }
                ]
            }
        )
        doc.save()
        lines = opening_balances.read_lines(doc)
        self.assertEqual([line.row for line in lines], [2, 4])  # the blank row is skipped
        self.assertEqual(lines[0].cells["account"], self.bank)
        self.assertEqual(lines[0].cells["debit"], "1,250.50")
        self.assertEqual(lines[0].cells["credit"], "")
        self.assertEqual(lines[1].cells["credit"], "1,250.50")

    def test_lines_with_a_balance_column(self):
        session = self._session([f"{self.bank},,,100", f"{self.capital},,,(100)"])
        self._setup(session, columns={"Account": "account", "Balance": "balance"})
        lines = opening_balances.read_lines(self._doc(session))
        self.assertEqual([line.cells["balance"] for line in lines], ["100", "(100)"])
        self.assertEqual(lines[0].cells["account"], self.bank)
        self.assertNotIn("debit", lines[0].cells)

    def _find(self, text):
        return opening_balances.find_account(self.company, self.abbr, text)

    def test_find_by_exact_name(self):
        found = self._find(self.bank)
        self.assertEqual(found.name, self.bank)
        self.assertEqual(found.company, self.company)
        self.assertEqual(found.account_type, "Bank")
        self.assertEqual(found.root_type, "Asset")
        self.assertEqual(found.report_type, "Balance Sheet")
        self.assertFalse(found.is_group)
        self.assertFalse(found.disabled)
        self.assertTrue(found.account_currency)

    def test_find_by_name_without_the_abbreviation(self):
        self.assertEqual(self._find(f"Debtors {self.tag}").name, self.debtors)

    def test_find_by_account_number(self):
        number = f"9{self.tag}"
        account = self._account("Numbered", "Asset", account_number=number)
        self.assertEqual(self._find(number).name, account)

    def test_find_by_unique_account_name_when_a_number_is_in_the_name(self):
        account = self._account("Prepaid", "Asset", account_number=f"7{self.tag}")
        self.assertNotEqual(account, f"Prepaid {self.tag} - {self.abbr}")
        self.assertEqual(self._find(f"Prepaid {self.tag}").name, account)

    def test_ambiguous_account_name_is_not_found(self):
        self._account("Twin", "Asset", account_number=f"1{self.tag}")
        self._account("Twin", "Liability", account_number=f"2{self.tag}")
        self.assertIsNone(self._find(f"Twin {self.tag}"))

    def test_nothing_found(self):
        self.assertIsNone(self._find(f"No such account {self.tag}"))
        self.assertIsNone(self._find(""))


class TestCheck(OpeningBalancesCase):
    def setUp(self):
        super().setUp()
        self.stock = self._account("Stock", "Asset", "Stock")
        self.retained = self._account("Retained", "Equity")

    # -- helpers -------------------------------------------------------------------------

    def _check(self, session):
        reply = self._run("dry_run_import", {"session": session})
        self.assertTrue(reply["success"], reply)
        return reply["result"]

    def _ready(self, lines, **setup):
        session = self._session(lines)
        self.assertTrue(self._setup(session, **setup)["success"])
        return session, self._check(session)

    def _groups(self, result):
        return {g["cause"]: g for g in result["groups"]}

    def _counts(self):
        return frappe.db.count("Journal Entry"), frappe.db.count("GL Entry")

    def _ready_lines(self, session):
        """The Ready rows the engine finds, for entry_lines."""
        checker = opening_balances._AccountChecker()
        return opening_balances._check_lines(self._doc(session), checker)

    def _lines_of(self, session):
        return opening_balances.entry_lines(
            opening_balances.settings(self._doc(session)), self._ready_lines(session)
        )

    def _simple(self, line):
        """A file with one row in question plus a capital row."""
        return [line, f"{self.capital},,100,"]

    # -- ready rows ----------------------------------------------------------------------

    def test_ready_rows_and_totals_write_nothing(self):
        before = self._counts()
        session, result = self._ready([f"{self.bank},100,,", f"{self.capital},,100,"])
        self.assertEqual((result["ready"], result["failed"]), (2, 0), result)
        totals = result["opening_balances"]
        self.assertEqual(totals["cut_off"], self.date)
        self.assertEqual((totals["rows"], totals["lines"], totals["covered"]), (2, 2, 0))
        self.assertEqual((totals["total_debit"], totals["total_credit"]), (100, 100))
        self.assertIsNone(totals["balancing"])
        self.assertEqual(totals["profit_and_loss"], "stop")
        self.assertEqual(result["balance"], {"debit": 100, "credit": 100, "difference": 0, "balanced": True})
        self.assertEqual(self._doc(session).status, "Ready to Import")
        self.assertEqual(self._counts(), before)

    def test_account_found_without_the_company_suffix(self):
        short = self.bank[: -len(f" - {self.abbr}")]
        _, result = self._ready([f"{short},100,,", f"{self.capital},,100,"])
        self.assertEqual(result["ready"], 2, result)

    def test_balance_column_rows(self):
        session = self._session([f"{self.bank},,,100", f"{self.capital},,,(100)"])
        self.assertTrue(self._setup(session, columns={"Account": "account", "Balance": "balance"})["success"])
        self.assertEqual(self._check(session)["ready"], 2)

    def test_an_all_zero_row_is_ready_and_adds_no_line(self):
        session, result = self._ready(
            [f"{self.bank},100,,", f"{self.capital},,100,", f"{self.retained},0,0,"]
        )
        self.assertEqual((result["ready"], result["failed"]), (3, 0), result)
        self.assertEqual(result["opening_balances"]["lines"], 2)
        self.assertEqual(len(self._lines_of(session)), 2)

    # -- each cause is one group -----------------------------------------------------------

    def _one_group(self, cause, line, **setup):
        _, result = self._ready(self._simple(line), **setup)
        groups = self._groups(result)
        self.assertIn(cause, groups, result)
        self.assertEqual(groups[cause]["count"], 1)
        self.assertEqual(groups[cause]["examples"][0]["row"], 2)
        return result, groups[cause]

    def test_missing_account(self):
        result, group = self._one_group(dry_run.CAUSE_MISSING_LINK, f"No such {self.tag},100,,")
        self.assertEqual(group["value"], f"No such {self.tag}")
        self.assertEqual(group["parent"], "Journal Entry Account")
        self.assertEqual(group["field"], "account")

    def _hint(self, line, transactions):
        with patch.object(opening_balances, "_has_transactions", return_value=transactions):
            _, result = self._ready(self._simple(line))
        return result["opening_balances"].get("chart_hint")

    def test_a_missing_account_in_a_company_without_transactions_carries_the_chart_hint(self):
        hint = self._hint(f"No such {self.tag},100,,", False)
        self.assertIn("Chart of Accounts Importer", hint)
        self.assertTrue(hint.startswith("This company has no transactions yet."))

    def test_no_chart_hint_once_the_company_has_transactions(self):
        self.assertIsNone(self._hint(f"No such {self.tag},100,,", True))

    def test_no_chart_hint_when_no_account_is_missing(self):
        self.assertIsNone(self._hint(f"{self.bank},100,,", False))

    def test_account_of_another_company(self):
        real = opening_balances.find_account

        def find(company, abbr, text):
            found = real(company, abbr, text)
            if found and found.name == self.bank:
                found["company"] = "Another Company"
            return found

        with patch.object(opening_balances, "find_account", side_effect=find):
            self._one_group(opening_balances.CAUSE_NOT_THIS_COMPANY, f"{self.bank},100,,")

    def test_group_account(self):
        self._one_group(opening_balances.CAUSE_GROUP_ACCOUNT, f"{self.equity_group},100,,")

    def test_disabled_account(self):
        frappe.db.set_value("Account", self.bank, "disabled", 1)
        self._one_group(opening_balances.CAUSE_DISABLED_ACCOUNT, f"{self.bank},100,,")

    def test_two_disabled_accounts_are_two_groups(self):
        frappe.db.set_value("Account", self.bank, "disabled", 1)
        frappe.db.set_value("Account", self.expense, "disabled", 1)
        _, result = self._ready([f"{self.bank},100,,", f"{self.expense},50,,", f"{self.capital},,150,"])
        disabled = [g for g in result["groups"] if g["cause"] == opening_balances.CAUSE_DISABLED_ACCOUNT]
        self.assertEqual(sorted(g["value"] for g in disabled), sorted([self.bank, self.expense]))

    def test_temporary_opening_account(self):
        self._one_group(opening_balances.CAUSE_TEMPORARY, f"{self.temporary},100,,")

    def test_foreign_currency_account(self):
        company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
        other = "USD" if company_currency != "USD" else "EUR"
        name = self._account("Foreign", "Asset", "Bank", account_currency=other)
        self._one_group(opening_balances.CAUSE_FOREIGN_CURRENCY, f"{name},100,,")

    def test_debit_and_credit_both(self):
        self._one_group(opening_balances.CAUSE_BOTH_SIDES, f"{self.bank},100,30,")

    def test_negative_amount(self):
        self._one_group(opening_balances.CAUSE_NEGATIVE, f"{self.bank},-100,,")

    def test_not_a_number(self):
        _, group = self._one_group(dry_run.CAUSE_BAD_VALUE, f"{self.bank},ten,,")
        self.assertIn("ten", group["message"])

    def test_totals_row(self):
        self._one_group(opening_stock.CAUSE_TOTALS_ROW, "Total,100,100,")

    def test_account_twice_names_the_earlier_row(self):
        _, result = self._ready([f"{self.bank},60,,", f"{self.bank},40,,", f"{self.capital},,100,"])
        group = self._groups(result)[opening_balances.CAUSE_ACCOUNT_TWICE]
        self.assertEqual([e["row"] for e in group["examples"]], [3])
        self.assertIn("row 2", group["message"])
        self.assertEqual(result["ready"], 2)

    def test_profit_and_loss_stops_by_default(self):
        _, result = self._ready([f"{self.bank},100,,", f"{self.expense},30,,", f"{self.capital},,130,"])
        group = self._groups(result)[opening_balances.CAUSE_PROFIT_AND_LOSS]
        self.assertIn("retained_earnings", group["message"])
        self.assertIn("set_opening_balances", group["message"])
        self.assertEqual(group["count"], 1)

    def test_profit_and_loss_folds_into_retained_earnings(self):
        session, result = self._ready(
            [f"{self.bank},100,,", f"{self.expense},30,,", f"{self.capital},,130,"],
            profit_and_loss="retained_earnings",
            retained_earnings_account=self.retained,
        )
        self.assertEqual((result["ready"], result["failed"]), (3, 0), result)
        self.assertEqual(result["opening_balances"]["lines"], 3)  # bank, capital, the folded line
        lines = self._lines_of(session)
        folded = [line for line in lines if line["account"] == self.retained]
        self.assertEqual(len(folded), 1)
        self.assertEqual(folded[0]["debit_in_account_currency"], 30)
        self.assertNotIn(self.expense, [line["account"] for line in lines])

    # -- covered rows and the balancing line ---------------------------------------------

    def test_covered_rows_are_ready_counted_and_not_in_the_entry(self):
        session, result = self._ready(
            [f"{self.bank},100,,", f"{self.debtors},50,,", f"{self.stock},20,,", f"{self.capital},,170,"]
        )
        self.assertEqual((result["ready"], result["failed"]), (4, 0), result)
        self.assertEqual(result["opening_balances"]["covered"], 2)
        accounts = [line["account"] for line in self._lines_of(session)]
        self.assertNotIn(self.debtors, accounts)
        self.assertNotIn(self.stock, accounts)

    def test_stock_rows_go_in_the_entry_when_perpetual_inventory_is_off(self):
        # Opening stock then posts no ledger entry, so only this entry can bring the stock
        # account's balance in; left out, it would stay on Temporary Opening for good.
        def set_perpetual(value):  # the Company is cached in Redis, which no rollback reaches
            frappe.db.set_value("Company", self.company, "enable_perpetual_inventory", value)
            frappe.clear_document_cache("Company", self.company)
            frappe.local.enable_perpetual_inventory = {}

        before = frappe.db.get_value("Company", self.company, "enable_perpetual_inventory")
        self.addCleanup(set_perpetual, before)
        set_perpetual(0)

        session, result = self._ready(
            [f"{self.bank},100,,", f"{self.debtors},50,,", f"{self.stock},20,,", f"{self.capital},,170,"]
        )

        self.assertEqual((result["ready"], result["failed"]), (4, 0), result)
        self.assertEqual(result["opening_balances"]["covered"], 1)
        accounts = [line["account"] for line in self._lines_of(session)]
        self.assertIn(self.stock, accounts)
        self.assertNotIn(self.debtors, accounts)

    def test_balancing_line_for_receivable_and_stock(self):
        session, result = self._ready(
            [f"{self.bank},100,,", f"{self.debtors},50,,", f"{self.stock},20,,", f"{self.capital},,170,"]
        )
        # the entry has debit 100 and credit 170: Temporary Opening takes the 70 debit
        last = self._lines_of(session)[-1]
        self.assertEqual(last["account"], self.temporary)
        self.assertEqual(last["debit_in_account_currency"], 70)
        self.assertEqual(last["credit_in_account_currency"], 0)
        self.assertEqual(
            result["opening_balances"]["balancing"], {"account": self.temporary, "debit": 70, "credit": 0}
        )
        self.assertEqual(result["opening_balances"]["lines"], 3)

    def test_balancing_line_for_payable_is_a_credit(self):
        session, result = self._ready(
            [f"{self.bank},100,,", f"{self.creditors},,40,", f"{self.capital},,60,"]
        )
        last = self._lines_of(session)[-1]
        self.assertEqual(last["account"], self.temporary)
        self.assertEqual(last["debit_in_account_currency"], 0)
        self.assertEqual(last["credit_in_account_currency"], 40)
        self.assertEqual(result["ready"], 3, result)

    def test_balancing_line_mixed(self):
        _, result = self._ready(
            [f"{self.bank},100,,", f"{self.debtors},80,,", f"{self.creditors},,30,", f"{self.capital},,150,"]
        )
        # the entry has debit 100 and credit 150; the covered net is a debit of 50
        self.assertEqual(
            result["opening_balances"]["balancing"], {"account": self.temporary, "debit": 50, "credit": 0}
        )

    def test_only_covered_rows_means_no_lines_and_no_erpnext_call(self):
        with patch.object(opening_balances, "_entry_error") as entry_error:
            _, result = self._ready([f"{self.debtors},50,,", f"{self.creditors},,50,"])
        entry_error.assert_not_called()
        self.assertEqual((result["ready"], result["failed"]), (2, 0), result)
        self.assertEqual(result["opening_balances"]["lines"], 0)
        self.assertEqual(result["opening_balances"]["covered"], 2)

    def test_build_entry(self):
        session, _ = self._ready([f"{self.bank},100,,", f"{self.capital},,100,"])
        entry = opening_balances.build_entry(
            opening_balances.settings(self._doc(session)), self._ready_lines(session)
        )
        self.assertEqual(entry.doctype, "Journal Entry")
        self.assertEqual(entry.voucher_type, "Opening Entry")
        self.assertEqual(entry.is_opening, "Yes")
        self.assertEqual(entry.company, self.company)
        self.assertEqual(str(entry.posting_date), self.date)
        self.assertIn(self.date, entry.user_remark)
        self.assertEqual(len(entry.accounts), 2)
        self.assertFalse(entry.name)

    # -- the balance check ---------------------------------------------------------------

    def test_a_file_that_does_not_balance_stops_everything(self):
        before = self._counts()
        session, result = self._ready([f"{self.bank},100,,", f"{self.capital},,90,"])
        self.assertEqual(result["ready"], 0, result)
        self.assertEqual(result["balance"], {"debit": 100, "credit": 90, "difference": 10, "balanced": False})
        group = self._groups(result)[opening_balances.CAUSE_NOT_BALANCED]
        self.assertEqual(group["count"], 2)
        self.assertIn("10", group["message"])
        self.assertEqual(
            len([g for g in result["groups"] if g["cause"] == opening_balances.CAUSE_NOT_BALANCED]), 1
        )
        self.assertEqual(self._doc(session).status, "Dry Run Failed")
        self.assertEqual(self._counts(), before)

    def test_balance_counts_rows_that_fail_for_another_reason(self):
        _, result = self._ready([f"{self.bank},100,,", f"Nowhere {self.tag},,100,"])
        self.assertEqual(result["balance"]["difference"], 0)
        self.assertNotIn(opening_balances.CAUSE_NOT_BALANCED, self._groups(result))

    def test_balance_includes_covered_rows(self):
        _, result = self._ready([f"{self.debtors},100,,", f"{self.capital},,100,"])
        self.assertEqual(result["balance"]["difference"], 0)
        self.assertEqual(result["ready"], 2)

    def test_tolerance_passes_a_rounding_difference(self):
        _, result = self._ready([f"{self.bank},100,,", f"{self.capital},,99.996,"])
        self.assertEqual(result["ready"], 2, result)
        self.assertNotIn(opening_balances.CAUSE_NOT_BALANCED, self._groups(result))

    def test_a_real_gap_is_not_balanced_however_many_rows_there_are(self):
        # #34433: 20 rows of 1.00 against 19.95 used to pass, as 0.5 x 0.01 x 21 rows of rounding.
        lines = [f"{self.bank},1.00,," for _ in range(20)] + [f"{self.capital},,19.95,"]
        session = self._session(lines)
        self.assertTrue(self._setup(session)["success"])

        self.assertFalse(opening_balances.is_balanced(self._doc(session)))

    def test_only_rows_with_more_decimals_than_the_currency_have_a_rounding_allowance(self):
        # each row is rounded first: 3 x 33.33 is 99.99 against 100, from 3 rows of 3 decimals
        session = self._session(
            [
                f"{self.bank},33.333,,",
                f"{self.bank},33.333,,",
                f"{self.bank},33.334,,",
                f"{self.capital},,100,",
            ]
        )
        self.assertTrue(self._setup(session)["success"])

        self.assertTrue(opening_balances.is_balanced(self._doc(session)))
        self.assertEqual(opening_balances.file_balance(self._doc(session))["debit"], 99.99)

    def test_the_check_says_what_the_card_must_show(self):
        # #34433: what is covered, what is left out, and the balancing line all reach the card.
        session = self._session(
            [f"{self.bank},100,,", f"{self.debtors},50,,", f"{self.retained},30,,", f"{self.capital},,180,"]
        )
        self.assertTrue(self._setup(session)["success"])
        self._leave_out(session, 4)

        totals = self._check(session)["opening_balances"]

        self.assertEqual(
            {k: totals[k] for k in opening_balances.CARD_AMOUNTS},
            {
                "balancing_amount": 80,  # the entry: 100 debit, 180 credit
                "covered_debit": 50,
                "covered_credit": 0,
                "excluded_debit": 30,
                "excluded_credit": 0,
            },
        )

    def test_a_plans_card_shows_the_entrys_totals_and_balancing_line(self):
        # #34433: the plan's approval card showed files, rows and decisions, not the entry
        from frappe_assistant_core.utils import import_plan

        session = self._session(
            [f"{self.bank},100,,", f"{self.debtors},50,,", f"{self.retained},30,,", f"{self.capital},,180,"]
        )
        self.assertTrue(self._setup(session)["success"])
        self._leave_out(session, 4)
        self._check(session)

        lines = import_plan._opening_entry(self._doc(session))

        self.assertEqual(len(lines), 1, lines)
        self.assertIn("debits 180.00, credits 180.00", lines[0])
        self.assertIn(f"Balanced by a debit of 80.00 to {self._temporary_account()}", lines[0])

    def test_file_balance_ignores_totals_rows(self):
        session = self._session([f"{self.bank},100,,", f"{self.capital},,100,", "Total,100,100,"])
        self._setup(session)
        self.assertEqual(
            opening_balances.file_balance(self._doc(session)), {"debit": 100, "credit": 100, "difference": 0}
        )

    def test_file_balance_skips_unreadable_numbers(self):
        session = self._session([f"{self.bank},100,,", f"{self.capital},ten,,"])
        self._setup(session)
        self.assertEqual(opening_balances.file_balance(self._doc(session))["debit"], 100)

    # -- the validation ERPNext does itself ------------------------------------------------

    def test_rejected_by_erpnext_fails_every_row_together_and_rolls_back(self):
        period = frappe.get_doc(
            {
                "doctype": "Accounting Period",
                "period_name": f"OB Closed {self.tag}",
                "company": self.company,
                "start_date": self.date,
                "end_date": self.date,
                "closed_documents": [{"document_type": "Journal Entry", "closed": 1}],
            }
        ).insert()
        self.addCleanup(frappe.delete_doc, "Accounting Period", period.name, force=True)
        before = self._counts()
        _, result = self._ready([f"{self.bank},100,,", f"{self.capital},,100,"])
        rejected = self._groups(result)[dry_run.CAUSE_REJECTED]
        self.assertIn("closed Accounting Period", rejected["message"])
        self.assertEqual(rejected["count"], 2)
        self.assertEqual(result["ready"], 0)
        self.assertEqual(self._counts(), before)

    def test_a_rejection_patched_in(self):
        error = frappe.ValidationError("No way")
        before = self._counts()
        with patch.object(opening_balances, "_entry_error", return_value=error):
            _, result = self._ready([f"{self.bank},100,,", f"{self.capital},,100,"])
        rejected = self._groups(result)[dry_run.CAUSE_REJECTED]
        self.assertEqual(rejected["count"], 2)
        self.assertIn("No way", rejected["message"])
        self.assertEqual(self._counts(), before)

    def test_erpnext_accepts_the_entry_and_it_is_rolled_back(self):
        session, _ = self._ready([f"{self.bank},100,,", f"{self.capital},,100,"])
        before = self._counts()
        error = opening_balances._entry_error(
            opening_balances.settings(self._doc(session)), self._ready_lines(session)
        )
        self.assertIsNone(error)
        self.assertEqual(self._counts(), before)

    # -- rows left out, junk balance cells, an unbalanced file with nothing ready ---------

    def _leave_out(self, session, *rows):
        doc = self._doc(session)
        doc.excluded_rows = frappe.as_json(list(rows))
        doc.save()

    def test_leaving_a_row_out_does_not_change_the_balance_check(self):
        session = self._session([f"{self.bank},100,,", f"{self.capital},,90,"])
        self.assertTrue(self._setup(session)["success"])
        self._leave_out(session, 2)
        result = self._check(session)
        self.assertEqual(result["ready"], 0, result)
        self.assertEqual(result["excluded"], 1)
        self.assertEqual(result["balance"], {"debit": 100, "credit": 90, "difference": 10, "balanced": False})
        self.assertIn(opening_balances.CAUSE_NOT_BALANCED, self._groups(result))

    def test_a_row_left_out_is_not_in_the_entry_and_goes_through_the_balancing_line(self):
        session = self._session([f"{self.bank},100,,", f"{self.retained},30,,", f"{self.capital},,130,"])
        self.assertTrue(self._setup(session)["success"])
        self._leave_out(session, 3)
        result = self._check(session)
        self.assertEqual((result["ready"], result["excluded"], result["failed"]), (2, 1, 0), result)
        self.assertTrue(result["balance"]["balanced"])
        lines = self._lines_of(session)
        self.assertNotIn(self.retained, [line["account"] for line in lines])
        last = lines[-1]
        self.assertEqual(last["account"], self.temporary)
        self.assertEqual(last["debit_in_account_currency"], 30)
        self.assertEqual(last["credit_in_account_currency"], 0)
        self.assertEqual(
            result["opening_balances"]["balancing"], {"account": self.temporary, "debit": 30, "credit": 0}
        )

    def test_a_junk_balance_cell_is_ignored_when_debit_is_given(self):
        session = self._session([f"{self.bank},100,,junk", f"{self.capital},,100,"])
        columns = {**COLUMNS, "Balance": "balance"}
        self.assertTrue(self._setup(session, columns=columns)["success"])
        result = self._check(session)
        self.assertNotIn(dry_run.CAUSE_BAD_VALUE, self._groups(result))
        self.assertEqual(result["ready"], 2, result)
        self.assertEqual(result["balance"]["debit"], 100)

    def test_a_junk_balance_cell_is_not_a_number_when_it_is_the_only_amount(self):
        session = self._session([f"{self.bank},,,junk", f"{self.capital},,100,"])
        columns = {**COLUMNS, "Balance": "balance"}
        self.assertTrue(self._setup(session, columns=columns)["success"])
        result = self._check(session)
        self.assertIn(dry_run.CAUSE_BAD_VALUE, self._groups(result))
        self.assertEqual(result["balance"]["debit"], 0)

    def test_an_unbalanced_file_with_nothing_ready_still_says_so_once(self):
        _, result = self._ready([f"Old A {self.tag},100,,", f"Old B {self.tag},,90,"])
        self.assertEqual(result["ready"], 0)
        self.assertFalse(result["balance"]["balanced"])
        groups = [g for g in result["groups"] if g["cause"] == opening_balances.CAUSE_NOT_BALANCED]
        self.assertEqual(len(groups), 1, result)
        self.assertEqual(groups[0]["count"], 1)
        self.assertEqual(result["failed"], 2)  # the two rows, each counted once


class TestFixes(OpeningBalancesCase):
    """Plain explanations, mapping an account, and the unbalanced group that has no fixes."""

    def setUp(self):
        super().setUp()
        self.stock = self._account("Stock", "Asset", "Stock")

    def _check(self, session):
        reply = self._run("dry_run_import", {"session": session})
        self.assertTrue(reply["success"], reply)
        return reply["result"]

    def _ready(self, lines, **setup):
        session = self._session(lines)
        self.assertTrue(self._setup(session, **setup)["success"])
        return session, self._check(session)

    def _groups(self, result):
        return {g["cause"]: g for g in result["groups"]}

    def _fix(self, session, group, action, **extra):
        return self._run(
            "dry_run_import", {"session": session, "fixes": [{"group": group, "action": action, **extra}]}
        )

    def _missing(self, lines=None):
        lines = lines or [f"No such {self.tag},100,,", f"{self.capital},,100,"]
        session, result = self._ready(lines)
        return session, self._groups(result)[dry_run.CAUSE_MISSING_LINK]

    def _elsewhere(self, name):
        """A find_account that says ``name`` belongs to another company."""
        real = opening_balances.find_account

        def find(company, abbr, text):
            found = real(company, abbr, text)
            if found and found.name == name:
                found["company"] = "Another Company"
            return found

        return patch.object(opening_balances, "find_account", side_effect=find)

    # -- every cause has its own explanation and fixes -----------------------------------

    def test_every_new_cause_has_its_own_explanation_and_fixes(self):
        company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
        other = "USD" if company_currency != "USD" else "EUR"
        foreign = self._account("Foreign", "Asset", "Bank", account_currency=other)
        elsewhere = self._account("Elsewhere", "Asset", "Bank")
        off = self._account("Off", "Asset", "Bank")
        frappe.db.set_value("Account", off, "disabled", 1)
        session = self._session(
            [
                f"{self.equity_group},10,,",
                f"{off},10,,",
                f"{elsewhere},10,,",
                f"{self.expense},10,,",
                f"{self.temporary},10,,",
                f"{foreign},10,,",
                f"{self.bank},10,5,",
                f"{self.capital},-10,,",
                f"{self.debtors},5,,",
                f"{self.debtors},5,,",
                f"No such {self.tag},10,,",
                "Total,10,10,",
                f"{self.bank},ten,,",
            ]
        )
        self.assertTrue(self._setup(session)["success"])
        with self._elsewhere(elsewhere):
            groups = self._groups(self._check(session))
        expected = {
            opening_balances.CAUSE_NOT_THIS_COMPANY: ["map", "leave_out"],
            opening_balances.CAUSE_GROUP_ACCOUNT: ["map", "leave_out"],
            opening_balances.CAUSE_DISABLED_ACCOUNT: ["map", "leave_out"],
            opening_balances.CAUSE_NOT_BALANCED: [],
        }
        self.assertEqual(set(opening_balances.NEW_CAUSES) - set(groups), set(), "every new cause is produced")
        for cause in opening_balances.NEW_CAUSES:
            group = groups[cause]
            self.assertTrue(group["message"], group)
            self.assertNotIn("would fail", group["explanation"])
            self.assertTrue(group["fix_in_file"], group)
            self.assertEqual([f["action"] for f in group["fixes"]], expected.get(cause, ["leave_out"]), cause)
            if cause != opening_balances.CAUSE_NOT_BALANCED:
                self.assertRegex(group["explanation"], r"^(1 row|\d+ rows)", group)
                self.assertIn(group["message"], group["explanation"])
        for cause in (
            opening_balances.CAUSE_NOT_THIS_COMPANY,
            opening_balances.CAUSE_GROUP_ACCOUNT,
            opening_balances.CAUSE_DISABLED_ACCOUNT,
        ):
            self.assertIn("closest", groups[cause]["fixes"][0])
        self.assertEqual([f["action"] for f in groups[dry_run.CAUSE_MISSING_LINK]["fixes"][:1]], ["map"])
        self.assertNotIn("create", [f["action"] for f in groups[dry_run.CAUSE_MISSING_LINK]["fixes"]])

    # -- the unbalanced group has no fixes ---------------------------------------------------

    def test_unbalanced_group_has_no_fixes_and_says_to_correct_the_file(self):
        _, result = self._ready([f"{self.bank},100,,", f"{self.capital},,90,"])
        group = self._groups(result)[opening_balances.CAUSE_NOT_BALANCED]
        self.assertEqual(group["fixes"], [])
        self.assertTrue(group["fix_in_file"])
        self.assertIn("in the file", group["explanation"])
        self.assertIn("checked again", group["explanation"])

    def test_a_fix_aimed_at_the_unbalanced_group_is_refused(self):
        session, result = self._ready([f"{self.bank},100,,", f"{self.capital},,90,"])
        group = self._groups(result)[opening_balances.CAUSE_NOT_BALANCED]
        before = self._doc(session).transformation_rules
        for action, extra in (("leave_out", {}), ("map", {"to": self.bank})):
            reply = self._fix(session, group["id"], action, **extra)
            self.assertFalse(reply["success"], reply)
            self.assertIn("can only be corrected in the file", frappe.as_json(reply))
        self.assertEqual(self._doc(session).transformation_rules, before)

    def test_profit_and_loss_keeps_leave_out_as_its_fix(self):
        _, result = self._ready([f"{self.bank},100,,", f"{self.expense},30,,", f"{self.capital},,130,"])
        group = self._groups(result)[opening_balances.CAUSE_PROFIT_AND_LOSS]
        self.assertEqual([f["action"] for f in group["fixes"]], ["leave_out"])

    # -- mapping an account --------------------------------------------------------------------

    def test_a_missing_account_is_mapped_to_an_account_and_is_ready(self):
        session, group = self._missing()
        self.assertEqual(group["fixes"][0]["action"], "map")
        result = self._fix(session, group["id"], "map", to=self.bank)["result"]
        self.assertEqual((result["ready"], result["failed"]), (2, 0), result)

    def test_a_disabled_account_is_mapped_to_a_good_one(self):
        frappe.db.set_value("Account", self.bank, "disabled", 1)
        other = self._account("Cash", "Asset", "Cash")
        session, result = self._ready([f"{self.bank},100,,", f"{self.capital},,100,"])
        group = self._groups(result)[opening_balances.CAUSE_DISABLED_ACCOUNT]
        result = self._fix(session, group["id"], "map", to=other)["result"]
        self.assertEqual((result["ready"], result["failed"]), (2, 0), result)

    def test_a_group_account_is_mapped_to_a_good_one(self):
        session, result = self._ready([f"{self.equity_group},,100,", f"{self.bank},100,,"])
        group = self._groups(result)[opening_balances.CAUSE_GROUP_ACCOUNT]
        result = self._fix(session, group["id"], "map", to=self.capital)["result"]
        self.assertEqual((result["ready"], result["failed"]), (2, 0), result)

    def test_an_account_of_another_company_is_mapped_to_a_good_one(self):
        cash = self._account("Cash", "Asset", "Cash")
        with self._elsewhere(self.bank):
            session, result = self._ready([f"{self.bank},100,,", f"{self.capital},,100,"])
            group = self._groups(result)[opening_balances.CAUSE_NOT_THIS_COMPANY]
            result = self._fix(session, group["id"], "map", to=cash)["result"]
        self.assertEqual((result["ready"], result["failed"]), (2, 0), result)

    def _map_group(self):
        return {
            "cause": dry_run.CAUSE_MISSING_LINK,
            "link_doctype": "Account",
            "parent": "accounts",
            "field": "parent_account",
            "label": "Parent Account",
            "value": "Nowhere",
        }

    def test_a_session_that_is_not_opening_balances_can_map_to_a_group_account(self):
        from frappe_assistant_core.utils import import_fixes

        plain = frappe._dict(template_options="{}")
        rules = import_fixes._map(plain, self._map_group(), {"to": self.equity_group}, [])
        self.assertEqual([(r["field"], r["to"]) for r in rules], [("parent_account", self.equity_group)])

    def test_an_opening_balances_session_still_cannot_map_to_a_group_account(self):
        from frappe_assistant_core.utils import import_fixes

        balances = frappe._dict(
            template_options=frappe.as_json({"opening_balances": {"company": self.company}})
        )
        with self.assertRaises(import_fixes.FixProblem):
            import_fixes._map(balances, self._map_group(), {"to": self.equity_group}, [])

    def _refused(self, to, message):
        session, group = self._missing()
        before = self._doc(session).transformation_rules
        reply = self._fix(session, group["id"], "map", to=to)
        self.assertFalse(reply["success"], reply)
        self.assertIn(message, frappe.as_json(reply))
        self.assertEqual(self._doc(session).transformation_rules, before)

    def test_mapping_to_an_account_that_does_not_exist_is_refused(self):
        self._refused(f"Nobody {self.tag}", "There is no Account called")

    def test_mapping_to_a_group_account_is_refused(self):
        self._refused(self.equity_group, "can't take entries")

    def test_mapping_to_a_disabled_account_is_refused(self):
        off = self._account("Off", "Asset", "Bank")
        frappe.db.set_value("Account", off, "disabled", 1)
        self._refused(off, "can't take entries")

    def test_mapping_to_an_account_of_another_company_is_refused(self):
        other = frappe.db.get_value(
            "Account", {"company": ["!=", self.company], "is_group": 0, "disabled": 0}
        )
        if not other:
            self.skipTest("the site has no other company with accounts")
        self._refused(other, "can't take entries")

    # -- masters_plan never proposes an Account ----------------------------------------------

    def test_masters_plan_is_empty_for_a_missing_account(self):
        from frappe_assistant_core.utils import import_fixes as fixes

        session, group = self._missing()
        self.assertIn("ERPNext names it itself", fixes.cannot_create("Account", self._doc(session)))
        self.assertEqual(fixes.masters_plan(self._doc(session), [group]), [])


class TestCreating(OpeningBalancesCase):
    def setUp(self):
        super().setUp()
        self.stock = self._account("Stock", "Asset", "Stock")
        self.retained = self._account("Retained", "Equity")

    # -- helpers -------------------------------------------------------------------------

    def _ready(self, lines=None, **setup):
        session = self._session(lines)
        self.assertTrue(self._setup(session, **setup)["success"])
        reply = self._run("dry_run_import", {"session": session})
        self.assertTrue(reply["success"], reply)
        return session, reply["result"]

    def _card(self, session, result, **changes):
        return {
            "session": session,
            "company": self.company,
            "cut_off": result["opening_balances"]["cut_off"],
            "rows": result["ready"],
            "total_debit": result["opening_balances"]["total_debit"],
            "total_credit": result["opening_balances"]["total_credit"],
            **{k: result["opening_balances"][k] for k in opening_balances.CARD_AMOUNTS},
            **changes,
        }

    def _import(self, session, result, **changes):
        reply = self._run("import_opening_balances", self._card(session, result, **changes))
        for record in self._doc(session).created_records or []:
            if record.record_doctype == "Journal Entry" and record.record_name not in self.made_entries:
                self.made_entries.append(record.record_name)
        return reply

    def _entries(self):
        return frappe.db.count("Journal Entry", {"company": self.company, "is_opening": "Yes"})

    def _entry_of(self, session):
        created = opening_balances.settings(self._doc(session))["created"]
        self.assertEqual(len(created), 1)
        return next(iter(created))

    # -- creating ------------------------------------------------------------------------

    def test_imports_one_submitted_opening_entry(self):
        session, result = self._ready(
            [f"{self.bank},100,,", f"{self.debtors},50,,", f"{self.stock},20,,", f"{self.capital},,170,"]
        )
        reply = self._import(session, result)
        self.assertTrue(reply["success"], reply)
        doc = self._doc(session)
        self.assertEqual(doc.status, "Completed")
        name = self._entry_of(session)
        entry = frappe.get_doc("Journal Entry", name)
        self.assertEqual(
            (entry.docstatus, entry.is_opening, entry.voucher_type, str(entry.posting_date)),
            (1, "Yes", "Opening Entry", self.date),
        )
        lines = {line.account: (line.debit, line.credit) for line in entry.accounts}
        self.assertEqual(lines, {self.bank: (100, 0), self.capital: (0, 170), self.temporary: (70, 0)})
        self.assertEqual(
            [(r.record_doctype, r.record_name) for r in doc.created_records], [("Journal Entry", name)]
        )
        gl = frappe.db.sql(
            "select sum(debit), sum(credit) from `tabGL Entry` where voucher_no=%s and is_cancelled=0",
            name,
        )[0]
        self.assertEqual(gl[0], gl[1])
        self.assertEqual("Success", [step for step in doc.steps if step.step == "Import"][-1].outcome)
        self.assertEqual(reply["result"]["journal_entry"], name)
        self.assertEqual(reply["result"]["status"], "Completed")

    def test_the_created_record_is_keyed_by_the_entry_with_the_files_numbers(self):
        session, result = self._ready(
            [f"{self.bank},100,,", f"{self.debtors},50,,", f"{self.stock},20,,", f"{self.capital},,170,"]
        )
        self.assertTrue(self._import(session, result)["success"])
        name = self._entry_of(session)
        held = opening_balances.settings(self._doc(session))["created"][name]
        self.assertEqual((held["lines"], held["rows"]), (3, 4))
        self.assertEqual(
            held["expected"],
            {
                self.bank: {"debit": 100, "credit": 0},
                self.capital: {"debit": 0, "credit": 170},
                self.temporary: {"debit": 70, "credit": 0},
                self.debtors: {"debit": 50, "credit": 0},
                self.stock: {"debit": 20, "credit": 0},
            },
        )
        self.assertEqual(held["balancing"], {"account": self.temporary, "debit": 70, "credit": 0})

    def test_no_balancing_line_when_the_file_needs_none(self):
        session, result = self._ready()
        self.assertTrue(self._import(session, result)["success"])
        held = opening_balances.settings(self._doc(session))["created"][self._entry_of(session)]
        self.assertIsNone(held["balancing"])
        self.assertEqual(held["lines"], 2)

    def test_profit_and_loss_is_folded_into_the_retained_earnings_line(self):
        session, result = self._ready(
            [f"{self.bank},100,,", f"{self.expense},30,,", f"{self.capital},,130,"],
            profit_and_loss="retained_earnings",
            retained_earnings_account=self.retained,
        )
        self.assertTrue(self._import(session, result)["success"])
        entry = frappe.get_doc("Journal Entry", self._entry_of(session))
        lines = {line.account: (line.debit, line.credit) for line in entry.accounts}
        self.assertEqual(lines, {self.bank: (100, 0), self.capital: (0, 130), self.retained: (30, 0)})
        self.assertNotIn(self.expense, lines)

    def test_a_card_that_does_not_match_the_check_is_refused(self):
        session, result = self._ready()
        before = self._entries()
        for changes in (
            {"total_debit": 999},
            {"total_credit": 1},
            {"rows": 7},
            {"cut_off": frappe.utils.add_days(self.date, -1)},
            {"company": "Another Company"},
        ):
            reply = self._import(session, result, **changes)
            self.assertFalse(reply["success"], changes)
            self.assertIn("approval card", frappe.as_json(reply))
        self.assertEqual(self._entries(), before)
        self.assertEqual(self._doc(session).status, "Ready to Import")

    def _left_out_and_covered(self):
        session = self._session(
            [f"{self.bank},100,,", f"{self.debtors},50,,", f"{self.retained},30,,", f"{self.capital},,180,"]
        )
        self.assertTrue(self._setup(session)["success"])
        doc = self._doc(session)
        doc.excluded_rows = frappe.as_json([4])
        doc.save()
        reply = self._run("dry_run_import", {"session": session})
        self.assertTrue(reply["success"], reply)
        return session, reply["result"]

    def test_a_card_without_the_balancing_line_is_refused(self):
        # #34433: the 30 left out goes to Temporary Opening; the card must say so.
        session, result = self._left_out_and_covered()
        before = self._entries()
        card = self._card(session, result)
        for key in opening_balances.CARD_AMOUNTS:
            card.pop(key)

        reply = self._run("import_opening_balances", card)

        self.assertFalse(reply["success"], reply)
        self.assertIn("80", reply["result"]["error"])
        self.assertEqual(self._entries(), before)

    def test_a_card_with_another_balancing_amount_or_covered_total_is_refused(self):
        session, result = self._left_out_and_covered()
        before = self._entries()

        for change in ({"balancing_amount": 50}, {"covered_debit": 0}, {"excluded_debit": 0}):
            with self.subTest(change=change):
                self.assertFalse(self._import(session, result, **change)["success"])
        self.assertEqual(self._entries(), before)

    def test_a_card_that_shows_the_balancing_line_imports(self):
        session, result = self._left_out_and_covered()
        before = self._entries()

        reply = self._import(session, result)

        self.assertTrue(reply["success"], reply)
        self.assertEqual(self._entries(), before + 1)

    def test_the_cut_off_in_another_format_is_the_same_card(self):
        session, result = self._ready()
        reply = self._import(session, result, cut_off=self.date.replace("-", "/"))
        self.assertTrue(reply["success"], reply)

    def test_a_change_after_the_check_is_refused(self):
        session, result = self._ready([f"{self.bank},100,,", f"{self.capital},,100,"])
        doc = self._doc(session)
        doc.excluded_rows = frappe.as_json([2])
        doc.save()
        before = self._entries()
        reply = self._import(session, result)
        self.assertFalse(reply["success"])
        self.assertIn("dry_run_import", frappe.as_json(reply))
        self.assertEqual(self._entries(), before)

    def test_calling_again_creates_nothing_and_reports(self):
        session, result = self._ready()
        self.assertTrue(self._import(session, result)["success"])
        before, name = self._entries(), self._entry_of(session)
        again = self._import(session, result)
        self.assertTrue(again["success"], again)
        self.assertEqual(again["result"]["journal_entry"], name)
        self.assertEqual(self._entries(), before)
        self.assertEqual(self._doc(session).status, "Completed")
        self.assertEqual(len(self._doc(session).created_records), 1)

    def test_a_completed_session_cannot_be_set_up_or_checked_again(self):
        session, result = self._ready()
        self.assertTrue(self._import(session, result)["success"])
        self.assertFalse(self._setup(session)["success"])
        self.assertFalse(self._run("dry_run_import", {"session": session})["success"])

    def test_a_file_that_does_not_balance_cannot_be_imported(self):
        session, result = self._ready([f"{self.bank},100,,", f"{self.capital},,90,"])
        self.assertEqual(result["ready"], 0)
        before = self._entries()
        reply = self._import(session, result)
        self.assertFalse(reply["success"], reply)
        self.assertEqual(self._entries(), before)
        self.assertNotEqual(self._doc(session).status, "Completed")

    def test_only_covered_rows_is_nothing_to_import(self):
        session, result = self._ready([f"{self.debtors},50,,", f"{self.creditors},,50,"])
        self.assertEqual(result["ready"], 2)
        before = self._entries()
        reply = self._import(session, result)
        self.assertFalse(reply["success"], reply)
        self.assertIn("Nothing to import", reply["error"])
        self.assertEqual(self._entries(), before)
        self.assertEqual(self._doc(session).status, "Ready to Import")

    def test_an_unchecked_session_is_refused(self):
        session = self._session()
        self.assertTrue(self._setup(session)["success"])
        before = self._entries()
        reply = self._run(
            "import_opening_balances",
            {
                "session": session,
                "company": self.company,
                "cut_off": self.date,
                "rows": 2,
                "total_debit": 100,
                "total_credit": 100,
            },
        )
        self.assertFalse(reply["success"], reply)
        self.assertEqual(self._entries(), before)

    def test_a_failure_at_submit_leaves_nothing_and_fails_the_session(self):
        session, result = self._ready()
        before, gl = self._entries(), frappe.db.count("GL Entry")

        def refuse(*args, **kwargs):
            frappe.throw(frappe._("ERPNext says no for the test"))

        with patch.object(opening_balances, "build_entry", side_effect=refuse):
            reply = self._import(session, result)
        self.assertFalse(reply["success"], reply)
        self.assertIn("ERPNext says no for the test", reply["error"])
        self.assertEqual((self._entries(), frappe.db.count("GL Entry")), (before, gl))
        doc = self._doc(session)
        self.assertEqual(doc.status, "Failed")
        self.assertEqual(len(doc.created_records), 0)
        self.assertNotIn("created", opening_balances.settings(doc))
        last = [step for step in doc.steps if step.step == "Import"][-1]
        self.assertEqual(last.outcome, "Failed")
        self.assertIn("ERPNext says no for the test", last.message)

    def test_a_failure_after_the_insert_rolls_the_entry_back(self):
        session, result = self._ready()
        before = self._entries()
        real = frappe.model.document.Document._submit

        def refuse(doc, *args, **kwargs):
            if doc.doctype == "Journal Entry":
                frappe.throw(frappe._("Refused at submit"))
            return real(doc, *args, **kwargs)

        with patch.object(frappe.model.document.Document, "_submit", refuse):
            reply = self._import(session, result)
        self.assertFalse(reply["success"], reply)
        self.assertIn("Refused at submit", reply["error"])
        self.assertEqual(self._entries(), before)
        self.assertEqual(frappe.db.count("Journal Entry", {"docstatus": 0, "is_opening": "Yes"}), 0)
        doc = self._doc(session)
        self.assertEqual(doc.status, "Failed")
        self.assertEqual([r for r in doc.created_records if r.record_doctype == "Journal Entry"], [])
        self.assertFalse(opening_balances.settings(doc).get("created"))

    def test_a_failed_entry_leaves_no_commit_callbacks_or_webhooks_behind(self):
        session, result = self._ready()
        real = frappe.model.document.Document._submit
        queue_before = getattr(frappe.local, "_webhook_queue", None)

        def spy():
            pass

        def cleanup():
            for name in ("before_commit", "after_commit"):
                functions = getattr(frappe.db, name)._functions
                while spy in functions:
                    functions.remove(spy)
            frappe.local._webhook_queue = queue_before

        self.addCleanup(cleanup)

        def refuse(doc, *args, **kwargs):
            if doc.doctype == "Journal Entry":
                frappe.db.after_commit.add(spy)
                frappe.db.before_commit.add(spy)
                frappe.local._webhook_queue = [frappe._dict(doc=doc, webhook=frappe._dict())]
                frappe.throw(frappe._("Refused at submit"))
            return real(doc, *args, **kwargs)

        with patch.object(frappe.model.document.Document, "_submit", refuse):
            reply = self._import(session, result)
        self.assertFalse(reply["success"], reply)
        self.assertNotIn(spy, frappe.db.after_commit._functions)
        self.assertNotIn(spy, frappe.db.before_commit._functions)
        self.assertEqual(getattr(frappe.local, "_webhook_queue", None), queue_before)

    def test_folded_profit_and_loss_accounts_are_reported_and_said_in_the_message(self):
        session, result = self._ready(
            [f"{self.bank},100,,", f"{self.expense},30,,", f"{self.capital},,130,"],
            profit_and_loss="retained_earnings",
            retained_earnings_account=self.retained,
        )
        reply = self._import(session, result)
        self.assertTrue(reply["success"], reply)
        report = reply["result"]
        self.assertEqual(report["folded"], [{"account": self.expense, "file_net": 30}])
        self.assertIn("1 Profit and Loss accounts were folded into", report["message"])
        self.assertIn(self.retained, report["message"])
        self.assertIn("not compared one by one", report["message"])

    def test_nothing_folded_adds_no_clause(self):
        session, result = self._ready()
        report = self._import(session, result)["result"]
        self.assertEqual(report["folded"], [])
        self.assertNotIn("folded", report["message"])

    def test_importing_again_after_a_failure_is_refused_until_the_sheet_is_checked(self):
        session, result = self._ready()
        with patch.object(
            opening_balances, "build_entry", side_effect=lambda *a, **k: frappe.throw(frappe._("No"))
        ):
            self.assertFalse(self._import(session, result)["success"])
        before = self._entries()
        again = self._import(session, result)
        self.assertFalse(again["success"], again)
        self.assertEqual(
            again["error"], "The last import failed. Check the sheet again with dry_run_import, then import."
        )
        self.assertEqual(self._entries(), before)

    def test_a_currency_precision_of_zero_is_used_as_given(self):
        with patch.object(opening_balances.frappe, "get_precision", return_value=0):
            self.assertEqual(opening_balances._precision(), 0)
            # 0.4 is a rounding difference at no decimals, but not at two
            session, result = self._ready([f"{self.bank},100.4,,", f"{self.capital},,100,"])
            self.assertEqual(result["ready"], 2, result)
            lines = opening_balances.entry_lines(
                opening_balances.settings(self._doc(session)),
                opening_balances.ready_lines(self._doc(session)),
            )
            self.assertEqual(
                [(x["debit_in_account_currency"], x["credit_in_account_currency"]) for x in lines],
                [(100, 0), (0, 100)],
            )
        with patch.object(opening_balances.frappe, "get_precision", return_value=None):
            self.assertEqual(opening_balances._precision(), 2)

    def test_a_failed_session_can_be_checked_and_imported_again(self):
        session, result = self._ready()
        with patch.object(
            opening_balances, "build_entry", side_effect=lambda *a, **k: frappe.throw(frappe._("No"))
        ):
            self.assertFalse(self._import(session, result)["success"])
        again = self._run("dry_run_import", {"session": session})
        self.assertTrue(again["success"], again)
        self.assertTrue(self._import(session, again["result"])["success"])
        self.assertEqual(self._doc(session).status, "Completed")

    def test_a_user_who_cannot_submit_gets_the_setup_error(self):
        session, result = self._ready()
        real = frappe.has_permission

        def no_submit(doctype=None, ptype="read", *args, **kwargs):
            if doctype == "Journal Entry" and ptype == "submit":
                return False
            return real(doctype, ptype, *args, **kwargs)

        before = self._entries()
        with patch.object(opening_balances.frappe, "has_permission", side_effect=no_submit):
            reply = self._import(session, result)
        self.assertFalse(reply["success"], reply)
        self.assertIn("Accounts Manager", frappe.as_json(reply))
        self.assertEqual(self._entries(), before)

    def test_another_opening_entry_at_the_date_is_refused_at_the_import(self):
        session, result = self._ready()
        entry = frappe.get_doc(
            {
                "doctype": "Journal Entry",
                "voucher_type": "Opening Entry",
                "company": self.company,
                "posting_date": self.date,
                "accounts": [
                    {"account": self.bank, "debit_in_account_currency": 5},
                    {"account": self.capital, "credit_in_account_currency": 5},
                ],
            }
        )
        entry.insert()
        entry.submit()
        self.made_entries.append(entry.name)
        reply = self._import(session, result)
        self.assertFalse(reply["success"], reply)
        self.assertIn(entry.name, frappe.as_json(reply))
        self.assertEqual(self._doc(session).status, "Ready to Import")

    def test_a_session_of_another_kind_is_pointed_to_start_import(self):
        started = self._run("start_import_session", {"file_id": self._file([f"{self.bank},1,,"]).name})
        reply = self._run(
            "import_opening_balances",
            {
                "session": started["result"]["session_id"],
                "company": self.company,
                "cut_off": self.date,
                "rows": 1,
                "total_debit": 1,
                "total_credit": 0,
            },
        )
        self.assertFalse(reply["success"])
        self.assertIn("start_import", reply["error"])

    # -- review fixes --------------------------------------------------------------------

    def test_an_entry_of_more_than_100_lines_is_imported_in_the_request(self):
        accounts = [self._account(f"Bulk {i}", "Asset") for i in range(101)]
        lines = [f"{account},1,," for account in accounts] + [f"{self.capital},,101,"]
        session, result = self._ready(lines)
        self.assertEqual((result["ready"], result["failed"]), (102, 0), result)
        queued = frappe.db.count("Submission Queue")
        reply = self._import(session, result)
        self.assertTrue(reply["success"], reply)
        entry = frappe.get_doc("Journal Entry", self._entry_of(session))
        self.assertEqual((entry.docstatus, len(entry.accounts)), (1, 102))
        self.assertEqual(self._doc(session).status, "Completed")
        self.assertEqual(frappe.db.count("Submission Queue"), queued)

    def test_the_check_submits_the_entry_the_way_the_import_does(self):
        accounts = [self._account(f"Bulk {i}", "Asset") for i in range(101)]
        lines = [f"{account},1,," for account in accounts] + [f"{self.capital},,101,"]
        queued = frappe.db.count("Submission Queue")
        with patch.object(frappe.model.document.Document, "_submit", autospec=True) as submitted:
            submitted.side_effect = lambda doc: setattr(doc, "docstatus", 1)
            self._ready(lines)
        self.assertTrue(submitted.called)
        self.assertEqual(frappe.db.count("Submission Queue"), queued)

    def test_create_returns_when_another_call_already_moved_the_session(self):
        for status in ("Importing", "Completed"):
            session, result = self._ready()
            stale = self._doc(session)
            frappe.db.set_value("FAC Import Session", session, "status", status, update_modified=False)
            before = self._entries()
            opening_balances.create(stale)
            self.assertEqual(self._entries(), before)
            self.assertEqual(frappe.db.get_value("FAC Import Session", session, "status"), status)

    def test_the_session_is_importing_while_the_entry_is_made(self):
        session, result = self._ready()
        seen = []
        real = opening_balances.build_entry

        def spy(*args, **kwargs):
            seen.append(frappe.db.get_value("FAC Import Session", session, "status"))
            return real(*args, **kwargs)

        with patch.object(opening_balances, "build_entry", side_effect=spy):
            self.assertTrue(self._import(session, result)["success"])
        self.assertEqual(seen, ["Importing"])

    def test_a_failure_does_not_overwrite_a_concurrent_completion(self):
        session, result = self._ready()
        real = frappe.db.rollback

        def rollback_then_complete(*args, **kwargs):
            real(*args, **kwargs)
            if kwargs.get("save_point") == opening_balances.CREATE_SAVEPOINT:
                options = frappe.parse_json(
                    frappe.db.get_value("FAC Import Session", session, "template_options")
                )
                options["opening_balances"]["created"] = {"ACC-JV-OTHER": {}}
                frappe.db.set_value(
                    "FAC Import Session",
                    session,
                    {"status": "Completed", "template_options": frappe.as_json(options)},
                    update_modified=False,
                )

        with (
            patch.object(
                opening_balances, "build_entry", side_effect=lambda *a, **k: frappe.throw(frappe._("No"))
            ),
            patch.object(frappe.db, "rollback", side_effect=rollback_then_complete),
        ):
            reply = self._import(session, result)
        self.assertFalse(reply["success"], reply)
        doc = self._doc(session)
        self.assertEqual(doc.status, "Completed")
        self.assertEqual(list(opening_balances.settings(doc)["created"]), ["ACC-JV-OTHER"])
        self.assertFalse([s for s in doc.steps if s.step == "Import" and s.outcome == "Failed"])

    def test_a_card_for_an_unchecked_sheet_says_so_without_none(self):
        session = self._session()
        self.assertTrue(self._setup(session)["success"])
        reply = self._run(
            "import_opening_balances",
            {
                "session": session,
                "company": self.company,
                "cut_off": self.date,
                "rows": 2,
                "total_debit": 100,
                "total_credit": 100,
            },
        )
        self.assertFalse(reply["success"], reply)
        self.assertIn("dry_run_import", reply["error"])
        self.assertNotIn("None", reply["error"])

    def test_a_changed_ready_count_is_refused(self):
        session, result = self._ready()
        before = self._entries()
        real = opening_balances.ready_lines
        with patch.object(opening_balances, "ready_lines", side_effect=lambda s: real(s)[:-1]):
            reply = self._import(session, result)
        self.assertFalse(reply["success"], reply)
        self.assertIn("changed since the last check", reply["error"])
        self.assertEqual(self._entries(), before)
        self.assertEqual(self._doc(session).status, "Ready to Import")


class TestReport(OpeningBalancesCase):
    def setUp(self):
        super().setUp()
        self.stock = self._account("Stock", "Asset", "Stock")

    def _temporary_net(self):
        row = frappe.db.sql(
            "select coalesce(sum(debit - credit), 0) from `tabGL Entry` where account=%s "
            "and is_cancelled=0 and posting_date<=%s",
            (self.temporary, self.date),
        )
        return row[0][0]

    def _imported(self, lines, **setup):
        session = self._session(lines)
        self.assertTrue(self._setup(session, **setup)["success"])
        result = self._run("dry_run_import", {"session": session})["result"]
        card = {
            "session": session,
            "company": self.company,
            "cut_off": result["opening_balances"]["cut_off"],
            "rows": result["ready"],
            "total_debit": result["opening_balances"]["total_debit"],
            "total_credit": result["opening_balances"]["total_credit"],
            **card_amounts(result),
        }
        reply = self._run("import_opening_balances", card)
        for record in self._doc(session).created_records or []:
            if record.record_doctype == "Journal Entry" and record.record_name not in self.made_entries:
                self.made_entries.append(record.record_name)
        self.assertTrue(reply["success"], reply)
        return session, reply["result"]

    def _second_entry(self, account, amount, party=None):
        """An ordinary Journal Entry debiting ``account`` and crediting Capital."""
        extra = {"party_type": "Customer", "party": party} if party else {}
        entry = frappe.get_doc(
            {
                "doctype": "Journal Entry",
                "company": self.company,
                "posting_date": self.date,
                "voucher_type": "Journal Entry",
                "accounts": [
                    {
                        "account": account,
                        "debit_in_account_currency": amount,
                        "credit_in_account_currency": 0,
                        **extra,
                    },
                    {
                        "account": self.capital,
                        "debit_in_account_currency": 0,
                        "credit_in_account_currency": amount,
                    },
                ],
            }
        ).insert()
        entry.submit()
        self.made_entries.insert(0, entry.name)  # cancelled before the opening entry
        return entry

    def test_matches_after_a_clean_import(self):
        session, report = self._imported([f"{self.bank},100,,", f"{self.capital},,100,"])
        self.assertEqual(report["accounts"], [])
        self.assertEqual(report["differences_count"], 0)
        self.assertIn("matches the file, account by account", report["message"])
        self.assertEqual(report["lines"], 2)
        self.assertIsNone(report["balancing"])
        self.assertEqual(report["temporary_opening"]["balance"], self._temporary_net())
        self.assertEqual(
            report["totals"],
            {"file_debit": 100, "file_credit": 100, "erpnext_debit": 100, "erpnext_credit": 100},
        )

    def test_a_row_imported_stays_imported_when_its_account_is_disabled(self):
        # An account disabled after go-live still holds its opening balance
        session, _report = self._imported([f"{self.bank},100,,", f"{self.capital},,100,"])
        frappe.db.set_value("Account", self.bank, "disabled", 1)
        self.addCleanup(frappe.db.set_value, "Account", self.bank, "disabled", 0)

        rows = [o for o in opening_balances.outcomes(self._doc(session)) if not o["totals_row"]]

        self.assertEqual([row["status"] for row in rows], ["imported", "imported"], rows)

    def test_a_second_entry_makes_an_account_differ(self):
        session, _ = self._imported([f"{self.bank},100,,", f"{self.capital},,100,"])
        self._second_entry(self.bank, 25)
        report = opening_balances.report(self._doc(session))
        self.assertEqual(report["differences_count"], 2)
        by_account = {row["account"]: row for row in report["accounts"]}
        self.assertEqual(
            by_account[self.bank],
            {"account": self.bank, "file_net": 100, "erpnext_net": 125, "difference": 25},
        )
        self.assertEqual(
            by_account[self.capital],
            {"account": self.capital, "file_net": -100, "erpnext_net": -125, "difference": -25},
        )
        self.assertIn("2 accounts differ from the file; they are listed.", report["message"])
        self.assertNotIn("matches", report["message"])

    def test_covered_rows_are_labelled_and_never_differences(self):
        session, report = self._imported(
            [f"{self.bank},100,,", f"{self.debtors},50,,", f"{self.stock},20,,", f"{self.capital},,170,"]
        )
        covered = {row["account"]: row for row in report["covered"]}
        self.assertEqual(set(covered), {self.debtors, self.stock})
        self.assertEqual(
            covered[self.debtors],
            {
                "account": self.debtors,
                "file_net": 50,
                "erpnext_net": 0,
                "source": "opening invoices / opening stock",
            },
        )
        self.assertEqual(covered[self.stock]["file_net"], 20)
        self.assertEqual(report["accounts"], [])
        self.assertEqual(report["differences_count"], 0)

    def test_temporary_opening_holds_the_covered_rows_until_they_are_imported(self):
        before = self._temporary_net()
        session, report = self._imported(
            [f"{self.bank},100,,", f"{self.debtors},50,,", f"{self.stock},20,,", f"{self.capital},,170,"]
        )
        self.assertEqual(report["balancing"], {"account": self.temporary, "debit": 70, "credit": 0})
        self.assertEqual(report["temporary_opening"], {"account": self.temporary, "balance": before + 70})
        self.assertIn("Temporary Opening still holds", report["message"])
        self.assertIn("it clears when the opening invoices and opening stock are imported", report["message"])

    def test_temporary_opening_not_netting_to_zero_when_everything_is_in(self):
        session, _ = self._imported([f"{self.bank},100,,", f"{self.debtors},50,,", f"{self.capital},,150,"])
        customer = frappe.get_all("Customer", pluck="name", limit=1)
        if not customer:
            self.skipTest("the site has no Customer")
        self._second_entry(self.debtors, 50, party=customer[0])  # the covered row is now in ERPNext
        report = opening_balances.report(self._doc(session))
        self.assertEqual(report["covered"][0]["erpnext_net"], 50)
        self.assertEqual(report["temporary_opening"]["balance"], self._temporary_net())
        self.assertIn("does not net to zero", report["message"])
        self.assertNotIn("clears when", report["message"])

    def test_differences_are_capped_with_their_count(self):
        session, _ = self._imported([f"{self.bank},100,,", f"{self.capital},,100,"])
        self._second_entry(self.bank, 5)
        with patch.object(opening_balances, "DIFFERENCES_SHOWN", 1):
            report = opening_balances.report(self._doc(session))
        self.assertEqual(len(report["accounts"]), 1)
        self.assertEqual(report["differences_count"], 2)
        self.assertIn("first 1 of 2", report["message"])

    def test_left_out_rows_are_listed_with_their_amounts(self):
        session, _ = self._imported(
            [f"{self.bank},100,,", f"{self.expense},30,,", f"{self.capital},,130,"],
            profit_and_loss="retained_earnings",
            retained_earnings_account=self._account("Retained", "Equity"),
        )
        self._doc(session).db_set("excluded_rows", frappe.as_json([3]))
        report = opening_balances.report(self._doc(session))
        self.assertEqual(len(report["not_brought_in"]), 1)
        held = report["not_brought_in"][0]
        self.assertEqual((held["count"], held["rows"], held["debit"], held["credit"]), (1, "3", 30, 0))
        self.assertIn("30", report["message"])
        self.assertIn(
            "Rows left out (net 30.00 debit) were not brought in, so Temporary Opening will not net "
            "to zero by that amount.",
            report["message"],
        )

    def test_a_session_without_an_entry_has_an_empty_report(self):
        session = self._session()
        self.assertTrue(self._setup(session)["success"])
        report = opening_balances.report(self._doc(session))
        self.assertIsNone(report["journal_entry"])
        self.assertEqual((report["accounts"], report["covered"], report["not_brought_in"]), ([], [], []))
        self.assertEqual(report["differences_count"], 0)

    def test_the_repeat_call_returns_the_full_report(self):
        session, first = self._imported(
            [f"{self.bank},100,,", f"{self.debtors},50,,", f"{self.capital},,150,"]
        )
        card = {
            "session": session,
            "company": self.company,
            "cut_off": self.date,
            "rows": 3,
            "total_debit": 150,
            "total_credit": 150,
            "balancing_amount": 50,  # the debtors' 50, which the opening invoices bring in
            "covered_debit": 50,
        }
        again = self._run("import_opening_balances", card)
        self.assertTrue(again["success"], again)
        for key in ("accounts", "covered", "temporary_opening", "totals", "differences_count", "message"):
            self.assertIn(key, again["result"])
        self.assertEqual(again["result"]["covered"], first["covered"])
