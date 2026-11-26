# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""start_import and run_migration_plan answer with an MCP task (spec §7.4).

Real sessions and plans go through tools/call and tasks/get. No RQ worker runs in a test: the
import's job is queued with ``enqueue`` patched (as on a production site, outside developer mode),
then run by calling the job function itself, with each commit a savepoint.
"""

import json
import unittest
from collections import OrderedDict
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.core.doctype.data_import.data_import import start_import as run_data_import

from frappe_assistant_core.mcp import tasks
from frappe_assistant_core.mcp.tool_adapter import build_tool_dict
from frappe_assistant_core.mcp.tool_result import finish_tool_result

# Modules, not their classes: a test class imported here would run again with this module's tests.
from frappe_assistant_core.tests import test_import_run as run_tests
from frappe_assistant_core.tests import test_run_migration_plan as plan_tests
from frappe_assistant_core.tests.test_mcp_modern_era import _json, _modern, _send
from frappe_assistant_core.tests.test_mcp_tasks import TASK_CAPS
from frappe_assistant_core.utils import import_plan, import_run

SESSION = "FAC Import Session"
ENQUEUED = "frappe.utils.background_jobs.is_job_enqueued"


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer and Item")
class TestImportTasks(run_tests.ImportRunCase):
    _mapped = plan_tests.TestRunMigrationPlan._mapped
    _ready_plan = plan_tests.TestRunMigrationPlan._ready_plan

    def setUp(self):
        super().setUp()
        frappe.db.delete("FAC MCP Task", {"tool": ("in", ("start_import", "run_migration_plan"))})
        self.tools = OrderedDict(
            (name, build_tool_dict(self.registry.get_tool(name)))
            for name in ("start_import", "run_migration_plan")
        )

    def tearDown(self):
        # A request leaves its era and capabilities on frappe.local; a direct call must not see them.
        frappe.local.mcp_era = frappe.local.mcp_client_caps = None
        super().tearDown()

    # -- helpers -----------------------------------------------------------------------

    def _call(self, tool, arguments, caps=TASK_CAPS) -> dict:
        body, headers = _modern("tools/call", {"name": tool, "arguments": arguments}, caps=caps)
        return _json(_send(body, headers, self.tools))["result"]

    def _get(self, task_id) -> dict:
        body, headers = _modern("tasks/get", {"taskId": task_id}, caps=TASK_CAPS)
        return _json(_send(body, headers, self.tools))["result"]

    @contextmanager
    def _in_the_background(self):
        """A production site: the import is queued for a worker, not run in the request."""
        with patch.object(import_run, "_runs_now", autospec=True, return_value=False), patch.object(
            import_run, "is_scheduler_inactive", autospec=True, return_value=False
        ), patch.object(import_run, "enqueue", autospec=True):
            yield

    def _queued_import(self, caps=TASK_CAPS):
        session, self.checked = self._ready_session()
        with self._in_the_background():
            result = self._call("start_import", self._card(session, self.checked), caps=caps)
        return session, result

    def _import_task(self):
        session, result = self._queued_import()
        self.assertEqual(result["resultType"], "task", result)
        data_import = self._doc(session).data_imports[-1].data_import
        return session, result["taskId"], data_import

    def _plan_task(self):
        plan, groups, items = self._ready_plan()
        figures = {"plan": plan, **import_plan.card_figures(import_plan.get_plan(plan))}
        # The plan's run is always a job (import_plan._enqueue): queued, not run here.
        with patch.object(import_plan.frappe, "enqueue"):
            result = self._call("run_migration_plan", figures)
        self.assertEqual(result["resultType"], "task", result)
        return plan, result["taskId"]

    def _hand_to(self, task_id, user):
        # Defence in depth: production cannot reach this, as tasks.create pins the row to its caller
        # and tasks/get refuses anyone else's. Rewriting owner_user hands the task to a user who
        # may use Desk but does not own the session it follows.
        frappe.db.set_value("FAC MCP Task", task_id, "owner_user", user)
        frappe.set_user(user)

    # -- start_import ------------------------------------------------------------------

    def test_queued_import_returns_task(self):
        session, result = self._queued_import()

        self.assertEqual(result["resultType"], "task", result)
        self.assertEqual(result["status"], "working")
        row = frappe.get_doc("FAC MCP Task", result["taskId"])
        self.assertEqual((row.reference_doctype, row.reference_name), (SESSION, session))
        self.assertIn("Customer", row.status_message)

    def test_import_task_is_working_while_the_job_runs(self):
        _session, task_id, _data_import = self._import_task()

        with patch(ENQUEUED, autospec=True, return_value=True):  # a worker holds the job
            result = self._get(task_id)

        self.assertEqual(result["status"], "working", result)
        self.assertNotIn("result", result)

    def test_import_task_completes(self):
        session, task_id, data_import = self._import_task()
        # What the worker runs (import_run.run_job): Data Import's own run, then its result recorded
        # on the session, which moves it from Importing to Completed.
        with self._each_row_commits():
            import_run.run_job(data_import, session)
        doc = self._doc(session)
        self.assertEqual(doc.status, "Completed")

        result = self._get(task_id)

        self.assertEqual(result["status"], "completed", result)
        payload = json.loads(result["result"]["content"][0]["text"])
        self.assertEqual((payload["state"], payload["created"], payload["session"]), ("finished", 3, session))
        self.assertFalse(result["result"]["isError"])

    def test_import_task_result_is_what_start_import_returns(self):
        session, task_id, data_import = self._import_task()
        with self._each_row_commits():
            run_data_import(data_import)  # run to its end from Desk: the session still says Importing
        # start_import, called now, records the finished import and returns its result
        with self._in_the_background():
            sync = self.registry.get_tool("start_import")._safe_execute(self._card(session, self.checked))
        self.assertEqual(sync["result"]["state"], "finished", sync)

        result = self._get(task_id)

        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["result"], finish_tool_result(self.tools["start_import"], sync))

    def test_a_dead_import_is_failed_not_working_for_ever(self):
        session, task_id, data_import = self._import_task()
        # The worker died: Frappe's job marked the Data Import Timed Out and nothing runs it now.
        frappe.db.set_value("Data Import", data_import, "status", "Timed Out")
        self.assertTrue(import_run.continues(self._doc(session)))

        result = self._get(task_id)

        self.assertEqual(result["status"], "failed", result)
        self.assertIn("start_import", result["error"]["message"])

    def test_import_task_of_another_user_is_failed(self):
        session, task_id, data_import = self._import_task()
        with self._each_row_commits():
            import_run.run_job(data_import, session)
        self._hand_to(task_id, self.make_throwaway_user("import-task", roles=("Desk User",)))

        result = self._get(task_id)

        self.assertEqual(result["status"], "failed", result)
        self.assertNotIn("result", result)
        self.assertNotIn(self._names()["alpha"], json.dumps(result))

    def test_import_adapter_found_in_a_fresh_worker(self):
        _session, task_id, _data_import = self._import_task()

        with patch.dict(tasks._ADAPTERS, clear=True), patch(ENQUEUED, autospec=True, return_value=True):
            result = self._get(task_id)

        self.assertEqual(result["status"], "working", result)

    def test_without_tasks_the_import_reply_is_unchanged(self):
        session, result = self._queued_import(caps={})

        self.assertEqual(result["resultType"], "complete", result)
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(payload["state"], "started")
        self.assertIn("in the background", payload["message"])
        self.assertNotIn(tasks.TASK_MARKER, payload)
        self.assertFalse(frappe.db.exists("FAC MCP Task", {"reference_name": session}))

    def test_a_direct_call_carries_no_task_marker(self):
        # FAC Chat and other callers run the tool without tools/call: nothing pops a marker there.
        session, checked = self._ready_session()
        with self._in_the_background():
            reply = self.registry.get_tool("start_import")._safe_execute(self._card(session, checked))
        self.assertEqual(reply["result"]["state"], "started", reply)
        self.assertNotIn(tasks.TASK_MARKER, reply["result"])

        plan, _groups, _items = self._ready_plan()
        figures = {"plan": plan, **import_plan.card_figures(import_plan.get_plan(plan))}
        with patch.object(import_plan.frappe, "enqueue"):
            reply = self.registry.get_tool("run_migration_plan")._safe_execute(figures)
        self.assertEqual(reply["result"]["status"], "Running", reply)
        self.assertNotIn(tasks.TASK_MARKER, reply["result"])

    def test_an_import_run_in_the_request_is_not_a_task(self):
        # Developer mode and tests: Data Import runs inside the call, so nothing is left to follow.
        session, checked = self._ready_session()
        with self._each_row_commits():
            result = self._call("start_import", self._card(session, checked))

        self.assertEqual(result["resultType"], "complete", result)
        self.assertEqual(json.loads(result["content"][0]["text"])["state"], "finished")

    # -- run_migration_plan --------------------------------------------------------------

    def test_running_plan_returns_task(self):
        plan, task_id = self._plan_task()

        row = frappe.get_doc("FAC MCP Task", task_id)
        self.assertEqual((row.reference_doctype, row.reference_name), (SESSION, plan))
        self.assertEqual(self._get(task_id)["status"], "working")

    def test_plan_task_completes(self):
        plan, task_id = self._plan_task()
        with self._each_row_commits():
            import_plan.run_job(plan, "Administrator")  # the run the approval queued
        self.assertEqual(import_plan.get_plan(plan).status, "Completed")

        result = self._get(task_id)

        self.assertEqual(result["status"], "completed", result)
        self.assertFalse(result["result"]["isError"])
        payload = json.loads(result["result"]["content"][0]["text"])
        self.assertEqual((payload["plan"], payload["status"]), (plan, "Completed"))

    def test_plan_task_fenced(self):
        plan, _groups, _items = self._ready_plan()
        figures = {"plan": plan, **import_plan.card_figures(import_plan.get_plan(plan))}
        # The synchronous call: in a test the plan's job runs inside it (import_plan._enqueue's
        # now=), so the tool returns the finished plan, as its reply for a plan that has ended.
        with self._each_row_commits():
            sync = self.registry.get_tool("run_migration_plan")._safe_execute(figures)
        self.assertEqual(sync["result"]["status"], "Completed", sync)
        # The row finish_call creates when a task-capable client's approval queues the job
        # (test_running_plan_returns_task); here the same plan, so both replies can be compared.
        task = tasks.create(
            "run_migration_plan", figures, {"reference_doctype": SESSION, "reference_name": plan}
        )

        result = self._get(task["taskId"])

        self.assertEqual(result["status"], "completed", result)
        finished = finish_tool_result(self.tools["run_migration_plan"], sync)
        self.assertEqual(result["result"], finished)
        file_name = sync["result"]["files"][0]["file_name"]
        self.assertIn(
            f"<import_file_content>{file_name}</import_file_content>", result["result"]["content"][0]["text"]
        )

    def test_plan_stopped_is_failed(self):
        plan, task_id = self._plan_task()
        # The scheduled sweep (sweep_dead_plans) stops a Running plan no job runs any more.
        self.assertTrue(import_plan._end_if_dead(plan))

        result = self._get(task_id)

        self.assertEqual(result["status"], "failed", result)
        self.assertIn("Stopped", result["error"]["message"])
        self.assertIn("No job was running the plan", result["error"]["data"]["message"])
        self.assertIn("<import_file_content>", result["error"]["data"]["message"])

    def test_plan_task_of_another_user_is_failed(self):
        plan, task_id = self._plan_task()
        with self._each_row_commits():
            import_plan.run_job(plan, "Administrator")
        self._hand_to(task_id, self.make_throwaway_user("plan-task", roles=("Desk User",)))

        result = self._get(task_id)

        self.assertEqual(result["status"], "failed", result)
        self.assertNotIn("result", result)
        self.assertNotIn("groups.csv", json.dumps(result))

    def test_without_tasks_the_plan_reply_is_unchanged(self):
        plan, _groups, _items = self._ready_plan()
        figures = {"plan": plan, **import_plan.card_figures(import_plan.get_plan(plan))}
        with patch.object(import_plan.frappe, "enqueue"):
            result = self._call("run_migration_plan", figures, caps={})

        self.assertEqual(result["resultType"], "complete", result)
        self.assertEqual(json.loads(result["content"][0]["text"])["status"], "Running")
        self.assertFalse(frappe.db.exists("FAC MCP Task", {"reference_name": plan}))
