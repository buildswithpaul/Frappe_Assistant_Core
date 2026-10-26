# Frappe Assistant Core - Browser turn claim tests
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Open Full Assistant hands a running turn's browser calls to the chat app (#34535).

A turn the Desk widget started keeps asking for the widget's browser tools after the user expands
to the chat app, and the widget is gone: the page screenshot timed out with "The FAC widget did not
respond". claim_live_turn retypes the conversation's browser calls for the chat app until the next
message starts a new turn.
"""

import json
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.chat import live_turn
from frappe_assistant_core.chat.api.chat.live_turn import claim_live_turn
from frappe_assistant_core.plugins.faco.tools import browser_bridge
from frappe_assistant_core.plugins.faco.tools.browser_bridge import (
    TURN_CLAIM_PREFIX,
    _pending_calls_key,
    release_session_claim,
    send_browser_tool_call,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestClaimLiveTurn(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.session_id = f"sess-claim-{frappe.generate_hash(length=8)}"
        self.addCleanup(self._clear_redis)

    def _clear_redis(self):
        frappe.cache.delete_value(f"{TURN_CLAIM_PREFIX}{self.session_id}")
        frappe.cache.delete_value(_pending_calls_key("", self.session_id))
        live_turn.clear(self.session_id)

    def _send(self, client_type="widget"):
        with patch.object(browser_bridge.frappe, "publish_realtime") as publish:
            send_browser_tool_call(
                user=frappe.session.user,
                call_id=f"call-{frappe.generate_hash(length=6)}",
                tool_name="take_screenshot",
                params={},
                session_id=self.session_id,
                client_type=client_type,
            )
        return publish.call_args.kwargs["message"]

    def _queued(self):
        raw_calls = frappe.cache.lrange(_pending_calls_key("", self.session_id), 0, -1)
        return [json.loads(raw) for raw in reversed(raw_calls)]

    def test_a_running_turn_is_claimed_and_its_widget_calls_go_to_the_chat_app(self):
        # The relay starts the live turn when the widget's message is accepted.
        live_turn.start(self.session_id)

        self.assertEqual(claim_live_turn(self.session_id), {"claimed": True})

        self.assertEqual(self._send("widget")["client_type"], "spa")

    def test_calls_already_queued_for_the_widget_are_retyped_in_order(self):
        live_turn.start(self.session_id)
        first = self._send("widget")
        second = self._send("widget")

        claim_live_turn(self.session_id)

        queued = self._queued()
        self.assertEqual([c["call_id"] for c in queued], [first["call_id"], second["call_id"]])
        self.assertEqual({c["client_type"] for c in queued}, {"spa"})

    def test_without_a_running_turn_nothing_is_claimed(self):
        self.assertEqual(claim_live_turn(self.session_id), {"claimed": False})
        self.assertEqual(self._send("widget")["client_type"], "widget")

    def test_another_users_running_turn_is_not_claimed(self):
        # A turn another user started on a conversation id this user names: start() records its user.
        live_turn._write(self.session_id, {"turn": "t-other", "user": "someone-else@example.com"})

        self.assertEqual(claim_live_turn(self.session_id), {"claimed": False})

    def test_a_conversation_the_caller_does_not_own_is_refused(self):
        frappe.get_doc(
            {
                "doctype": "FAC Chat Message",
                "session_id": self.session_id,
                "user": "Guest",
                "role": "user",
                "content": "hello",
                "timestamp": frappe.utils.now(),
            }
        ).insert(ignore_permissions=True)
        # A System Manager may continue anyone's conversation; the claim is for its owner.
        with patch.object(frappe, "get_roles", autospec=True, return_value=["Employee"]):
            with self.assertRaises(frappe.PermissionError):
                claim_live_turn(self.session_id)

    def test_a_new_turn_releases_the_claim(self):
        live_turn.start(self.session_id)
        claim_live_turn(self.session_id)

        # start_turn calls this before a new turn runs.
        release_session_claim(self.session_id)

        self.assertEqual(self._send("widget")["client_type"], "widget")

    def test_start_turn_releases_the_claim_before_the_new_turn(self):
        from frappe_assistant_core.chat.api.chat import messages

        # Stops right after the release: the rest of start_turn talks to AR.
        with (
            patch.object(messages, "_assert_session_owner", autospec=True),
            patch("frappe_assistant_core.chat.api.settings.can_use_faco", return_value={"can_use": True}),
            patch.object(messages, "clear_cancel", autospec=True),
            patch.object(browser_bridge, "release_session_claim", autospec=True) as release,
            patch.object(messages, "_is_processing_restricted", side_effect=RuntimeError("stop")),
        ):
            with self.assertRaises(RuntimeError):
                messages.start_turn(self.session_id, "hi")

        release.assert_called_once_with(self.session_id)

    def test_a_mobile_or_api_call_is_never_retyped(self):
        live_turn.start(self.session_id)
        claim_live_turn(self.session_id)

        self.assertEqual(self._send("mobile")["client_type"], "mobile")
