# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
#34413 and #34438: the review's smaller findings on the data migration, one test each.
"""

import unittest
from unittest.mock import patch

import frappe
from frappe.database import get_db
from frappe.query_builder import DocType

from frappe_assistant_core.assistant_core.doctype.fac_import_session.fac_import_session import engine_session
from frappe_assistant_core.tests.test_import_mapping import ImportToolTestCase
from frappe_assistant_core.utils import import_failures


class TestFailedRowsFile(unittest.TestCase):
    def test_a_cell_that_starts_like_a_formula_is_not_run_by_a_spreadsheet(self):
        for cell in ('=HYPERLINK("http://x")', "+1+1", "-2+3", "@SUM(A1)", "\tx"):
            with self.subTest(cell=cell):
                self.assertEqual(import_failures.csv_cell(cell), "'" + cell)

    def test_numbers_and_plain_text_are_left_as_they_are(self):
        for cell in ("-5", "+3.5", "Acme", "", "1=1"):
            with self.subTest(cell=cell):
                self.assertEqual(import_failures.csv_cell(cell), cell)


class TestSessionDoctype(ImportToolTestCase):
    def test_the_owner_is_indexed_as_every_list_filters_on_it(self):
        self.assertTrue(frappe.get_meta("FAC Import Session").get_field("user").search_index)

    def test_a_save_keeps_its_history_without_the_large_json_fields(self):
        session = self._session()
        doc = engine_session(session)  # only the engine writes a session
        doc.validation_summary = frappe.as_json({"rows": ["x" * 1000] * 50})
        doc.status = "Dry Run Failed"
        doc.save(ignore_version=False)  # Frappe skips Versions under tests unless asked

        version = frappe.get_last_doc(
            "Version", filters={"ref_doctype": "FAC Import Session", "docname": session}
        )
        changed = {change[0] for change in frappe.parse_json(version.data).get("changed", [])}
        self.assertIn("status", changed)
        self.assertNotIn("validation_summary", changed)

    def test_the_sites_max_file_size_is_kept_when_the_engine_reads_a_file(self):
        from frappe_assistant_core.utils import import_session

        file_doc = frappe.get_doc(
            {"doctype": "File", "file_name": "small.csv", "content": b"Name\nAcme\n", "is_private": 1}
        ).insert()
        with patch.object(import_session, "get_max_file_size", return_value=4):
            with self.assertRaises(import_session.FileProblem) as raised:
                import_session.read_sheet_rows(file_doc)
        self.assertIn("largest file this site takes", str(raised.exception))


class TestMessages(unittest.TestCase):
    def test_the_dry_run_and_the_import_read_a_message_log_alike(self):
        from frappe_assistant_core.utils import import_dry_run

        log = [frappe.as_json({"message": "<b>Row 3</b>:  refused"}), {"message": "last  one"}, "plain"]

        self.assertEqual(import_dry_run.message_texts(log), ["Row 3: refused", "last one", "plain"])
        self.assertEqual(import_failures.log_reason(frappe.as_json(log)), "plain")

    def test_a_rows_check_leaves_the_requests_own_messages_alone(self):
        from frappe_assistant_core.utils import import_dry_run

        frappe.clear_messages()
        frappe.msgprint(frappe._("before the check"))
        with import_dry_run.own_messages():
            frappe.msgprint(frappe._("the row's"))
            self.assertEqual(len(frappe.local.message_log), 1)

        self.assertEqual(
            [
                frappe.parse_json(m)["message"] if isinstance(m, str) else m["message"]
                for m in frappe.local.message_log
            ],
            ["before the check"],
        )
        frappe.clear_messages()


class TestRealImportOptions(unittest.TestCase):
    def test_the_import_parses_with_the_date_formats_the_check_used(self):
        from frappe_assistant_core.utils import import_run

        session = frappe._dict(
            template_options=frappe.as_json(
                {
                    "column_to_field_map": {"0": "x"},
                    "column_to_date_format_map": {"2": "%d-%m-%Y"},
                    "undo": {},
                }
            )
        )

        options = import_run.data_import_options(session, {"0": "customer_name"})

        self.assertEqual(
            options,
            {"column_to_field_map": {"0": "customer_name"}, "column_to_date_format_map": {"2": "%d-%m-%Y"}},
        )


class TestGoogleSheetDownload(unittest.TestCase):
    def test_a_slow_sheet_is_refused_before_the_web_workers_timeout(self):
        # #34438: gunicorn's default is 120 s; the whole is checked as each piece arrives
        from frappe_assistant_core.utils import import_session

        worst = import_session.DOWNLOAD_SECONDS + import_session.DOWNLOAD_TIMEOUT[1]
        self.assertLessEqual(worst, 90)


class TestUpdateMatchKeys(unittest.TestCase):
    def test_a_date_or_number_key_matches_the_stored_value_whatever_its_format(self):
        # #34438: "100.00" never equalled 100, nor a typed date the stored one
        import datetime

        from frappe_assistant_core.utils import import_update

        date, number = frappe._dict(fieldtype="Date"), frappe._dict(fieldtype="Float")

        self.assertEqual(import_update.match_key(number, "100.00"), import_update.match_key(number, 100))
        self.assertEqual(import_update.match_key(number, "1,250.50"), import_update.match_key(number, 1250.5))
        self.assertEqual(
            import_update.match_key(date, "2024-02-01"),
            import_update.match_key(date, datetime.date(2024, 2, 1)),
        )
        self.assertEqual(import_update.match_key(None, " Acme "), "acme")
        self.assertEqual(import_update.match_key(number, "not a number"), "not a number")


class TestPlanAnswers(unittest.TestCase):
    def test_answers_applied_before_a_failure_are_reported_as_applied(self):
        # #34438: apply_answers released its savepoint, so they stay applied when the next step fails
        from frappe_assistant_core.plugins.migration.tools.dry_run_import import DryRunImport
        from frappe_assistant_core.utils import import_plan

        plan = frappe._dict(name="PLAN-1", status=import_plan.OPEN[0], reload=lambda: None)
        with patch.object(import_plan, "load_plan", return_value=plan), patch.object(
            import_plan, "apply_answers", return_value=[{"id": "q1"}]
        ), patch.object(import_plan, "open_questions", side_effect=import_plan.PlanProblem("broke")):
            reply = DryRunImport().execute({"plan": "PLAN-1", "answers": [{"id": "q1"}]})

        self.assertFalse(reply["success"])
        self.assertEqual(reply["applied"], [{"id": "q1"}])
        self.assertIn("were applied", reply["error"])


class TestReviewFindings(ImportToolTestCase):
    """The full round's review of fixes 8-18, each pinned by a test that failed first."""

    def test_a_cell_made_spreadsheet_safe_comes_back_as_the_user_wrote_it(self):
        # #34413: the failed-rows file writes '+91 98450 12345; read back, the ' comes off
        from frappe_assistant_core.utils import import_session

        for cell in ("+91 98450 12345", "-A12", "=x", "@home", "Acme", "'quoted"):
            with self.subTest(cell=cell):
                self.assertEqual(import_session._as_text(import_failures.csv_cell(cell)), cell)

    def test_a_session_copy_over_the_sites_max_file_size_is_refused_plainly(self):
        # #34405: an xlsx grows as CSV; Frappe's own refusal named neither cause nor way out
        from frappe_assistant_core.utils import import_session

        chosen = frappe._dict(rows=[["Name"], ["x" * 200]], columns=["Name"])
        with patch("frappe.core.api.file.get_max_file_size", return_value=100), self.assertRaises(
            import_session.FileProblem
        ) as raised:
            import_session.save_session_copy("big.xlsx", chosen)

        self.assertIn("Max File Size", str(raised.exception))

    def test_the_trial_submit_leaves_no_stock_cache_for_the_real_one(self):
        # #34435: ERPNext caches future stock moves by voucher name, which the real one reuses
        from frappe_assistant_core.utils import import_opening_stock

        frappe.local.future_sle = {"MAT-RECO-0001": {("A", "W"): 1}}
        with patch.object(import_opening_stock, "build_document", side_effect=frappe.ValidationError("x")):
            import_opening_stock._draft_error({}, [])

        self.assertEqual(frappe.local.future_sle, {})

    def test_a_sheet_is_not_kept_in_memory_past_the_sites_max_file_size(self):
        # security review: a small compressed workbook can hold far more text than the copy may be
        from frappe_assistant_core.utils import import_session

        rows = [["Name"]] + [["x" * 50] for _ in range(1000)]  # about 50 KB of text
        with patch.object(import_session, "max_file_size", return_value=10_000), self.assertRaises(
            import_session.FileProblem
        ) as raised:
            import_session._summarise("Sheet1", iter(rows), keep=True)

        self.assertIn("Max File Size", str(raised.exception))
        # counting a sheet without keeping it has no such limit
        self.assertEqual(import_session._summarise("Sheet1", iter(rows)).row_count, 1000)


