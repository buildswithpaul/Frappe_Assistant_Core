# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""A retry of a slow prepared report must pick up the report already running.

The timeout told the user to retry for "the cached result", but a retry while
the first job was still Queued queued a second one, and a third, never
converging. Production reaches the in-flight state whenever a report takes
longer than the tool's poll window (the RQ worker owns the job); the harness
stubs that Frappe boundary exactly as the zero-rows tests do. An in-flight row
older than the report's timeout is a lost background job (worker killed, row
never moved to Failed) and must not be reused.
"""

from unittest.mock import patch

import frappe
from frappe.utils import add_to_date, now_datetime

from frappe_assistant_core.plugins.core.tools.report_tools import ReportTools
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.tests.report_fixtures import make_todo_query_report
from frappe_assistant_core.tests.test_prepared_report_zero_rows import report_stub, stub_frappe


class TestPreparedReportReuse(BaseAssistantTest):
    def test_retry_polls_the_in_flight_report_instead_of_queueing_another(self):
        in_flight = [{"name": "PREP-INFLIGHT", "creation": add_to_date(now_datetime(), seconds=-30)}]
        with stub_frappe(in_flight=in_flight, prepared_status="Queued") as mocks:
            result = ReportTools._handle_prepared_report_execution(report_stub(), {"company": "X"})

        mocks.make_prepared.assert_not_called()
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["prepared_report_name"], "PREP-INFLIGHT")

    def test_in_flight_report_older_than_the_timeout_is_ignored(self):
        # A worker killed mid-job leaves the row Queued/Started forever.
        stale = [{"name": "PREP-DEAD", "creation": add_to_date(now_datetime(), seconds=-600)}]
        with stub_frappe(in_flight=stale, prepared_status="Queued", report_timeout=120) as mocks:
            result = ReportTools._handle_prepared_report_execution(report_stub(), {"company": "X"})

        mocks.make_prepared.assert_called_once()
        self.assertEqual(result["prepared_report_name"], "PREP-QUEUED")

    def test_first_call_still_queues_one(self):
        """Regression guard: green before the change too."""
        with stub_frappe(prepared_status="Queued") as mocks:
            result = ReportTools._handle_prepared_report_execution(report_stub(), {"company": "X"})

        mocks.make_prepared.assert_called_once()
        self.assertEqual(result["prepared_report_name"], "PREP-QUEUED")

    def test_timeout_message_says_still_preparing_and_reuse(self):
        with stub_frappe(prepared_status="Queued"):
            result = ReportTools._handle_prepared_report_execution(report_stub(), {"company": "X"})

        self.assertIn("still being prepared", result["message"])
        self.assertIn("same report", result["message"])


class TestTimeoutReachesTheCaller(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; isolated transaction
        frappe.set_user("Administrator")
        self.report = make_todo_query_report(1)

    def test_execute_report_keeps_the_timeout_status(self):
        # What _handle_prepared_report_execution returns when the poll window runs out.
        timeout = {
            "result": [],
            "columns": [],
            "status": "timeout",
            "prepared_report": True,
            "prepared_report_name": "PREP-INFLIGHT",
            "message": "still being prepared",
        }
        with patch.object(ReportTools, "_execute_query_report", return_value=timeout):
            result = ReportTools.execute_report(self.report)

        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["prepared_report_name"], "PREP-INFLIGHT")
        self.assertNotIn("suggestion", result)
