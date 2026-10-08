# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""generate_report returns at most max_rows rows and says how many it had.

A report of a few thousand rows filled the model's context; the agent could
not even tell it had been given everything. Runs a real Query Report.
"""

from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.plugins.core.tools.generate_report import GenerateReport
from frappe_assistant_core.plugins.core.tools.report_tools import (
    DEFAULT_MAX_ROWS,
    MAX_ROWS_CAP,
    ReportTools,
    _clamp_max_rows,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.tests.report_fixtures import make_todo_query_report
from frappe_assistant_core.utils.tool_api import FrappeAssistantAPI

ROWS = 7


class TestGenerateReportRowCap(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # nosemgrep: frappe-setuser — test bootstrap; isolated transaction
        frappe.set_user("Administrator")
        # Built once: the base class rolls back per class, so a per-test build would stack rows.
        cls.report = make_todo_query_report(ROWS)

    def setUp(self):
        super().setUp()
        self.full = ReportTools.execute_report(self.report, max_rows=MAX_ROWS_CAP)
        self.assertTrue(self.full["success"], self.full.get("error"))

    def test_full_run_counts_rows_and_the_total(self):
        self.assertEqual(self.full["row_count"], ROWS + 1)
        self.assertFalse(self.full["truncated"])

    def test_max_rows_cuts_and_keeps_the_totals_row(self):
        capped = ReportTools.execute_report(self.report, max_rows=3)

        self.assertEqual(len(capped["data"]), 3)
        self.assertEqual(capped["row_count"], ROWS + 1)
        self.assertTrue(capped["truncated"])
        self.assertEqual(capped["data"][-1], self.full["data"][-1])
        self.assertIn("truncation_note", capped)

    def test_summary_only_returns_no_rows_but_the_count(self):
        summary = ReportTools.execute_report(self.report, summary_only=True)

        self.assertEqual(summary["data"], [])
        self.assertEqual(summary["row_count"], ROWS + 1)
        self.assertTrue(summary["columns"])
        self.assertNotIn("suggestion", summary)

    def test_the_tool_passes_its_arguments_through(self):
        result = GenerateReport().execute({"report_name": self.report, "max_rows": 2})
        self.assertEqual(len(result["data"]), 2)
        self.assertTrue(result["truncated"])

    def test_clamp(self):
        self.assertEqual(_clamp_max_rows(999_999), MAX_ROWS_CAP)
        self.assertEqual(_clamp_max_rows(0), 1)
        self.assertEqual(_clamp_max_rows("abc"), DEFAULT_MAX_ROWS)
        self.assertEqual(_clamp_max_rows(None), DEFAULT_MAX_ROWS)

    def test_sandbox_generate_report_asks_for_the_cap(self):
        # The sandbox's tools.generate_report builds its helper via _ensure_report_tools;
        # the stand-in replaces that helper so only the arguments are observed.
        tools = FrappeAssistantAPI("Administrator")
        tools._report_tools = MagicMock()

        tools.generate_report("Any Report", {"a": 1})

        kwargs = tools._report_tools.execute_report.call_args.kwargs
        self.assertEqual(kwargs["max_rows"], MAX_ROWS_CAP)

    def test_total_count_sits_beside_the_rows(self):
        capped = ReportTools.execute_report(self.report, max_rows=3)

        self.assertEqual(capped["total_count"], ROWS + 1)
        self.assertGreater(capped["total_count"], len(capped["data"]))

    def test_max_rows_one_returns_just_the_totals_row(self):
        capped = ReportTools.execute_report(self.report, max_rows=1)

        self.assertEqual(capped["data"], [self.full["data"][-1]])

    def test_summary_only_passes_through_the_tool(self):
        result = GenerateReport().execute({"report_name": self.report, "summary_only": True})

        self.assertEqual(result["data"], [])
        self.assertEqual(result["row_count"], ROWS + 1)

    def test_no_totals_row_when_frappe_skipped_it(self):
        # Frappe's run() reports add_total_row=False when a report sets skip_total_row even though
        # the Report doc has add_total_row=1; the stub stands in for that run() result.
        rows = [{"name": f"r{i}"} for i in range(6)]
        stub = {"result": rows, "columns": [], "add_total_row": False}
        with patch.object(ReportTools, "_execute_query_report", return_value=stub):
            capped = ReportTools.execute_report(self.report, max_rows=3)

        self.assertEqual(capped["data"], rows[:3])
