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

"""
Regression tests for: https://github.com/buildswithpaul/Frappe_Assistant_Core/issues/280

A report that finishes with zero rows has answered the question. It is not an
unfinished report, and `_handle_prepared_report_execution` could not tell the
two apart: every branch asked "did this run?" with `if result and
result.get("result"):`, and an empty list is falsy.

So a Prepared Report that Frappe marked `Completed` in seconds was read as "not
ready yet" three different ways:

  * the cached branch fell through and queued a *brand new* Prepared Report, so
    retrying the same filters never converged — it just made more rows in
    `tabPrepared Report`;
  * the direct-execution branch queued a background job for a report it had
    already finished running in the foreground;
  * the polling branch never returned, so the tool spun until `max_wait_time`
    and answered `status: "timeout"` — which MCP clients usually outlive by
    timing out first.

The distinction the code wants is presence, not truthiness. Frappe's
`generate_report_result` always returns a dict carrying a `"result"` key — `[]`
when nothing matched — and `get_prepared_report_result` merges that dict with
`{"prepared_report": True, "doc": doc}` before returning it. It omits `"result"`
only when there is genuinely nothing to read, because `get_prepared_data()` came
back empty or unparseable. That is the case that should fall through and
regenerate, and `is not None` keeps it falling through.

Production reaches this handler with an RQ worker writing the Prepared Report's
result file; a test has neither worker nor result file, so the four Frappe
entry points the handler reaches for are stubbed at the boundary. They are
autospec'd, so a Frappe rename or signature change fails here rather than
quietly passing against a Mock that accepts anything.
"""

import time
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from frappe_assistant_core.plugins.core.tools.report_tools import ReportTools
from frappe_assistant_core.tests.base_test import BaseAssistantTest

PREPARED_REPORT = "frappe.core.doctype.prepared_report.prepared_report"
QUERY_REPORT = "frappe.desk.query_report"

COLUMNS = [{"fieldname": "item_code", "label": "Item", "fieldtype": "Data"}]


def report_stub(name="Stock Balance"):
    """A Report doc as the handler uses it — it only ever reads `.name`.

    SimpleNamespace rather than MagicMock, so reading any other attribute raises
    instead of quietly returning a Mock.
    """
    return SimpleNamespace(name=name)


def empty_prepared_result():
    """What `get_prepared_report_result` returns for a report that matched no rows.

    Frappe stores the whole `generate_report_result` dict in the result file, so
    the key is always there and it is the row list that is empty.
    """
    return {
        "result": [],
        "columns": COLUMNS,
        "message": None,
        "prepared_report": True,
        "doc": frappe._dict(modified="2026-10-08 09:00:00"),
    }


def empty_direct_result():
    """What `run(ignore_prepared_report=True)` returns for the same report."""
    return {"result": [], "columns": COLUMNS, "message": None}


@contextmanager
def stub_frappe(
    *,
    completed_name=None,
    prepared_result=None,
    direct_result=None,
    report_timeout=120,
    prepared_status="Completed",
):
    """Patch the Frappe boundary `_handle_prepared_report_execution` calls into."""
    real_get_value = frappe.get_value
    real_get_doc = frappe.get_doc

    def fake_get_value(doctype, *args, **kwargs):
        if doctype == "Report" and args and args[-1] == "timeout":
            return report_timeout
        return real_get_value(doctype, *args, **kwargs)

    def fake_get_doc(*args, **kwargs):
        if args and args[0] == "Prepared Report":
            return frappe._dict(
                status=prepared_status,
                modified="2026-10-08 09:00:00",
                error_message=None,
            )
        return real_get_doc(*args, **kwargs)

    with ExitStack() as stack:
        mocks = frappe._dict(
            get_completed=stack.enter_context(
                patch(
                    f"{PREPARED_REPORT}.get_completed_prepared_report",
                    autospec=True,
                    return_value=completed_name,
                )
            ),
            make_prepared=stack.enter_context(
                patch(
                    f"{PREPARED_REPORT}.make_prepared_report",
                    autospec=True,
                    return_value={"name": "PREP-QUEUED"},
                )
            ),
            prepared_result=stack.enter_context(
                patch(
                    f"{QUERY_REPORT}.get_prepared_report_result",
                    autospec=True,
                    return_value=prepared_result,
                )
            ),
            run=stack.enter_context(patch(f"{QUERY_REPORT}.run", autospec=True, return_value=direct_result)),
        )
        stack.enter_context(patch.object(frappe, "get_value", side_effect=fake_get_value))
        stack.enter_context(patch.object(frappe, "get_doc", side_effect=fake_get_doc))

        # The polling loop sleeps between attempts and rolls back to re-read the
        # Prepared Report row. Left alone, the sleeps make a red run take the
        # full timeout it is asserting against, and the rollback would discard
        # IntegrationTestCase's own transaction.
        stack.enter_context(patch.object(time, "sleep"))
        stack.enter_context(patch.object(frappe.db, "rollback"))

        yield mocks


