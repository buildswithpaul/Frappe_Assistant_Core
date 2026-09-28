# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""A Continue must append to its turn's row, never overwrite it."""

import json
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.api.chat import cancel as cancel_mod
from frappe_assistant_core.chat.api.chat import relay
from frappe_assistant_core.chat.api.chat.helpers import _load_turn_blocks
from frappe_assistant_core.chat.api.chat.relay import _continued_turn_updates
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestContinuedTurnUpdates(unittest.TestCase):
    def _row(self, content="The first half of the answer", credits=10, breakdown=None):
        return SimpleNamespace(content=content, credits_used=credits, model_breakdown=breakdown)

    def test_appends_the_continuation_to_the_stored_answer(self):
        updates = _continued_turn_updates(self._row(), " and the rest.", 4, None)
        self.assertEqual(updates["content"], "The first half of the answer and the rest.")

    def test_accumulates_credits_across_the_continue(self):
        updates = _continued_turn_updates(self._row(credits=10), " more", 4.126, None)
        self.assertEqual(updates["credits_used"], 14.13)

    def test_merges_the_model_breakdown(self):
        stored = json.dumps([{"model_id": "m1", "role": "orchestrator", "credits": 10}])
        incoming = [{"model_id": "m1", "role": "orchestrator", "credits": 4}]
        updates = _continued_turn_updates(self._row(breakdown=stored), " more", 4, incoming)
        rows = json.loads(updates["model_breakdown"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["credits"], 14)

    def test_leaves_the_breakdown_alone_when_the_continue_reports_none(self):
        updates = _continued_turn_updates(self._row(), " more", 4, None)
        self.assertNotIn("model_breakdown", updates)

    def test_tolerates_a_missing_row(self):
        updates = _continued_turn_updates(None, "only this", 3, None)
        self.assertEqual(updates["content"], "only this")
        self.assertEqual(updates["credits_used"], 3)

    def test_appends_the_continuations_tool_calls(self):
        row = SimpleNamespace(
            content="", credits_used=0, model_breakdown=None, tool_calls=json.dumps([{"id": "t1"}])
        )
        updates = _continued_turn_updates(row, "", 0, None, tool_calls=[{"id": "t2"}])
        self.assertEqual([call["id"] for call in json.loads(updates["tool_calls"])], ["t1", "t2"])


class TestLoadTurnBlocks(BaseAssistantTest):
    def test_returns_the_stored_blocks(self):
        blocks = [{"type": "text", "id": "t1", "content": "Hello"}]
        row = frappe._dict(name="MSG-1", blocks=json.dumps(blocks))
        with patch.object(frappe.db, "get_value", return_value=row):
            self.assertEqual(_load_turn_blocks("S1", "msg-1"), blocks)

    def test_returns_nothing_without_a_message_id(self):
        with patch.object(frappe.db, "get_value") as get_value:
            self.assertEqual(_load_turn_blocks("S1", None), [])
            get_value.assert_not_called()

    def test_returns_nothing_for_corrupt_json(self):
        row = frappe._dict(name="MSG-1", blocks="{not json")
        with patch.object(frappe.db, "get_value", return_value=row):
            self.assertEqual(_load_turn_blocks("S1", "msg-1"), [])


MARKER = cancel_mod.ABORT_MARKER_TEXT
MESSAGE_ID = "msg-truncated"
FIRST_PART = "Here is the first half of the report"
REST = " and here is the rest."
FIRST_BLOCKS = [
    {"type": "tool_call", "id": "toolu_1", "tool_name": "get_list", "status": "success"},
    {"type": "text", "id": "text-1", "content": FIRST_PART},
]
FIRST_BREAKDOWN = [{"model_id": "m1", "role": "orchestrator", "credits": 10}]


def _event(name: str, **data) -> dict:
    return {"event": name, "data": data}


CONTINUE_START = _event("stream_start", message_id=MESSAGE_ID, zero_retention=False)
# AR seeds a Continue's full_response with its own copy of the answer, the text
# of the answer's last model message, which on a multi-step answer is shorter
# than the row's.
AR_COPY = "the first half of the report"


class TestAContinueAppendsToItsTurn(BaseAssistantTest):
    """Drives ``_relay_ar_stream`` as ``continue_response`` queues it, over a fake
    AR stream, against a real truncated answer owned by a throwaway user. The
    worker-thread Frappe context, the cancel flag, the socket and the quota cache
    are stubbed; the row writes are real and roll back with the test."""

    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("continue-append")
        frappe.set_user(self.user)
        self.sid = f"continue-append-{frappe.generate_hash(length=8)}"
        self.answer = (
            frappe.get_doc(
                {
                    "doctype": "FAC Chat Message",
                    "session_id": self.sid,
                    "message_id": MESSAGE_ID,
                    "user": self.user,
                    "role": "assistant",
                    "content": FIRST_PART,
                    "blocks": json.dumps(FIRST_BLOCKS),
                    "credits_used": 10,
                    "model_breakdown": json.dumps(FIRST_BREAKDOWN),
                    "tool_calls": json.dumps([{"id": "toolu_1", "name": "get_list"}]),
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _continue(self, events, polls=None) -> tuple[MagicMock, list[dict]]:
        """Run the Continue over ``events``; the cancel flag answers ``polls`` in
        turn (the first read is the relay's check before it calls AR)."""
        client = MagicMock()
        client.stream_chat.return_value = iter(events)
        emitted = []
        with ExitStack() as stack:
            enter = stack.enter_context
            enter(
                patch(
                    "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
                    return_value=client,
                )
            )
            # set_user is stubbed because the real one resets the running session.
            for name in ("init", "connect", "set_user", "destroy"):
                enter(patch(f"frappe.{name}"))
            if polls is None:
                enter(patch.object(relay, "is_cancelled", return_value=False))
            else:
                enter(patch.object(relay, "is_cancelled", side_effect=polls))
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
            relay._relay_ar_stream(
                self.sid,
                full_prompt=None,
                original_message=None,
                context=None,
                message_name=None,
                user=self.user,
                site=frappe.local.site,
                continue_from_message_id=MESSAGE_ID,
            )
        return client, emitted

    def _stored(self):
        return frappe.db.get_value(
            "FAC Chat Message",
            self.answer,
            ["content", "blocks", "credits_used", "model_breakdown", "tool_calls", "aborted", "errored"],
            as_dict=True,
        )

    def _block_types(self, row) -> list[str]:
        return [block["type"] for block in json.loads(row.blocks)]

    def assertOneAnswer(self):
        answers = frappe.get_all("FAC Chat Message", filters={"session_id": self.sid, "role": "assistant"})
        self.assertEqual(len(answers), 1, "a Continue writes to the answer it continues, never a copy")

    def test_a_finished_continue_keeps_the_first_part_its_tools_and_its_spend(self):
        # Whatever AR's full_response holds (its copy of the answer, the same or
        # shorter than the row's, or none), the row appends what was streamed.
        for ar_full_response in (FIRST_PART + REST, AR_COPY + REST, REST):
            with self.subTest(ar_full_response=ar_full_response):
                frappe.db.set_value(
                    "FAC Chat Message",
                    self.answer,
                    {
                        "content": FIRST_PART,
                        "blocks": json.dumps(FIRST_BLOCKS),
                        "credits_used": 10,
                        "model_breakdown": json.dumps(FIRST_BREAKDOWN),
                        "tool_calls": json.dumps([{"id": "toolu_1", "name": "get_list"}]),
                    },
                )
                _client, emitted = self._continue(
                    [
                        CONTINUE_START,
                        _event("tool_call_start", tool_id="toolu_2", tool_name="get_doc", input={}),
                        _event("tool_call_result", tool_id="toolu_2", tool_name="get_doc", result="ok"),
                        _event("stream_chunk", content=REST),
                        _event(
                            "stream_complete",
                            full_response=ar_full_response,
                            credits_used=4,
                            model="m1",
                            model_breakdown=[{"model_id": "m1", "role": "orchestrator", "credits": 4}],
                        ),
                    ]
                )

                row = self._stored()
                self.assertEqual(row.content, FIRST_PART + REST)
                self.assertEqual(self._block_types(row), ["tool_call", "text", "tool_call", "text"])
                self.assertEqual(row.credits_used, 14)
                self.assertEqual(json.loads(row.model_breakdown)[0]["credits"], 14)
                self.assertEqual([call["id"] for call in json.loads(row.tool_calls)], ["toolu_1", "toolu_2"])
                self.assertOneAnswer()
                complete = emitted[-1]
                # The event keeps reporting this cycle's cost; clients add it.
                self.assertEqual(complete["credits_used"], 4)
                self.assertEqual(complete["blocks"], json.loads(row.blocks))

    def test_a_continue_that_errors_mid_answer_appends_its_partial(self):
        _client, emitted = self._continue(
            [CONTINUE_START, _event("stream_chunk", content=REST), _event("stream_error", error="x")]
        )

        row = self._stored()
        self.assertEqual(row.content, FIRST_PART + REST)
        self.assertEqual(self._block_types(row), ["tool_call", "text"])
        self.assertTrue(row.errored)
        self.assertEqual(row.credits_used, 10)
        self.assertOneAnswer()
        self.assertEqual(emitted[-1]["blocks"], json.loads(row.blocks))

    def test_a_continue_whose_relay_fails_appends_its_partial(self):
        def ar_stream():
            yield CONTINUE_START
            yield _event("stream_chunk", content=REST)
            raise ConnectionError("AR went away")

        with patch("frappe.log_error"):
            self._continue(ar_stream())

        row = self._stored()
        self.assertEqual(row.content, FIRST_PART + REST)
        self.assertTrue(row.errored)
        self.assertOneAnswer()

    def test_a_continue_that_errors_before_stream_start_leaves_the_answer_as_it_stood(self):
        _client, emitted = self._continue(
            [_event("stream_error", error="Cannot continue", error_code="INVALID_CONTINUE_TARGET")]
        )

        row = self._stored()
        self.assertEqual(row.content, FIRST_PART)
        self.assertEqual(json.loads(row.blocks), FIRST_BLOCKS)
        self.assertFalse(row.errored)
        self.assertOneAnswer()
        self.assertEqual(emitted[-1]["blocks"], FIRST_BLOCKS)

    def test_a_continue_stopped_mid_answer_appends_its_partial_and_the_marker(self):
        self._continue(
            [CONTINUE_START, _event("stream_chunk", content=REST), _event("stream_chunk", content=" More")],
            polls=[False, False, False, True],
        )

        row = self._stored()
        self.assertEqual(row.content, FIRST_PART + REST + MARKER)
        self.assertTrue(json.loads(row.blocks)[-1].get("_abortMarker"))
        self.assertTrue(row.aborted)
        self.assertOneAnswer()

    def test_a_continue_stopped_before_stream_start_marks_the_answer_and_makes_no_copy(self):
        _client, emitted = self._continue([CONTINUE_START], polls=[False, True])

        row = self._stored()
        self.assertEqual(row.content, FIRST_PART + MARKER)
        self.assertEqual(self._block_types(row), ["tool_call", "text", "text"])
        self.assertTrue(row.aborted)
        self.assertOneAnswer()
        self.assertEqual(emitted[-1]["event"], "stream_aborted")

    def test_a_continue_stopped_before_ar_is_called_marks_the_answer_and_makes_no_copy(self):
        client, emitted = self._continue([CONTINUE_START], polls=[True])

        client.stream_chat.assert_not_called()
        row = self._stored()
        self.assertEqual(row.content, FIRST_PART + MARKER)
        self.assertTrue(row.aborted)
        self.assertOneAnswer()
        # AR's own stream_start never ran, so ar_message_id is still None, but
        # the turn this Continue continues already has an id — the emitted
        # event must name it, not leave message_id null.
        self.assertEqual(emitted[-1]["message_id"], MESSAGE_ID)

    def test_ar_cancelling_a_continue_appends_what_was_streamed(self):
        self._continue(
            [
                CONTINUE_START,
                _event("stream_chunk", content=REST),
                _event("stream_cancelled", full_response=AR_COPY + REST, credits_used=1),
            ]
        )

        row = self._stored()
        self.assertEqual(row.content, FIRST_PART + REST + MARKER)
        self.assertTrue(row.aborted)
        self.assertOneAnswer()

    def test_a_stop_cancel_stream_finalized_first_keeps_the_streamed_text_and_one_marker(self):
        """A Stop naming the answer (the phone names it) lets cancel_stream mark
        the row first, before the continuation reached it. The relay's write
        still holds the whole turn, with a single marker."""

        def ar_stream():
            yield CONTINUE_START
            frappe.db.set_value(  # cancel_stream's finalizer
                "FAC Chat Message",
                self.answer,
                {
                    "content": FIRST_PART + MARKER,
                    "blocks": json.dumps([*FIRST_BLOCKS, {"type": "text", "id": "m", "_abortMarker": True}]),
                    "aborted": 1,
                },
            )
            yield _event("stream_chunk", content=REST)
            yield _event("stream_chunk", content=" More")

        self._continue(ar_stream(), polls=[False, False, False, True])

        row = self._stored()
        self.assertEqual(row.content, FIRST_PART + REST + MARKER)
        markers = [block for block in json.loads(row.blocks) if block.get("_abortMarker")]
        self.assertEqual(len(markers), 1)
        self.assertTrue(row.aborted)

    def test_a_stop_polled_after_stream_complete_does_not_append_the_cycle_again(self):
        """Once a Continue's stream_complete has persisted the cycle, a Stop
        polled on a later event (compaction, a heartbeat while AR finishes) must
        not re-add the cycle or reset its credits."""
        _client, emitted = self._continue(
            [
                CONTINUE_START,
                _event("stream_chunk", content=REST),
                _event(
                    "stream_complete",
                    full_response=FIRST_PART + REST,  # AR seeds full_response with its own stored copy
                    credits_used=4,
                    model="m1",
                    model_breakdown=[{"model_id": "m1", "role": "orchestrator", "credits": 4}],
                ),
                _event("context_summarized", summary="…"),
            ],
            polls=[False, False, False, False, True],
        )

        row = self._stored()
        self.assertEqual(row.content, FIRST_PART + REST + MARKER)
        self.assertEqual(row.credits_used, 14)
        self.assertEqual(json.loads(row.model_breakdown)[0]["credits"], 14)
        self.assertTrue(row.aborted)
        self.assertOneAnswer()
        self.assertEqual(emitted[-1]["event"], "stream_aborted")

    def test_a_stream_error_after_stream_complete_does_not_append_the_cycle_again(self):
        """Same guarantee for a stream_error arriving after stream_complete —
        AR's context_summarized housekeeping, or a dropped connection the SDK
        turns into a synthetic CONNECTION_INTERRUPTED."""
        self._continue(
            [
                CONTINUE_START,
                _event("stream_chunk", content=REST),
                _event(
                    "stream_complete",
                    full_response=FIRST_PART + REST,
                    credits_used=4,
                    model="m1",
                    model_breakdown=[{"model_id": "m1", "role": "orchestrator", "credits": 4}],
                ),
                _event("stream_error", error="Connection interrupted", error_code="CONNECTION_INTERRUPTED"),
            ]
        )

        row = self._stored()
        self.assertEqual(row.content, FIRST_PART + REST)
        self.assertEqual(row.credits_used, 14)
        self.assertEqual(json.loads(row.model_breakdown)[0]["credits"], 14)
        self.assertTrue(row.errored)
        self.assertOneAnswer()

    def test_an_exception_after_stream_complete_does_not_append_the_cycle_again(self):
        """Same guarantee for the outer except when the SDK iterator raises
        on the *next* event, after stream_complete's write and reset have both
        already landed — a dropped connection right after the answer finished."""

        def ar_stream():
            yield CONTINUE_START
            yield _event("stream_chunk", content=REST)
            yield _event(
                "stream_complete",
                full_response=FIRST_PART + REST,
                credits_used=4,
                model="m1",
                model_breakdown=[{"model_id": "m1", "role": "orchestrator", "credits": 4}],
            )
            raise ConnectionError("AR went away after the answer finished")

        with patch("frappe.log_error"):
            self._continue(ar_stream())

        row = self._stored()
        self.assertEqual(row.content, FIRST_PART + REST)
        self.assertEqual(row.credits_used, 14)
        self.assertEqual(json.loads(row.model_breakdown)[0]["credits"], 14)
        self.assertTrue(row.errored)
        self.assertOneAnswer()

    def test_an_exception_between_the_write_and_the_emit_does_not_append_the_cycle_again(self):
        """The reset must land with the write, not after the emit.
        _persist_session_blob (or _update_subscription_cache, or
        get_quota_snapshot) can still raise into the outer except between
        stream_complete's persist and its own socket emit; an earlier version
        of this code ran the reset only after that emit, so the accumulator
        still held AR's combined text and the except duplicated the whole
        answer."""
        with patch.object(relay, "_persist_session_blob", side_effect=RuntimeError("boom")), patch(
            "frappe.log_error"
        ):
            self._continue(
                [
                    CONTINUE_START,
                    _event("stream_chunk", content=REST),
                    _event(
                        "stream_complete",
                        full_response=FIRST_PART + REST,
                        credits_used=4,
                        model="m1",
                        model_breakdown=[{"model_id": "m1", "role": "orchestrator", "credits": 4}],
                    ),
                ]
            )

        row = self._stored()
        self.assertEqual(row.content, FIRST_PART + REST)
        self.assertEqual(row.credits_used, 14)
        self.assertEqual(json.loads(row.model_breakdown)[0]["credits"], 14)
        self.assertTrue(row.errored)
        self.assertOneAnswer()

    def test_the_write_itself_raising_a_non_1020_error_does_not_append_the_cycle_again(self):
        """_set_faco_message_with_retry only retries QueryDeadlockError
        (1020); anything else propagates before continued_turn is rebased and
        before the accumulators reset. The row must still end up with the
        first part and this cycle's text exactly once, never AR's combined
        text, and the failed cycle's own credits are not billed on the row."""
        real_write = relay._set_faco_message_with_retry
        calls = {"n": 0}

        def flaky_write(name, updates, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("lock wait timeout")
            return real_write(name, updates, **kwargs)

        with patch.object(relay, "_set_faco_message_with_retry", side_effect=flaky_write), patch(
            "frappe.log_error"
        ):
            self._continue(
                [
                    CONTINUE_START,
                    _event("stream_chunk", content=REST),
                    _event("stream_complete", full_response=FIRST_PART + REST, credits_used=4, model="m1"),
                ]
            )

        row = self._stored()
        self.assertEqual(row.content, FIRST_PART + REST)
        self.assertEqual(row.credits_used, 10)
        self.assertTrue(row.errored)
        self.assertOneAnswer()

    def test_a_successful_continue_clears_a_stale_errored_flag(self):
        """An earlier failed Continue on this same answer left errored=1.
        The clients keep it continuable (continuedOutcome), so a later
        successful Continue must clear the flag on the row too, or a reload
        renders a finished answer as errored."""
        frappe.db.set_value("FAC Chat Message", self.answer, "errored", 1)

        self._continue(
            [
                CONTINUE_START,
                _event("stream_chunk", content=REST),
                _event("stream_complete", full_response=FIRST_PART + REST, credits_used=4, model="m1"),
            ]
        )

        row = self._stored()
        self.assertFalse(row.errored)
        self.assertEqual(row.content, FIRST_PART + REST)