class TestSeriesLocks(unittest.TestCase):
    """#34401: a row a check tries never locks its naming series, so no commit is needed to free
    it, and a migration plan's transaction stays whole."""

    def setUp(self):
        self.key = f"FACLOCK{frappe.generate_hash(length=6).upper()}-"
        series = DocType("Series")
        # A series users already number documents in: committed, as theirs is.
        frappe.qb.into(series).columns(series.name, series.current).insert(self.key, 7).run()
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — the other connection must see the row

    def tearDown(self):
        frappe.db.rollback()
        series = DocType("Series")
        frappe.qb.from_(series).delete().where(series.name == self.key).run()
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — setUp committed the row

    def _current(self):
        series = DocType("Series")
        return frappe.qb.from_(series).select(series.current).where(series.name == self.key).run()[0][0]

    def _locked_elsewhere(self) -> bool:
        """Whether another user's save would have to wait for the series row."""
        conf = frappe.conf
        other = get_db(
            host=conf.db_host,
            port=conf.db_port,
            user=conf.db_user or conf.db_name,
            password=conf.db_password,
            cur_db_name=conf.db_name,
            socket=conf.db_socket,
        )
        other.connect()
        try:
            other.sql("select `current` from `tabSeries` where `name`=%s for update nowait", self.key)
            return False
        except Exception:
            return True
        finally:
            other.rollback()
            other.close()

    def test_a_tried_row_neither_locks_nor_moves_a_naming_series(self):
        # make_autoname is how a row's insert reaches getseries (an "ABC-.#####" naming series)
        from frappe.model.naming import make_autoname

        from frappe_assistant_core.utils import import_dry_run

        with import_dry_run.held_back():
            names = [make_autoname(f"{self.key}.#####"), make_autoname(f"{self.key}.#####")]
            locked = self._locked_elsewhere()

        self.assertFalse(locked)
        # each name the row takes is the next one, as the import will give it
        self.assertEqual(names, [f"{self.key}00008", f"{self.key}00009"])
        self.assertEqual(self._current(), 7)
        # outside a check, the series moves as before
        self.assertEqual(make_autoname(f"{self.key}.#####"), f"{self.key}00008")


