# Frappe Assistant Core - browser-tool budget model tests
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0 License

"""The browser-tool wait is three phases, not one flat timeout.

A screenshot call legitimately sits waiting on a human clicking Approve. Sizing
that with the same budget as "the widget is not listening" is what made every
prior fix invisible: the server gave up at 45s while the user was still reading
the approval card, so tuning capture speed changed nothing.

These tests pin the phase transitions and the key-namespacing trap that the
blocking pop depends on.
"""

import threading
import time

import frappe

from frappe_assistant_core.plugins.faco.tools import browser_bridge as bb
from frappe_assistant_core.tests.base_test import BaseAssistantTest


def _answer_after(site: str, call_id: str, delay: float, response: dict) -> threading.Thread:
    """Post a browser result from another thread after `delay` seconds.

    The thread needs its own `frappe.init` — `frappe.local` is thread-local, so
    without it `frappe.cache.make_key` raises AttributeError on `conf`. No
    `frappe.connect()`: this touches Redis only, and opening a second DB
    connection inside the test transaction buys nothing.
    """

    def run():
        frappe.init(site=site)
        try:
            time.sleep(delay)
            bb.store_browser_tool_response(call_id, response)
        finally:
            frappe.destroy()

    t = threading.Thread(target=run)
    t.start()
    return t


class TestNotifyKeyNamespacing(BaseAssistantTest):
    """frappe.cache wraps lpush/rpop with make_key but has NO brpop wrapper.

    A bare brpop reads an un-namespaced key and would block forever against a
    list that lpush wrote under `<db_name>|<key>` — the same trap as hincrby vs
    hget/hset. If this test fails, the waiter is silently deaf to every result.
    """

    def test_blocking_pop_sees_what_lpush_wrote(self):
        call_id = frappe.generate_hash(length=12)
        bb._notify_waiter(call_id)

        popped = bb._await_notification(call_id, block_seconds=1)

        self.assertIsNotNone(popped, "brpop did not observe the lpush — key namespacing drifted")


class TestPhasedWait(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.call_id = frappe.generate_hash(length=12)
        # Register ownership WITHOUT send_browser_tool_call: that publishes to the
        # live user room, and on a dev site with a real tab open the widget
        # answers the test's call for real (it auto-denies when the widget DOM is
        # absent). The wait path only needs the owner record.
        bb._remember_call_owner(self.call_id, frappe.session.user)

    def test_gives_up_fast_when_widget_never_acks(self):
        # The common failure — widget closed / not mounted. Must fail in the ACK
        # window, NOT after the full execution budget.
        started = time.monotonic()
        response, state = bb.wait_for_browser_response(
            self.call_id, timeout=30, ack_timeout=1, block_interval=1
        )
        elapsed = time.monotonic() - started

        self.assertIsNone(response)
        self.assertIsNone(state)
        self.assertLess(elapsed, 5, "did not fail fast on a silent widget")

    def test_awaiting_user_ack_outlives_the_ack_window(self):
        # A human taking longer than ACK_TIMEOUT to click must NOT be treated
        # as a dead widget. This is the regression that kept biting.
        bb.record_call_progress(self.call_id, bb.ACK_AWAITING_USER)
        t = _answer_after(frappe.local.site, self.call_id, 2, {"success": True, "late": True})
        try:
            response, state = bb.wait_for_browser_response(
                self.call_id,
                timeout=30,
                ack_timeout=1,
                user_decision_timeout=10,
                block_interval=1,
            )
        finally:
            t.join()

        self.assertIsNotNone(response, "waiter gave up while the user was still deciding")
        self.assertTrue(response.get("late"))
        self.assertEqual(state, bb.ACK_AWAITING_USER)

    def test_result_is_picked_up_without_polling_lag(self):
        bb.record_call_progress(self.call_id, bb.ACK_EXECUTING)
        bb.store_browser_tool_response(self.call_id, {"success": True})

        started = time.monotonic()
        response, _ = bb.wait_for_browser_response(self.call_id, timeout=30, ack_timeout=5, block_interval=1)
        elapsed = time.monotonic() - started

        self.assertIsNotNone(response)
        self.assertLess(elapsed, 1.0, "blocking pop should return immediately on a ready result")

    def test_out_of_order_acks_never_shrink_the_deadline(self):
        # Acks are fire-and-forget from the browser, so 'executing' can land
        # before 'awaiting_user'. A late-arriving earlier state must not pull
        # the deadline back in and strand a user mid-decision.
        bb.record_call_progress(self.call_id, bb.ACK_AWAITING_USER)
        bb.record_call_progress(self.call_id, bb.ACK_RECEIVED)
        t = _answer_after(frappe.local.site, self.call_id, 2, {"success": True})
        try:
            response, _ = bb.wait_for_browser_response(
                self.call_id,
                timeout=30,
                ack_timeout=1,
                user_decision_timeout=10,
                block_interval=1,
            )
        finally:
            t.join()

        self.assertIsNotNone(response, "a regressing ack shrank the deadline")

    def test_reports_last_state_so_the_error_can_be_specific(self):
        bb.record_call_progress(self.call_id, bb.ACK_EXECUTING)

        response, state = bb.wait_for_browser_response(
            self.call_id, timeout=1, ack_timeout=1, block_interval=1
        )

        self.assertIsNone(response)
        self.assertEqual(state, bb.ACK_EXECUTING)


class TestAckEndpoint(BaseAssistantTest):
    def test_rejects_unknown_call_id(self):
        with self.assertRaises(frappe.PermissionError):
            bb.submit_browser_tool_ack(call_id=frappe.generate_hash(length=12), state=bb.ACK_RECEIVED)

    def test_rejects_malformed_call_id(self):
        with self.assertRaises(frappe.ValidationError):
            bb.submit_browser_tool_ack(call_id="../../etc/passwd", state=bb.ACK_RECEIVED)

    def test_rejects_unknown_state(self):
        call_id = frappe.generate_hash(length=12)
        bb._remember_call_owner(call_id, frappe.session.user)
        with self.assertRaises(frappe.ValidationError):
            bb.submit_browser_tool_ack(call_id=call_id, state="whatever")

    def test_records_progress_for_the_owning_user(self):
        call_id = frappe.generate_hash(length=12)
        bb._remember_call_owner(call_id, frappe.session.user)

        result = bb.submit_browser_tool_ack(call_id=call_id, state=bb.ACK_AWAITING_USER)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(bb.read_call_progress(call_id), bb.ACK_AWAITING_USER)


class TestBudgetInvariants(BaseAssistantTest):
    def test_pending_calls_outlive_the_longest_possible_wait(self):
        # PENDING_CALL_MAX_AGE used to equal the screenshot timeout exactly, so a
        # call drained from the durable queue at the boundary executed against a
        # server that had already given up.
        self.assertGreaterEqual(bb.PENDING_CALL_MAX_AGE, bb.MAX_TOTAL_WAIT)

    def test_owner_record_outlives_the_longest_possible_wait(self):
        self.assertGreater(bb.CALL_OWNER_TTL, bb.MAX_TOTAL_WAIT)

    def test_user_decision_window_is_generous_enough_for_a_human(self):
        self.assertGreaterEqual(bb.USER_DECISION_TIMEOUT, 60)
