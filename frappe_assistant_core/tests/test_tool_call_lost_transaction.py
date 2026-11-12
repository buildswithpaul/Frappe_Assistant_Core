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
A tool call whose transaction MariaDB rolls back whole must never be reported as a success.

Two calls at once (FAC Cloud runs tools in parallel) each take a number from a naming series. On
MariaDB 11.6+, whose innodb_snapshot_isolation is on by default, the second one gets error 1020
("Record has changed since last read in table 'tabSeries'") and MariaDB rolls its whole transaction
back: the tool's own writes go with it. Every call takes one for its audit row after the tool has
run, and the audit logger swallowed the error, so the call said success while nothing was saved
(PR #392 hands-on test, F1). A tool's own series (an import session's) failed with the raw database
error instead (F3).

MariaDB 10.6 has no snapshot isolation, so these tests stand the database in: they raise
frappe.QueryDeadlockError (what Frappe raises for both 1213 and 1020). The tool call undoes its work
itself, to the savepoint it took when it started (MariaDB has already undone it on 11.6+).
"""

from typing import Any, Dict
from unittest.mock import patch

import frappe
from frappe.model.document import Document

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.tests.base_test import BaseAssistantTest

_TOOL = "test_lost_transaction_tool"
_MARK = "lost transaction test"


class _Tool(BaseTool):
    def __init__(self, executor, retry=False):
        super().__init__()
        self.name = _TOOL
        self.description = "Test tool"
        self.inputSchema = {"type": "object", "properties": {}}
        self.requires_permission = None
        self.source_app = "frappe_assistant_core"
        self.retry_on_deadlock = retry
        self._executor = executor

    def execute(self, arguments: Dict[str, Any]) -> Any:
        return self._executor(arguments)


def _write_note(arguments):
    """The tool's own work: one ToDo."""
    frappe.get_doc({"doctype": "ToDo", "description": _MARK}).insert(ignore_permissions=True)
    return {"saved": True}


def _notes() -> int:
    return frappe.db.count("ToDo", {"description": _MARK})


def _lose_transaction():
    """The error MariaDB gives when it rolls the transaction back: 1020, or a deadlock (1213)."""
    raise frappe.QueryDeadlockError(
        "(1020, \"Record has changed since last read in table 'tabSeries'; try restarting transaction\")"
    )


class TestToolCallLostTransaction(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.db.delete("ToDo", {"description": _MARK})
        frappe.db.delete("Assistant Audit Log", {"tool_name": _TOOL})

    def _audit_insert_loses_once(self):
        """The first audit row's insert loses the call's transaction, as two calls at once did."""
        real_insert = Document.insert
        lost = []

        def insert(doc, *args, **kwargs):
            if doc.doctype == "Assistant Audit Log" and not lost:
                lost.append(doc)
                _lose_transaction()
            return real_insert(doc, *args, **kwargs)

        return patch.object(Document, "insert", insert)

    def test_the_audit_row_takes_no_naming_series_number(self):
        """The audit row is written by every call, after the tool: a series number there is what
        made parallel calls collide. Its name keeps the date, with a random part for the number."""

        def no_series(*args, **kwargs):
            raise AssertionError("the audit row took a naming series number")

        with patch("frappe.model.naming.getseries", no_series):
            response = _Tool(_write_note)._safe_execute({})

        self.assertTrue(response["success"], response)
        name = frappe.db.get_value("Assistant Audit Log", {"tool_name": _TOOL}, "name")
        self.assertTrue(name.startswith("ASST-AUDIT-" + frappe.utils.nowdate()), name)

    def test_a_transaction_lost_while_auditing_is_not_reported_as_success(self):
        with self._audit_insert_loses_once():
            response = _Tool(_write_note)._safe_execute({})

        self.assertEqual(_notes(), 0)  # the database undid the tool's work...
        self.assertFalse(response["success"], response)  # ...so the call must not say it worked
        self.assertEqual(response["error_type"], "DatabaseBusy")
        self.assertIn("nothing from it was saved", response["error"])
        self.assertTrue(response.get("own_message"))

    def test_a_tool_that_can_run_again_is_run_again(self):
        calls = []

        def executor(arguments):
            calls.append(1)
            return _write_note(arguments)

        with self._audit_insert_loses_once():
            response = _Tool(executor, retry=True)._safe_execute({})

        self.assertTrue(response["success"], response)
        self.assertEqual(len(calls), 2)
        self.assertEqual(_notes(), 1)  # saved once: the lost attempt left nothing behind

    def test_a_deadlock_inside_the_tool_is_run_again(self):
        calls = []

        def executor(arguments):
            calls.append(1)
            _write_note(arguments)
            if len(calls) == 1:
                _lose_transaction()
            return {"saved": True}

        response = _Tool(executor, retry=True)._safe_execute({})

        self.assertTrue(response["success"], response)
        self.assertEqual(_notes(), 1)

    def test_a_deadlock_inside_a_tool_that_cannot_run_again_says_so_plainly(self):
        def executor(arguments):
            _write_note(arguments)
            _lose_transaction()

        response = _Tool(executor)._safe_execute({})

        self.assertFalse(response["success"])
        self.assertEqual(response["error_type"], "DatabaseBusy")
        self.assertNotIn("Record has changed", response["error"])  # not the raw database error
        self.assertEqual(_notes(), 0)

    def test_it_gives_up_after_a_few_tries(self):
        calls = []

        def executor(arguments):
            calls.append(1)
            _lose_transaction()

        response = _Tool(executor, retry=True)._safe_execute({})

        self.assertFalse(response["success"])
        self.assertEqual(response["error_type"], "DatabaseBusy")
        self.assertEqual(len(calls), 3)


class TestMigrationToolsOnALostTransaction(BaseAssistantTest):
    """The migration tools catch their own errors: a lost transaction must get past them."""

    def test_the_tools_that_only_prepare_are_run_again_and_the_imports_are_not(self):
        from frappe_assistant_core.plugins.migration import tools

        again = {
            "get_import_schema",
            "start_import_session",
            "set_column_mapping",
            "dry_run_import",
            "plan_migration",
            "stop_migration_plan",
            "set_opening_balances",
            "set_opening_invoices",
            "set_opening_stock",
        }
        never = {
            "start_import",
            "run_migration_plan",
            "import_opening_balances",
            "import_opening_invoices",
            "import_opening_stock",
        }
        found = {}
        for module_name in again | never:
            module = frappe.get_module(f"{tools.__name__}.{module_name}")
            for value in vars(module).values():
                if isinstance(value, type) and issubclass(value, BaseTool) and value is not BaseTool:
                    tool = value()
                    if tool.name == module_name:
                        found[module_name] = tool.retry_on_deadlock
        self.assertEqual(set(found), again | never)
        self.assertEqual({n for n, r in found.items() if r}, again)

    def test_a_session_whose_series_number_collides_is_opened_on_the_next_try(self):
        """F3: two files opened at once collided on the import sessions' naming series."""
        from frappe_assistant_core.plugins.migration.tools.start_import_session import StartImportSession

        content = "Customer Name,Customer Type\nLost Trx Co,Company\n"
        file_doc = frappe.get_doc(
            {"doctype": "File", "file_name": "lost_trx.csv", "is_private": 1, "content": content}
        ).insert(ignore_permissions=True)

        real_create = StartImportSession._create_session
        tries = []

        def create(tool, *args, **kwargs):
            tries.append(1)
            if len(tries) == 1:
                _lose_transaction()
            return real_create(tool, *args, **kwargs)

        with patch.object(StartImportSession, "_create_session", create):
            response = StartImportSession()._safe_execute(
                {"file_id": file_doc.name, "target_doctype": "Customer"}
            )

        self.assertTrue(response["success"], response)
        session = response["result"]["session_id"]
        self.assertTrue(frappe.db.exists("FAC Import Session", session))
        self.assertEqual(len(tries), 2)