class TestPlanFencing(unittest.TestCase):
    def test_only_what_the_files_say_is_fenced_in_the_plans_questions(self):
        # #34438: FAC's own directions were fenced as file content. The decisions quote the files,
        # so each line is fenced on its own and the approval is still a list of lines.
        from frappe_assistant_core.plugins.migration.tools.dry_run_import import DryRunImport
        from frappe_assistant_core.utils.untrusted_output import fence_fields, unfenced

        result = {
            "questions": [
                {
                    "kind": "fix",
                    "file_name": "items.csv",
                    "message": "Brand 'Acme' doesn't exist.",
                    "fixes": [{"action": "map"}],
                },
                {
                    "kind": "cut_off",
                    "message": "The cut-off date: never guess it.",
                    "dates": {"stock.csv": "2026-03-31"},
                },
                {"kind": "waiting", "message": "Checked once items.csv is."},
            ],
            "approval": {
                "files": 1,
                "decisions": ["Create Brand 'Acme'.", "Rows that still fail: the plan stops."],
            },
        }

        fenced = fence_fields(result, DryRunImport().untrusted_fields)

        fix, cut_off, waiting = fenced["questions"]
        self.assertNotEqual(fix["message"], "Brand 'Acme' doesn't exist.")
        self.assertIn("Acme", fix["message"])
        self.assertNotEqual(fix["file_name"], "items.csv")
        self.assertEqual(cut_off["message"], "The cut-off date: never guess it.")
        self.assertNotEqual(cut_off["dates"], {"stock.csv": "2026-03-31"})
        self.assertNotEqual(waiting["message"], "Checked once items.csv is.")
        self.assertEqual(fenced["approval"]["files"], 1)
        decisions = fenced["approval"]["decisions"]
        self.assertEqual(len(decisions), 2)
        self.assertNotIn(decisions[0], result["approval"]["decisions"])
        self.assertEqual([unfenced(line) for line in decisions], result["approval"]["decisions"])


