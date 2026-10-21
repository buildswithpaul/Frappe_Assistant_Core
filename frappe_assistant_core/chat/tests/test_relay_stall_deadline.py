# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""A relay that gets no real progress from AR stops waiting and ends the turn with an error."""

import json
import time
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.api.chat import relay
from frappe_assistant_core.tests.base_test import BaseAssistantTest

MESSAGE_ID = "msg-stalled"
STEP_SECONDS = 60
# A red run must fail rather than hang, so the fake stream gives up after this many events.
EVENT_CAP = 200


def _event(name: str, **data) -> dict:
    return {"event": name, "data": data}


# Reads are 60 s apart, so the 36th read lands past RELAY_MAX_TURN_SECONDS.
LATE_CHUNKS = 35
PAUSED_BLOCKS = [
    {"type": "text", "id": "text-1", "content": "I will create the ToDo once you approve."},
    {
        "type": "interaction",
        "id": "toolu_1",
        "interactionType": "approval",
        "tool_name": "create_document",
        "input": {"doctype": "ToDo"},
        "interrupts": [{"id": "int-1", "name": "create_document", "reason": {"type": "approval"}}],
        "status": "pending",
    },
]


class FakeStream:
    """Yields ``events``, then ``tail`` forever (until ``EVENT_CAP``), and records ``close()``."""

    def __init__(self, events, tail=None):
        self.events = list(events)
        self.tail = tail
        self.closed = False
        self.yielded = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.closed or self.yielded >= EVENT_CAP:
            raise AssertionError("the relay kept reading a stalled stream")
        self.yielded += 1
        if self.events:
            return self.events.pop(0)
        if self.tail is None:
            raise StopIteration
        return self.tail

    def close(self):
        self.closed = True


class TestRelayDeadlineTripped(BaseAssistantTest):
    def test_idle_past_the_no_progress_bound_trips(self):
        tripped = relay._relay_deadline_tripped(0, 0, relay.RELAY_NO_PROGRESS_SECONDS)
        self.assertEqual(tripped, "no_progress")

    def test_a_long_turn_that_keeps_moving_trips_at_the_turn_bound(self):
        now = relay.RELAY_MAX_TURN_SECONDS
        self.assertEqual(relay._relay_deadline_tripped(0, now - 1, now), "max_turn")
        self.assertIsNone(relay._relay_deadline_tripped(0, now - 1, now - 1))


