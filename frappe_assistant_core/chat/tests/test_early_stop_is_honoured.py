# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""An early Stop is always honoured.

send_message, resume_interrupt and continue_response accept a turn and queue
its relay on a thread pool. The relay cleared the session's cancel flag as it
started, so a Stop that landed after the endpoint accepted the turn, but before
the relay thread started, was erased: the turn ran to completion and billed
while the SPA already showed it stopped. On a resume, the approved tool ran.
Each endpoint now clears the flag as it accepts the turn, the relay checks the
flag before it contacts AR, and nothing else clears it.

Runs as a throwaway user against real FAC Chat Message rows and the real cancel
flag, on a session of its own per test. The relay pool, AR, the socket, the
quota cache and the relay's worker-thread Frappe context are stubbed.
"""

import json
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.api.chat import cancel as cancel_mod
from frappe_assistant_core.chat.api.chat import messages as messages_mod
from frappe_assistant_core.chat.api.chat import relay
from frappe_assistant_core.tests.base_test import BaseAssistantTest

MARKER = cancel_mod.ABORT_MARKER_TEXT
QUESTION = "Which invoices are overdue?"
ANSWER = "Two are overdue."
PAUSED_TEXT = "I will create the ToDo once you approve."
PENDING_CARD = {
    "type": "interaction",
    "id": "toolu_1",
    "interactionType": "approval",
    "tool_name": "create_document",
    "interrupts": [{"id": "int-1", "name": "create_document", "reason": {"type": "approval"}}],
    "status": "pending",
}
APPROVE = json.dumps([{"interruptId": "int-1", "response": "approve"}])
TRUNCATED_TEXT = "Here is the first half of the report"


def _event(name: str, **data) -> dict:
    return {"event": name, "data": data}


def _turn(message_id: str, **start) -> list[dict]:
    """AR's events for a turn that runs to completion and costs 2 credits."""
    return [
        _event("stream_start", message_id=message_id, zero_retention=False, **start),
        _event("stream_chunk", content=ANSWER),
        _event("stream_complete", full_response=ANSWER, credits_used=2, model="m"),
    ]


# Each endpoint with its arguments, and the AR events of the turn it starts.
ENDPOINTS = (
    ("send_message", {"message": QUESTION}, _turn("msg-new")),
    (
        "resume_interrupt",
        {"interrupt_response": APPROVE, "message_id": "msg-paused"},
        _turn("msg-paused", resumed=True),
    ),
    ("continue_response", {"message_id": "msg-truncated"}, _turn("msg-truncated")),
)


