# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
The migration's sign-off report (#33999), the ERPNext report "Migration Sign-off": per DocType,
the rows in the files and how many were imported, left out (with reasons), failed and not imported;
the opening balances in ERPNext against the files' totals; and the trial balance against the opening
balances file. FACO runs it with generate_report; every number is counted by the engine. Sessions
are made the way production makes them, through the tools; nothing is mocked but the v16 query rule.
"""

import unittest
from unittest.mock import patch

import frappe

# Modules, not their classes: a test class imported here would run again with this module's tests.
from frappe_assistant_core.tests import test_import_failures as failures_tests
from frappe_assistant_core.tests import test_import_opening_balances as balances_tests
from frappe_assistant_core.tests import test_import_opening_invoices as invoices_tests
from frappe_assistant_core.tests import test_import_opening_stock as stock_tests
from frappe_assistant_core.tests import test_import_run as run_tests
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils import import_failures, import_signoff

GROUP_NODE = failures_tests.GROUP_NODE
REPORT = "Migration Sign-off"
refuse_sql_functions = stock_tests.refuse_sql_functions


def section(data, name):
    return [row for row in data if row.get("section") == name]


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
class TestDataImportSession(run_tests.ImportRunCase):
    """A Data Import session: alpha and delta imported, beta left out, gamma refused by ERPNext."""

    _partly_imported = failures_tests.TestImportFailures._partly_imported

    def setUp(self):
        super().setUp()
        self.held = f"Held {self.tag}"  # the group _partly_imported turns into a group node
        frappe.get_doc(
            {
                "doctype": "Customer Group",
                "customer_group_name": self.held,
                "parent_customer_group": "All Customer Groups",
            }
        ).insert()

    def _report(self, **filters):
        reply = self._run("generate_report", {"report_name": REPORT, "filters": filters})
        self.assertTrue(reply["success"], reply)
        return reply["result"]

    def test_every_row_of_the_file_is_imported_left_out_or_failed_with_why(self):
        session, _checked, _result = self._partly_imported()

        summary = import_signoff.session_summary(self._doc(session))

        self.assertEqual(
            summary["rows"],
            {"source": 4, "imported": 2, "unchanged": 0, "excluded": 1, "failed": 1, "not_imported": 0},
        )
        self.assertEqual(summary["excluded"], [{"reason": "Closed shop", "count": 1, "rows": "3"}])
        [failed] = summary["failed"]
        self.assertEqual((failed["count"], failed["rows"]), (1, "4"))
        self.assertIn(GROUP_NODE, failed["reason"])
        self.assertEqual((summary["label"], summary["finished"]), ("Customer", True))

    _failed_rows = failures_tests.TestImportFailures._failed_rows
    _check = failures_tests.TestImportFailures._check
    _csv = failures_tests.TestImportFailures._csv

    def _send_back(self, session, groups, before_import=None):
        """The failed-rows file's rows in ``groups`` (1 is its first data row) given that Customer
        Group, sent back as the corrected file, checked and imported."""
        _out, _file_doc, rows = self._failed_rows(session)
        corrected = [rows[0]] + [rows[i][:1] + [group] + rows[i][2:] for i, group in groups.items()]
        checked = self._check(session, file_id=self._csv("corrected.csv", corrected).name)
        if before_import:
            before_import()
        with self._each_row_commits():
            response = self._import(session, checked)
        self.assertTrue(response["success"], response)
        return response["result"]

    def test_rows_sent_back_corrected_are_counted_with_the_first_file(self):
        # The documented retry: only gamma (row 4) comes back, fixed; beta stays left out
        session, _checked, _result = self._partly_imported()
        self._send_back(session, {2: self.group})

        summary = import_signoff.session_summary(self._doc(session))

        self.assertEqual(
            summary["rows"],
            {"source": 4, "imported": 3, "unchanged": 0, "excluded": 1, "failed": 0, "not_imported": 0},
        )
        self.assertEqual(summary["excluded"][0]["rows"], "3")

    def test_a_second_corrected_file_is_laid_over_the_one_before_it(self):
        # Beta and gamma come back; gamma fails at import again (its group made a group node after
        # the check, as _partly_imported does) and comes back again: its FACO Original Row in the
        # second failed-rows file is its row in the first corrected file.
        session, _checked, _result = self._partly_imported()
        frappe.db.set_value("Customer Group", self.held, "is_group", 0)
        self._send_back(
            session,
            {1: self.group, 2: self.held},
            before_import=lambda: frappe.db.set_value("Customer Group", self.held, "is_group", 1),
        )
        midway = import_signoff.session_summary(self._doc(session))
        self.assertEqual(
            midway["rows"],
            {"source": 4, "imported": 3, "unchanged": 0, "excluded": 0, "failed": 1, "not_imported": 0},
        )
        frappe.db.set_value("Customer Group", self.held, "is_group", 0)
        self._send_back(session, {1: self.held})

        summary = import_signoff.session_summary(self._doc(session))

        self.assertEqual(
            summary["rows"],
            {"source": 4, "imported": 4, "unchanged": 0, "excluded": 0, "failed": 0, "not_imported": 0},
        )

    def test_a_linked_data_import_of_someone_else_is_not_followed(self):
        # A session's child rows can be written over the REST API, so a link there can name another
        # user's Data Import: its rows and failure messages must not reach this user's report.
        session, _checked, _result = self._partly_imported()
        doc = self._doc(session)
        self.assertEqual(import_failures.imported_rows(doc), {2, 5})
        user = self.make_throwaway_user("signoff", roles=("Sales User",))  # can't read Data Imports
        doc.user = doc.owner = user  # a session of theirs that links the Administrator's import

        frappe.set_user(user)

        self.assertEqual(import_failures.imported_rows(doc), set())
        self.assertEqual(import_failures._import_file_rows(doc.data_imports[0].data_import), [])
        self.assertEqual(import_failures.runs(doc), [])
        with self.assertRaises(run_tests.import_run.ImportProblem):  # never started again for them
            run_tests.import_run.resume(doc)

    def test_before_the_import_the_checked_rows_are_not_imported_yet(self):
        session, _checked = self._ready_session()

        summary = import_signoff.session_summary(self._doc(session))

        self.assertEqual(
            summary["rows"],
            {"source": 4, "imported": 0, "unchanged": 0, "excluded": 1, "failed": 0, "not_imported": 3},
        )
        self.assertFalse(summary["finished"])

    def test_generate_report_runs_it_and_gets_the_counts_reasons_and_cards(self):
        session, _checked, _result = self._partly_imported()

        result = self._report(import_session=session)

        [records] = section(result["data"], "Records")
        self.assertEqual(
            [
                records[key]
                for key in (
                    "item",
                    "source_rows",
                    "imported_rows",
                    "left_out_rows",
                    "failed_rows",
                    "not_imported_rows",
                )
            ],
            ["Customer", 4, 2, 1, 1, 0],
        )
        why = " ".join(row["details"] for row in section(result["data"], "Why Not Imported"))
        self.assertIn("Closed shop (row 3 of", why)
        self.assertIn(GROUP_NODE, why)
        self.assertTrue(section(result["data"], "Open Points"))
        self.assertIn("4 rows in the files, 2 imported, 1 left out, 1 failed", result["message"])
        cards = {card["label"]: card["value"] for card in result["report_summary"]}
        self.assertEqual(
            (cards["Rows in the Files"], cards["Failed"], cards["Ready to Sign Off"]), (4, 1, "No")
        )

    def test_with_document_the_message_is_the_whole_report_for_the_pdf(self):
        session, _checked, _result = self._partly_imported()

        result = self._report(import_session=session, document=1)

        text = result["message"]
        self.assertIn("4 rows in the files, 2 imported, 1 left out, 1 failed", text)
        self.assertIn(
            "| Item | Rows in the Files | Imported | Unchanged | Left Out | Failed | Not Imported |", text
        )
        self.assertIn("| Customer | 4 | 2 | 0 | 1 | 1 | 0 |", text)
        self.assertIn("Closed shop (row 3 of", text)
        self.assertIn(GROUP_NODE, text)
        self.assertIn("## Open Points", text)
        self.assertIn("Name: ______", text)
        # every row of the report is in the document, so nothing has to be typed out again
        for row in result["data"]:
            self.assertIn(row["item"].replace("|", "\\|"), text)

    def test_text_from_files_and_reasons_is_escaped_for_desk(self):
        session, _checked, _result = self._partly_imported()
        # Production: a left-out reason is the user's own words; a cell of a file can hold anything.
        doc = self._doc(session)
        rules = frappe.parse_json(doc.transformation_rules)
        rules["left_out"]["3"] = "<img src=x onerror=alert(1)>"
        doc.db_set("transformation_rules", frappe.as_json(rules))

        result = self._report(import_session=session, document=1)

        details = " ".join(row.get("details") or "" for row in result["data"])
        self.assertNotIn("<img", details)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", details)
        self.assertNotIn("<img", result["message"])

    def test_without_document_the_message_is_the_headline(self):
        session, _checked, _result = self._partly_imported()

        result = self._report(import_session=session)

        self.assertNotIn("##", result["message"])

    def test_without_sessions_it_covers_the_users_own_sessions(self):
        session, _checked, _result = self._partly_imported()

        # Dates given, as the skill asks: left out, generate_report fills in the newest Fiscal Year,
        # which on a site with next year's (or ERPNext's test fixtures, up to 2050) misses today.
        result = self._report(from_date=frappe.utils.today(), to_date=frappe.utils.today())

        self.assertIn(session, [row["item"] for row in section(result["data"], "Sessions")])

    def test_a_named_session_is_reported_whatever_the_dates(self):
        session, _checked, _result = self._partly_imported()

        result = self._report(import_session=session, from_date="2050-01-01", to_date="2050-12-31")

        self.assertEqual([row["item"] for row in section(result["data"], "Sessions")], [session])

    def test_a_migration_plan_is_reported_on_its_own(self):
        # #34549: the report could be narrowed by dates only, so earlier test runs came into it
        session, _checked, _result = self._partly_imported()
        # another session of the user's, the same day: an earlier test run, say
        other_file = self._file("other.csv", f"Customer Name\nOther {self.tag}\n".encode())
        other = self._run("start_import_session", {"file_url": other_file.file_url})["result"]["session_id"]
        # what plan_migration does with the plan's files: the plan is its first file's session
        frappe.db.set_value("FAC Import Session", session, "migration_plan", session)

        result = self._report(migration_plan=session, from_date="2050-01-01", to_date="2050-12-31")

        self.assertEqual([row["item"] for row in section(result["data"], "Sessions")], [session])
        self.assertNotIn(other, frappe.as_json(result["data"]))
        self.assertTrue(
            result["message"].startswith(f"Scope: migration plan {session}, 1 file."), result["message"]
        )

    def test_a_session_the_user_cannot_read_is_refused(self):
        session, _checked = self._ready_session()
        frappe.set_user(self.make_throwaway_user("signoff", roles=("Desk User",)))

        with self.assertRaises(frappe.DoesNotExistError):
            import_signoff.execute({"import_session": session})

    def test_a_desk_user_can_run_it_on_their_own_sessions(self):
        frappe.set_user(self.make_throwaway_user("signoff", roles=("Desk User",)))

        reply = self._run("generate_report", {"report_name": REPORT, "filters": {}})

        self.assertTrue(reply["success"], reply)
        self.assertTrue(reply["result"]["message"].endswith("No import sessions to report on."), reply)


class TestOpeningInvoicesInTheReport(invoices_tests.OpeningInvoicesCase):
    def _imported(self, lines):
        session, result = self._ready(lines)
        totals = self._groups(result).get("Totals row")
        if totals:  # the file's own totals row is left out, as the user would
            fix = {"group": totals["id"], "action": "leave_out", "reason": "The file's total"}
            result = self._run("dry_run_import", {"session": session, "fixes": [fix]})["result"]
        reply = self._run("import_opening_invoices", self._card(session, result))
        self.assertTrue(reply["success"], reply)
        return session

    def test_receivables_in_erpnext_are_set_against_the_files_total(self):
        session = self._imported(
            [
                f"{self.customer},{self._number(1)},{self.date},,10.5",
                f"{self.customer2},{self._number(2)},{self.date},,20",
                "Total,,,,30.5",
            ]
        )
        summary = import_signoff.session_summary(self._doc(session))
        self.assertEqual(summary["file_says"], 30.5)  # the file's own total, a check on its rows

        report = import_signoff.build([self._doc(session)])

        receivables = report["opening_balances"][self.company]["receivables"]
        self.assertEqual(
            {k: receivables[k] for k in ("file", "imported", "erpnext", "difference", "not_in")},
            {"file": 30.5, "imported": 30.5, "erpnext": 30.5, "difference": 0, "not_in": 0},
        )
        trial = report["opening_balances"][self.company]["trial_balance"]
        self.assertEqual((trial["as_of"], trial["difference"], trial["source"]), (self.date, 0, None))
        # Only the receivables are in: their other side waits on Temporary Opening.
        self.assertTrue(trial["temporary_opening"]["balance"])
        self.assertTrue(any("Temporary Opening" in p for p in report["open_points"]), report["open_points"])

        self.assertIn(
            "| Receivables | Promantia | 30.50 |",
            import_signoff.document(report).replace(self.company, "Promantia"),
        )
        [row] = section(import_signoff.rows(report), "Opening Balances")
        self.assertEqual(
            (row["item"], row["in_files"], row["in_erpnext"], row["difference"]),
            ("Receivables", 30.5, 30.5, 0),
        )

    def test_payables_come_from_purchase_invoices(self):
        session, result = self._ready(
            [f"{self.supplier},{self._number(1)},{self.date},,12"], invoice_type="Purchase"
        )
        self.assertTrue(self._run("import_opening_invoices", self._card(session, result))["success"])

        balances = import_signoff.build([self._doc(session)])["opening_balances"][self.company]

        self.assertEqual((balances["payables"]["file"], balances["payables"]["erpnext"]), (12, 12))
        self.assertNotIn("receivables", balances)

    def test_an_invoice_changed_after_the_import_is_a_difference(self):
        session = self._imported([f"{self.customer},{self._number(1)},{self.date},,10"])
        frappe.db.set_value("Sales Invoice", self._number(1), "grand_total", 9)

        report = import_signoff.build([self._doc(session)])

        self.assertEqual(report["opening_balances"][self.company]["receivables"]["difference"], -1)
        self.assertTrue(any("differs from the file's rows by -1.00" in p for p in report["open_points"]))

    def test_a_user_who_cannot_read_the_books_sees_their_rows_but_not_erpnexts_totals(self):
        session = self._imported([f"{self.customer},{self._number(1)},{self.date},,10"])
        user = self.make_throwaway_user("signoff", roles=("Desk User",))
        # Production: a Desk User's own session and file; an Accounts Manager imported for them,
        # or their role was taken away since.
        self._doc(session).db_set("user", user)
        frappe.db.set_value("File", self._doc(session).source_file, "owner", user)
        frappe.set_user(user)

        report = import_signoff.build(import_signoff.sessions_of([session]))

        [summary] = report["sessions"]
        self.assertEqual((summary["rows"]["source"], summary["rows"]["imported"]), (1, 1))
        self.assertEqual(list(summary["erpnext"]), ["problem"])
        balances = report["opening_balances"][self.company]
        self.assertEqual((balances["receivables"]["file"], balances["receivables"]["erpnext"]), (10, None))
        self.assertEqual(set(balances["trial_balance"]), {"as_of", "problem"})
        self.assertIn("can't read", " ".join(report["open_points"]))
        self.assertFalse(report["ready_to_sign"])

    def test_no_query_asks_get_all_for_a_sql_function(self):
        session = self._imported([f"{self.customer},{self._number(1)},{self.date},,10"])

        with patch("frappe.get_all", refuse_sql_functions(frappe.get_all)):
            report = import_signoff.build([self._doc(session)])

        self.assertEqual(report["opening_balances"][self.company]["receivables"]["erpnext"], 10)


class TestOpeningStockInTheReport(stock_tests.OpeningStockCase):
    def test_the_stock_value_in_the_ledger_is_set_against_the_files(self):
        session, result = self._ready([f"{self.item},{self.stores},5,10", f"{self.item2},{self.shop},2,7.5"])
        self.assertTrue(self._run("import_opening_stock", self._card(session, result))["success"])

        with patch("frappe.get_all", refuse_sql_functions(frappe.get_all)):
            report = import_signoff.build([self._doc(session)])

        stock = report["opening_balances"][self.company]["stock"]
        self.assertEqual(
            {k: stock[k] for k in ("file", "imported", "erpnext", "difference")},
            {"file": 65, "imported": 65, "erpnext": 65, "difference": 0},
        )
        [entry] = report["doctypes"]
        self.assertEqual((entry["label"], entry["rows"]["imported"]), ("Opening Stock", 2))


class TestOpeningBalancesInTheReport(balances_tests.OpeningBalancesCase):
    def _import(self, lines):
        session = self._session(lines)
        self.assertTrue(self._setup(session)["success"])
        result = self._run("dry_run_import", {"session": session})["result"]
        card = {
            "session": session,
            "company": self.company,
            "cut_off": result["opening_balances"]["cut_off"],
            "rows": result["ready"],
            "total_debit": result["opening_balances"]["total_debit"],
            "total_credit": result["opening_balances"]["total_credit"],
            **balances_tests.card_amounts(result),
        }
        reply = self._run("import_opening_balances", card)
        for record in self._doc(session).created_records or []:
            if record.record_doctype == "Journal Entry" and record.record_name not in self.made_entries:
                self.made_entries.append(record.record_name)
        self.assertTrue(reply["success"], reply)
        return session

    def test_the_trial_balance_is_set_against_the_opening_balances_file(self):
        session = self._import([f"{self.bank},100,,", f"{self.capital},,100,"])

        with patch("frappe.get_all", refuse_sql_functions(frappe.get_all)):
            report = import_signoff.build([self._doc(session)])

        summary = report["sessions"][0]
        self.assertEqual(
            summary["rows"],
            {"source": 2, "imported": 2, "unchanged": 0, "excluded": 0, "failed": 0, "not_imported": 0},
        )
        source = report["opening_balances"][self.company]["trial_balance"]["source"]
        self.assertEqual(
            (source["debit"], source["credit"], source["imported_debit"], source["accounts_differing"]),
            (100, 100, 100, 0),
        )
        rows = section(import_signoff.rows(report), "Trial Balance")
        self.assertIn("Every account matches the file", " ".join(r.get("details") or "" for r in rows))

    def test_receivable_rows_are_left_to_the_opening_invoices_and_said_so(self):
        session = self._import([f"{self.bank},100,,", f"{self.debtors},50,,", f"{self.capital},,150,"])

        report = import_signoff.build([self._doc(session)])

        summary = report["sessions"][0]
        self.assertEqual((summary["rows"]["imported"], summary["rows"]["excluded"]), (2, 1))
        self.assertIn("opening invoices", summary["excluded"][0]["reason"])
        # Nothing brought the 50 into Debtors yet: the report says the books don't hold it.
        self.assertTrue(any(self.debtors in point for point in report["open_points"]), report["open_points"])


class TestRowWording(BaseAssistantTest):
    def test_one_row_is_a_row_and_several_are_rows(self):
        # The report read "Negative opening quantity (rows 6 of bt26_opening_stock.csv)".
        one = {"reason": "Negative opening quantity", "count": 1, "rows": "6"}
        two = {"reason": "Customer does not exist", "count": 2, "rows": "5, 9"}

        self.assertEqual(
            import_signoff.rows_of(one, "stock.csv"), "Negative opening quantity (row 6 of stock.csv)"
        )
        self.assertEqual(
            import_signoff.rows_of(two, "invoices.csv"), "Customer does not exist (rows 5, 9 of invoices.csv)"
        )
