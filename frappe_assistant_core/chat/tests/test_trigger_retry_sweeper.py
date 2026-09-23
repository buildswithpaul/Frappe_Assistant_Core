# Frappe Assistant Core - Powered by FAC Cloud
# Copyright (C) 2026 Paul Clinton
# AGPLv3

"""The retry sweep over fires that never reached AR.

``frappe.enqueue`` has no retry policy, so before this sweep every trigger that
fired during an AR outage was simply lost.
"""

from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.workflows.triggers import sweeper
from frappe_assistant_core.chat.workflows.triggers.log import (
    STATUS_ENQUEUE_FAILED,
    STATUS_RETRY_SCHEDULED,
    write_trigger_log,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestRetrySweeper(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

        self.todo = frappe.get_doc({"doctype": "ToDo", "description": "sweeper probe"}).insert(
            ignore_permissions=True
        )

        self.trigger = frappe.get_doc(
            {
                "doctype": "FAC Workflow Trigger",
                "title": "Sweeper probe",
                "workflow_name": "Sweeper Probe",
                "workflow_docname": "WF-09999",
                "reference_doctype": "ToDo",
                "doctype_event": "on_update",
                "enabled": 1,
            }
        ).insert(ignore_permissions=True)

    def _failed_row(self, docname=None, retry_attempts=0):
        return write_trigger_log(
            self.trigger.name,
            STATUS_ENQUEUE_FAILED,
            reference_doctype="ToDo",
            reference_docname=docname or self.todo.name,
            event="on_update",
            user="Administrator",
            error_message="AR unreachable",
            retry_attempts=retry_attempts,
        )

    def _sweep(self):
        with patch("frappe_assistant_core.chat.gate.is_chat_enabled", return_value=True), patch(
            "frappe_assistant_core.chat.workflows.triggers.sweeper.enqueue_remote_fire"
        ) as enqueue:
            sweeper.sweep_failed_trigger_fires()
        return enqueue

    def _row(self, name):
        return frappe.db.get_value(
            "FAC Workflow Trigger Log", name, ["status", "retry_attempts", "error_message"], as_dict=True
        )

    def test_a_lost_fire_is_re_enqueued_once(self):
        name = self._failed_row()
        enqueue = self._sweep()

        row = self._row(name)
        self.assertEqual(row.status, STATUS_RETRY_SCHEDULED)
        self.assertEqual(row.retry_attempts, 1)

        mine = [c for c in enqueue.call_args_list if c.kwargs.get("trigger_name") == self.trigger.name]
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0].kwargs["attempt"], 1)
        self.assertEqual(mine[0].kwargs["workflow_docname"], "WF-09999")
        self.assertEqual(mine[0].kwargs["payload"]["trigger"]["retry"], 1)

    def test_the_attempt_cap_stops_the_sweep(self):
        name = self._failed_row(retry_attempts=sweeper.MAX_RETRY_ATTEMPTS)
        enqueue = self._sweep()

        self.assertEqual(self._row(name).status, STATUS_ENQUEUE_FAILED)
        mine = [c for c in enqueue.call_args_list if c.kwargs.get("trigger_name") == self.trigger.name]
        self.assertEqual(mine, [])

    def test_a_deleted_document_is_abandoned_with_a_reason(self):
        name = self._failed_row(docname="TODO-does-not-exist")
        self._sweep()

        row = self._row(name)
        self.assertEqual(row.retry_attempts, sweeper.MAX_RETRY_ATTEMPTS)
        self.assertIn("no longer exists", row.error_message)

    def test_a_disabled_trigger_is_abandoned(self):
        frappe.db.set_value("FAC Workflow Trigger", self.trigger.name, "enabled", 0)
        name = self._failed_row()
        self._sweep()

        row = self._row(name)
        self.assertEqual(row.retry_attempts, sweeper.MAX_RETRY_ATTEMPTS)
        self.assertIn("disabled", row.error_message)
