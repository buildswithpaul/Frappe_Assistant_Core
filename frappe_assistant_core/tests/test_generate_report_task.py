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

"""generate_report answers with an MCP task (spec §7.4) instead of sleeping on a Prepared Report.

A real prepared Query Report runs through tools/call and tasks/get. No RQ worker runs in a test, and
the Prepared Report's job is only enqueued after a commit the test never makes, so the tests finish
the Prepared Report the way Frappe's ``generate_report`` job does.
"""

import json
import time
from collections import OrderedDict
from unittest.mock import patch

import frappe
from frappe.core.doctype.prepared_report.prepared_report import create_json_gz_file, make_prepared_report
from frappe.desk.query_report import generate_report_result
from frappe.utils import set_request

from frappe_assistant_core.api.fac_endpoint import handle_mcp
from frappe_assistant_core.mcp import tasks
from frappe_assistant_core.mcp.tool_adapter import build_tool_dict
from frappe_assistant_core.mcp.tool_result import finish_tool_result
from frappe_assistant_core.plugins.core.tools.generate_report import GenerateReport
from frappe_assistant_core.plugins.core.tools.report_tools import ReportTools
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.tests.report_fixtures import PROBE_DESCRIPTION, make_todo_query_report
from frappe_assistant_core.tests.test_fac_cloud_only_tools import MCP_PATH, _make_oauth_client, _mint
from frappe_assistant_core.tests.test_mcp_modern_era import _json, _modern, _send
from frappe_assistant_core.tests.test_mcp_tasks import TASK_CAPS

TOOL = "generate_report"


def _no_sleep(seconds):
    raise AssertionError(f"generate_report slept {seconds}s although the client takes tasks")


