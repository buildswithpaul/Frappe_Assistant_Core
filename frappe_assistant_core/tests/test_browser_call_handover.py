# Frappe Assistant Core - Browser call hand-over tests
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Open Full Assistant must never leave a browser call with nobody to answer it (#34689).

Open Full Assistant navigates the Desk tab to the chat app, which destroys the widget and any card
it was showing. The turn claim (#34535) used to retype only the calls still parked on the queue. A
call the widget had already taken (drained on load, or delivered live and acknowledged) was left
waiting on a widget that no longer exists, up to the 120 s approval budget. The claim now works
from the server's record of the calls still being waited on, not from the queue.
"""

import json
import time
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.chat import live_turn
from frappe_assistant_core.chat.api.chat.live_turn import claim_live_turn
from frappe_assistant_core.plugins.faco.tools import browser_bridge
from frappe_assistant_core.plugins.faco.tools.browser_bridge import (
    ACK_AWAITING_USER,
    BROWSER_TOOL_ACK_PREFIX,
    BROWSER_TOOL_NOTIFY_PREFIX,
    BROWSER_TOOL_RESPONSE_PREFIX,
    CALL_OWNER_PREFIX,
    SESSION_CALLS_PREFIX,
    TURN_CLAIM_PREFIX,
    _await_notification,
    _pending_calls_key,
    get_pending_browser_tool_calls,
    release_browser_call,
    send_browser_tool_call,
    submit_browser_tool_ack,
    submit_browser_tool_result,
    wait_for_browser_response,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestBrowserCallHandover(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.session_id = f"sess-handover-{frappe.generate_hash(length=8)}"
        self.call_ids = []
        self.addCleanup(self._clear_redis)
        # The relay starts the live turn when the widget's message is accepted.
        live_turn.start(self.session_id)

    def _clear_redis(self):
        frappe.cache.delete_value(f"{TURN_CLAIM_PREFIX}{self.session_id}")
        frappe.cache.delete_value(f"{SESSION_CALLS_PREFIX}{self.session_id}")
        frappe.cache.delete_value(_pending_calls_key("", self.session_id))
        live_turn.clear(self.session_id)
        for call_id in self.call_ids:
            for prefix in (
                BROWSER_TOOL_RESPONSE_PREFIX,
                BROWSER_TOOL_ACK_PREFIX,
                BROWSER_TOOL_NOTIFY_PREFIX,
                CALL_OWNER_PREFIX,
            ):
                frappe.cache.delete_value(f"{prefix}{call_id}")

    def _send(self, tool_name="take_screenshot"):
        call_id = f"call-{frappe.generate_hash(length=8)}"
        self.call_ids.append(call_id)
        with patch.object(browser_bridge.frappe, "publish_realtime"):
            send_browser_tool_call(
                user=frappe.session.user,
                call_id=call_id,
                tool_name=tool_name,
                params={},
                session_id=self.session_id,
                client_type="widget",
            )
        return call_id

    def _queued_ids(self):
        raw_calls = frappe.cache.lrange(_pending_calls_key("", self.session_id), 0, -1)
        return [json.loads(raw)["call_id"] for raw in reversed(raw_calls)]

    @staticmethod
    def _end_request():
        # The widget's answer, the claim and the wait each run in their own request. On v15 a read
        # with expires=True still consults the request-local cache, which the submit filled with None.
        frappe.local.cache.clear()

    def _widget_drains(self):
        # The widget drains the queue 500 ms after it loads (widget/desk/browserTools.js initialize).
        return get_pending_browser_tool_calls(session_id=self.session_id)

    def _answer_now(self, call_id):
        """What the server's wait returns once the hand-over has answered the call, and how long it took."""
        started = time.monotonic()
        response, _state = wait_for_browser_response(call_id, timeout=1, ack_timeout=1, max_total=5)
        return response, time.monotonic() - started

    def test_a_call_drained_on_load_and_shown_as_a_card_is_answered_at_once_on_claim(self):
        call_id = self._send("take_screenshot")
        self.assertEqual([c["call_id"] for c in self._widget_drains()], [call_id])
        submit_browser_tool_ack(call_id, ACK_AWAITING_USER)

        claim_live_turn(self.session_id)

        # The waiter is parked on the notify list, so the claim must wake it, not only store a result.
        self.assertTrue(_await_notification(call_id, 1))
        response, elapsed = self._answer_now(call_id)
        self.assertLess(elapsed, 2)
        self.assertIn("full chat app", response["error"])
        self.assertIn("browser_take_screenshot again", response["error"])
        self.assertNotIn(call_id, self._queued_ids())

    def test_a_desk_only_call_is_answered_with_the_desk_only_error(self):
        call_id = self._send("get_form_data")
        self._widget_drains()
        submit_browser_tool_ack(call_id, ACK_AWAITING_USER)

        claim_live_turn(self.session_id)

        response, _elapsed = self._answer_now(call_id)
        self.assertIn("works only in the Desk widget", response["error"])

    def test_a_call_delivered_live_with_its_card_open_is_answered_not_re_delivered(self):
        # Delivered over the socket: it also stays on the queue, which only a widget load drains.
        call_id = self._send("take_screenshot")
        submit_browser_tool_ack(call_id, ACK_AWAITING_USER)

        claim_live_turn(self.session_id)

        response, elapsed = self._answer_now(call_id)
        self.assertLess(elapsed, 2)
        self.assertIn("full chat app", response["error"])
        self.assertNotIn(call_id, self._queued_ids())

    def test_a_call_drained_before_its_ack_landed_is_requeued_for_the_chat_app(self):
        # The widget drained it and the tab left before its fire-and-forget ack reached the server.
        call_id = self._send("take_screenshot")
        self._widget_drains()

        claim_live_turn(self.session_id)

        calls = get_pending_browser_tool_calls(session_id=self.session_id)
        self.assertEqual([(c["call_id"], c["client_type"]) for c in calls], [(call_id, "spa")])

    def test_a_call_already_answered_is_not_re_delivered_to_the_chat_app(self):
        call_id = self._send("take_screenshot")
        submit_browser_tool_ack(call_id, ACK_AWAITING_USER)
        submit_browser_tool_result(call_id, result={"file_url": "/files/shot.jpg"})
        self._end_request()
        wait_for_browser_response(call_id, timeout=1, ack_timeout=1, max_total=5)
        # BaseBrowserTool.execute releases the call as its wait ends.
        release_browser_call(self.session_id, call_id)

        claim_live_turn(self.session_id)

        self.assertEqual(self._queued_ids(), [])

    def test_an_answer_that_landed_before_the_claim_is_kept(self):
        call_id = self._send("take_screenshot")
        submit_browser_tool_ack(call_id, ACK_AWAITING_USER)
        # The user approved in the widget just before expanding; the waiter has not read it yet.
        submit_browser_tool_result(call_id, result={"file_url": "/files/shot.jpg"})
        self._end_request()

        claim_live_turn(self.session_id)

        response, _elapsed = self._answer_now(call_id)
        self.assertEqual(response, {"file_url": "/files/shot.jpg"})

    def test_another_clients_call_is_left_alone(self):
        call_id = f"call-{frappe.generate_hash(length=8)}"
        self.call_ids.append(call_id)
        with patch.object(browser_bridge.frappe, "publish_realtime"):
            send_browser_tool_call(
                user=frappe.session.user,
                call_id=call_id,
                tool_name="take_screenshot",
                params={},
                session_id=self.session_id,
                client_type="mobile",
            )
        submit_browser_tool_ack(call_id, ACK_AWAITING_USER)

        claim_live_turn(self.session_id)

        self.assertIsNone(frappe.cache.get_value(f"{BROWSER_TOOL_RESPONSE_PREFIX}{call_id}", expires=True))
        self.assertEqual(self._queued_ids(), [call_id])


class TestBrowserCallRegistry(BaseAssistantTest):
    """The claim relies on every waited-on call being registered until its wait ends."""

    def setUp(self):
        super().setUp()
        self.session_id = f"sess-registry-{frappe.generate_hash(length=8)}"
        self.addCleanup(frappe.cache.delete_value, f"{SESSION_CALLS_PREFIX}{self.session_id}")
        self.addCleanup(frappe.cache.delete_value, _pending_calls_key("", self.session_id))

    def _registered(self):
        return frappe.cache.hkeys(f"{SESSION_CALLS_PREFIX}{self.session_id}")

    def test_a_waited_on_call_is_released_when_its_wait_ends(self):
        from frappe_assistant_core.plugins.faco.tools.browser_take_screenshot import BrowserTakeScreenshot

        seen = []

        def widget_answers(call_id, timeout):
            seen.append(self._registered())
            return {"error": "declined"}, None

        frappe.local.ar_session_id = self.session_id
        self.addCleanup(setattr, frappe.local, "ar_session_id", None)
        with (
            patch.object(browser_bridge.frappe, "publish_realtime"),
            patch.object(browser_bridge, "wait_for_browser_response", side_effect=widget_answers),
        ):
            BrowserTakeScreenshot().execute({})

        self.assertEqual(len(seen[0]), 1)
        self.assertEqual(self._registered(), [])

    def test_navigate_is_not_registered_since_nothing_waits_for_it(self):
        from frappe_assistant_core.plugins.faco.tools.browser_navigate_to import BrowserNavigateTo

        frappe.local.ar_session_id = self.session_id
        self.addCleanup(setattr, frappe.local, "ar_session_id", None)
        with patch.object(browser_bridge.frappe, "publish_realtime"):
            BrowserNavigateTo().execute({"url": "/app/todo"})

        self.assertEqual(self._registered(), [])