class TestAnEarlyStopIsHonoured(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("early-stop")
        frappe.set_user(self.user)
        self.sid = f"early-stop-{frappe.generate_hash(length=8)}"
        self.paused = self._row(
            PAUSED_TEXT,
            [{"type": "text", "id": "text-1", "content": PAUSED_TEXT}, PENDING_CARD],
            message_id="msg-paused",
        )
        self.truncated = self._row(
            TRUNCATED_TEXT,
            [{"type": "text", "id": "text-2", "content": TRUNCATED_TEXT}],
            message_id="msg-truncated",
        )

    def tearDown(self):
        cancel_mod.clear(self.sid)
        frappe.set_user("Administrator")
        super().tearDown()

    def _row(self, content: str, blocks: list, message_id: str) -> str:
        return (
            frappe.get_doc(
                {
                    "doctype": "FAC Chat Message",
                    "session_id": self.sid,
                    "message_id": message_id,
                    "user": self.user,
                    "role": "assistant",
                    "content": content,
                    "blocks": json.dumps(blocks),
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def _stored(self, name: str):
        row = frappe.db.get_value("FAC Chat Message", name, ["content", "blocks", "aborted"], as_dict=True)
        return row, json.loads(row.blocks or "[]")

    def _accept(self, endpoint: str, **kwargs) -> tuple:
        """Call ``endpoint`` as the user; return the relay call it queued and
        whether the cancel flag was up when it queued it."""
        queued = []

        def submit(fn, *args, **kw):
            queued.append((fn, args, kw, cancel_mod.is_cancelled(self.sid)))

        with patch(
            "frappe_assistant_core.chat.api.settings.can_use_faco", return_value={"can_use": True}
        ), patch.object(messages_mod._relay_pool, "submit", side_effect=submit):
            getattr(messages_mod, endpoint)(session_id=self.sid, **kwargs)
        self.assertEqual(len(queued), 1)
        return queued[0]

    def _relay(self, queued: tuple, events) -> tuple:
        """Run the queued relay over AR ``events``. Returns the AR client, the
        socket payloads and the quota-cache increment mock."""
        fn, args, kwargs, _flag_at_queue = queued
        client = MagicMock()
        client.stream_chat.return_value = iter(events)
        emitted = []

        def emit(_sid, payload):
            emitted.append(payload)

        with ExitStack() as stack:
            enter = stack.enter_context
            enter(
                patch(
                    "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
                    return_value=client,
                )
            )
            # The relay opens and tears down a worker-thread Frappe context; here it
            # runs inside the test's. set_user is stubbed because the real one resets
            # the running session.
            for name in ("init", "connect", "set_user", "destroy"):
                enter(patch(f"frappe.{name}"))
            enter(patch.object(relay, "_emit_socket_event", side_effect=emit))
            enter(patch.object(cancel_mod, "_emit_socket_event", side_effect=emit))
            billed = enter(patch.object(relay, "_update_subscription_cache"))
            enter(
                patch(
                    "frappe_assistant_core.chat.quota_cache.get_quota_snapshot",
                    return_value={"quota_used": 0, "quota_total": 100},
                )
            )
            fn(*args, **kwargs)
        return client, emitted, billed

    def test_each_endpoint_clears_an_earlier_stop_before_it_queues_the_relay(self):
        """A Stop pressed during the previous turn's approval pause, or after it
        ended, leaves the flag up with no relay running to consume it."""
        for endpoint, kwargs, _events in ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                cancel_mod.mark_cancelled(self.sid)

                *_call, flag_at_queue = self._accept(endpoint, **kwargs)

                self.assertFalse(flag_at_queue)

    def test_a_refused_call_never_clears_a_flag_raised_for_a_turn_still_open(self):
        """Each endpoint clears the flag only after its ownership and
        access checks pass. Moving the clear above either check would erase a
        Stop that belongs to a still-open earlier turn even though a refused
        call never queues a relay to observe it."""
        other_user = self.make_throwaway_user("early-stop-other")
        for endpoint, kwargs, _events in ENDPOINTS:
            with self.subTest(endpoint=endpoint, refusal="ownership"):
                cancel_mod.mark_cancelled(self.sid)
                frappe.set_user(other_user)
                try:
                    with self.assertRaises(frappe.PermissionError):
                        getattr(messages_mod, endpoint)(session_id=self.sid, **kwargs)
                finally:
                    frappe.set_user(self.user)
                self.assertTrue(cancel_mod.is_cancelled(self.sid))

            with self.subTest(endpoint=endpoint, refusal="access"):
                cancel_mod.mark_cancelled(self.sid)
                with patch(
                    "frappe_assistant_core.chat.api.settings.can_use_faco",
                    return_value={"can_use": False, "reason": "Plan limit reached"},
                ), self.assertRaises(frappe.ValidationError):
                    getattr(messages_mod, endpoint)(session_id=self.sid, **kwargs)
                self.assertTrue(cancel_mod.is_cancelled(self.sid))

    def test_a_stop_from_an_earlier_turn_does_not_stop_the_next_one(self):
        for endpoint, kwargs, events in ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                cancel_mod.mark_cancelled(self.sid)

                client, emitted, billed = self._relay(self._accept(endpoint, **kwargs), events)

                client.stream_chat.assert_called_once()
                self.assertEqual(emitted[-1]["event"], "stream_complete")
                self.assertNotIn("stream_aborted", [p["event"] for p in emitted])
                billed.assert_called_once_with(2)

    def test_a_stop_after_the_send_was_accepted_stops_the_turn_before_ar(self):
        queued = self._accept("send_message", message=QUESTION)
        cancel_mod.mark_cancelled(self.sid)  # Stop, before the relay thread starts

        client, emitted, billed = self._relay(queued, _turn("msg-new"))

        client.stream_chat.assert_not_called()
        billed.assert_not_called()
        self.assertEqual([p["event"] for p in emitted], ["stream_aborted"])
        self.assertIsNone(emitted[0]["message_id"])
        # AR never named the turn, so its row has no message_id (tier 3).
        stopped = frappe.get_all(
            "FAC Chat Message",
            filters={"session_id": self.sid, "role": "assistant", "message_id": ("is", "not set")},
            fields=["content", "aborted"],
        )
        self.assertEqual([(row.content, row.aborted) for row in stopped], [(MARKER, 1)])

    def test_a_stop_after_a_resume_was_accepted_never_sends_the_approval(self):
        queued = self._accept("resume_interrupt", interrupt_response=APPROVE, message_id="msg-paused")
        cancel_mod.mark_cancelled(self.sid)

        client, emitted, billed = self._relay(queued, _turn("msg-paused", resumed=True))

        client.stream_chat.assert_not_called()
        billed.assert_not_called()
        row, blocks = self._stored(self.paused)
        card = next(b for b in blocks if b["type"] == "interaction")
        self.assertEqual((card["status"], card["result"]), ("aborted", {"message": "Stopped by user"}))
        self.assertEqual(row.content, PAUSED_TEXT + MARKER)
        self.assertTrue(row.aborted)
        self.assertEqual([p["event"] for p in emitted], ["stream_aborted"])
        self.assertEqual(emitted[0]["message_id"], "msg-paused")

    def test_a_stop_after_a_continue_was_accepted_stops_it_before_ar(self):
        queued = self._accept("continue_response", message_id="msg-truncated")
        cancel_mod.mark_cancelled(self.sid)

        client, emitted, billed = self._relay(queued, _turn("msg-truncated"))

        client.stream_chat.assert_not_called()
        billed.assert_not_called()
        self.assertEqual([p["event"] for p in emitted], ["stream_aborted"])
        row, _blocks = self._stored(self.truncated)
        self.assertTrue(row.content.startswith(TRUNCATED_TEXT))

    def test_a_finishing_relay_leaves_a_later_stop_for_the_next_turn(self):
        """AR closes a turn's response only after its stream_complete, and the
        client may already have sent the next turn. A Stop raised then belongs
        to that turn: the finishing relay must not erase it."""
        queued = self._accept("send_message", message=QUESTION)

        def ar_stream():
            yield from _turn("msg-new")
            cancel_mod.mark_cancelled(self.sid)

        self._relay(queued, ar_stream())

        self.assertTrue(cancel_mod.is_cancelled(self.sid))