class RelayStallBase(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("relay-stall")
        frappe.set_user(self.user)
        self.sid = f"relay-stall-{frappe.generate_hash(length=8)}"

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _run(self, relay_call, stream):
        """Run ``relay_call`` over ``stream`` with the clock advancing STEP_SECONDS per read."""
        client = MagicMock()
        client.stream_chat.return_value = stream
        emitted = []
        clock = {"now": 0.0}

        def monotonic():
            clock["now"] += STEP_SECONDS
            return clock["now"]

        with ExitStack() as stack:
            enter = stack.enter_context
            enter(
                patch(
                    "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
                    return_value=client,
                )
            )
            for name in ("init", "connect", "set_user", "destroy"):
                enter(patch(f"frappe.{name}"))
            enter(patch.object(relay, "is_cancelled", return_value=False))
            enter(patch.object(relay, "_update_subscription_cache"))
            enter(
                patch(
                    "frappe_assistant_core.chat.quota_cache.get_quota_snapshot",
                    return_value={"quota_used": 0, "quota_total": 100},
                )
            )
            enter(
                patch.object(
                    relay, "_emit_socket_event", side_effect=lambda _sid, payload: emitted.append(payload)
                )
            )
            # Only the relay's clock moves; its time.sleep (write retries) stays real.
            enter(patch.object(relay, "time", SimpleNamespace(monotonic=monotonic, sleep=time.sleep)))
            relay_call()
        return emitted

    def _send(self, stream):
        return self._run(
            lambda: relay._relay_ar_stream(
                self.sid,
                full_prompt="hi",
                original_message="hi",
                context=None,
                message_name=None,
                user=self.user,
                site=frappe.local.site,
            ),
            stream,
        )

    def _resume(self, stream, message_id=None):
        return self._run(
            lambda: relay._relay_ar_interrupt_resume(
                self.sid,
                [{"interruptId": "i1", "response": "approve"}],
                self.user,
                frappe.local.site,
                message_id=message_id,
            ),
            stream,
        )

    def _stored(self):
        return frappe.db.get_value(
            "FAC Chat Message",
            {"session_id": self.sid, "role": "assistant"},
            ["content", "errored"],
            as_dict=True,
        )

    def assertEndedAsStalled(self, emitted, stream):
        self.assertTrue(stream.closed, "the AR connection must be closed")
        self.assertEqual(emitted[-1]["event"], "stream_error")
        self.assertEqual(emitted[-1]["error_code"], "RELAY_STALLED")
        self.assertEqual(
            emitted[-1]["error"],
            "The assistant stopped waiting for a reply. Anything after the last step shown may not have finished; check before trying again.",
        )
        self.assertEqual([e["event"] for e in emitted].count("stream_error"), 1)


class TestSendRelayStalls(RelayStallBase):
    # AR heartbeats every 10 s while a turn is parked, so a
    # turn that hangs mid-tool reaches the relay as stream_start, a chunk, then heartbeats.
    def test_heartbeats_alone_end_the_turn_and_keep_the_partial(self):
        stream = FakeStream(
            [
                _event("stream_start", message_id=MESSAGE_ID, zero_retention=False),
                _event("stream_chunk", content="Working on it"),
            ],
            tail=_event("heartbeat"),
        )

        emitted = self._send(stream)

        self.assertEndedAsStalled(emitted, stream)
        self.assertEqual(emitted[-1]["partial_response"], "Working on it")
        row = self._stored()
        self.assertEqual(row.content, "Working on it")
        self.assertTrue(row.errored)

    def test_heartbeats_never_count_as_progress(self):
        stream = FakeStream([_event("stream_start", message_id=MESSAGE_ID)], tail=_event("heartbeat"))

        emitted = self._send(stream)

        self.assertEndedAsStalled(emitted, stream)
        reads = relay.RELAY_NO_PROGRESS_SECONDS // STEP_SECONDS
        self.assertLessEqual(stream.yielded, reads + 2)

    def test_steady_chunks_never_trip(self):
        chunks = [_event("stream_chunk", content="x") for _ in range(20)]
        stream = FakeStream(
            [_event("stream_start", message_id=MESSAGE_ID), *chunks]
            + [_event("stream_complete", full_response="x" * 20, credits_used=0, model="m1")]
        )

        emitted = self._send(stream)

        self.assertFalse(stream.closed)
        self.assertEqual(emitted[-1]["event"], "stream_complete")
        self.assertNotIn("stream_error", [e["event"] for e in emitted])

    def test_a_final_event_past_the_turn_bound_still_completes_the_turn(self):
        complete = _event(
            "stream_complete",
            full_response="x" * LATE_CHUNKS,
            credits_used=3,
            model="m1",
            session_state="blob",
        )
        stream = FakeStream(
            [
                _event("stream_start", message_id=MESSAGE_ID, zero_retention=True),
                *[_event("stream_chunk", content="x") for _ in range(LATE_CHUNKS)],
                complete,
            ]
        )

        with patch.object(relay, "_persist_session_blob") as persist_blob:
            emitted = self._send(stream)

        self.assertFalse(stream.closed)
        self.assertEqual(emitted[-1]["event"], "stream_complete")
        self.assertNotIn("stream_error", [e["event"] for e in emitted])
        persist_blob.assert_called_once()
        self.assertEqual(persist_blob.call_args[0][2]["session_state"], "blob")
        row = frappe.db.get_value(
            "FAC Chat Message",
            {"session_id": self.sid, "role": "assistant"},
            ["credits_used", "errored"],
            as_dict=True,
        )
        self.assertEqual(row.credits_used, 3)
        self.assertFalse(row.errored)

    def test_a_chunk_past_the_turn_bound_is_kept_and_the_next_heartbeat_trips(self):
        stream = FakeStream(
            [
                _event("stream_start", message_id=MESSAGE_ID),
                *[_event("stream_chunk", content="x") for _ in range(LATE_CHUNKS)],
            ],
            tail=_event("heartbeat"),
        )

        emitted = self._send(stream)

        self.assertEndedAsStalled(emitted, stream)
        self.assertEqual(emitted[-1]["partial_response"], "x" * LATE_CHUNKS)
        self.assertEqual(self._stored().content, "x" * LATE_CHUNKS)
        self.assertEqual(stream.yielded, LATE_CHUNKS + 2)


class TestResumeRelayStalls(RelayStallBase):
    def test_heartbeats_alone_end_a_resumed_turn(self):
        stream = FakeStream(
            [
                _event("stream_start", message_id=MESSAGE_ID, zero_retention=False),
                _event("stream_chunk", content="Resumed and running"),
            ],
            tail=_event("heartbeat"),
        )

        emitted = self._resume(stream)

        self.assertEndedAsStalled(emitted, stream)
        self.assertEqual(emitted[-1]["partial_response"], "Resumed and running")
        row = self._stored()
        self.assertEqual(row.content, "Resumed and running")
        self.assertTrue(row.errored)

    def test_steady_chunks_never_trip_a_resumed_turn(self):
        chunks = [_event("stream_chunk", content="x") for _ in range(20)]
        stream = FakeStream(
            [_event("stream_start", message_id=MESSAGE_ID), *chunks]
            + [_event("stream_complete", full_response="x" * 20, credits_used=0, model="m1")]
        )

        emitted = self._resume(stream)

        self.assertFalse(stream.closed)
        self.assertNotIn("stream_error", [e["event"] for e in emitted])

    def test_a_final_event_past_the_turn_bound_still_completes_a_resumed_turn(self):
        stream = FakeStream(
            [
                _event("stream_start", message_id=MESSAGE_ID, zero_retention=True),
                *[_event("stream_chunk", content="x") for _ in range(LATE_CHUNKS)],
                _event(
                    "stream_complete",
                    full_response="x" * LATE_CHUNKS,
                    credits_used=3,
                    model="m1",
                    session_state="blob",
                ),
            ]
        )

        with patch.object(relay, "_persist_session_blob") as persist_blob:
            emitted = self._resume(stream)

        self.assertFalse(stream.closed)
        self.assertEqual(emitted[-1]["event"], "stream_complete")
        self.assertNotIn("stream_error", [e["event"] for e in emitted])
        persist_blob.assert_called_once()
        self.assertEqual(persist_blob.call_args[0][2]["session_state"], "blob")

    def test_a_chunk_past_the_turn_bound_is_kept_and_the_next_heartbeat_trips_a_resume(self):
        stream = FakeStream(
            [
                _event("stream_start", message_id=MESSAGE_ID),
                *[_event("stream_chunk", content="x") for _ in range(LATE_CHUNKS)],
            ],
            tail=_event("heartbeat"),
        )

        emitted = self._resume(stream)

        self.assertEndedAsStalled(emitted, stream)
        self.assertEqual(emitted[-1]["partial_response"], "x" * LATE_CHUNKS)
        self.assertEqual(self._stored().content, "x" * LATE_CHUNKS)
        self.assertEqual(stream.yielded, LATE_CHUNKS + 2)

    def test_a_stall_before_the_pause_is_consumed_leaves_the_cards_and_the_row_alone(self):
        # AR accepted the resume (stream_start) but its agent parks before running anything,
        # heartbeating the whole time; the pause is still held on AR's side.
        row = (
            frappe.get_doc(
                {
                    "doctype": "FAC Chat Message",
                    "session_id": self.sid,
                    "message_id": MESSAGE_ID,
                    "user": self.user,
                    "role": "assistant",
                    "content": "paused",
                    "blocks": json.dumps(PAUSED_BLOCKS),
                }
            )
            .insert(ignore_permissions=True)
            .name
        )
        stream = FakeStream(
            [_event("stream_start", message_id=MESSAGE_ID, resumed=True)], tail=_event("heartbeat")
        )

        with patch.object(relay, "_set_faco_message_with_retry") as write:
            emitted = self._resume(stream, message_id=MESSAGE_ID)

        self.assertTrue(stream.closed)
        self.assertEqual(emitted[-1]["event"], "stream_error")
        self.assertEqual(emitted[-1]["error_code"], "RELAY_STALLED")
        interactions = [b for b in emitted[-1]["blocks"] if b["type"] == "interaction"]
        self.assertEqual([b["status"] for b in interactions], ["pending"])
        write.assert_not_called()
        stored = frappe.db.get_value("FAC Chat Message", row, ["content", "blocks"], as_dict=True)
        self.assertEqual(stored.content, "paused")
        self.assertEqual(json.loads(stored.blocks), PAUSED_BLOCKS)