class TestPreparedReportZeroRows(BaseAssistantTest):
    """A completed prepared report with zero rows is a completed report."""

    def test_cached_zero_row_report_is_returned_not_requeued(self):
        """An existing Completed report with no rows must not queue another one."""
        with stub_frappe(
            completed_name="PREP-CACHED",
            prepared_result=empty_prepared_result(),
        ) as mocks:
            result = ReportTools._handle_prepared_report_execution(report_stub(), {"company": "X"})

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["source"], "cached")
        self.assertEqual(result["result"], [])
        self.assertEqual(result["columns"], COLUMNS)
        self.assertEqual(result["prepared_report_name"], "PREP-CACHED")

        # The symptom users actually report: every retry left another row in
        # tabPrepared Report because the cached hit was discarded.
        mocks.make_prepared.assert_not_called()

    def test_background_job_completing_with_zero_rows_returns_completed(self):
        """A queued report that finishes empty must end the poll, not run it out."""
        with stub_frappe(
            completed_name=None,
            prepared_result=empty_prepared_result(),
        ) as mocks:
            result = ReportTools._handle_prepared_report_execution(report_stub(), {"company": "X"})

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["source"], "background_job_completed")
        self.assertEqual(result["result"], [])
        self.assertEqual(result["columns"], COLUMNS)
        self.assertEqual(result["prepared_report_name"], "PREP-QUEUED")
        mocks.make_prepared.assert_called_once()

    def test_direct_execution_with_zero_rows_does_not_queue_a_job(self):
        """A fast report that runs inline and finds nothing is already done."""
        with stub_frappe(
            completed_name=None,
            direct_result=empty_direct_result(),
            report_timeout=30,  # under 60, so the handler tries inline execution
        ) as mocks:
            result = ReportTools._handle_prepared_report_execution(report_stub(), {"company": "X"})

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["source"], "direct_execution")
        self.assertEqual(result["result"], [])
        self.assertFalse(result["prepared_report"])
        mocks.run.assert_called_once()
        mocks.make_prepared.assert_not_called()

    def test_report_with_rows_still_returns_them(self):
        """The fix must not change the path that was already working."""
        rows = [{"item_code": "ITEM-001"}]
        payload = empty_prepared_result() | {"result": rows}

        with stub_frappe(completed_name="PREP-CACHED", prepared_result=payload):
            result = ReportTools._handle_prepared_report_execution(report_stub(), {"company": "X"})

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["result"], rows)

    def test_unreadable_result_file_still_regenerates(self):
        """A Completed row whose result file is empty has no "result" key at all.

        `get_prepared_report_result` skips `get_report_data` when the stored data
        is empty or unparseable, returning just {"prepared_report", "doc"}. That
        is the one case that genuinely has nothing to return, and it must keep
        falling through to a fresh job instead of reporting an empty success.
        """
        unreadable = {"prepared_report": True, "doc": None}

        with stub_frappe(completed_name="PREP-CACHED", prepared_result=unreadable) as mocks:
            result = ReportTools._handle_prepared_report_execution(report_stub(), {"company": "X"})

        mocks.make_prepared.assert_called_once()
        self.assertNotEqual(result["status"], "completed")
