# Frappe Assistant Core - Powered by FAC Cloud
# Copyright (C) 2026 Paul Clinton
# AGPLv3

"""The trigger loop circuit breaker and the filtered-out log row.

The obvious first workflow anyone builds — "on Sales Order update, summarize
and write it back" — re-enters `on_update` through the customer's own MCP
server, so it loops, billed, at up to the rate limit. The static DocType
blocklist cannot see that; only a per-document counter can.
"""

from contextlib import contextmanager
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.workflows.triggers import breaker, dispatcher
from frappe_assistant_core.tests.base_test import BaseAssistantTest

MAX_FIRES = 3
WINDOW_SECONDS = 60


@contextmanager
def _conf(**values):
    """Override site_config keys for the duration of the block."""
    sentinel = object()
    previous = {key: frappe.conf.get(key, sentinel) for key in values}
    frappe.conf.update(values)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is sentinel:
                frappe.conf.pop(key, None)
            else:
                frappe.conf[key] = value


class _TriggerFixture(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

        self.todo = frappe.get_doc({"doctype": "ToDo", "description": "loop breaker probe"}).insert(
            ignore_permissions=True
        )

        self.trigger = frappe.get_doc(
            {
                "doctype": "FAC Workflow Trigger",
                "title": "Loop breaker probe",
                "workflow_name": "Loop Probe",
                "reference_doctype": "ToDo",
                "doctype_event": "on_update",
                "enabled": 1,
            }
        ).insert(ignore_permissions=True)

        # Redis outlives the test transaction, so counters are cleared on both
        # sides of the test rather than left to leak into the next run.
        self._clear_breaker()
        self.addCleanup(self._clear_breaker)

    def _clear_breaker(self):
        breaker.reset(self.trigger.name, "ToDo", self.todo.name)
        cache = frappe.cache()
        cache.delete(cache.make_key(f"fac_trigger_filtered:{self.trigger.name}:ToDo"))

    def _fire(self, times):
        """Run the dispatcher's per-trigger path N times, recording dispatches."""
        with patch("frappe_assistant_core.chat.workflows.triggers.remote.enqueue_remote_fire") as enqueue:
            for _i in range(times):
                dispatcher._process_trigger(self.trigger.name, self.todo, "on_update")
        return enqueue.call_args_list

    def _log_rows(self, status):
        return frappe.get_all(
            "FAC Workflow Trigger Log",
            filters={"trigger": self.trigger.name, "status": status},
            fields=["name", "error_message", "reference_docname"],
        )


class TestTriggerLoopBreaker(_TriggerFixture):
    def test_n_plus_one_fires_produce_n_dispatches_and_one_refusal(self):
        with _conf(
            fac_trigger_breaker_max_fires=MAX_FIRES,
            fac_trigger_breaker_window_seconds=WINDOW_SECONDS,
        ):
            calls = self._fire(MAX_FIRES + 1)

        self.assertEqual(len(calls), MAX_FIRES)

        refusals = self._log_rows("loop_blocked")
        self.assertEqual(len(refusals), 1)
        self.assertIn("Loop guard", refusals[0].error_message)
        self.assertEqual(refusals[0].reference_docname, self.todo.name)

    def test_a_runaway_loop_writes_only_one_refusal_row(self):
        with _conf(
            fac_trigger_breaker_max_fires=MAX_FIRES,
            fac_trigger_breaker_window_seconds=WINDOW_SECONDS,
        ):
            calls = self._fire(MAX_FIRES + 20)

        self.assertEqual(len(calls), MAX_FIRES)
        self.assertEqual(len(self._log_rows("loop_blocked")), 1)

    def test_a_second_document_gets_its_own_budget(self):
        other = frappe.get_doc({"doctype": "ToDo", "description": "second doc"}).insert(
            ignore_permissions=True
        )
        self.addCleanup(breaker.reset, self.trigger.name, "ToDo", other.name)

        with _conf(
            fac_trigger_breaker_max_fires=MAX_FIRES,
            fac_trigger_breaker_window_seconds=WINDOW_SECONDS,
        ):
            self._fire(MAX_FIRES + 1)
            with patch("frappe_assistant_core.chat.workflows.triggers.remote.enqueue_remote_fire") as enqueue:
                dispatcher._process_trigger(self.trigger.name, other, "on_update")

        self.assertEqual(enqueue.call_count, 1)

    def test_zero_disables_the_breaker(self):
        with _conf(fac_trigger_breaker_max_fires=0):
            calls = self._fire(MAX_FIRES + 4)

        self.assertEqual(len(calls), MAX_FIRES + 4)
        self.assertEqual(self._log_rows("loop_blocked"), [])


class TestFilteredOutIsVisible(_TriggerFixture):
    def setUp(self):
        super().setUp()
        self.trigger.append("filters", {"fieldname": "status", "operator": "=", "value": "Closed"})
        self.trigger.save(ignore_permissions=True)

    def test_a_filtered_out_fire_says_which_filter_stopped_it(self):
        calls = self._fire(1)

        self.assertEqual(len(calls), 0)
        rows = self._log_rows("filtered_out")
        self.assertEqual(len(rows), 1)
        self.assertIn("status", rows[0].error_message)
        self.assertIn("Closed", rows[0].error_message)

    def test_filtered_out_rows_are_sampled(self):
        self._fire(5)
        self.assertEqual(len(self._log_rows("filtered_out")), 1)