class TestGenerateReportTask(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; isolated transaction
        frappe.set_user("Administrator")
        self.track_test_files()
        self.report = make_todo_query_report(3)
        # The class shares one transaction: earlier tests' reports and tasks would be found first.
        frappe.db.delete("Prepared Report", {"report_name": self.report})
        frappe.db.delete("FAC MCP Task", {"tool": TOOL})
        # Every probe ToDo the class has inserted, plus the totals row.
        self.rows = frappe.db.count("ToDo", {"description": PROBE_DESCRIPTION}) + 1
        # An administrator ticks "Prepared Report" on a slow report. Its timeout stays 0 (unset), so
        # FAC queues it instead of trying it inline.
        frappe.db.set_value("Report", self.report, {"prepared_report": 1, "timeout": 0})
        self.tool = GenerateReport()
        self.registry = OrderedDict({TOOL: build_tool_dict(self.tool)})

    def tearDown(self):
        # nosemgrep: frappe-setuser — restores the bootstrap user before the shared tearDown
        frappe.set_user("Administrator")
        self.delete_test_files()
        super().tearDown()

    def _call(self, caps=TASK_CAPS) -> dict:
        params = {"name": TOOL, "arguments": {"report_name": self.report}}
        body, headers = _modern("tools/call", params, caps=caps)
        return _json(_send(body, headers, self.registry))["result"]

    def _get(self, task_id: str) -> dict:
        body, headers = _modern("tasks/get", {"taskId": task_id}, caps=TASK_CAPS)
        return _json(_send(body, headers, self.registry))["result"]

    def _new_task(self) -> tuple[str, str]:
        with patch.object(time, "sleep", side_effect=_no_sleep):
            result = self._call()
        self.assertEqual(result["resultType"], "task", result)
        row = frappe.db.get_value(
            "FAC MCP Task", result["taskId"], ["reference_doctype", "reference_name"], as_dict=True
        )
        self.assertEqual(row.reference_doctype, "Prepared Report")
        return result["taskId"], row.reference_name

    def _complete(self, prepared_report: str) -> None:
        # What Frappe's generate_report job does once the report has run: store the result as a
        # json.gz File attached to the Prepared Report, then mark it Completed.
        prepared = frappe.get_doc("Prepared Report", prepared_report)
        report_doc = frappe.get_doc("Report", prepared.report_name)
        result = generate_report_result(report=report_doc, filters=prepared.filters, user=prepared.owner)
        create_json_gz_file(result, prepared.doctype, prepared.name, prepared.report_name)
        frappe.db.set_value("Prepared Report", prepared.name, "status", "Completed")

    def test_queued_report_returns_task_without_sleeping(self):
        task_id, prepared_report = self._new_task()

        row = frappe.get_doc("FAC MCP Task", task_id)
        self.assertIn(self.report, row.status_message)
        self.assertEqual(row.owner_user, "Administrator")
        self.assertEqual(frappe.db.get_value("Prepared Report", prepared_report, "status"), "Queued")

    def test_task_status_message_names_the_report(self):
        with patch.object(time, "sleep", side_effect=_no_sleep):
            result = self._call()

        self.assertEqual(result["status"], "working")
        self.assertIn(self.report, result["statusMessage"])

    def test_working_while_the_job_runs(self):
        task_id, prepared_report = self._new_task()
        # The RQ worker sets Started when it picks the job up (update_job_id).
        frappe.db.set_value("Prepared Report", prepared_report, "status", "Started")

        result = self._get(task_id)

        self.assertEqual(result["status"], "working")
        self.assertIn(self.report, result["statusMessage"])
        self.assertNotIn("result", result)

    def test_cached_report_is_not_a_task(self):
        # A Completed Prepared Report for the same filters: an earlier call's job finished.
        self._complete(make_prepared_report(report_name=self.report, filters={})["name"])

        with patch.object(time, "sleep", side_effect=_no_sleep):
            result = self._call()

        self.assertEqual(result["resultType"], "complete")
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["row_count"], self.rows)
        self.assertFalse(frappe.db.exists("FAC MCP Task", {"tool": TOOL, "owner_user": "Administrator"}))

    def test_task_completes_with_rows(self):
        task_id, prepared_report = self._new_task()
        self._complete(prepared_report)

        result = self._get(task_id)

        self.assertEqual(result["status"], "completed")
        # The synchronous tool, called now, finds the same Completed Prepared Report.
        sync = self.tool.execute({"report_name": self.report})
        self.assertEqual(sync["prepared_report_name"], prepared_report)
        self.assertEqual(result["result"], finish_tool_result(self.registry[TOOL], sync))
        self.assertEqual(len(sync["data"]), self.rows)

    def _post(self, method: str, params: dict, token: str) -> dict:
        """POST to the whitelisted endpoint, which authenticates and builds the registry itself."""
        body, headers = _modern(method, params, caps=TASK_CAPS)
        headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        set_request(method="POST", path=MCP_PATH, headers=headers, data=json.dumps(body))
        response = handle_mcp()
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return _json(response)["result"]

    def test_task_polls_to_completed_through_the_endpoint(self):
        # A client the user connected themselves, signed in over OAuth.
        token = _mint("Administrator", _make_oauth_client(f"dcr-client-{frappe.generate_hash(length=8)}"))
        params = {"name": TOOL, "arguments": {"report_name": self.report}}
        with patch.object(time, "sleep", side_effect=_no_sleep):
            created = self._post("tools/call", params, token)
        self.assertEqual(created["resultType"], "task", created)
        task_id = created["taskId"]

        working = self._post("tasks/get", {"taskId": task_id}, token)
        self.assertEqual(working["status"], "working", working)

        self._complete(frappe.db.get_value("FAC MCP Task", task_id, "reference_name"))
        completed = self._post("tasks/get", {"taskId": task_id}, token)

        self.assertEqual(completed["status"], "completed", completed)
        payload = json.loads(completed["result"]["content"][0]["text"])
        self.assertEqual(len(payload["data"]), self.rows)

    def test_task_error_is_failed(self):
        task_id, prepared_report = self._new_task()
        # What Frappe's job stores when the report raises (_save_error): the whole traceback.
        traceback = (
            "Traceback (most recent call last):\n"
            '  File "apps/erpnext/report.py", line 9, in execute\n'
            "frappe.exceptions.ValidationError: Fiscal Year 2031 is missing"
        )
        frappe.db.set_value(
            "Prepared Report", prepared_report, {"status": "Error", "error_message": traceback}
        )

        result = self._get(task_id)

        self.assertEqual(result["status"], "failed")
        self.assertIn("Fiscal Year 2031 is missing", result["error"]["message"])
        self.assertNotIn("Traceback", result["error"]["message"])

    def test_revoked_report_permission_is_failed(self):
        user = self.make_throwaway_user("report-task", roles=("System Manager",))
        # nosemgrep: frappe-setuser — the task's owner is a non-Administrator user
        frappe.set_user(user)
        task_id, prepared_report = self._new_task()
        self._complete(prepared_report)
        # An administrator restricts the report to a role the user lacks while its job runs.
        # nosemgrep: frappe-setuser — the administrator's edit, then back to the task's owner
        frappe.set_user("Administrator")
        report = frappe.get_doc("Report", self.report)
        report.set("roles", [{"role": "Accounts Manager"}])
        report.save()
        # nosemgrep: frappe-setuser — back to the task's owner
        frappe.set_user(user)

        result = self._get(task_id)

        self.assertEqual(result["status"], "failed")
        self.assertNotIn("result", result)
        self.assertNotIn("fac-report-rows-probe", json.dumps(result))

    def test_another_users_prepared_report_is_failed(self):
        task_id, prepared_report = self._new_task()
        self._complete(prepared_report)
        other = self.make_throwaway_user("report-task-other", roles=("System Manager",))
        # Defence in depth: production cannot reach this, as tasks.create pins the row to its
        # caller and tasks/get refuses anyone else's. Rewriting owner_user hands Administrator's
        # Prepared Report to a user who may run the report but does not own that result.
        frappe.db.set_value("FAC MCP Task", task_id, "owner_user", other)
        # nosemgrep: frappe-setuser — act as the rewritten owner
        frappe.set_user(other)

        result = self._get(task_id)

        self.assertEqual(result["status"], "failed")
        self.assertNotIn("result", result)

    def test_adapter_found_in_a_fresh_worker(self):
        task_id, _prepared_report = self._new_task()

        # A worker that never served the tools/call starts with an empty registry.
        with patch.dict(tasks._ADAPTERS, clear=True):
            result = self._get(task_id)

        self.assertEqual(result["status"], "working", result)

    def test_no_tasks_declared_keeps_the_wait(self):
        slept = []
        # The RQ worker never runs in a test, so the Prepared Report stays Queued; the wait still
        # happens (on a fake clock) and ends in the timeout answer, exactly as before tasks.
        with patch.object(time, "sleep", slept.append), patch.object(frappe.db, "rollback"):
            result = self._call(caps={})

        self.assertEqual(result["resultType"], "complete")
        self.assertTrue(slept)
        self.assertEqual(json.loads(result["content"][0]["text"])["status"], "timeout")
        self.assertFalse(frappe.db.exists("FAC MCP Task", {"tool": TOOL, "owner_user": "Administrator"}))

    def test_sync_result_unchanged_by_refactor(self):
        """The prepared-report result through execute_report, field for field."""
        self._complete(make_prepared_report(report_name=self.report, filters={})["name"])

        result = ReportTools.execute_report(self.report)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["row_count"], self.rows)
        self.assertEqual(
            result["raw_result_keys"],
            [
                "result",
                "columns",
                "message",
                "prepared_report",
                "source",
                "prepared_report_name",
                "generated_at",
                "status",
                "add_total_row",
            ],
        )
