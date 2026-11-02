# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Import progress in FAC Chat (#34416): where a conversation's sessions stand, read by the chat."""

import json

import frappe

from frappe_assistant_core.assistant_core.doctype.fac_import_session.fac_import_session import engine_write
from frappe_assistant_core.chat.api import imports
from frappe_assistant_core.tests.base_test import BaseAssistantTest

SESSION = "FAC Import Session"


class TestImportProgressApi(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def _session(self, status, user="Administrator", **fields):
        # written by the engine, as the import tools write a session
        doc = engine_write(
            frappe.get_doc(
                {
                    "doctype": SESSION,
                    "user": user,
                    "file_name": "customers.csv",
                    "target_doctype": "Customer",
                    **fields,
                }
            )
        )
        doc.insert(ignore_permissions=True)
        frappe.db.set_value(SESSION, doc.name, "status", status)
        return doc.name

    def test_each_status_is_a_step_of_the_card(self):
        cases = {
            "File Read": "read",
            "Mapped": "mapped",
            "Dry Run Failed": "checked",
            "Ready to Import": "checked",
            "Importing": "imported",
            "Completed": "imported",
            "Failed": "checked",  # failed before any import: the check is where it stopped
        }
        names = {status: self._session(status) for status in cases}

        reply = imports.import_progress(json.dumps(list(names.values())))

        by_name = {s["session"]: s for s in reply["sessions"]}
        for status, step in cases.items():
            with self.subTest(status=status):
                self.assertEqual(by_name[names[status]]["step"], step)
        self.assertEqual([s["key"] for s in reply["steps"]], ["read", "mapped", "checked", "imported"])

    def test_a_session_says_its_total_counts_and_link(self):
        name = self._session(
            "Importing",
            validation_summary=json.dumps({"ready": 250}),
            created_records=[{"record_doctype": "Customer", "record_name": "A"}],
        )
        session = imports.import_progress([name])["sessions"][0]

        self.assertEqual((session["total"], session["created"], session["failed"]), (250, 1, 0))
        self.assertTrue(session["importing"])
        self.assertFalse(session["ended"])
        self.assertIn(name, session["url"])

    def test_another_users_session_is_left_out(self):
        other = self.make_throwaway_user("importer", roles=("Desk User",))
        theirs = self._session("Importing", user=other)
        mine_user = self.make_throwaway_user("viewer", roles=("Desk User",))
        frappe.set_user(mine_user)
        try:
            reply = imports.import_progress([theirs, "NO-SUCH-SESSION"])
        finally:
            frappe.set_user("Administrator")
        self.assertEqual(reply["sessions"], [])

    def test_at_most_twenty_sessions_are_read(self):
        self.assertEqual(len(imports._names([f"IMP-{n}" for n in range(30)])), imports.MAX_SESSIONS)
