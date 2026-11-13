# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.


"""
FACO says so in the chat when a background check, import or migration plan ends (#34416 AC3):
it was seen four times that the user had to ask. A job's end posts the result in the
conversation the session was started from, and the open chat is told to read it.
"""

import unittest
from unittest.mock import patch

import frappe

from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils import import_dry_run, import_plan, import_run

MAPPING = {
    "Customer Name": "customer_name",
    "Customer Group": "customer_group",
    "Customer Type": "customer_type",
}


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
class TestTheResultIsPostedInTheChat(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.registry = get_tool_registry()
        self.track_test_files()
        self.tag = frappe.generate_hash(length=6)
        self.chat = self._conversation("Administrator")
        self.group = (
            frappe.get_doc(
                {
                    "doctype": "Customer Group",
                    "customer_group_name": f"Posted {self.tag}",
                    "parent_customer_group": "All Customer Groups",
                }
            )
            .insert()
            .name
        )
        published = patch.object(frappe, "publish_realtime", autospec=True)
        self.published = published.start()
        self.addCleanup(published.stop)

    def tearDown(self):
        # Removed, not set to None: Frappe's is_valid_http_method checks hasattr(frappe.local, "job"),
        # so a None left behind makes every later test in the run look like a background job
        if hasattr(frappe.local, "job"):
            del frappe.local.job
        frappe.set_user("Administrator")
        self.delete_test_files()
        super().tearDown()

    def _conversation(self, user):
        chat = f"fac-test-chat-{frappe.generate_hash(length=8)}"
        frappe.get_doc({"doctype": "FAC Chat Conversation", "session_id": chat, "user": user}).insert(
            ignore_permissions=True
        )
        return chat

    def _run(self, tool_name, arguments):
        return self.registry.get_tool(tool_name)._safe_execute(arguments)

    def _session(self):
        lines = [
            ",".join(MAPPING),
            f"Alpha {self.tag},{self.group},Company",
            f"Beta {self.tag},{self.group},Company",
        ]
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "customers.csv",
                "content": ("\n".join(lines) + "\n").encode(),
                "is_private": 1,
            }
        ).insert()
        frappe.local.ar_session_id = self.chat  # as FAC Cloud's tool call in that conversation sets it
        self.addCleanup(setattr, frappe.local, "ar_session_id", None)
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]
        self._run("set_column_mapping", {"session": session, "mapping": MAPPING, "doctype": "Customer"})
        return session

    def _as_a_job(self):
        frappe.local.job = frappe._dict(method="test")  # what Frappe's worker sets for a job it runs

    def _posted(self):
        return frappe.get_all("FAC Chat Message", filters={"session_id": self.chat}, pluck="content")

    def test_a_background_check_posts_its_result_and_the_chat_reloads(self):
        session = self._session()
        self._as_a_job()

        import_dry_run.run_job(session, "Administrator")

        posted = self._posted()
        self.assertEqual(len(posted), 1, posted)
        self.assertIn("customers.csv has finished: 2 rows ready, 0 would fail", posted[0])
        sent = self.published.call_args.kwargs
        self.assertEqual(
            (sent["room"], sent["message"]["event"]), (f"task_progress:{self.chat}", "message_posted")
        )

    def test_a_plans_file_says_the_plan_goes_on_not_to_import_it(self):
        # Live, 2026-11-06: "Say when to import them" for a file in a plan; the user's "import"
        # was then refused, as the plan imports its files after its own approval.
        session = self._session()
        plan = self._run("plan_migration", {"sessions": [session]})["result"]["plan"]
        self._as_a_job()

        import_dry_run.run_job(session, "Administrator")

        posted = self._posted()
        self.assertEqual(len(posted), 1, posted)
        self.assertIn(f"in migration plan {plan}", posted[0])
        self.assertNotIn("Say when to import them", posted[0])

    def test_a_check_in_the_request_posts_nothing(self):
        # developer mode or a small file: the tool call's own reply carries the result
        session = self._session()

        import_dry_run.run_job(session, "Administrator")

        self.assertEqual(self._posted(), [])

    def test_a_background_import_posts_what_it_imported(self):
        session = self._session()
        checked = self._run("dry_run_import", {"session": session})["result"]
        doc = frappe.get_doc(import_dry_run.SESSION_DOCTYPE, session)
        card = {
            "session": session,
            "doctype": "Customer",
            "rows": checked["ready"],
            "import_type": "Insert New Records",
            "validated_fingerprint": checked.get("validated_fingerprint"),
            "file_name": doc.file_name,
        }
        with patch.object(import_run, "enqueue", autospec=True):  # queued for the worker
            data_import = self._run("start_import", card)["result"]["data_import"]
        self._as_a_job()

        import_run.run_job(data_import, session)

        posted = self._posted()
        self.assertEqual(len(posted), 1, posted)
        self.assertIn("Imported 2 Customer records", posted[0])

    def test_a_plan_that_ends_in_its_job_posts_each_files_result(self):
        session = self._session()
        plan = self._run("plan_migration", {"sessions": [session]})["result"]["plan"]
        self._as_a_job()

        import_plan._end(plan, "Completed", "1 files imported.")

        posted = self._posted()
        self.assertEqual(len(posted), 1, posted)
        self.assertIn(f"Migration plan {plan} has ended: Completed", posted[0])
        self.assertIn("customers.csv (Customer)", posted[0])

    def test_nothing_is_posted_in_another_users_conversation(self):
        # the conversation id comes from the caller's X-AR-Session-Id header: it can name anyone's
        self.chat = self._conversation("Guest")
        session = self._session()
        self._as_a_job()

        import_dry_run.run_job(session, "Administrator")

        self.assertEqual(self._posted(), [])
        self.assertNotIn(self.chat, [str(c.kwargs.get("room")) for c in self.published.call_args_list])
