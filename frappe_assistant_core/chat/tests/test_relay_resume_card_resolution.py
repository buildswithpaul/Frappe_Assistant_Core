# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""A resume resolves its answered cards only once AR is running the resumed turn.

The resume relay used to mark the cards approved or rejected before it called
AR. When AR was unreachable, or refused the resume after its stream_start
(SESSION_BUSY), the error branch saved the turn's row with the cards decided
and its text replaced by the cycle's empty reply, while AR still held the
pause. After a reload no client could answer the cards again.

Drives ``_relay_ar_interrupt_resume`` over a fake SDK stream against a real
FAC Chat Message row owned by a throwaway user. The worker-thread Frappe
context, the cancel flag, the socket and the quota cache are stubbed; the row
writes are real and roll back when the class finishes.
"""

import json
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.api.block_builder import BlockBuilder
from frappe_assistant_core.chat.api.chat import relay
from frappe_assistant_core.tests.base_test import BaseAssistantTest

SESSION_ID = "s-resume-cards"
MESSAGE_ID = "msg-resume-cards"
PAUSED_TEXT = "I will create the ToDo once you approve."
PAUSED_BLOCKS = [
    {"type": "text", "id": "text-1", "content": PAUSED_TEXT},
    {"type": "tool_call", "id": "toolu_1", "tool_name": "create_document", "status": "running"},
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


def _event(name: str, **data) -> dict:
    return {"event": name, "data": data}


def _error(code: str) -> dict:
    return _event("stream_error", error="The assistant could not continue.", error_code=code)


RESUMED_START = _event("stream_start", message_id=MESSAGE_ID, resumed=True, zero_retention=False)
TOOL_RAN = _event(
    "tool_call_result",
    tool_id="toolu_1",
    tool_name="create_document",
    result={"success": True},
    status="success",
)


class TestResumeResolvesCardsOnlyOnceARRuns(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("resume-cards")
        frappe.set_user(self.user)
        self.row = (
            frappe.get_doc(
                {
                    "doctype": "FAC Chat Message",
                    "session_id": SESSION_ID,
                    "message_id": MESSAGE_ID,
                    "user": self.user,
                    "role": "assistant",
                    "content": PAUSED_TEXT,
                    "blocks": json.dumps(PAUSED_BLOCKS),
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _resume(self, *events, response="approve", stream=None, polls=None) -> list[dict]:
        """Run one resume over ``events``, or over ``stream`` when given; return
        the socket payloads it emitted. ``polls`` feeds the cancel flag's
        answers in turn (the first read is the pre-AR check, then one per
        event); omitted, the flag never reads True."""
        client = MagicMock()
        client.stream_chat.return_value = stream if stream is not None else (event for event in events)
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
            relay._relay_ar_interrupt_resume(
                session_id=SESSION_ID,
                interrupt_response=[{"interruptId": "int-1", "response": response}],
                user=self.user,
                site=frappe.local.site,
                message_id=MESSAGE_ID,
            )
        return emitted

    def _stored(self):
        row = frappe.db.get_value(
            "FAC Chat Message",
            self.row,
            ["content", "blocks", "errored", "aborted", "credits_used"],
            as_dict=True,
        )
        return row, json.loads(row.blocks)

    @staticmethod
    def _card_status(blocks: list[dict]) -> str:
        return next(b["status"] for b in blocks if b.get("type") == "interaction")

    def assertTurnUntouched(self):
        row, blocks = self._stored()
        self.assertEqual(blocks, PAUSED_BLOCKS)
        self.assertEqual(row.content, PAUSED_TEXT)
        self.assertFalse(row.errored)

    def test_an_unreachable_ar_leaves_the_pause_as_it_stood(self):
        emitted = self._resume(_error("CONNECTION_ERROR"))

        self.assertTurnUntouched()
        self.assertEqual(emitted[-1]["error_code"], "CONNECTION_ERROR")

    def test_a_refusal_after_the_resumed_start_keeps_the_cards_pending(self):
        """AR emits the resumed stream_start before agent_pool takes the session
        lock, and can emit a task_updated event right before the refusal: neither
        shows that AR consumed the pause."""
        plan = {
            "id": "plan-1",
            "status": "running",
            "tasks": [{"id": "t1", "title": "Create the ToDo", "status": "running"}],
        }
        emitted = self._resume(
            RESUMED_START,
            _event("heartbeat"),
            _event("task_updated", plan=plan),
            _error("SESSION_BUSY"),
        )

        self.assertTurnUntouched()
        error = emitted[-1]
        self.assertEqual(error["error_code"], "SESSION_BUSY")
        self.assertEqual(self._card_status(error["blocks"]), "pending")

    def test_a_pause_answered_elsewhere_is_left_to_the_resume_that_took_it(self):
        self._resume(RESUMED_START, _error("INTERRUPT_ALREADY_RESOLVED"))

        self.assertTurnUntouched()

    def test_a_pause_ar_no_longer_holds_settles_as_expired(self):
        for code in ("INTERRUPT_EXPIRED", "INTERRUPT_NOT_FOUND"):
            with self.subTest(code=code):
                frappe.db.set_value(
                    "FAC Chat Message",
                    self.row,
                    {"blocks": json.dumps(PAUSED_BLOCKS), "content": PAUSED_TEXT, "errored": 0},
                )
                emitted = self._resume(RESUMED_START, _error(code))

                row, blocks = self._stored()
                self.assertEqual(self._card_status(blocks), "expired")
                self.assertEqual(self._card_status(emitted[-1]["blocks"]), "expired")
                self.assertEqual(row.content, PAUSED_TEXT)
                self.assertFalse(row.errored)

    def test_a_pause_gone_refusal_after_a_plan_or_sources_event_does_not_persist_them(self):
        """AR can emit ``sources`` or ``plan_created``/``task_updated`` ahead of
        a refusal (both are kept out of _RESUME_PROGRESS_EVENTS) — neither
        means AR consumed the pause. INTERRUPT_EXPIRED still settles the card
        as expired, but the sources/plan blocks belong to a cycle that
        produced nothing and must never land on the row."""
        plan = {
            "id": "plan-1",
            "status": "running",
            "tasks": [{"id": "t1", "title": "Create the ToDo", "status": "running"}],
        }
        emitted = self._resume(
            RESUMED_START,
            _event("sources", sources=[{"title": "doc", "url": "https://example.com"}]),
            _event("task_updated", plan=plan),
            _error("INTERRUPT_EXPIRED"),
        )

        row, blocks = self._stored()
        self.assertEqual(self._card_status(blocks), "expired")
        self.assertEqual(row.content, PAUSED_TEXT)
        self.assertFalse(row.errored)
        # Only the original three blocks, with the card settled — no sources or plan.
        self.assertEqual([b["type"] for b in blocks], ["text", "tool_call", "interaction"])

        # The live socket payload still carries this cycle's blocks (plan +
        # sources + the settled card) — only the STORED row is scoped down.
        live_blocks = emitted[-1]["blocks"]
        self.assertIn("sources", [b["type"] for b in live_blocks])
        self.assertIn("plan", [b["type"] for b in live_blocks])
        self.assertEqual(self._card_status(live_blocks), "expired")

    def test_a_resumed_turn_that_runs_resolves_the_cards(self):
        emitted = self._resume(
            RESUMED_START,
            TOOL_RAN,
            _event("stream_chunk", content="Done: the ToDo is created."),
            _event("stream_complete", full_response="Done: the ToDo is created.", credits_used=2, model="m"),
        )

        row, blocks = self._stored()
        self.assertEqual(self._card_status(blocks), "approved")
        self.assertEqual(self._card_status(emitted[-1]["blocks"]), "approved")
        self.assertIn(PAUSED_TEXT, row.content)
        self.assertIn("Done: the ToDo is created.", row.content)

    def test_a_rejection_resolves_once_the_resumed_turn_answers(self):
        self._resume(
            RESUMED_START,
            _event("stream_chunk", content="Understood, I will not create it."),
            _event(
                "stream_complete",
                full_response="Understood, I will not create it.",
                credits_used=1,
                model="m",
            ),
            response="rejected",
        )

        _row, blocks = self._stored()
        self.assertEqual(self._card_status(blocks), "rejected")

    def test_an_error_after_the_turn_ran_keeps_the_decision(self):
        self._resume(RESUMED_START, TOOL_RAN, _error("LLM_UNAVAILABLE"))

        row, blocks = self._stored()
        self.assertEqual(self._card_status(blocks), "approved")
        self.assertTrue(row.errored)
        self.assertEqual(row.content, PAUSED_TEXT)

    def test_an_error_after_the_resumed_turn_wrote_text_keeps_the_text_before_the_pause(self):
        """The errored cycle is appended to the turn, as a Stop's is, never replacing it."""
        self._resume(
            RESUMED_START,
            TOOL_RAN,
            _event("stream_chunk", content="The ToDo is created, and"),
            _error("LLM_UNAVAILABLE"),
        )

        row, blocks = self._stored()
        self.assertEqual(row.content, f"{PAUSED_TEXT}\n\nThe ToDo is created, and")
        self.assertTrue(row.errored)
        self.assertEqual(self._card_status(blocks), "approved")

    def test_a_resume_relay_that_fails_after_the_turn_ran_keeps_the_text_before_the_pause(self):
        def ar_stream():
            yield RESUMED_START
            yield _event("stream_chunk", content="The ToDo is created, and")
            raise ConnectionError("AR went away")

        with patch("frappe.log_error"):
            self._resume(stream=ar_stream())

        row, _blocks = self._stored()
        self.assertEqual(row.content, f"{PAUSED_TEXT}\n\nThe ToDo is created, and")
        self.assertTrue(row.errored)

    def test_a_stream_error_after_a_finished_resume_cycle_does_not_append_it_twice(self):
        """The same root cause as the Continue path's own double-append bug, here
        on the resume path. _persist_resume_cycle re-reads the row on every call,
        so once stream_complete has persisted this
        cycle, a later stream_error (a dropped connection after the answer
        finished) must not append the same text a second time."""
        self._resume(
            RESUMED_START,
            TOOL_RAN,
            _event("stream_chunk", content="Done."),
            _event("stream_complete", full_response="Done.", credits_used=2, model="m"),
            _error("CONNECTION_INTERRUPTED"),
        )

        row, blocks = self._stored()
        self.assertEqual(row.content, f"{PAUSED_TEXT}\n\nDone.")
        self.assertTrue(row.errored)
        self.assertEqual(row.credits_used, 2)
        self.assertEqual(self._card_status(blocks), "approved")

    def test_a_stop_polled_after_a_finished_resume_cycle_does_not_append_it_twice(self):
        """Same root cause on the resume's own Stop check (relay.py ~653), which
        polls on every loop iteration, including one after stream_complete
        already persisted the cycle (a heartbeat while AR finishes)."""
        emitted = self._resume(
            RESUMED_START,
            TOOL_RAN,
            _event("stream_chunk", content="Done."),
            _event("stream_complete", full_response="Done.", credits_used=2, model="m"),
            _event("heartbeat"),
            polls=[False, False, False, False, False, True],
        )

        row, blocks = self._stored()
        self.assertEqual(row.content, f"{PAUSED_TEXT}\n\nDone.")
        self.assertTrue(row.aborted)
        self.assertEqual(row.credits_used, 2)
        self.assertEqual(self._card_status(blocks), "approved")
        self.assertEqual(emitted[-1]["event"], "stream_aborted")

    def test_a_stop_that_cancel_py_finalized_first_keeps_the_approved_decision_and_text(self):
        """A Stop pressed while an approved resume is running reaches cancel_stream,
        which always does two things: it flips the Redis flag this relay polls, AND
        it runs _abort_pending_interactions on the stored row right away. The row
        still holds the card as pending at that point (this relay writes it only on
        stream_complete, an error or its own Stop), so cancel.py finalizes it as
        'Stopped by user' and appends the marker before this relay's own poll even
        notices the flag. _persist_resume_cycle used to see the row already
        aborted and skip entirely, losing the tool row and the streamed text and
        leaving the approved card's own decision overwritten by cancel.py's."""
        from frappe_assistant_core.chat.api.chat import cancel as cancel_mod

        polls_seen = {"n": 0}

        def poll(_session_id):
            polls_seen["n"] += 1
            if polls_seen["n"] == 5:
                # cancel_stream's own finalizer wins the race and writes the
                # row before this relay's poll notices the same flag, right
                # after the streamed text above has already reached the
                # block_builder (call 4, the check before this one).
                with patch.object(cancel_mod, "_emit_socket_event"):
                    cancel_mod._abort_pending_interactions(SESSION_ID, None)
                return True
            return False

        emitted = self._resume(
            RESUMED_START,
            TOOL_RAN,
            _event("stream_chunk", content="Creating it now, and"),
            _event("heartbeat"),
            polls=poll,
        )

        row, blocks = self._stored()
        self.assertEqual(self._card_status(blocks), "approved")
        self.assertEqual(row.content, f"{PAUSED_TEXT}\n\nCreating it now, and{cancel_mod.ABORT_MARKER_TEXT}")
        self.assertTrue(row.aborted)
        self.assertEqual(sum(1 for b in blocks if b.get("_abortMarker")), 1)
        self.assertEqual(next(b for b in blocks if b["type"] == "tool_call")["status"], "success")
        self.assertEqual(emitted[-1]["event"], "stream_aborted")

    def test_an_exception_between_the_write_and_the_emit_does_not_append_it_twice(self):
        """The reset must land with the write, not after the emit.
        _persist_session_blob can still raise into the outer except between
        stream_complete's persist and its own socket emit; an earlier version
        of this code ran the reset only after that emit, so the accumulator
        still held this cycle's text and the except appended it a second
        time."""
        with patch.object(relay, "_persist_session_blob", side_effect=RuntimeError("boom")), patch(
            "frappe.log_error"
        ):
            self._resume(
                RESUMED_START,
                TOOL_RAN,
                _event("stream_chunk", content="Done."),
                _event("stream_complete", full_response="Done.", credits_used=2, model="m"),
            )

        row, blocks = self._stored()
        self.assertEqual(row.content, f"{PAUSED_TEXT}\n\nDone.")
        self.assertTrue(row.errored)
        self.assertEqual(row.credits_used, 2)
        self.assertEqual(self._card_status(blocks), "approved")

    def test_the_write_itself_raising_a_non_1020_error_does_not_append_it_twice(self):
        """_set_faco_message_with_retry only retries QueryDeadlockError
        (1020); anything else propagates out of _persist_resume_cycle before
        the accumulators reset, and before any DB write lands. The outer
        except's own retry must then append this cycle's text exactly once."""
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
            self._resume(
                RESUMED_START,
                TOOL_RAN,
                _event("stream_chunk", content="Done."),
                _event("stream_complete", full_response="Done.", credits_used=2, model="m"),
            )

        row, blocks = self._stored()
        self.assertEqual(row.content, f"{PAUSED_TEXT}\n\nDone.")
        self.assertTrue(row.errored)
        self.assertEqual(row.credits_used, 0)
        self.assertEqual(self._card_status(blocks), "approved")


class TestSettlePendingInteractions(unittest.TestCase):
    def test_settles_only_pending_cards(self):
        builder = BlockBuilder(
            existing_blocks=[
                {"type": "interaction", "id": "a", "status": "pending"},
                {"type": "interaction", "id": "b", "status": "approved"},
                {"type": "tool_call", "id": "c", "status": "running"},
            ]
        )

        self.assertTrue(builder.settle_pending_interactions("expired"))
        self.assertEqual([b["status"] for b in builder.snapshot()], ["expired", "approved", "running"])

    def test_reports_no_change_without_a_pending_card(self):
        builder = BlockBuilder(existing_blocks=[{"type": "interaction", "id": "b", "status": "approved"}])

        self.assertFalse(builder.settle_pending_interactions("expired"))
