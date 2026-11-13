# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Import session housekeeping (#34542): a System Manager sees every session and releases a stuck
one, through the engine, with who and why in its step log."""

from unittest.mock import patch

import frappe

from frappe_assistant_core.assistant_core.doctype.fac_import_session.fac_import_session import engine_write
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils import import_housekeeping, import_run
from frappe_assistant_core.utils.import_session import HOLDING_STATUSES

SESSION = "FAC Import Session"


class TestImportHousekeeping(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def _session(self, status="Importing", **fields):
        # A session reaches Importing through start_import; its job dying (a worker restart, Redis
        # flushed) leaves it there. The engine's own copy writes it as start_import would.
        doc = engine_write(
            frappe.get_doc(
                {
                    "doctype": SESSION,
                    "user": "Administrator",
                    "file_name": "customers.csv",
                    "target_doctype": "Customer",
                    **fields,
                }
            )
        )
        doc.insert(ignore_permissions=True)
        frappe.db.set_value(SESSION, doc.name, "status", status)
        return doc.name

    def _release(self, name, reason="the worker was restarted"):
        return frappe.get_doc(SESSION, name).release(reason)

    def test_a_stuck_session_is_released_as_failed_saying_who_and_why(self):
        name = self._session()

        result = self._release(name)

        doc = frappe.get_doc(SESSION, name)
        self.assertEqual((result["status"], doc.status), ("Failed", "Failed"))
        # out of Importing: no longer locked by an import that won't end. Failed still holds the file
        # for the user's retry (#34437) until retention deletes it
        self.assertIn(doc.status, HOLDING_STATUSES)
        step = doc.steps[-1]
        self.assertEqual((step.step, step.outcome), ("Release", "Warning"))
        self.assertIn("Released by Administrator: the worker was restarted", step.message)

    def test_a_session_that_imported_rows_is_released_as_partially_completed(self):
        name = self._session(created_records=[{"record_doctype": "Customer", "record_name": "X"}])

        self.assertEqual(self._release(name)["status"], "Partially Completed")

    def test_only_a_system_manager_releases(self):
        name = self._session()
        user = self.make_throwaway_user("importer", roles=("Desk User",))
        frappe.db.set_value(SESSION, name, "user", user)
        frappe.set_user(user)
        try:
            with self.assertRaises(frappe.PermissionError):
                import_housekeeping.release(name, "mine")
        finally:
            frappe.set_user("Administrator")
        self.assertEqual(frappe.db.get_value(SESSION, name, "status"), "Importing")

    def test_a_reason_is_required(self):
        name = self._session()
        with self.assertRaises(frappe.ValidationError):
            self._release(name, "  ")
        self.assertEqual(frappe.db.get_value(SESSION, name, "status"), "Importing")

    def test_a_session_that_isnt_stuck_is_not_released(self):
        name = self._session("Completed")
        with self.assertRaises(frappe.ValidationError):
            self._release(name)
        self.assertEqual(frappe.db.get_value(SESSION, name, "status"), "Completed")

    def test_a_session_whose_import_is_still_running_is_left_alone(self):
        # RQ is the boundary here: a queued Data Import job is what job_running reads
        name = self._session()
        with patch.object(import_run, "job_running", autospec=True, return_value=True):
            with self.assertRaises(frappe.ValidationError):
                self._release(name)
        self.assertEqual(frappe.db.get_value(SESSION, name, "status"), "Importing")

    def test_a_plan_nothing_runs_is_stopped(self):
        from frappe_assistant_core.utils import import_plan

        # a plan is kept on its first file's session, which names itself as the plan (#34351)
        name = self._session("Ready to Import")
        frappe.db.set_value(
            SESSION,
            name,
            {
                "plan_status": "Running",
                "migration_plan": name,
                "plan_settings": frappe.as_json({"status": "Running"}),
            },
        )
        with patch.object(import_plan, "alive", autospec=True, return_value=False):
            result = self._release(name)

        self.assertEqual(result["plan_status"], "Stopped")
        self.assertEqual(frappe.db.get_value(SESSION, name, "plan_status"), "Stopped")

    def test_releasing_leaves_the_engine_guard_on(self):
        # the release writes through the engine; a hand edit is still refused afterwards
        name = self._session()
        self._release(name)
        doc = frappe.get_doc(SESSION, name)
        doc.status = "Completed"
        with self.assertRaises(frappe.PermissionError):
            doc.save()

    def test_the_report_lists_every_session_with_the_stuck_ones_marked(self):
        from frappe_assistant_core.assistant_core.report.import_sessions.import_sessions import execute

        stuck, done = self._session(), self._session("Completed")

        _columns, rows = execute({})
        by_name = {row["session"]: row for row in rows}
        self.assertEqual(by_name[stuck]["may_release"], 1)
        self.assertEqual(by_name[done]["may_release"], 0)
        self.assertEqual(by_name[stuck]["user"], "Administrator")

        _columns, rows = execute({"stuck_only": 1})
        self.assertIn(stuck, {row["session"] for row in rows})
        self.assertNotIn(done, {row["session"] for row in rows})

    def test_every_session_of_a_plan_shows_its_plan(self):
        # PR #392, L5: the Plan column was filled only on the plan's first session, and the
        # session ids were cut to "IMP-2026-169..."
        from frappe_assistant_core.assistant_core.report.import_sessions.import_sessions import execute

        first, second = self._session("Completed"), self._session("Completed")
        frappe.db.set_value(SESSION, first, {"migration_plan": first, "plan_status": "Partially Completed"})
        frappe.db.set_value(SESSION, second, "migration_plan", first)

        columns, rows = execute({})

        by_name = {row["session"]: row for row in rows}
        for name in (first, second):
            self.assertEqual(by_name[name]["migration_plan"], first)
            self.assertEqual(by_name[name]["plan_status"], "Partially Completed")
        widths = {c["fieldname"]: c["width"] for c in columns}
        self.assertGreaterEqual(widths["session"], 170)
        self.assertIn("migration_plan", widths)

    def test_the_report_is_for_system_managers(self):
        from frappe_assistant_core.assistant_core.report.import_sessions.import_sessions import execute

        frappe.set_user(self.make_throwaway_user("reader", roles=("Desk User",)))
        try:
            with self.assertRaises(frappe.PermissionError):
                execute({})
        finally:
            frappe.set_user("Administrator")
