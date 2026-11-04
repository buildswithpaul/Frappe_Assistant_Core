# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
dry_run_import (#33990): every row checked exactly as Data Import would import it,
nothing written, failures grouped by cause.

Customer is the target because it carries every kind of failure the story names: a Link
(Customer Group), a Select (Customer Type), a required, naming field (Customer Name) and a
controller rule the import preview never runs ("Cannot select a Group type Customer
Group", raised for a group node such as All Customer Groups). The row names that group itself:
left empty, it took Selling Settings' default group, which a site may not have (fac16 doesn't).
"""

import hashlib
import json
import os
import threading
import unittest
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.core.doctype.data_import.importer import INSERT, Importer

from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils import import_dry_run

TEST_SAVEPOINT = "fac_dry_run_test"
GROUP = "FAC Dry Run Group"
GROUP_NODE = "All Customer Groups"  # a group: a Customer can't be in it
MAPPING = {
    "Customer Name": "customer_name",
    "Customer Group": "customer_group",
    "Customer Type": "customer_type",
    "Notes": "Don't Import",
}


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
class TestDryRunImport(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.registry = get_tool_registry()
        self.track_test_files()
        self.tag = frappe.generate_hash(length=6)
        # The test transaction is rolled back once per class. Each test undoes its own rows
        # instead, so the one test that commits for real (the series lock) doesn't make the
        # rows of the tests before it permanent.
        frappe.db.savepoint(TEST_SAVEPOINT)
        # A misspelt group of this test's own: one test creates it to show a fix.
        self.typo = f"Retial {self.tag}"
        self.made_group = not frappe.db.exists("Customer Group", GROUP)
        if self.made_group:
            frappe.get_doc(
                {
                    "doctype": "Customer Group",
                    "customer_group_name": GROUP,
                    "parent_customer_group": "All Customer Groups",
                    "is_group": 0,
                }
            ).insert()
        self.existing = f"Existing {self.tag}"
        self.name_customers_by("Naming Series")  # so a repeated customer name is no clash of record names
        # Named by a series, so its record name is not its customer name: keep the record name.
        self.existing_record = (
            frappe.get_doc({"doctype": "Customer", "customer_name": self.existing, "customer_group": GROUP})
            .insert()
            .name
        )

    def tearDown(self):
        frappe.set_user("Administrator")
        self.delete_test_files()
        try:
            frappe.db.rollback(save_point=TEST_SAVEPOINT)
        except Exception as e:
            # A real commit (the series lock test's) ends every savepoint; it cleans up its own.
            if "SAVEPOINT" not in str(e).upper():
                raise
        super().tearDown()

    # -- helpers -----------------------------------------------------------------------

    def _run(self, tool_name, arguments):
        return self.registry.get_tool(tool_name)._safe_execute(arguments)

    def _csv(self, rows):
        lines = ["Customer Name,Customer Group,Customer Type,Notes"]
        lines += [",".join(row) for row in rows]
        return ("\n".join(lines) + "\n").encode()

    def _session(self, rows, mapping=MAPPING):
        """Upload a CSV, open its session and map it, as the earlier steps do."""
        file_doc = frappe.get_doc(
            {"doctype": "File", "file_name": "customers.csv", "content": self._csv(rows), "is_private": 1}
        ).insert()
        started = self._run("start_import_session", {"file_url": file_doc.file_url})
        self.assertTrue(started["success"], started)
        session = started["result"]["session_id"]
        mapped = self._run(
            "set_column_mapping", {"session": session, "mapping": mapping, "doctype": "Customer"}
        )
        self.assertTrue(mapped["success"], mapped)
        return session

    def _check(self, session, **arguments):
        response = self._run("dry_run_import", {"session": session, **arguments})
        self.assertTrue(response["success"], response)
        return response["result"]

    def _check_fails(self, session, expected_text, **arguments):
        response = self._run("dry_run_import", {"session": session, **arguments})
        self.assertFalse(response["success"], response)
        self.assertIn(expected_text, response["error"])
        return response

    def _mixed_rows(self):
        t = self.tag
        return [
            [f"Alpha {t}", GROUP, "Company", "fine"],  # row 2: ready
            [f"Beta {t}", self.typo, "Company", ""],  # row 3: missing link
            [f"Gamma {t}", self.typo, "Company", ""],  # row 4: missing link, same group
            [f"Delta {t}", GROUP_NODE, "Company", ""],  # row 5: controller rule
            [f"Alpha {t}", GROUP, "Company", ""],  # row 6: shares its name with row 2: allowed, ready
            [self.existing, GROUP, "Company", ""],  # row 7: shares its name with a customer in ERPNext: ready
            [f"Eps {t}", GROUP, "Robot", ""],  # row 8: not an allowed option
        ]

    @staticmethod
    def _group(result, cause):
        return next(g for g in result["groups"] if g["cause"] == cause)

    @staticmethod
    def _stored(session):
        """The check's full result, as the session keeps it: every group with all its rows."""
        url = frappe.db.get_value("FAC Import Session", session, "validation_results")
        return json.loads(frappe.get_doc("File", {"file_url": url}).get_content())

    # -- what a check must not leave behind -------------------------------------------

    def test_a_row_with_no_customer_name_is_its_own_group(self):
        # #34537, live: ERPNext names a Customer by its name and strips it before Frappe says it is
        # required, so a blank-name row came back as "'NoneType' object has no attribute 'strip'"
        session = self._session([[f"Named {self.tag}", GROUP, "Company", ""], ["", GROUP, "Company", "end"]])

        result = self._check(session)

        groups = {g["cause"]: g for g in result["groups"]}
        self.assertIn(import_dry_run.CAUSE_REQUIRED_MISSING, groups, result["groups"])
        group = groups[import_dry_run.CAUSE_REQUIRED_MISSING]
        self.assertEqual(group["count"], 1)
        self.assertIn("Customer Name", group["explanation"])
        self.assertEqual([fix["action"] for fix in group["fixes"]], ["leave_out"])
        self.assertNotIn("NoneType", frappe.as_json(result))

    def test_an_internal_error_is_told_plainly_and_logged(self):
        # #34537: a refusal never shows a Python exception's class or text; the server log has it
        try:
            None.strip()
        except AttributeError as e:
            with patch.object(import_dry_run.frappe, "logger") as logger:
                kind, message = import_dry_run.refusal(e)

        self.assertNotIn("AttributeError", kind + message)
        self.assertNotIn("NoneType", message)
        logger.return_value.error.assert_called_once()

    def test_an_internal_error_reaches_the_error_log_once(self):
        # #34417: the server log alone is out of an administrator's sight; the Error Log is written
        # once the check is done, outside the rows' savepoints, and only once per error
        title = import_dry_run.INTERNAL_ERROR_TITLE
        frappe.local.fac_logged_errors = {}  # this request's errors so far: another test's are not this one's
        before = frappe.db.count("Error Log", {"method": title})
        for _row in range(2):
            try:
                {}["no such key"]
            except KeyError as e:
                import_dry_run.refusal(e)
        import_dry_run.log_internal_errors()
        import_dry_run.log_internal_errors()

        self.assertEqual(frappe.db.count("Error Log", {"method": title}), before + 1)

    def test_a_check_adds_nothing_to_global_search(self):
        # Saving a Customer queues its search entry in Redis, which no rollback undoes.
        session = self._session([[f"Alpha {self.tag}", GROUP, "Company", ""]])
        setting = frappe.local.conf.get("disable_global_search")

        with patch("frappe.utils.global_search.sync_value_in_queue", autospec=True) as queued:
            result = self._check(session)

        self.assertEqual(result["ready"], 1, result)
        # The check's own results file is kept, so its entry is right; the rows' are not.
        queued_doctypes = [call.args[0]["doctype"] for call in queued.call_args_list]
        self.assertNotIn("Customer", queued_doctypes)
        self.assertEqual(frappe.local.conf.get("disable_global_search"), setting)

    def test_the_rollback_work_a_row_registers_runs_after_its_rollback(self):
        # A row's save registers work for a rollback, e.g. File.handle_is_private_changed moving
        # the file back; a rollback to a savepoint doesn't run it, so the check must.
        ran = []
        frappe.db.after_rollback.add(lambda: ran.append("before the check"))
        before = list(frappe.db.after_rollback._functions)

        with import_dry_run.held_back():
            frappe.db.savepoint("fac_test_held_back")
            frappe.db.after_rollback.add(lambda: ran.append("the row's"))
            frappe.db.rollback(save_point="fac_test_held_back")

        self.assertEqual(ran, ["the row's"])
        self.assertEqual(list(frappe.db.after_rollback._functions), before)
        frappe.db.after_rollback._functions.clear()

    def test_doctypes_whose_save_reaches_past_the_database_are_not_checked(self):
        # A File's save can move it on disk; a Website Theme's deletes and writes its CSS files.
        for doctype in ("File", "Website Theme"):
            self.assertTrue(import_dry_run.unsafe_reason(doctype), doctype)

    # -- registration ------------------------------------------------------------------

    def test_tool_is_registered_and_raises_no_approval_card(self):
        from frappe_assistant_core.plugins.migration.plugin import MigrationPlugin
        from frappe_assistant_core.utils.tool_category_detector import detect_tool_category

        self.assertIn("dry_run_import", MigrationPlugin().get_tools())
        self.assertEqual(detect_tool_category(self.registry.get_tool("dry_run_import")), "read_only")

    # -- criterion 1 and 2: every row checked, grouped summary, nothing written ------------

    def test_every_row_is_checked_and_failures_are_grouped_by_cause(self):
        session = self._session(self._mixed_rows())

        result = self._check(session)

        self.assertEqual((result["total_rows"], result["ready"], result["failed"]), (7, 3, 4))
        self.assertEqual(result["message"], "3 rows ready, 4 would fail. Nothing was written.")
        link = self._group(result, "Missing link")
        self.assertEqual((link["field"], link["value"], link["count"]), ("customer_group", self.typo, 2))
        self.assertEqual([e["row"] for e in link["examples"]], [3, 4])
        self.assertEqual(self._group(result, "Not an allowed option")["value"], "Robot")

    def test_controller_rules_the_preview_misses_are_caught(self):
        session = self._session(self._mixed_rows())

        rejected = self._group(self._check(session), "Rejected by ERPNext")

        self.assertEqual(rejected["error"], "ValidationError")
        self.assertIn("Group type Customer Group", rejected["message"])
        self.assertEqual([e["row"] for e in rejected["examples"]], [5])

    def test_nothing_is_written(self):
        # Counting rows afterwards proves nothing when the insert never ran (it stayed green while
        # every insert crashed on Frappe 16.52): the ready row's real insert is watched as well.
        from frappe.model.document import Document

        session = self._session(self._mixed_rows())
        doctypes = ("Customer", "Contact", "Email Queue", "Version")
        before = {dt: frappe.db.count(dt) for dt in doctypes}
        queued = self._queue_lengths()
        private = self._private_files()
        files = self.new_files()
        inserted, real_db_insert = [], Document.db_insert

        def db_insert(doc, *args, **kwargs):
            result = real_db_insert(doc, *args, **kwargs)  # past this line the row is in the table
            inserted.append((doc.doctype, doc.get("customer_name")))
            return result

        with patch.object(Document, "db_insert", db_insert):
            result = self._check(session)

        # The rows with nothing wrong reached the insert, and only they did.
        self.assertEqual(result["ready"], 3, result)
        self.assertEqual(
            [i for i in inserted if i[0] == "Customer"],
            [("Customer", name) for name in (f"Alpha {self.tag}", f"Alpha {self.tag}", self.existing)],
        )
        # ... and it left nothing behind: not in a table, not on the queue, not on disk.
        self.assertEqual({dt: frappe.db.count(dt) for dt in doctypes}, before)
        self.assertFalse(frappe.db.exists("Customer", {"customer_name": f"Alpha {self.tag}"}))
        self.assertEqual(frappe.db.count("Customer", {"customer_name": self.existing}), 1)
        self.assertEqual(self._queue_lengths(), queued)
        # The only File is the check's own result, attached to the session.
        new_files = self.new_files() - files
        url = frappe.db.get_value("FAC Import Session", session, "validation_results")
        results = frappe.get_doc("File", {"file_url": url})
        self.assertEqual(new_files, {results.name})
        self.assertEqual(
            (results.attached_to_doctype, results.attached_to_name), ("FAC Import Session", session)
        )
        self.assertEqual(self._private_files() - private, {os.path.basename(results.file_url)})

    def _run_job(self, session):
        """What the queue runs. The job commits when it is done, as a worker's job must: the
        commit is held here, so a test's rows never stay in the site's database (#34412)."""
        with patch.object(frappe.db.__class__, "commit", autospec=True) as commit:
            import_dry_run.run_job(session, "Administrator")
        commit.assert_called()  # the job did reach its commit: it is the patch that held it

    @staticmethod
    def _queue_lengths():
        from frappe.utils.background_jobs import get_queue

        return {name: get_queue(name).count for name in ("short", "default", "long")}

    @staticmethod
    def _private_files():
        folder = frappe.get_site_path("private", "files")
        return set(os.listdir(folder)) if os.path.isdir(folder) else set()

    def test_a_group_shows_at_most_three_example_rows(self):
        rows = [[f"Row {i} {self.tag}", self.typo, "Company", ""] for i in range(5)]
        session = self._session(rows)

        link = self._group(self._check(session), "Missing link")

        self.assertEqual(link["count"], 5)
        self.assertEqual(len(link["examples"]), 3)
        self.assertEqual(link["examples"][0]["values"]["Customer Group"], self.typo)
        self.assertNotIn("Notes", link["examples"][0]["values"])  # not imported, not shown

    # -- criterion 3: duplicates are their own groups ---------------------------------------

    def test_customers_sharing_a_name_are_no_duplicates(self):
        # Customer is named by its naming series: rows 6 and 7 repeat a name, and are no failure (#34398)
        session = self._session(self._mixed_rows())

        result = self._check(session)

        self.assertNotIn("Duplicate in the file", [g["cause"] for g in result["groups"]])
        self.assertNotIn("Already in ERPNext", [g["cause"] for g in result["groups"]])
        self.assertIsNone(result["duplicate_key"])

    def test_a_duplicate_is_found_beside_its_first_rows_other_problem(self):
        # The first row's own problem (a Customer Type typo) must not hide the duplicate below it:
        # found only after the typo is fixed, it would be a second round of questions. The key is a
        # unique field here, Represents Company.
        t, company = self.tag, self._company()
        session = self._unique_session(
            [[f"Ravi {t}", "Compnay", company], [f"Ravi2 {t}", "Company", company]]
        )

        result = self._check(session)

        in_file = self._group(result, "Duplicate in the file")
        self.assertEqual([e["row"] for e in in_file["examples"]], [3])

    # -- #34398: only a record's name or a unique field is a duplicate key ---------------------

    def _other_session(self, doctype, header, rows, mapping):
        """A session for another DocType, with a one-column or wider CSV."""
        content = ("\n".join([",".join(header)] + [",".join(row) for row in rows]) + "\n").encode()
        file_doc = frappe.get_doc(
            {"doctype": "File", "file_name": "records.csv", "content": content, "is_private": 1}
        ).insert()
        started = self._run("start_import_session", {"file_url": file_doc.file_url})
        self.assertTrue(started["success"], started)
        session = started["result"]["session_id"]
        mapped = self._run("set_column_mapping", {"session": session, "mapping": mapping, "doctype": doctype})
        self.assertTrue(mapped["success"], mapped)
        return session

    @staticmethod
    def _company():
        return frappe.get_all("Company", pluck="name", limit=1)[0]

    def _unique_session(self, rows):
        """Customers with a Represents Company column, a field marked unique: rows are
        [name, type, company]."""
        return self._other_session(
            "Customer",
            ["Customer Name", "Customer Group", "Customer Type", "Represents Company"],
            [[name, GROUP, kind, company] for name, kind, company in rows],
            {
                "Customer Name": "customer_name",
                "Customer Group": "customer_group",
                "Customer Type": "customer_type",
                "Represents Company": "represents_company",
            },
        )

    def test_customers_sharing_a_name_are_all_ready_with_a_warning(self):
        # Customer is named by its naming series here, so its name is no key: two customers may
        # share a customer_name, in the file and with one already in ERPNext.
        t = self.tag
        session = self._session(
            [
                [f"Shared {t}", GROUP, "Company", ""],  # row 2
                [f"Shared {t}", GROUP, "Company", ""],  # row 3: same name as row 2
                [self.existing, GROUP, "Company", ""],  # row 4: same name as a record in ERPNext
                [f"Other {t}", GROUP, "Company", ""],  # row 5
            ]
        )

        result = self._check(session)

        self.assertEqual((result["ready"], result["failed"], result["groups"]), (4, 0, []), result)
        self.assertIsNone(result["duplicate_key"])
        (warning,) = result["warnings"]
        self.assertEqual(
            (warning["cause"], warning["field"], warning["count"], warning["example_rows"]),
            ("Shared value", "customer_name", 2, [3, 4]),
        )
        self.assertIn("2", warning["message"])
        self.assertIn("Customer Name", warning["message"])
        # The session keeps it with the summary, and the rows stay ready.
        stored = self._stored(session)
        self.assertEqual(stored["summary"]["warnings"], result["warnings"])
        self.assertEqual({r["status"] for r in stored["rows"]}, {"ready"})
        self.assertEqual(frappe.db.get_value("FAC Import Session", session, "status"), "Ready to Import")

    def test_a_name_that_is_the_records_name_is_refused_by_erpnext(self):
        # Named by its customer name, a Customer's name is the field: ERPNext's own insert, which
        # the check runs, refuses a second one. (setUp named customers by series.)
        self.name_customers_by("Customer Name")
        frappe.get_doc(
            {"doctype": "Customer", "customer_name": f"Named {self.tag}", "customer_group": GROUP}
        ).insert()
        session = self._session([[f"Named {self.tag}", GROUP, "Company", ""]])

        result = self._check(session)

        self.assertEqual((result["ready"], result["failed"]), (0, 1), result)
        self.assertEqual(self._group(result, "Rejected by ERPNext")["error"], "DuplicateEntryError")

    def test_a_name_repeated_in_the_file_fails_where_customers_are_named_by_it(self):
        # On a default site a Customer is named by its customer name: the import would refuse the
        # second "Shared", though the check, rolling each row back, never sees the first (#34398).
        self.name_customers_by("Customer Name")
        t = self.tag
        session = self._session(
            [
                [f"Shared {t}", GROUP, "Company", ""],  # row 2
                [f"shared {t}", GROUP, "Company", ""],  # row 3: the same name to MariaDB
                [f"Other {t}", GROUP, "Company", ""],  # row 4
            ]
        )

        result = self._check(session)

        self.assertEqual((result["ready"], result["failed"]), (2, 1), result)
        group = self._group(result, "Duplicate in the file")
        self.assertEqual((group["field"], [e["row"] for e in group["examples"]]), ("customer_name", [3]))
        self.assertEqual(result.get("warnings") or [], [])

    def test_no_warning_when_no_name_is_shared(self):
        session = self._session([[f"One {self.tag}", GROUP, "Company", ""]])

        result = self._check(session)

        self.assertEqual(result["ready"], 1, result)
        self.assertEqual(result["warnings"], [])

    def test_a_repeated_record_name_is_still_a_duplicate(self):
        # Brand is named by its own field: that field is the record's name, so a repeat is a real
        # duplicate, and so is a name already in ERPNext.
        t = self.tag
        frappe.get_doc({"doctype": "Brand", "brand": f"Old {t}"}).insert()
        session = self._other_session(
            "Brand",
            ["Brand"],
            [[f"New {t}"], [f"New {t}"], [f"Old {t}"]],
            {"Brand": "brand"},
        )

        result = self._check(session)

        self.assertEqual(result["duplicate_key"], "brand")
        self.assertEqual((result["ready"], result["failed"]), (1, 2), result)
        in_file = self._group(result, "Duplicate in the file")
        self.assertEqual(([e["row"] for e in in_file["examples"]], in_file["field"]), ([3], "brand"))
        existing = self._group(result, "Already in ERPNext")
        self.assertEqual([e["row"] for e in existing["examples"]], [4])
        self.assertEqual(result["warnings"], [])

    def test_a_repeated_value_of_a_unique_field_is_still_a_duplicate(self):
        # Customer.represents_company is marked unique: it is the key, whatever the title field is.
        t, company = self.tag, self._company()
        session = self._unique_session(
            [[f"Int A {t}", "Company", company], [f"Int B {t}", "Company", company]]
        )

        result = self._check(session)

        self.assertEqual(result["duplicate_key"], "represents_company")
        in_file = self._group(result, "Duplicate in the file")
        self.assertEqual(
            ([e["row"] for e in in_file["examples"]], in_file["field"]), ([3], "represents_company")
        )

    # -- the session holds the result ----------------------------------------------------------

    def test_the_session_holds_the_summary_the_full_list_and_a_step(self):
        session = self._session(self._mixed_rows())

        self._check(session)

        doc = frappe.get_doc("FAC Import Session", session)
        self.assertEqual(doc.status, "Dry Run Failed")
        summary = json.loads(doc.validation_summary)
        self.assertEqual((summary["ready"], summary["failed"]), (3, 4))
        results = frappe.get_doc("File", {"file_url": doc.validation_results})
        self.assertTrue(results.is_private)
        self.assertEqual(
            (results.attached_to_doctype, results.attached_to_name), ("FAC Import Session", session)
        )
        per_row = {r["row"]: r["status"] for r in json.loads(results.get_content())["rows"]}
        self.assertEqual(
            per_row,
            {2: "ready", 3: "failed", 4: "failed", 5: "failed", 6: "ready", 7: "ready", 8: "failed"},
        )
        step = doc.steps[-1]
        self.assertEqual(
            (step.step, step.outcome, step.rows_ok, step.rows_failed), ("Dry Run", "Warning", 3, 4)
        )
        self.assertTrue(doc.validated_fingerprint)

    def test_a_clean_file_is_ready_to_import(self):
        session = self._session([[f"Clean {self.tag}", GROUP, "Company", ""]])

        result = self._check(session)

        self.assertEqual((result["ready"], result["failed"], result["status"]), (1, 0, "Ready to Import"))
        self.assertEqual(frappe.get_doc("FAC Import Session", session).steps[-1].outcome, "Success")

    def test_the_session_keeps_no_row_of_the_file(self):
        session = self._session(self._mixed_rows())

        self._check(session)

        stored = frappe.as_json(frappe.get_doc("FAC Import Session", session).as_dict())
        self.assertNotIn(f"Beta {self.tag}", stored)

    # -- criterion 5: checking again reports only what still fails ------------------------------

    def test_checking_again_after_a_fix_reports_only_remaining_failures(self):
        session = self._session(self._mixed_rows())
        self._check(session)
        frappe.get_doc(
            {
                "doctype": "Customer Group",
                "customer_group_name": self.typo,
                "parent_customer_group": "All Customer Groups",
            }
        ).insert()

        result = self._check(session)

        self.assertEqual((result["ready"], result["failed"]), (5, 2))
        self.assertNotIn("Missing link", [g["cause"] for g in result["groups"]])
        self.assertEqual(result["previous"], {"failed": 4, "fixed": 2})
        attached = frappe.get_all(
            "File",
            filters={
                "attached_to_doctype": "FAC Import Session",
                "attached_to_name": session,
                "attached_to_field": "validation_results",  # beside the session's copy (#34405)
            },
        )
        self.assertEqual(len(attached), 1)  # the old result file is replaced, not kept

    def test_rows_left_out_are_not_checked(self):
        session = self._session(self._mixed_rows())
        frappe.db.set_value("FAC Import Session", session, "excluded_rows", json.dumps([3, 4]))

        result = self._check(session)

        self.assertEqual((result["ready"], result["failed"], result["excluded"]), (3, 2, 2))

    # -- references between rows of the same file ---------------------------------------------

    def test_a_tree_row_whose_parent_is_an_earlier_row_of_the_file_is_ready(self):
        # The import inserts row 2 before row 3, so row 3's parent exists by then. The check
        # rolls each row back, and must not report the parent as missing.
        parent, child = f"Parent {self.tag}", f"Child {self.tag}"
        content = (
            "Item Group Name,Parent Item Group,Is Group\n"
            f"{parent},All Item Groups,1\n"  # row 2
            f"{child},{parent},0\n"  # row 3: its parent is row 2
        ).encode()
        file_doc = frappe.get_doc(
            {"doctype": "File", "file_name": "item_groups.csv", "content": content, "is_private": 1}
        ).insert()
        started = self._run("start_import_session", {"file_url": file_doc.file_url})
        self.assertTrue(started["success"], started)
        session = started["result"]["session_id"]
        mapping = {
            "Item Group Name": "item_group_name",
            "Parent Item Group": "parent_item_group",
            "Is Group": "is_group",
        }
        mapped = self._run(
            "set_column_mapping", {"session": session, "mapping": mapping, "doctype": "Item Group"}
        )
        self.assertTrue(mapped["success"], mapped)

        result = self._check(session)

        self.assertEqual((result["ready"], result["failed"]), (2, 0), result.get("groups"))

    def _account_session(self, rows):
        """A session of an Account file (name, parent, company, is group), mapped."""
        lines = ["Account Name,Parent Account,Company,Is Group", *(",".join(row) for row in rows)]
        content = "\n".join(lines) + "\n"
        file_doc = frappe.get_doc(
            {"doctype": "File", "file_name": "accounts.csv", "content": content.encode(), "is_private": 1}
        ).insert()
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]
        mapping = {
            "Account Name": "account_name",
            "Parent Account": "parent_account",
            "Company": "company",
            "Is Group": "is_group",
        }
        mapped = self._run(
            "set_column_mapping", {"session": session, "mapping": mapping, "doctype": "Account"}
        )
        self.assertTrue(mapped["success"], mapped)
        return session

    def _company_and_root(self):
        company = frappe.get_all("Company", pluck="name", order_by="creation", limit=1)[0]
        root = frappe.db.get_value(
            "Account", {"company": company, "root_type": "Asset", "is_group": 1}, order_by="lft"
        )
        return company, root

    # Frappe 16's Data Import takes a tree's parent by its title (an Account's name without the
    # company's abbreviation); Frappe 15's refuses it as a missing link. The check says what each does.
    RESOLVES_TITLES = hasattr(Importer, "_resolve_tree_parent_link")

    def test_an_account_naming_its_parent_by_account_name_from_an_earlier_row_is_ready(self):
        t = self.tag
        company, root = self._company_and_root()
        session = self._account_session(
            [
                [f"Group {t}", root, company, "1"],  # row 2
                [f"Leaf {t}", f"Group {t}", company, "0"],  # row 3: row 2 by its account name
                [f"Orphan {t}", f"No Such {t}", company, "1"],  # row 4: its parent doesn't exist
                [f"Under Orphan {t}", f"Orphan {t}", company, "0"],  # row 5: its parent row fails
            ]
        )

        self._check(session)

        stored = self._stored(session)
        rows = {r["row"]: r for r in stored["rows"]}
        leaf = "ready" if self.RESOLVES_TITLES else "failed"
        self.assertEqual(
            {n: r["status"] for n, r in rows.items()},
            {2: "ready", 3: leaf, 4: "failed", 5: "failed"},
            stored["groups"],
        )
        missing = {g["value"] for g in stored["groups"] if g["cause"] == "Missing link"}
        if self.RESOLVES_TITLES:
            self.assertEqual(rows[3]["after"], [2])  # imported once row 2 is
            self.assertEqual(missing, {f"No Such {t}", f"Orphan {t}"})
        else:
            self.assertEqual(missing, {f"No Such {t}", f"Orphan {t}", f"Group {t}"})
        self.assertFalse(frappe.db.exists("Account", {"account_name": f"Group {t}"}))

    def test_an_account_naming_an_existing_parent_by_account_name_is_ready(self):
        t = self.tag
        company, root = self._company_and_root()
        frappe.get_doc(
            {
                "doctype": "Account",
                "account_name": f"Existing Group {t}",
                "parent_account": root,
                "company": company,
                "is_group": 1,
            }
        ).insert()
        session = self._account_session([[f"Leaf {t}", f"Existing Group {t}", company, "0"]])

        result = self._check(session)

        if self.RESOLVES_TITLES:
            self.assertEqual((result["ready"], result["failed"]), (1, 0), result["groups"])
        else:
            self.assertEqual(
                [(g["cause"], g["value"]) for g in result["groups"]],
                [("Missing link", f"Existing Group {t}")],
            )

    # -- #34395: rows go through Frappe's own importer, its warnings become groups ----------------

    def test_each_row_is_tried_through_frappes_own_process_doc(self):
        t = self.tag
        session = self._session(
            [
                [f"Alpha {t}", GROUP, "Company", ""],  # row 2: tried, ready
                [f"Beta {t}", GROUP, "Company", ""],  # row 3: tried, ready
                [f"Delta {t}", GROUP_NODE, "Company", ""],  # row 4: tried, refused by the controller
                [f"Gamma {t}", self.typo, "Company", ""],  # row 5: a missing link, never tried
            ]
        )
        frappe.db.set_value("FAC Import Session", session, "submit_after_import", 1)

        real = Importer.process_doc
        with patch.object(Importer, "process_doc", autospec=True, side_effect=real) as tried:
            result = self._check(session)

        self.assertEqual((result["ready"], result["failed"]), (2, 2), result["groups"])
        self.assertEqual(tried.call_count, 3)
        names = [call.args[1].get("customer_name") for call in tried.call_args_list]
        self.assertEqual(names, [f"Alpha {t}", f"Beta {t}", f"Delta {t}"])
        importer = tried.call_args.args[0]
        self.assertIsInstance(importer, Importer)
        self.assertEqual(importer.data_import.doctype, "Data Import")
        self.assertTrue(importer.data_import.is_new())  # never saved
        data_import = importer.data_import
        self.assertEqual((data_import.import_type, data_import.submit_after_import), (INSERT, 1))

    def test_a_bad_link_value_is_its_own_group_with_every_row(self):
        # Frappe 16 reports a bad link once for its column, listing six rows; each value is still
        # a group of its own, with all its rows.
        t, other = self.tag, f"Whole {self.tag}"
        rows = [[f"Clean {t}", GROUP, "Company", ""]]  # row 2
        rows += [[f"A{i} {t}", self.typo, "Company", ""] for i in range(7)]  # rows 3-9
        rows += [[f"B{i} {t}", other, "Company", ""] for i in range(2)]  # rows 10-11
        session = self._session(rows)

        result = self._check(session)

        self.assertEqual((result["ready"], result["failed"]), (1, 9))
        groups = sorted(self._stored(session)["groups"], key=lambda g: -g["count"])
        self.assertEqual(
            [(g["cause"], g["parent"], g["field"], g["value"], g["count"], g["rows"]) for g in groups],
            [
                ("Missing link", "Customer", "customer_group", self.typo, 7, list(range(3, 10))),
                ("Missing link", "Customer", "customer_group", other, 2, [10, 11]),
            ],
        )
        for group, value in zip(groups, (self.typo, other)):
            self.assertEqual(group["message"], f"Customer Group '{value}' doesn't exist.")
            key = json.dumps(["Missing link", "Customer", "customer_group", value])
            self.assertEqual(group["id"], "G" + hashlib.sha256(key.encode()).hexdigest()[:6])

    def test_a_bad_select_value_is_its_own_group_with_every_row(self):
        t = self.tag
        session = self._session(
            [
                [f"Alpha {t}", GROUP, "Company", ""],  # row 2
                [f"Beta {t}", GROUP, "Pvt Ltd", ""],  # row 3
                [f"Gamma {t}", GROUP, "Company", ""],  # row 4
                [f"Delta {t}", GROUP, "Pvt Ltd", ""],  # row 5
            ]
        )

        result = self._check(session)

        self.assertEqual((result["ready"], result["failed"]), (2, 2))
        groups = self._stored(session)["groups"]
        self.assertEqual(
            [(g["cause"], g["field"], g["value"], g["message"], g["rows"]) for g in groups],
            [
                (
                    "Not an allowed option",
                    "customer_type",
                    "Pvt Ltd",
                    "'Pvt Ltd' isn't one of the options for Customer Type.",
                    [3, 5],
                )
            ],
        )

    def test_a_bad_value_only_on_rows_left_out_makes_no_group(self):
        t = self.tag
        session = self._session(
            [
                [f"Alpha {t}", GROUP, "Company", ""],  # row 2
                [f"Beta {t}", self.typo, "Company", ""],  # row 3: left out
                [f"Gamma {t}", GROUP, "Robot", ""],  # row 4: left out
            ]
        )
        frappe.db.set_value("FAC Import Session", session, "excluded_rows", json.dumps([3, 4]))

        result = self._check(session)

        self.assertEqual((result["ready"], result["failed"], result["excluded"]), (1, 0, 2))
        self.assertEqual((result["groups"], result["status"]), ([], "Ready to Import"))

    def _provider(self):
        """The class of Customer's import provider (Frappe 16: ERPNext's PartyImportProvider)."""
        try:
            from frappe.core.doctype.data_import.import_provider import get_import_provider
        except ImportError:
            self.skipTest("this Frappe has no import providers (data_import_providers came with Frappe 16)")
        provider = get_import_provider("Customer")
        if not provider:
            self.skipTest("no import provider is registered for Customer on this site")
        return type(provider)

    def test_a_registered_import_provider_imports_the_row(self):
        provider = self._provider()
        t = self.tag
        session = self._session([[f"Alpha {t}", GROUP, "Company", ""], [f"Beta {t}", GROUP, "Company", ""]])

        real = provider.import_row
        with patch.object(provider, "import_row", autospec=True, side_effect=real) as imported:
            result = self._check(session)

        self.assertEqual((result["ready"], result["failed"]), (2, 0), result["groups"])
        self.assertEqual(imported.call_count, 2)

        # The provider's error is ERPNext refusing the row.
        refused = frappe.ValidationError("The provider refused it")
        with patch.object(provider, "import_row", autospec=True, side_effect=refused):
            result = self._check(session)

        rejected = self._group(result, "Rejected by ERPNext")
        self.assertEqual((rejected["count"], rejected["message"]), (2, "The provider refused it"))

    def test_an_import_providers_warning_is_a_group(self):
        provider = self._provider()
        t = self.tag
        session = self._session(
            [[f"{n} {t}", GROUP, "Company", ""] for n in ("Alpha", "Beta", "Gamma")]  # rows 2-4
        )
        warnings = [
            {"row": 3, "message": "Beta's <b>PAN</b> is missing"},
            {"row": 4, "message": "Just so you know", "type": "info"},
        ]

        with patch.object(provider, "validate", autospec=True, return_value=warnings):
            result = self._check(session)

        self.assertEqual((result["ready"], result["failed"]), (2, 1))
        self.assertEqual(
            [(g["cause"], g["message"], g["rows"]) for g in self._stored(session)["groups"]],
            [("Invalid value", "Beta's PAN is missing", [3])],
        )

    def test_a_check_saves_no_data_import_or_log(self):
        t = self.tag
        session = self._session([[f"Alpha {t}", GROUP, "Company", ""], [f"Beta {t}", GROUP, "Company", ""]])
        doctypes = (
            "Customer",
            "Contact",
            "Address",
            "Email Queue",
            "Version",
            "Data Import",
            "Data Import Log",
        )
        before = {dt: frappe.db.count(dt) for dt in doctypes}

        result = self._check(session)

        self.assertEqual((result["ready"], result["failed"]), (2, 0), result["groups"])
        self.assertEqual({dt: frappe.db.count(dt) for dt in doctypes}, before)

    def test_a_check_leaves_the_import_flags_as_they_were(self):
        # Data Import's own setup sets them, and its end sets them to False: neither is the caller's.
        session = self._session([[f"Alpha {self.tag}", GROUP, "Company", ""]])
        saved = {name: frappe.flags.get(name) for name in ("in_import", "mute_emails")}
        frappe.flags.in_import = frappe.flags.mute_emails = None
        try:
            result = self._check(session)
            flags = (frappe.flags.in_import, frappe.flags.mute_emails)
        finally:
            frappe.flags.update(saved)

        self.assertEqual(result["ready"], 1, result["groups"])
        self.assertEqual(flags, (None, None))

    # -- criterion 4: large files run in the background -------------------------------------------

    def test_a_large_file_is_checked_in_the_background(self):
        session = self._session(self._mixed_rows())

        with patch.object(import_dry_run, "BACKGROUND_ROWS", 5), patch("frappe.enqueue") as enqueue:
            started = self._check(session)
            again = self._check(session)

        self.assertEqual((started["state"], started["total_rows"]), ("running", 7))
        self.assertEqual(again["state"], "running")
        enqueue.assert_called_once()
        self.assertEqual(enqueue.call_args.kwargs["session_name"], session)
        self.assertEqual(enqueue.call_args.args[0], "frappe_assistant_core.utils.import_dry_run.run_job")
        progress = json.loads(frappe.db.get_value("FAC Import Session", session, "progress"))
        self.assertEqual((progress["state"], progress["total"]), ("queued", 7))

        self._run_job(session)

        doc = frappe.get_doc("FAC Import Session", session)
        self.assertEqual(doc.status, "Dry Run Failed")
        self.assertEqual(json.loads(doc.progress)["state"], "done")
        self.assertEqual(json.loads(doc.validation_summary)["failed"], 4)

    # -- side effects are held back ------------------------------------------------------------------

    def test_a_server_scripts_job_is_held_back(self):
        # A Server Script's frappe.enqueue is safe_exec's own copy of enqueue
        from frappe.utils import safe_exec

        with patch.object(safe_exec, "enqueue", autospec=True) as real_enqueue:
            with import_dry_run.held_back():
                safe_exec.safe_enqueue("frappe.ping")
            real_enqueue.assert_not_called()

    def test_the_google_calendar_sync_of_a_row_is_held_back(self):
        # Frappe's doc events call Google at once when an Event is saved, not at commit
        from frappe.integrations.doctype.google_calendar import google_calendar

        with patch.object(google_calendar, "insert_event_in_google_calendar", autospec=True) as sync:
            with import_dry_run.held_back():
                frappe.db.savepoint("fac_test_google")
                frappe.get_doc(
                    {
                        "doctype": "Event",
                        "subject": "Held back",
                        "event_type": "Private",
                        "starts_on": frappe.utils.now_datetime(),
                    }
                ).insert()
                frappe.db.rollback(save_point="fac_test_google")
            sync.assert_not_called()

    # Jobs are proved on the real queue, by the tests below (a patched enqueue only proves what
    # the patch swaps, #34401).
    def test_held_back_swallows_commits_and_events_then_restores_them(self):
        frappe.db.after_commit.add(print)
        with (
            patch.object(frappe.db.__class__, "commit") as real_commit,
            patch("frappe.publish_realtime") as real_publish,
        ):
            with import_dry_run.held_back():
                self.assertTrue(frappe.flags.mute_emails and frappe.flags.in_import)
                # nosemgrep: frappe-realtime-pick-room — mocked: the test checks it is held back
                frappe.publish_realtime("x")
                # nosemgrep: frappe-manual-commit — mocked: the test checks it is held back
                frappe.db.commit()
                frappe.db.after_commit.add(len)  # a row's callback must not outlive the row

            for real in (real_commit, real_publish):
                real.assert_not_called()
            # Restored afterwards.
            # nosemgrep: frappe-manual-commit — mocked: the test checks it goes out again
            frappe.db.commit()
            real_commit.assert_called_once()

        self.assertEqual(list(frappe.db.after_commit._functions)[-1], print)
        frappe.db.after_commit._functions.pop()
        self.assertFalse(frappe.flags.in_import)

    def test_held_back_holds_back_only_its_own_request(self):
        # A web worker with threads (frappe_docker runs gunicorn --threads=4) serves other
        # requests while a small file is checked inline: their jobs and events still go out.
        with (
            patch("frappe.enqueue") as real_enqueue,
            patch("frappe.utils.background_jobs.enqueue") as real_bg_enqueue,
            patch("frappe.publish_realtime") as real_publish,
            patch("frappe.realtime.publish_realtime") as real_realtime_publish,
        ):
            with import_dry_run.held_back():
                other_request = threading.Thread(
                    target=lambda: (
                        frappe.enqueue("frappe.ping"),
                        frappe.utils.background_jobs.enqueue("frappe.ping"),
                        # nosemgrep: frappe-realtime-pick-room — mocked: another request's event
                        frappe.publish_realtime("x"),
                        frappe.realtime.publish_realtime("x"),
                    )
                )
                other_request.start()
                other_request.join()
                frappe.enqueue("frappe.ping")  # this request's own: held back

            for real in (real_enqueue, real_bg_enqueue, real_publish, real_realtime_publish):
                real.assert_called_once()

    # -- what a row's controller does while the check runs (#34401) ------------------------------------

    @contextmanager
    def _customer_controller(self, does):
        """Run ``does(doc)`` in Customer's own validate, as an app's controller does. Frappe runs a
        row through the real Importer and controller; only the extra work is added."""
        from erpnext.selling.doctype.customer.customer import Customer

        original = Customer.validate

        def validate(doc, *args, **kwargs):
            does(doc)
            return original(doc, *args, **kwargs)

        with patch.object(Customer, "validate", validate):
            yield

    @staticmethod
    def _remove_jobs(queue, jobs):
        from rq.exceptions import NoSuchJobError
        from rq.job import Job

        for job in jobs:
            try:
                Job.fetch(job.id, connection=queue.connection).delete()
            except NoSuchJobError:
                pass

    def test_a_job_enqueued_through_a_bound_import_never_reaches_the_queue(self):
        # HRMS' salary_slip and ERPNext's payment_request did `from frappe.utils.background_jobs
        # import enqueue`: they hold the function itself, so swapping the module's attribute
        # misses them. inspect.unwrap is that function, however held_back holds it back.
        import inspect

        from frappe.utils.background_jobs import get_queue
        from rq.job import Job

        bound_enqueue = inspect.unwrap(frappe.utils.background_jobs.enqueue)
        queue = get_queue("short")
        before, sent = queue.count, []
        self.addCleanup(self._remove_jobs, queue, sent)
        session = self._session([[f"Alpha {self.tag}", GROUP, "Company", ""]])

        with self._customer_controller(lambda doc: sent.append(bound_enqueue("frappe.ping", queue="short"))):
            result = self._check(session)

        self.assertEqual(result["ready"], 1, result)
        self.assertTrue(sent, "the controller didn't run")
        self.assertEqual(queue.count, before)
        # A worker may have taken a job off the queue: its record is still there.
        self.assertFalse([job.id for job in sent if Job.exists(job.id, connection=queue.connection)])

    def test_jobs_enqueued_many_at_once_or_for_later_never_reach_redis(self):
        # #34401, Paul's review of 49da112: RQ's enqueue_many and enqueue_at / enqueue_in go past
        # enqueue_job (to _enqueue_job and schedule_job), so a controller using them still queued
        import datetime

        from frappe.utils.background_jobs import get_queue
        from rq.job import Job
        from rq.registry import ScheduledJobRegistry

        queue = get_queue("short")
        scheduled = ScheduledJobRegistry(queue=queue)
        before, later, sent = queue.count, scheduled.count, []
        self.addCleanup(self._remove_jobs, queue, sent)
        session = self._session([[f"Alpha {self.tag}", GROUP, "Company", ""]])

        def enqueue(doc):
            sent.extend(queue.enqueue_many([queue.prepare_data("frappe.ping")]))
            sent.append(queue.enqueue_in(datetime.timedelta(hours=1), "frappe.ping"))

        with self._customer_controller(enqueue):
            result = self._check(session)

        self.assertEqual(result["ready"], 1, result)
        self.assertEqual(len(sent), 2, "the controller didn't run")
        self.assertEqual((queue.count, scheduled.count), (before, later))
        self.assertFalse([job.id for job in sent if Job.exists(job.id, connection=queue.connection)])

    def test_a_held_job_has_an_id_a_controller_can_read(self):
        session = self._session([[f"Alpha {self.tag}", GROUP, "Company", ""]])
        ids = []

        def read_ids(doc):
            ids.append(frappe.enqueue("frappe.ping", queue="short").id)
            ids.append(frappe.utils.background_jobs.enqueue("frappe.ping", queue="short").id)

        with self._customer_controller(read_ids):
            result = self._check(session)

        self.assertEqual((result["ready"], result["failed"]), (1, 0), result)
        self.assertTrue(ids and all(isinstance(i, str) and i for i in ids), ids)

    def test_a_controllers_full_rollback_doesnt_end_the_run(self):
        # The savepoint a row is tried in is gone after a full rollback: the check used to end
        # with "SAVEPOINT ... does not exist" instead of a result.
        session = self._session([[f"Alpha {self.tag}", GROUP, "Company", ""]])

        with self._customer_controller(lambda doc: frappe.db.rollback()):
            result = self._check(session)

        self.assertEqual((result["total_rows"], result["ready"]), (1, 1), result)

    def _series_is_free(self, prefix):
        """Whether a second database connection can lock the series row at once."""
        import pymysql

        conf = frappe.conf
        connection = pymysql.connect(
            host=conf.get("db_host") or "127.0.0.1",
            port=int(conf.get("db_port") or 3306),
            user=conf.get("db_user") or conf.db_name,
            password=conf.db_password,
            database=conf.db_name,
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET SESSION innodb_lock_wait_timeout = 1")
                try:
                    cursor.execute(
                        "SELECT `current` FROM `tabSeries` WHERE `name` = %s FOR UPDATE", (prefix,)
                    )
                except pymysql.err.OperationalError as e:
                    if e.args[0] == 1205:  # lock wait timeout
                        return False
                    raise
                return True
        finally:
            connection.rollback()
            connection.close()

    def _remove_committed(self, session, prefix, started):
        """What the series test committed for real, deleted again and committed."""
        from frappe.database.database import Database

        gone = {"force": True, "ignore_permissions": True, "delete_permanently": True}
        doc = frappe.get_doc("FAC Import Session", session)
        # its files: the upload, the session's own copy and the check's results (#34412)
        files = set(
            frappe.get_all(
                "File",
                filters={"attached_to_doctype": "FAC Import Session", "attached_to_name": session},
                pluck="name",
            )
        )
        for ref in (doc.get("original_file"), doc.get("source_file")):
            if ref:
                files.update(frappe.get_all("File", or_filters={"name": ref, "file_url": ref}, pluck="name"))
        deleted = [session, self.existing_record, *files]
        frappe.delete_doc("FAC Import Session", session, **gone)
        frappe.delete_doc("Customer", self.existing_record, **gone)
        if self.made_group:  # this test's setUp made it, and the commit made it permanent
            frappe.delete_doc("Customer Group", GROUP, **gone)
            deleted.append(GROUP)
        for name in files:
            frappe.delete_doc("File", name, **gone)
        frappe.db.delete("Series", {"name": prefix})
        # only this test's: other users' deletions in the same minutes stay (#34412)
        frappe.db.delete("Deleted Document", {"creation": (">=", started), "deleted_name": ("in", deleted)})
        # the audit rows of the tool calls this test made, which name its session
        log = frappe.qb.DocType("Assistant Audit Log")
        (
            frappe.qb.from_(log)
            .delete()
            .where(log.creation >= started)
            .where(log.input_data.like(f"%{session}%") | log.output_data.like(f"%{session}%"))
        ).run()
        Database.commit(frappe.db)

    def test_a_check_lets_go_of_the_series_it_locked_every_hundred_rows(self):
        # A controller that names its record from a series (getseries) locks the series row with
        # SELECT ... FOR UPDATE, which a savepoint rollback doesn't release. The check commits
        # every PROGRESS_EVERY rows, in every mode, to end that transaction.
        # This test commits for real (BaseAssistantTest turns commit into a no-op, and a lock is
        # only seen from a second connection once its row is committed): _remove_committed deletes
        # what it made, all of it named with this test's own tag.
        from frappe.database.database import Database
        from frappe.model.naming import getseries

        started = frappe.utils.now_datetime()
        prefix = f"FACLOCK-{self.tag}-"
        count = import_dry_run.PROGRESS_EVERY + 1
        session = self._session([[f"Row{n} {self.tag}", GROUP, "Company", ""] for n in range(count)])
        self.addCleanup(self._remove_committed, session, prefix, started)
        frappe.qb.into("Series").columns("name", "current").insert(prefix, 0).run()
        Database.commit(frappe.db)
        named, free = set(), []

        def name_from_series(doc):
            named.add(doc.customer_name)
            if len(named) == count:  # the row after the first hundred, before it takes the lock again
                free.append(self._series_is_free(prefix))
            getseries(prefix, 5)

        with (
            patch.object(frappe.db.__class__, "commit", Database.commit),
            self._customer_controller(name_from_series),
        ):
            result = self._check(session)

        self.assertEqual(result["ready"], count, result)
        self.assertEqual(free, [True], "the series row was still locked after a hundred rows")

    def test_the_series_tests_cleanup_removes_the_rows_setup_made(self):
        # setUp's customer is named by a series (CUST-.), so its record name isn't its customer
        # name: the cleanup missed it, and the commit made it and its group permanent (#34412).
        # The commit is held here only so this test's rows stay in its own transaction.
        started = frappe.utils.now_datetime()
        session = self._session([[f"Row {self.tag}", GROUP, "Company", ""]])
        self._check(session)  # its results file, and the tool calls' audit rows
        # someone else's deletion at the same time is theirs to keep (#34412)
        other = frappe.get_doc(
            {
                "doctype": "Deleted Document",
                "deleted_doctype": "ToDo",
                "deleted_name": f"Other {self.tag}",
                "data": "{}",
            }
        ).insert(ignore_permissions=True)
        with patch("frappe.database.database.Database.commit"):
            self._remove_committed(session, f"FACLOCK-{self.tag}-", started)
        self.assertFalse(frappe.db.exists("Customer", {"customer_name": self.existing}))
        if self.made_group:  # on a site that already holds the group, the test must leave it
            self.assertFalse(frappe.db.exists("Customer Group", GROUP))
        self.assertTrue(frappe.db.exists("Deleted Document", other.name))
        self.assertFalse(frappe.get_all("File", filters={"attached_to_name": session}))
        log = frappe.qb.DocType("Assistant Audit Log")
        left = frappe.qb.from_(log).select(log.name).where(log.input_data.like(f"%{session}%")).run()
        self.assertEqual(left, ())

    # -- when it can't run ---------------------------------------------------------------------------

    def test_an_unmapped_session_is_refused(self):
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "c.csv",
                "content": self._csv([["A", GROUP, "Company", ""]]),
                "is_private": 1,
            }
        ).insert()
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]

        self._check_fails(session, "Map the columns first")

    def test_a_file_only_in_the_chat_asks_for_the_file_then_continues_with_it(self):
        session = self._chat_session()

        self._check_fails(session, "Upload it in File Manager")

        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "customers.csv",
                "content": self._csv([[f"Chat {self.tag}", GROUP, "Company", ""]]),
                "is_private": 1,
            }
        ).insert()
        result = self._check(session, file_url=file_doc.file_url)
        self.assertEqual(result["ready"], 1)
        doc = frappe.get_doc("FAC Import Session", session)
        self.assertEqual((doc.file_source, doc.original_file), ("Site File", file_doc.name))

    def test_a_file_with_other_columns_is_not_linked(self):
        session = self._chat_session()
        other = frappe.get_doc(
            {"doctype": "File", "file_name": "other.csv", "content": b"Name\nX\n", "is_private": 1}
        ).insert()

        self._check_fails(session, "columns don't match", file_url=other.file_url)

        self.assertFalse(frappe.db.get_value("FAC Import Session", session, "source_file"))

    def _chat_session(self):
        """A mapped session whose file stayed in the chat. Only sessions started before #34405
        are: start_import_session now asks for such a file to be uploaded first. Made as it made
        them."""
        from frappe_assistant_core.assistant_core.doctype.fac_import_session.fac_import_session import (
            engine_write,
        )

        doc = frappe.get_doc(
            {
                "doctype": "FAC Import Session",
                "user": frappe.session.user,
                "file_name": "customers.csv",
                "file_source": "Chat Attachment",
                "sheets": frappe.as_json([{"name": None, "columns": list(MAPPING), "row_count": 1}]),
                "status": "File Read",
            }
        )
        doc.log_step("Read File", "Success", "Read 1 rows and 4 columns.", rows_ok=1)
        engine_write(doc).insert()
        mapped = self._run(
            "set_column_mapping", {"session": doc.name, "mapping": MAPPING, "doctype": "Customer"}
        )
        self.assertTrue(mapped["success"], mapped)
        return doc.name

    def _upload(self, rows):
        return frappe.get_doc(
            {"doctype": "File", "file_name": "customers.csv", "content": self._csv(rows), "is_private": 1}
        ).insert()

    def test_the_file_uploaded_in_file_manager_is_given_by_its_id(self):
        session = self._chat_session()
        file_doc = self._upload([[f"Manager {self.tag}", GROUP, "Company", ""]])

        result = self._check(session, file_id=file_doc.name)

        self.assertEqual(result["ready"], 1)
        self.assertEqual(frappe.db.get_value("FAC Import Session", session, "original_file"), file_doc.name)

    def test_a_file_the_user_cannot_read_is_not_linked_by_its_id(self):
        user = self.make_throwaway_user("clerk", roles=("Sales Master Manager", "Desk User"))
        theirs = self._upload([["CEO pay", GROUP, "Company", ""]])  # Administrator's, private
        frappe.set_user(user)
        session = self._chat_session()

        response = self._check_fails(session, "don't have access", file_id=theirs.name)

        self.assertNotIn("CEO pay", frappe.as_json(response))
        self.assertFalse(frappe.db.get_value("FAC Import Session", session, "source_file"))

    def test_an_unknown_file_id_reads_the_same_as_one_the_user_cannot_read(self):
        session = self._chat_session()

        unknown = self._check_fails(session, "don't have access", file_id="no-such-file")
        folder = self._check_fails(session, "don't have access", file_id="Home")

        self.assertEqual(unknown["error"], folder["error"])

    def test_file_id_and_file_url_of_different_files_are_refused(self):
        # Both of the same file are taken (test_import_session); two different files are not.
        session = self._chat_session()
        file_doc = self._upload([[f"Both {self.tag}", GROUP, "Company", ""]])
        other = self._upload([[f"Other {self.tag}", GROUP, "Company", ""]])

        self._check_fails(session, "different files", file_id=file_doc.name, file_url=other.file_url)

        self.assertFalse(frappe.db.get_value("FAC Import Session", session, "source_file"))

    def test_a_doctype_whose_side_effects_cant_be_held_back_is_refused(self):
        session = self._session(self._mixed_rows())

        with patch.dict(import_dry_run.UNSAFE_DOCTYPES, {"Customer": "test reason"}):
            self._check_fails(session, "can't be done for Customer")

    def test_another_users_session_is_refused(self):
        session = self._session(self._mixed_rows())
        other = self.make_desk_user("other")
        self.assert_cannot(other, "write", "FAC Import Session", session)
        frappe.set_user(other)

        response = self._run("dry_run_import", {"session": session})

        self.assertFalse(response["success"])
        self.assertFalse(frappe.db.get_value("FAC Import Session", session, "validation_summary"))
