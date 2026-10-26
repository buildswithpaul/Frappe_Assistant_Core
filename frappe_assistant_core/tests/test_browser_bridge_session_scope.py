# Frappe Assistant Core - Browser Bridge Session Scoping Tests
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Browser tool calls must address one conversation, not one user.

Emitting to the user room delivered every call to every open tab, so the wrong
tab could execute it and answer with the wrong page's state — and
browser_navigate_to navigated all of them. Delivery is session-scoped whenever
AR supplies the conversation id, and falls back to the user room when it does
not (an older AR that never sends the header).
"""

import unittest
from unittest.mock import patch

import frappe

from frappe_assistant_core.plugins.faco.tools.browser_bridge import (
    PENDING_CALLS_PREFIX,
    _pending_calls_key,
    send_browser_tool_call,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest

_MOD = "frappe_assistant_core.plugins.faco.tools.browser_bridge"


def _send(session_id):
    """Dispatch one call, returning (publish_realtime mock, cache mock)."""
    with patch(f"{_MOD}.frappe.publish_realtime") as publish, patch(f"{_MOD}.frappe.cache") as cache:
        send_browser_tool_call(
            user="owner@example.com",
            call_id="call-1",
            tool_name="browser_get_page_context",
            params={},
            session_id=session_id,
        )
    return publish, cache


class TestSessionScopedDelivery(unittest.TestCase):
    def test_call_targets_the_session_room(self):
        publish, _ = _send("sess-abc")
        kwargs = publish.call_args.kwargs
        self.assertEqual(kwargs["room"], "task_progress:sess-abc")
        self.assertIsNone(kwargs.get("user"))

    def test_payload_carries_the_session_so_the_widget_can_filter(self):
        publish, _ = _send("sess-abc")
        self.assertEqual(publish.call_args.kwargs["message"]["session_id"], "sess-abc")

    def test_queue_is_session_scoped_so_another_tab_cannot_drain_it(self):
        _, cache = _send("sess-abc")
        self.assertEqual(cache.lpush.call_args.args[0], f"{PENDING_CALLS_PREFIX}session:sess-abc")

    def test_queued_call_records_its_session(self):
        import json

        _, cache = _send("sess-abc")
        queued = json.loads(cache.lpush.call_args.args[1])
        self.assertEqual(queued["session_id"], "sess-abc")


class TestUserRoomFallback(unittest.TestCase):
    """An AR that does not send X-AR-Session-Id must behave exactly as before."""

    def test_call_without_a_session_targets_the_user(self):
        publish, _ = _send(None)
        kwargs = publish.call_args.kwargs
        self.assertEqual(kwargs["user"], "owner@example.com")
        self.assertIsNone(kwargs.get("room"))

    def test_queue_without_a_session_stays_per_user(self):
        _, cache = _send(None)
        self.assertEqual(cache.lpush.call_args.args[0], f"{PENDING_CALLS_PREFIX}owner@example.com")

    def test_send_and_drain_agree_on_the_key(self):
        # The widget drains with the same helper the sender keys on; a mismatch
        # would strand every queued call.
        for session_id in ("sess-abc", None):
            _, cache = _send(session_id)
            self.assertEqual(
                cache.lpush.call_args.args[0],
                _pending_calls_key("owner@example.com", session_id),
            )


class TestOwnershipStillEnforced(unittest.TestCase):
    def test_owner_record_is_written_regardless_of_session(self):
        # submit_browser_tool_result refuses a call with no owner record, so
        # session scoping must not skip writing it.
        for session_id in ("sess-abc", None):
            _, cache = _send(session_id)
            keys = [c.args[0] for c in cache.set_value.call_args_list]
            self.assertTrue(any(k.endswith("call-1") for k in keys))


class TestClientTypeIsCarried(BaseAssistantTest):
    """The widget and the chat app can hold the same conversation and both sit in its room, so a
    call must say which client's turn asked; each answers only its own."""

    def _send(self, client_type):
        # Only the queue push and the owner record are replaced, on the real cache object, so
        # frappe.cache itself stays the site's cache for anything else in the test.
        with patch(f"{_MOD}.frappe.publish_realtime", autospec=True) as publish, patch.object(
            frappe.cache, "lpush", autospec=True
        ) as lpush, patch.object(frappe.cache, "set_value", autospec=True):
            send_browser_tool_call(
                user="owner@example.com",
                call_id="call-1",
                tool_name="take_screenshot",
                params={},
                session_id="sess-abc",
                client_type=client_type,
            )
        return publish, lpush

    def test_socket_and_queue_payloads_carry_the_client_type(self):
        import json

        publish, lpush = self._send("spa")
        self.assertEqual(publish.call_args.kwargs["message"]["client_type"], "spa")
        self.assertEqual(json.loads(lpush.call_args.args[1])["client_type"], "spa")

    def test_an_older_ar_sends_none(self):
        publish, _ = self._send(None)
        self.assertIsNone(publish.call_args.kwargs["message"]["client_type"])

    def test_the_browser_tool_passes_the_turns_client_type(self):
        from frappe_assistant_core.plugins.faco.tools.browser_take_screenshot import BrowserTakeScreenshot

        # fac_endpoint sets these from AR's X-AR-Session-Id and X-AR-Client-Type headers.
        with patch(f"{_MOD}.send_browser_tool_call", autospec=True) as send, patch(
            f"{_MOD}.wait_for_browser_response", autospec=True, return_value=(None, None)
        ), patch.object(frappe.local, "ar_session_id", "sess-abc", create=True), patch.object(
            frappe.local, "ar_client_type", "spa", create=True
        ):
            BrowserTakeScreenshot().execute({})
        self.assertEqual(send.call_args.kwargs["client_type"], "spa")


if __name__ == "__main__":
    unittest.main()
