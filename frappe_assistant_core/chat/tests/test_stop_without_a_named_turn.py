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
            # The first read is the relay's check before it calls AR.
            enter(patch.object(relay, "is_cancelled", side_effect=[False, *polls]))
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


RELAY_TEXT = "Today, the weather is calm and clear."
RELAY_CONTENT = RELAY_TEXT + MARKER
RELAY_BLOCKS = [
    {"type": "text", "id": "text-1", "content": RELAY_TEXT},
    {"type": "text", "id": "abort-marker-1", "content": MARKER, "_abortMarker": True},
]


def _relay_write() -> dict:
    """The fields the relay's own abort write saves: the streamed text and the marker, flagged aborted."""
    return {"content": RELAY_CONTENT, "blocks": json.dumps(RELAY_BLOCKS), "aborted": 1}


class TestAbortMergedRetryNeverLosesRelayText(BaseAssistantTest):
    """A Stop must never lose the text the relay saved.

    ``_abort_pending_interactions`` used to write through
    ``_set_faco_message_with_retry``, which retries a FIXED updates dict on
    ``frappe.QueryDeadlockError``. On a live send turn, cancel_stream's read
    of the row (still the empty shell ``_ensure_assistant_msg`` created)
    races the relay's own full replace-write (``_handle_stream_aborted``):
    if the relay's write commits in the gap between cancel's plain read and
    its own write, the retry re-applied the SAME stale merge (just the
    marker) over the relay's already-committed text, discarding it. Fixed by
    ``_update_faco_message_merged`` (relay.py): every attempt re-reads the
    row with a locking read (``for_update=True``) and recomputes the merge
    from that fresh state, so a retry only ever adds what's still missing.

    Runs as a throwaway user against a real FAC Chat Message row, rolled
    back with the class. The cancel flag, AR and the socket are stubbed; the
    row read/write is real.
    """

    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("abort-merged-retry")
        frappe.set_user(self.user)
        self.sid = f"abort-merged-retry-{frappe.generate_hash(length=8)}"

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _row(self) -> str:
        """The empty-shell row ``_ensure_assistant_msg`` creates on stream_start.

        Empty ``content`` needs ``ignore_mandatory``, exactly as
        ``FACChatMessage.create_message`` does for this same shell.
        """
        return (
            frappe.get_doc(
                {
                    "doctype": "FAC Chat Message",
                    "session_id": self.sid,
                    "message_id": "msg-live",
                    "user": self.user,
                    "role": "assistant",
                    "content": "",
                    "blocks": None,
                    "aborted": 0,
                }
            )
            .insert(ignore_permissions=True, ignore_mandatory=True)
            .name
        )

    def _stored(self, name: str):
        row = frappe.db.get_value("FAC Chat Message", name, ["content", "blocks", "aborted"], as_dict=True)
        return row, (json.loads(row.blocks) if row.blocks else [])

    def _cancel(self, message_id: str | None) -> list[dict]:
        """Press Stop through the real endpoint; return the socket payloads it emitted."""
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

    def _stub_rollback(self) -> MagicMock:
        """Stub ``frappe.db.rollback`` for the rest of this test; return the stub.

        BaseAssistantTest runs the whole test class in ONE transaction and
        rolls it back once at class teardown (no per-test savepoint): see
        frappe.tests.classes.integration_test_case._rollback_db. A real, bare
        frappe.db.rollback() issued mid-test by the code under test would roll
        back that WHOLE transaction. That wipes the fixture row, and with it
        any write the test stands in for as the relay's already-committed
        one, which a rollback on the request's own connection never touches.
        _block_commits neutralizes frappe.db.commit() for the same reason.
        """
        patcher = patch("frappe.db.rollback")
        self.addCleanup(patcher.stop)
        return patcher.start()

    def assertRelayTextKept(self, name: str):
        """The row holds the relay's text and its one marker, flagged aborted."""
        row, blocks = self._stored(name)
        self.assertEqual(row.content, RELAY_CONTENT)
        self.assertEqual(blocks, RELAY_BLOCKS)
        self.assertEqual(sum(1 for b in blocks if b.get("_abortMarker")), 1)
        self.assertTrue(row.aborted)

    def test_a_deadlocked_retry_re_reads_and_keeps_the_relays_committed_text(self):
        """A named Stop on a live send turn whose row is the empty shell. The
        first write deadlocks, but only after the relay's own full write has
        committed underneath it. The retry must re-read and see that
        committed text, never re-apply the stale marker-only merge over it."""
        name = self._row()
        real_set_value = frappe.db.set_value
        writes = []

        def flaky_set_value(dt, dn, updates, *args, **kwargs):
            # A copy: frappe.db.set_value stamps modified/modified_by onto the dict it is given.
            writes.append(dict(updates))
            if len(writes) == 1:
                # The relay's own abort write (_handle_stream_aborted) commits
                # its full snapshot in the gap between this attempt's read and
                # its own write.
                real_set_value(dt, dn, _relay_write())
                raise frappe.QueryDeadlockError("Record has changed since last read")
            return real_set_value(dt, dn, updates, *args, **kwargs)

        self._stub_rollback()
        with patch("frappe.db.set_value", side_effect=flaky_set_value):
            emitted = self._cancel("msg-live")

        # The first attempt merged onto the empty shell and deadlocked. The
        # second re-read the row, found the text and the marker, and only
        # flipped `aborted`.
        self.assertEqual(len(writes), 2)
        self.assertEqual(writes[0]["content"], MARKER)
        self.assertEqual(writes[1], {"aborted": 1})
        # Nothing new for the client: the superseded first attempt emits no stream_aborted.
        self.assertEqual([p["event"] for p in emitted], ["stream_cancel_requested"])
        self.assertRelayTextKept(name)

    def test_a_locked_read_refused_by_snapshot_isolation_is_retried_on_the_fresh_row(self):
        """Under REPEATABLE READ with innodb_snapshot_isolation (MariaDB's
        default since 11.6.2) the locked read itself raises 1020 when the
        relay committed the row after this request's snapshot. The retry runs
        in a new transaction and reads the relay's text."""
        name = self._row()
        real_get_value = frappe.db.get_value
        locked_reads = []

        def refuse_first_locked_read(*args, **kwargs):
            if kwargs.get("for_update"):
                locked_reads.append(args)
                if len(locked_reads) == 1:
                    # The relay committed its full write after this request's snapshot.
                    frappe.db.set_value("FAC Chat Message", name, _relay_write())
                    raise frappe.QueryDeadlockError("Record has changed since last read")
            return real_get_value(*args, **kwargs)

        self._stub_rollback()
        with patch("frappe.db.get_value", side_effect=refuse_first_locked_read):
            emitted = self._cancel("msg-live")

        self.assertEqual(len(locked_reads), 2)
        self.assertEqual([p["event"] for p in emitted], ["stream_cancel_requested"])
        self.assertRelayTextKept(name)

    def test_a_stop_whose_every_attempt_deadlocks_writes_nothing_and_says_so(self):
        """When every attempt deadlocks the Stop gives up: it returns None,
        emits no stream_aborted, logs one contention error and leaves the row
        as it found it."""
        name = self._row()
        before = self._stored(name)
        deadlock = frappe.QueryDeadlockError("Record has changed since last read")

        self._stub_rollback()
        with ExitStack() as stack:
            enter = stack.enter_context
            enter(patch("frappe.db.set_value", side_effect=deadlock))
            log_error = enter(patch("frappe.log_error"))
            emit = enter(patch.object(cancel_mod, "_emit_socket_event"))
            returned = cancel_mod._abort_pending_interactions(self.sid, "msg-live")

        self.assertIsNone(returned)
        emit.assert_not_called()
        log_error.assert_called_once()
        self.assertEqual(log_error.call_args.kwargs["title"], "FAC Chat Message write contention")
        self.assertIn(name, log_error.call_args.kwargs["message"])
        self.assertEqual(self._stored(name), before)

    def test_an_error_after_the_locked_read_rolls_back_and_reaches_the_caller(self):
        """Anything but a deadlock, raised after the locked read, must still
        release the row lock: cancel_stream swallows the error and goes on to
        its AR round-trip, and until then the relay's abort write would wait
        on that lock."""
        name = self._row()
        before = self._stored(name)
        merge = MagicMock(side_effect=ValueError("merge failed"))

        rollback = self._stub_rollback()
        with self.assertRaises(ValueError):
            relay._update_faco_message_merged(name, ["message_id"], merge)

        merge.assert_called_once()
        rollback.assert_called_once()
        self.assertEqual(self._stored(name), before)

    def test_the_merged_write_reports_a_write(self):
        name = self._row()

        outcome = relay._update_faco_message_merged(name, ["message_id"], lambda row: {"aborted": 1})

        self.assertTrue(outcome.written)
        # Exactly what merge returned: the modified/modified_by stamps that
        # frappe.db.set_value adds to the dict it is given are not in it.
        self.assertEqual(outcome.updates, {"aborted": 1})
        self.assertEqual(outcome.row.message_id, "msg-live")
        self.assertTrue(self._stored(name)[0].aborted)

    def test_the_merged_write_reports_a_merge_that_chose_not_to_write(self):
        name = self._row()

        outcome = relay._update_faco_message_merged(name, ["message_id"], lambda row: None)

        self.assertFalse(outcome.written)
        self.assertIsNone(outcome.updates)
        self.assertEqual(outcome.row.message_id, "msg-live")
        self.assertFalse(self._stored(name)[0].aborted)

    def test_the_merged_write_reports_exhausted_attempts_as_not_written(self):
        name = self._row()
        deadlock = frappe.QueryDeadlockError("Record has changed since last read")

        self._stub_rollback()
        with patch("frappe.db.set_value", side_effect=deadlock), patch("frappe.log_error"):
            outcome = relay._update_faco_message_merged(name, ["message_id"], lambda row: {"aborted": 1})

        self.assertEqual(outcome, relay.MergedWrite(False, None, None))

    def test_the_relay_committed_first_leaves_the_row_byte_identical_except_aborted(self):
        """No retry needed at all: the row already holds the relay's full
        text plus marker when cancel_stream runs, and is not yet flagged
        ``aborted``. Only ``aborted`` flips; content and blocks stay
        byte-identical, and nothing is emitted, since there is nothing new
        for the SPA."""
        name = self._row()
        frappe.db.set_value("FAC Chat Message", name, dict(_relay_write(), aborted=0))
        before, _ = self._stored(name)
        self.assertEqual(before.aborted, 0)

        emitted = self._cancel("msg-live")

        row, _ = self._stored(name)
        self.assertEqual(row.aborted, 1)
        self.assertEqual((row.content, row.blocks), (before.content, before.blocks))
        self.assertEqual([p["event"] for p in emitted], ["stream_cancel_requested"])

    def test_cancel_wins_the_race_then_the_relays_full_write_still_lands(self):
        """Cancel reads the empty shell first, writes just the marker and
        emits stream_aborted with it, so a client may briefly show only the
        marker. The relay's own abort write then lands, as it does once it
        notices the cancel flag, and the final row holds the text with one
        marker."""
        name = self._row()

        emitted = self._cancel("msg-live")

        row, blocks = self._stored(name)
        self.assertEqual(row.content, MARKER)
        self.assertEqual(len(blocks), 1)
        self.assertTrue(blocks[0].get("_abortMarker"))
        self.assertTrue(row.aborted)
        self.assertEqual(emitted[0]["event"], "stream_aborted")
        self.assertEqual(emitted[0]["partial_response"], MARKER)

        # The relay's own abort write, through the real writer.
        builder = MagicMock()
        builder.snapshot.return_value = [RELAY_BLOCKS[0]]
        with patch.object(relay, "_emit_socket_event"):
            relay._handle_stream_aborted(self.sid, "msg-live", RELAY_TEXT, builder, [], "", stream_iter=None)

        row, blocks = self._stored(name)
        self.assertEqual(row.content, RELAY_CONTENT)
        self.assertEqual(blocks[0], RELAY_BLOCKS[0])
        self.assertEqual(sum(1 for b in blocks if b.get("_abortMarker")), 1)
        self.assertTrue(row.aborted)

    def test_the_locked_read_uses_for_update(self):
        """The read inside the merge takes a row lock, so the relay's
        write (if concurrent) waits for this transaction to commit rather
        than racing it."""
        self._row()

        with patch("frappe.db.get_value", wraps=frappe.db.get_value) as spy:
            self._cancel("msg-live")

        locked_calls = [c for c in spy.call_args_list if c.kwargs.get("for_update")]
        self.assertTrue(locked_calls, f"expected a for_update=True read; calls were {spy.call_args_list}")
        self.assertEqual(locked_calls[0].args[0], "FAC Chat Message")
        self.assertTrue(locked_calls[0].kwargs.get("as_dict"))