class TestSessionReuse(ImportToolTestCase):
    """#34413: the same file sent again in the same chat carries on with its open session."""

    def setUp(self):
        super().setUp()
        self.file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "reuse.csv",
                "content": b"Name,City\nAcme,Pune\n",
                "is_private": 1,
            }
        ).insert()
        self.addCleanup(setattr, frappe.local, "ar_session_id", None)

    def _start(self, chat, **arguments):
        frappe.local.ar_session_id = chat
        reply = self._run("start_import_session", {"file_id": self.file_doc.name, **arguments})
        self.assertTrue(reply["success"], reply)
        return reply["result"]

    def test_the_same_file_in_the_same_chat_carries_on_with_its_session(self):
        first = self._start("chat-1")
        again = self._start("chat-1")

        self.assertEqual(again["session_id"], first["session_id"])
        self.assertTrue(again["reused"])
        self.assertEqual(frappe.db.count("FAC Import Session", {"original_file": self.file_doc.name}), 1)

    def test_the_target_a_second_call_names_is_kept(self):
        # #34541: a session opened without a target, carried on with by a call that names one,
        # kept no target
        first = self._start("chat-1")
        again = self._start("chat-1", target_doctype="Customer")

        self.assertEqual(again["session_id"], first["session_id"])
        self.assertEqual(
            frappe.db.get_value("FAC Import Session", first["session_id"], "target_doctype"), "Customer"
        )

    def test_another_chat_or_another_import_opens_its_own(self):
        first = self._start("chat-1")

        self.assertNotEqual(self._start("chat-2")["session_id"], first["session_id"])
        update = self._start("chat-1", import_type="Update Existing Records")
        self.assertNotEqual(update["session_id"], first["session_id"])
        self.assertNotIn("reused", update)

    def test_outside_fac_chat_each_call_opens_its_own(self):
        self.assertNotEqual(self._start(None)["session_id"], self._start(None)["session_id"])


class TestThirdReview(unittest.TestCase):
    """Paul's third review of 49da112 (#34541): the small defects with no database to set up."""

    def test_a_western_european_csv_is_read_as_windows_1252(self):
        from frappe_assistant_core.utils.import_session import decode_csv

        western = "Crème brûlée,Señor,£5\n"
        central = "Łódź,Gdańsk,Žižkov\n"
        self.assertEqual(decode_csv(western.encode("cp1252")), western)  # was "Crčme brűlée,Seńor,Ł5"
        self.assertEqual(decode_csv(central.encode("cp1250")), central)

    def test_rounding_is_at_most_one_unit_of_the_currency(self):
        from frappe_assistant_core.utils.import_opening_stock import rounding_allowed

        self.assertEqual([rounding_allowed(p) for p in (0, 2, 3)], [1, 1.0, 0.1])  # 0 decimals: was 100

    def test_a_refusal_groups_short_values_where_quoted_and_never_masks_a_doctype(self):
        from frappe_assistant_core.utils.import_dry_run import QUOTED, message_pattern

        text, found = message_pattern("Value 'xy' isn't allowed for Customer Type", ["xy", "Customer"])
        self.assertEqual((text, found), (f"Value '{QUOTED}' isn't allowed for Customer Type", ["xy"]))
        # a short value the message doesn't quote is a part of other words, not the value
        self.assertEqual(message_pattern("A row is in ERPNext", ["in"]), ("A row is in ERPNext", []))

    def test_an_invoice_files_parties_are_looked_up_once(self):
        from frappe_assistant_core.utils import import_opening_invoices

        frappe.local.fac_found_parties = None
        with patch.object(
            import_opening_invoices, "find_party", return_value=frappe._dict(name="Acme")
        ) as find:
            for _ in range(3):
                import_opening_invoices._found_party("Customer", "acme")
        self.assertEqual(find.call_count, 1)
        frappe.local.fac_found_parties = None
