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
from frappe.core.doctype.prepared_report.prepared_report import REPORT_TIMEOUT
from frappe.utils import add_to_date, now_datetime

from frappe_assistant_core.plugins.core.tools.report_tools import (
    PREPARED_REPORT_WAIT_SECONDS,
    QUEUE_WAIT_SLACK_SECONDS,
    ReportTools,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.tests.report_fixtures import make_todo_query_report
from frappe_assistant_core.tests.test_prepared_report_zero_rows import report_stub, stub_frappe


class TestPreparedReportReuse(BaseAssistantTest):
    def test_retry_after_a_timeout_response_reuses_the_still_running_job(self):
        # Production reaches this on the retry after a timeout response: FAC polled for
        # min(timeout, PREPARED_REPORT_WAIT_SECONDS) seconds, gave up, and the RQ job
        # (lifetime Report.timeout or REPORT_TIMEOUT) is still Queued/Started and older
        # than the poll window.
        in_flight = [{"name": "PREP-INFLIGHT", "creation": add_to_date(now_datetime(), seconds=-400)}]
        with stub_frappe(in_flight=in_flight, prepared_status="Queued", report_timeout=120) as mocks:
            result = ReportTools._handle_prepared_report_execution(report_stub(), {"company": "X"})

        mocks.make_prepared.assert_not_called()
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["prepared_report_name"], "PREP-INFLIGHT")

    def test_in_flight_report_beyond_the_job_lifetime_is_ignored(self):
        # A worker killed mid-job leaves the row Queued/Started forever.
        age = REPORT_TIMEOUT + QUEUE_WAIT_SLACK_SECONDS + 60
        stale = [{"name": "PREP-DEAD", "creation": add_to_date(now_datetime(), seconds=-age)}]
        with stub_frappe(in_flight=stale, prepared_status="Queued", report_timeout=None) as mocks:
            result = ReportTools._handle_prepared_report_execution(report_stub(), {"company": "X"})

        mocks.make_prepared.assert_called_once()
        self.assertEqual(result["prepared_report_name"], "PREP-QUEUED")

    def test_another_users_in_flight_report_is_never_reused(self):
        # Frappe's helper filters by owner; this guards against relying on that.
        other = [{"name": "PREP-OTHER", "owner": "someone-else@example.com"}]
        with stub_frappe(in_flight=other, prepared_status="Queued") as mocks:
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

    def test_new_prepared_report_returns_within_wait_cap(self):
        # Production reaches this whenever the RQ worker takes longer than the wait:
        # the Prepared Report row stays Queued while FAC polls. A fake clock stands in
        # for real sleeping.
        slept = []
        with stub_frappe(prepared_status="Queued", report_timeout=300), patch("time.sleep", slept.append):
            result = ReportTools._handle_prepared_report_execution(report_stub(), {"company": "X"})

        self.assertLessEqual(sum(slept), PREPARED_REPORT_WAIT_SECONDS)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["prepared_report_name"], "PREP-QUEUED")

    def test_timeout_message_tells_caller_to_retry_same_filters(self):
        with stub_frappe(prepared_status="Queued"), patch("time.sleep"):
            result = ReportTools._handle_prepared_report_execution(report_stub(), {"company": "X"})

        self.assertIn("generate_report again with the same filters", result["message"])


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

    def test_execute_report_surfaces_a_prepared_report_error(self):
        failed = {
            "success": False,
            "result": [],
            "columns": [],
            "status": "error",
            "error": "Report generation failed: boom",
            "prepared_report_name": "PREP-X",
        }
        with patch.object(ReportTools, "_execute_query_report", return_value=failed):
            result = ReportTools.execute_report(self.report)

        self.assertFalse(result["success"])
        self.assertIn("boom", result["error"])


def make_dated_query_report() -> str:
    """A UI-built Query Report whose SQL declares from_date and to_date, as Desk users write them."""
    name = f"FAC Dated {frappe.generate_hash(length=8)}"
    frappe.get_doc(
        {
            "doctype": "Report",
            "report_name": name,
            "ref_doctype": "ToDo",
            "report_type": "Query Report",
            "is_standard": "No",
            "module": "Desk",
            "prepared_report": 0,
            "query": (
                "select name as `Name:Link/ToDo:120` from `tabToDo` "
                "where date(creation) between %(from_date)s and %(to_date)s"
            ),
        }
    ).insert()
    return name


class TestDefaultedFiltersAreVisible(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; isolated transaction
        frappe.set_user("Administrator")
        self.report = make_dated_query_report()
        self.undated_report = make_todo_query_report(1)

    def test_result_lists_filters_that_were_defaulted(self):
        first = ReportTools.execute_report(self.report)

        self.assertTrue(first["success"], first)
        self.assertIn("from_date", first["defaulted_filters"])
        self.assertIn("to_date", first["defaulted_filters"])
        self.assertEqual(first["defaulted_filters"]["to_date"], first["filters_applied"]["to_date"])

        explicit = ReportTools.execute_report(self.report, filters=first["filters_applied"])
        self.assertEqual(explicit["defaulted_filters"], {})

    def test_blank_caller_value_counts_as_defaulted(self):
        result = ReportTools.execute_report(self.report, filters={"from_date": ""})

        self.assertIn("from_date", result["defaulted_filters"])

    def test_report_without_date_filters_reports_no_date_defaults(self):
        # make_todo_query_report's SQL has no placeholders, so it takes no filters and
        # answers for all time: claiming a fiscal year or company for it would mislead.
        result = ReportTools.execute_report(self.undated_report)

        self.assertTrue(result["success"], result)
        self.assertEqual(result["defaulted_filters"], {})
        self.assertNotIn("from_date", result["filters_applied"])
        self.assertNotIn("company", result["filters_applied"])

    def test_unknown_filter_contract_reports_null_not_empty(self):
        # Production reaches None when discovery cannot tell (a Script Report with no
        # readable JS, a Query Report with positional %s): the contract is unknown, not empty.
        with patch.object(ReportTools, "_filter_definitions", return_value=None):
            result = ReportTools.execute_report(self.undated_report)

        self.assertTrue(result["success"], result)
        self.assertIsNone(result["defaulted_filters"])

    def test_every_prepared_result_shape_carries_defaulted_filters(self):
        # The prepared handler returns these shapes in production; execute_report
        # must annotate each one, including the timeout the model sees most.
        shapes = {
            "timeout": {"result": [], "columns": [], "status": "timeout", "prepared_report_name": "P"},
            "cached": {"result": [], "columns": [], "status": "completed", "source": "cached"},
        }
        for name, shape in shapes.items():
            with self.subTest(shape=name), patch.object(
                ReportTools, "_execute_query_report", return_value=dict(shape)
            ):
                result = ReportTools.execute_report(self.report)
            self.assertEqual(result["defaulted_filters"], {})
