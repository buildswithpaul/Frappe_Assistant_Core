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
Tests for Assistant Audit Log status classification and field capture.

These tests exercise BaseTool._safe_execute directly via a minimal in-memory
tool subclass, so they do not depend on any specific plugin being loaded.
"""

from typing import Any, Dict

import frappe

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.tests.base_test import BaseAssistantTest

_TEST_TOOL_NAME = "test_audit_tool"


class _ToolBase(BaseTool):
    """Minimal concrete BaseTool used only in these tests."""

    def __init__(self, executor=None):
        super().__init__()
        self.name = _TEST_TOOL_NAME
        self.description = "Test tool"
        self.inputSchema = {"type": "object", "properties": {}}
        self.requires_permission = None  # skip the DocType permission check
        self.source_app = "frappe_assistant_core"
        self._executor = executor

    def execute(self, arguments: Dict[str, Any]) -> Any:
        return self._executor(arguments)


def _fetch_latest_audit_row(tool_name: str) -> Dict[str, Any]:
    rows = frappe.get_all(
        "Assistant Audit Log",
        filters={"tool_name": tool_name},
        fields=[
            "name",
            "status",
            "error_type",
            "error_message",
            "traceback",
            "source_app",
            "session_id",
            "client_id",
            "output_truncated",
        ],
        order_by="creation desc",
        limit=1,
    )
    assert rows, f"No audit row found for tool {tool_name}"
    return rows[0]


def _delete_test_rows(tool_name: str):
    frappe.db.delete("Assistant Audit Log", {"tool_name": tool_name})


class TestAuditLogStatusClassification(BaseAssistantTest):
    """A tool call's audit status must reflect what actually happened."""

    def setUp(self):
        super().setUp()
        _delete_test_rows(_TEST_TOOL_NAME)

    def test_successful_execution_logs_success(self):
        tool = _ToolBase(executor=lambda arguments: {"items": [1, 2, 3]})
        response = tool._safe_execute({})

        self.assertTrue(response["success"])
        row = _fetch_latest_audit_row(_TEST_TOOL_NAME)
        self.assertEqual(row["status"], "Success")
        self.assertIsNone(row["error_type"])
        self.assertIsNone(row["error_message"])

    def test_tool_reported_failure_logs_error(self):
        """A tool returning {"success": False, ...} was previously logged as
        Success. It must now be logged as Error with ToolReportedError type."""

        def executor(arguments):
            return {"success": False, "error": "file not found"}

        tool = _ToolBase(executor=executor)
        response = tool._safe_execute({})

        self.assertFalse(response["success"])
        self.assertEqual(response["error_type"], "ToolReportedError")

        row = _fetch_latest_audit_row(_TEST_TOOL_NAME)
        self.assertEqual(row["status"], "Error")
        self.assertEqual(row["error_type"], "ToolReportedError")
        self.assertIn("file not found", row["error_message"] or "")

    def test_permission_error_logs_permission_denied(self):
        def executor(arguments):
            raise frappe.PermissionError("no access")

        tool = _ToolBase(executor=executor)
        tool._safe_execute({})

        row = _fetch_latest_audit_row(_TEST_TOOL_NAME)
        self.assertEqual(row["status"], "Permission Denied")
        self.assertEqual(row["error_type"], "PermissionError")

    def test_uncaught_exception_logs_error_with_traceback(self):
        def executor(arguments):
            raise RuntimeError("boom")

        tool = _ToolBase(executor=executor)
        tool._safe_execute({})

        row = _fetch_latest_audit_row(_TEST_TOOL_NAME)
        self.assertEqual(row["status"], "Error")
        self.assertEqual(row["error_type"], "ExecutionError")
        self.assertTrue(row["traceback"], "traceback must be captured on exception path")
        self.assertIn("RuntimeError", row["traceback"])

    def test_timeout_error_logs_timeout(self):
        def executor(arguments):
            raise TimeoutError("tool timed out")

        tool = _ToolBase(executor=executor)
        tool._safe_execute({})

        row = _fetch_latest_audit_row(_TEST_TOOL_NAME)
        self.assertEqual(row["status"], "Timeout")
        self.assertEqual(row["error_type"], "Timeout")


class TestAuditLogFieldCapture(BaseAssistantTest):
    """New audit columns must actually be populated end-to-end."""

    def setUp(self):
        super().setUp()
        _delete_test_rows(_TEST_TOOL_NAME)

    def test_source_app_is_written(self):
        tool = _ToolBase(executor=lambda arguments: {"ok": True})
        tool._safe_execute({})

        row = _fetch_latest_audit_row(_TEST_TOOL_NAME)
        self.assertEqual(row["source_app"], "frappe_assistant_core")

    def test_session_and_client_ids_from_frappe_local(self):
        frappe.local.assistant_session_id = "session-abc"
        frappe.local.assistant_client_id = "claude-desktop-test"
        try:
            tool = _ToolBase(executor=lambda arguments: {"ok": True})
            tool._safe_execute({})

            row = _fetch_latest_audit_row(_TEST_TOOL_NAME)
            self.assertEqual(row["session_id"], "session-abc")
            self.assertEqual(row["client_id"], "claude-desktop-test")
        finally:
            # Don't bleed state into other tests
            frappe.local.assistant_session_id = None
            frappe.local.assistant_client_id = None

    def test_large_output_is_truncated_and_flagged(self):
        # BaseTool._sanitize_data clips long values under common keys, so
        # build a payload that survives sanitization but still exceeds the
        # 50KB sink cap. Many small items under an unrecognised key works.
        big_payload = {f"item_{i}": "padding" * 200 for i in range(60)}

        tool = _ToolBase(executor=lambda arguments: big_payload)
        tool._safe_execute({})

        row = _fetch_latest_audit_row(_TEST_TOOL_NAME)
        self.assertEqual(row["output_truncated"], 1)


class TestAuditSinkSanitization(BaseAssistantTest):
    """The sink defensively redacts sensitive keys even if the caller forgot."""

    def test_sink_redacts_sensitive_keys(self):
        from frappe_assistant_core.utils.audit_trail import log_tool_execution

        tool_name = "test_audit_sanitization"
        _delete_test_rows(tool_name)

        log_tool_execution(
            tool_name=tool_name,
            user=frappe.session.user,
            arguments={"password": "hunter2", "doctype": "ToDo"},
            status="Success",
            execution_time=0.01,
            source_app="frappe_assistant_core",
        )

        row = frappe.get_all(
            "Assistant Audit Log",
            filters={"tool_name": tool_name},
            fields=["input_data"],
            order_by="creation desc",
            limit=1,
        )[0]
        self.assertIn("REDACTED", row["input_data"])
        self.assertNotIn("hunter2", row["input_data"])

    def test_invalid_status_is_coerced_to_error(self):
        from frappe_assistant_core.utils.audit_trail import log_tool_execution

        tool_name = "test_audit_invalid_status"
        _delete_test_rows(tool_name)

        log_tool_execution(
            tool_name=tool_name,
            user=frappe.session.user,
            arguments={},
            status="Failed",  # legacy value, not in the Select enum
            execution_time=0.0,
            source_app="frappe_assistant_core",
        )

        row = frappe.get_all(
            "Assistant Audit Log",
            filters={"tool_name": tool_name},
            fields=["status"],
            order_by="creation desc",
            limit=1,
        )[0]
        self.assertEqual(row["status"], "Error")
