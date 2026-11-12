# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Import progress in FAC Chat (#34416): where a conversation's sessions stand, read by the chat."""

import json
from unittest.mock import patch

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


class TestPlanProgressApi(BaseAssistantTest):
    """#34351: a migration plan ran with text only; the chat reads where each file stands."""

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.track_test_files()
        self.tag = frappe.generate_hash(length=6)

    def tearDown(self):
        frappe.set_user("Administrator")
        self.delete_test_files()
        super().tearDown()

    def _mapped(self, file_name, content, doctype, mapping):
        from frappe_assistant_core.core.tool_registry import get_tool_registry

        registry = get_tool_registry()
        file_doc = frappe.get_doc(
            {"doctype": "File", "file_name": file_name, "content": content, "is_private": 1}
        ).insert()
        session = registry.get_tool("start_import_session")._safe_execute({"file_url": file_doc.file_url})
        name = session["result"]["session_id"]
        registry.get_tool("set_column_mapping")._safe_execute(
            {"session": name, "mapping": mapping, "doctype": doctype}
        )
        return name

    def test_a_plan_says_its_status_and_each_files_progress_in_order(self):
        from frappe_assistant_core.core.tool_registry import get_tool_registry

        groups = self._mapped(
            "groups.csv", f"Name\nG {self.tag}\n".encode(), "Item Group", {"Name": "item_group_name"}
        )
        regions = self._mapped(
            "regions.csv", f"Name\nT {self.tag}\n".encode(), "Territory", {"Name": "territory_name"}
        )
        planned = (
            get_tool_registry().get_tool("plan_migration")._safe_execute({"sessions": [groups, regions]})
        )
        plan = planned["result"]["plan"]

        reply = imports.plan_progress(plan)

        self.assertEqual(reply["plan"], plan)
        self.assertEqual(reply["status"], "Planning")
        self.assertFalse(reply["ended"])
        self.assertEqual({f["file_name"] for f in reply["files"]}, {"groups.csv", "regions.csv"})
        self.assertTrue(all("created" in f and "status" in f for f in reply["files"]))

    # -- the Stop button on the plan's progress block (PR #392, F7) --------------------------

    def _plan(self):
        from frappe_assistant_core.core.tool_registry import get_tool_registry

        groups = self._mapped(
            "groups.csv", f"Name\nG {self.tag}\n".encode(), "Item Group", {"Name": "item_group_name"}
        )
        return (
            get_tool_registry()
            .get_tool("plan_migration")
            ._safe_execute({"sessions": [groups]})["result"]["plan"]
        )

    def test_the_block_stops_a_running_plan_after_its_file_without_a_chat_turn(self):
        # Live: "stop now" waited in the composer while FACO's turn ran, and the plan had finished
        # by the time it was sent
        from frappe_assistant_core.utils import import_plan

        plan = self._plan()
        running = import_plan.get_plan(plan)
        running.status = "Running"
        running.save()

        with patch.object(import_plan, "alive", return_value=True):
            reply = imports.stop_plan(plan)

        self.assertTrue(reply["success"], reply)
        self.assertIn("stops once", reply["message"])
        self.assertEqual(import_plan._settings(plan).get("stop_requested"), 1)
        self.assertEqual(reply["progress"]["plan"], plan)
        audit = frappe.get_all("Assistant Audit Log", filters={"tool_name": "stop_migration_plan"}, limit=1)
        self.assertTrue(audit)  # the stop_migration_plan tool did it: its checks and its audit row

    def test_the_block_drops_a_plan_not_run_yet(self):
        plan = self._plan()

        reply = imports.stop_plan(plan)

        self.assertTrue(reply["success"], reply)
        self.assertEqual(reply["progress"]["status"], "Stopped")
        self.assertTrue(reply["progress"]["ended"])

    def test_an_ended_plan_says_it_isnt_running(self):
        plan = self._plan()
        imports.stop_plan(plan)

        reply = imports.stop_plan(plan)

        self.assertFalse(reply["success"])
        self.assertIn("not running", reply["error"])

    def test_another_users_plan_cant_be_stopped(self):
        plan = self._plan()
        frappe.set_user(self.make_throwaway_user("stopper", roles=("Desk User",)))
        try:
            with self.assertRaises(frappe.DoesNotExistError):
                imports.stop_plan(plan)
        finally:
            frappe.set_user("Administrator")
        self.assertNotEqual(frappe.db.get_value("FAC Import Session", plan, "status"), "Stopped")

    def test_another_users_plan_is_not_found(self):
        viewer = self.make_throwaway_user("viewer", roles=("Desk User",))
        theirs = self._mapped(
            "groups.csv", f"Name\nG {self.tag}\n".encode(), "Item Group", {"Name": "item_group_name"}
        )
        from frappe_assistant_core.core.tool_registry import get_tool_registry

        plan = (
            get_tool_registry()
            .get_tool("plan_migration")
            ._safe_execute({"sessions": [theirs]})["result"]["plan"]
        )
        frappe.set_user(viewer)
        try:
            with self.assertRaises(frappe.DoesNotExistError):
                imports.plan_progress(plan)
        finally:
            frappe.set_user("Administrator")
