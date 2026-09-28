# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""A Stop that names no turn changes only a reply that is really still open.

A Stop can reach ``cancel_stream`` without a ``message_id`` that names a stored
turn: it may come before the new turn's ``stream_start``, and the SPA always
sends a client-side id of its own. ``_abort_pending_interactions`` then took
the session's latest assistant row and marked it aborted with "(Stopped by
user)", even when that row was the previous, finished answer. The send relay's
abort finalizer made the same fallback before AR's ``stream_start`` and
replaced that answer's text with the bare marker.

Runs as a throwaway user against real FAC Chat Message rows, rolled back with
the class. The cancel flag, AR, the socket and the relay's worker-thread Frappe
context are stubbed.
"""

import json
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.api.chat import cancel as cancel_mod
from frappe_assistant_core.chat.api.chat import relay
from frappe_assistant_core.tests.base_test import BaseAssistantTest

MARKER = cancel_mod.ABORT_MARKER_TEXT
PREVIOUS_TEXT = "Here are the three open invoices."
PREVIOUS_BLOCKS = [{"type": "text", "id": "text-prev", "content": PREVIOUS_TEXT}]
PAUSED_TEXT = "I will create the ToDo once you approve."
PENDING_CARD = {
    "type": "interaction",
    "id": "toolu_1",
    "interactionType": "approval",
    "tool_name": "create_document",
    "status": "pending",
}
QUESTION = "And the overdue ones?"


def _event(name: str, **data) -> dict:
    return {"event": name, "data": data}


class TestStopWithoutANamedTurn(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("stop-unnamed")
        frappe.set_user(self.user)
        self.sid = f"stop-unnamed-{frappe.generate_hash(length=8)}"

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _row(self, role, content, blocks=None, message_id=None, aborted=0) -> str:
        return (
            frappe.get_doc(
                {
                    "doctype": "FAC Chat Message",
                    "session_id": self.sid,
                    "message_id": message_id,
                    "user": self.user,
                    "role": role,
                    "content": content,
                    "blocks": json.dumps(blocks) if blocks is not None else None,
                    "aborted": aborted,
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def _previous_answer(self) -> str:
        """A finished answer, then the question of the turn the user stops."""
        name = self._row("assistant", PREVIOUS_TEXT, PREVIOUS_BLOCKS, message_id="msg-previous")
        self._row("user", QUESTION)
        return name

    def _stored(self, name: str):
        row = frappe.db.get_value("FAC Chat Message", name, ["content", "blocks", "aborted"], as_dict=True)
        return row, (json.loads(row.blocks) if row.blocks else [])

    def assertUntouched(self, name: str):
        row, blocks = self._stored(name)
        self.assertEqual((row.content, blocks, row.aborted), (PREVIOUS_TEXT, PREVIOUS_BLOCKS, 0))

    def _cancel(self, message_id=None) -> list[dict]:
        """Press Stop through the endpoint; return the socket payloads it emitted."""
        emitted = []
        with ExitStack() as stack:
            enter = stack.enter_context
            enter(patch.object(cancel_mod, "mark_cancelled"))
            enter(
                patch(
                    "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
                    return_value=None,
                )
            )
            enter(
                patch.object(
                    cancel_mod,
                    "_emit_socket_event",
                    side_effect=lambda _sid, payload: emitted.append(payload),
                )
            )
            cancel_mod.cancel_stream(self.sid, message_id)
        return emitted

    def _relay(self, *events, polls) -> list[dict]:
        """Run the send relay over ``events``, the cancel flag answering ``polls`` in turn."""
        client = MagicMock()
        client.stream_chat.return_value = (event for event in events)
        emitted = []
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
            enter(patch.object(relay, "clear_cancel"))
            enter(patch.object(relay, "is_cancelled", side_effect=list(polls)))
            enter(
                patch.object(
                    relay, "_emit_socket_event", side_effect=lambda _sid, payload: emitted.append(payload)
                )
            )
            relay._relay_ar_stream(
                session_id=self.sid,
                full_prompt=QUESTION,
                original_message=QUESTION,
                context=None,
                message_name=None,
                user=self.user,
                site=frappe.local.site,
            )
        return emitted

    def test_a_stop_before_the_turn_is_named_leaves_the_previous_answer_alone(self):
        previous = self._previous_answer()
        # No id (the phone, before stream_start), or an id no row carries (the SPA's _requestId).
        for message_id in (None, "spa-request-5f0c"):
            with self.subTest(message_id=message_id):
                frappe.db.set_value(
                    "FAC Chat Message",
                    previous,
                    {"content": PREVIOUS_TEXT, "blocks": json.dumps(PREVIOUS_BLOCKS), "aborted": 0},
                )
                emitted = self._cancel(message_id)

                self.assertUntouched(previous)
                self.assertEqual([p["event"] for p in emitted], ["stream_cancel_requested"])

    def test_a_stop_leaves_a_stale_pending_card_alone_once_a_newer_turn_has_begun(self):
        """A pending card AR expired (or a caller other than the SPA's
        abort-then-send composer left unresolved) is an *older* turn once a
        new user message follows it. A no-id Stop must not reach back into it."""
        stale_blocks = [{"type": "text", "id": "text-1", "content": PAUSED_TEXT}, PENDING_CARD]
        stale = self._row("assistant", PAUSED_TEXT, stale_blocks, message_id="msg-stale")
        self._row("user", QUESTION)

        self._cancel(None)

        row, blocks = self._stored(stale)
        self.assertEqual((row.content, blocks, row.aborted), (PAUSED_TEXT, stale_blocks, 0))

    def test_a_stop_while_paused_at_an_approval_still_aborts_the_card(self):
        previous = self._previous_answer()
        paused = self._row(
            "assistant",
            PAUSED_TEXT,
            [{"type": "text", "id": "text-1", "content": PAUSED_TEXT}, PENDING_CARD],
            message_id="msg-paused",
        )

        emitted = self._cancel(None)

        row, blocks = self._stored(paused)
        card = next(b for b in blocks if b["type"] == "interaction")
        self.assertEqual(card["status"], "aborted")
        self.assertEqual(card["result"], {"message": "Stopped by user"})
        self.assertTrue(blocks[-1].get("_abortMarker"))
        self.assertEqual(row.content, PAUSED_TEXT + MARKER)
        self.assertTrue(row.aborted)
        self.assertEqual([p["event"] for p in emitted], ["stream_aborted", "stream_cancel_requested"])
        self.assertUntouched(previous)

    def test_a_resume_stop_the_relay_finalized_first_still_gets_its_marker(self):
        """_persist_resume_cycle flags the row aborted and writes no marker; once
        AR ran the resumed turn, its card is no longer pending."""
        resumed = self._row(
            "assistant",
            PAUSED_TEXT,
            [{"type": "text", "id": "text-1", "content": PAUSED_TEXT}, dict(PENDING_CARD, status="approved")],
            message_id="msg-resumed",
            aborted=1,
        )

        self._cancel(None)

        row, blocks = self._stored(resumed)
        self.assertTrue(blocks[-1].get("_abortMarker"))
        self.assertEqual(row.content, PAUSED_TEXT + MARKER)
        self.assertEqual(next(b for b in blocks if b["type"] == "interaction")["status"], "approved")

    def test_a_stop_that_names_its_turn_is_unchanged(self):
        previous = self._previous_answer()
        live = self._row(
            "assistant",
            "Two are overdue",
            [{"type": "text", "id": "text-live", "content": "Two are overdue"}],
            message_id="msg-live",
        )

        emitted = self._cancel("msg-live")

        row, blocks = self._stored(live)
        self.assertEqual(row.content, "Two are overdue" + MARKER)
        self.assertTrue(blocks[-1].get("_abortMarker"))
        self.assertTrue(row.aborted)
        self.assertEqual(emitted[0]["event"], "stream_aborted")
        self.assertEqual(emitted[0]["message_id"], "msg-live")
        self.assertUntouched(previous)

    def test_the_relay_records_a_stop_before_stream_start_on_a_row_of_its_own(self):
        """The cancel flag is up when AR's stream_start arrives, so the relay
        aborts before it knows the turn's message_id."""
        previous = self._previous_answer()

        emitted = self._relay(
            _event("stream_start", message_id="msg-new", zero_retention=False),
            polls=[True],
        )

        self.assertUntouched(previous)
        answers = frappe.get_all(
            "FAC Chat Message",
            filters={"session_id": self.sid, "role": "assistant"},
            order_by="creation asc",
            pluck="name",
        )
        self.assertEqual(len(answers), 2)
        row, blocks = self._stored(answers[1])
        self.assertEqual(row.content, MARKER)
        self.assertTrue(row.aborted)
        self.assertTrue(blocks[-1].get("_abortMarker"))
        self.assertEqual(emitted[-1]["event"], "stream_aborted")
        self.assertIsNone(emitted[-1]["message_id"])

    def test_the_relay_marks_a_named_turn_on_its_own_row(self):
        previous = self._previous_answer()

        emitted = self._relay(
            _event("stream_start", message_id="msg-new", zero_retention=False),
            _event("stream_chunk", content="Two are overdue"),
            polls=[False, True],
        )

        self.assertUntouched(previous)
        stopped = frappe.db.get_value(
            "FAC Chat Message", {"session_id": self.sid, "role": "assistant", "message_id": "msg-new"}
        )
        row, blocks = self._stored(stopped)
        self.assertEqual(row.content, MARKER)
        self.assertTrue(row.aborted)
        self.assertTrue(blocks[-1].get("_abortMarker"))
        self.assertEqual(emitted[-1]["message_id"], "msg-new")
