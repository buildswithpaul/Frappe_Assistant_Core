"""A live-turn entry whose relay died stops being written; a surface can tell, and end it."""

import json
import time
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat import credit_status_cache
from frappe_assistant_core.chat.api.block_builder import BlockBuilder
from frappe_assistant_core.chat.api.chat import live_turn, relay
from frappe_assistant_core.tests.base_test import BaseAssistantTest


def _aged(session_id: str, seconds: float) -> dict:
    """Push the entry's last write ``seconds`` into the past and return it."""
    entry = live_turn.get(session_id)
    entry["last_progress_at"] = time.time() - seconds
    # Written straight to the cache: _write would stamp the time as now.
    frappe.cache().set_value(live_turn._key(session_id), entry, expires_in_sec=live_turn.ENTRY_TTL_SECONDS)
    return entry


class TestHeartbeat(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.sid = f"beat-{frappe.generate_hash(length=10)}"

    def tearDown(self):
        live_turn.unbind(self.sid)
        live_turn.clear(self.sid)
        super().tearDown()

    def test_entries_carry_their_last_progress(self):
        before = time.time()
        live_turn.start(self.sid)
        self.assertGreaterEqual(live_turn.get(self.sid)["last_progress_at"], before)
        live_turn.bind(self.sid, BlockBuilder())
        self.assertGreaterEqual(live_turn.get(self.sid)["last_progress_at"], before)

    def test_a_bound_turn_keeps_the_starting_bound_until_ar_responds(self):
        turn = live_turn.start(self.sid)
        live = live_turn.bind(self.sid, BlockBuilder(), turn=turn)
        # AR can take minutes to send its first byte (its own queue, a busy wait); 120 s is real.
        entry = _aged(self.sid, 120)
        self.assertEqual(entry["status"], "starting")
        self.assertFalse(live_turn.is_stale(entry))
        live.ar_responded()
        entry = _aged(self.sid, 61)
        self.assertEqual(entry["status"], "streaming")
        self.assertTrue(live_turn.is_stale(entry))

    def test_a_turn_ended_elsewhere_is_never_rewritten(self):
        turn = live_turn.start(self.sid)
        live = live_turn.bind(self.sid, BlockBuilder(), turn=turn)
        live.ar_responded()
        # mark_turn_interrupted (or a Retry's new turn) took the entry from this relay.
        live_turn.clear(self.sid)
        live.record({"event": "tool_call_start"})
        self.assertIsNone(live_turn.get(self.sid))
        self.assertTrue(live.lost)
        newer = live_turn.start(self.sid)
        live.record({"event": "tool_call_start"})
        self.assertEqual(live_turn.get(self.sid)["turn"], newer)

    def test_heartbeat_event_refreshes_last_progress(self):
        clock = iter([100.0, 100.0, 110.0, 116.0, 116.0])
        with patch.object(live_turn, "_clock", side_effect=lambda: next(clock)):
            live = live_turn.bind(self.sid, BlockBuilder())
            live.ar_responded()
            # A SIGKILLed worker stops writing; a write 30 s ago is that worker's last.
            _aged(self.sid, 30)
            live.record({"event": "heartbeat"})  # +10 s: under HEARTBEAT_SECONDS, not written
            self.assertGreater(time.time() - live_turn.get(self.sid)["last_progress_at"], 25)
            live.record({"event": "heartbeat"})  # +16 s: written
        self.assertLess(time.time() - live_turn.get(self.sid)["last_progress_at"], 5)

    def test_streaming_entry_stale_after_60s(self):
        live_turn.bind(self.sid, BlockBuilder()).ar_responded()
        # A SIGKILLed worker stops writing; last_progress_at 61 s ago is that state.
        entry = _aged(self.sid, 61)
        self.assertTrue(live_turn.is_stale(entry))
        self.assertFalse(live_turn.is_stale(entry, now=entry["last_progress_at"] + 59))

    def test_queued_turn_is_not_stale_before_180s(self):
        live_turn.start(self.sid)
        # A turn queued behind a full relay pool has no heartbeat yet; 120 s in the queue is real.
        entry = _aged(self.sid, 120)
        self.assertFalse(live_turn.is_stale(entry))
        self.assertTrue(live_turn.is_stale(entry, now=entry["last_progress_at"] + 181))


class TestMarkTurnInterrupted(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.owner = self.make_throwaway_user("beat-owner")
        self.other = self.make_throwaway_user("beat-other")
        self.sid = f"beat-ep-{frappe.generate_hash(length=8)}"
        # Production: send_message saves the user row before the relay is queued.
        frappe.get_doc(
            {
                "doctype": "FAC Chat Message",
                "session_id": self.sid,
                "user": self.owner,
                "role": "user",
                "content": "hello",
            }
        ).insert(ignore_permissions=True)
        frappe.set_user(self.owner)
        self.published = []
        self.publish = patch(
            "frappe.publish_realtime",
            side_effect=lambda event, message, **kw: self.published.append(dict(message))
            if event == "faco_message_stream"
            else None,
        )
        self.publish.start()

    def tearDown(self):
        self.publish.stop()
        live_turn.unbind(self.sid)
        live_turn.clear(self.sid)
        frappe.set_user("Administrator")
        super().tearDown()

    def _dead_streaming_turn(self, seconds=61):
        builder = BlockBuilder(existing_blocks=[{"type": "text", "id": "t0", "content": "Half an ans"}])
        live = live_turn.bind(self.sid, builder, message_id="m-dead")
        live.ar_responded()
        # The relay thread died with its worker: nothing unbinds it, nothing writes again.
        live_turn._registry().pop(self.sid, None)
        _aged(self.sid, seconds)
        return live

    def _assistant_rows(self):
        return frappe.get_all(
            "FAC Chat Message",
            filters={"session_id": self.sid, "role": "assistant"},
            fields=["content", "blocks", "errored", "message_id"],
        )

    def test_get_live_turn_reports_staleness(self):
        self._dead_streaming_turn()
        self.assertTrue(live_turn.get_live_turn(self.sid)["stale"])
        _aged(self.sid, 1)
        self.assertFalse(live_turn.get_live_turn(self.sid)["stale"])

    def test_mark_interrupted_persists_partial_as_errored(self):
        self._dead_streaming_turn()
        result = live_turn.mark_turn_interrupted(self.sid)
        self.assertEqual(
            result,
            {
                "interrupted": True,
                "message_id": "m-dead",
                "error": "This answer was interrupted by a server restart.",
            },
        )
        rows = self._assistant_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].content, "Half an ans")
        self.assertEqual(rows[0].errored, 1)
        self.assertEqual(json.loads(rows[0].blocks)[0]["content"], "Half an ans")
        self.assertIsNone(live_turn.get(self.sid))
        error = self.published[-1]
        self.assertEqual(error["event"], "stream_error")
        self.assertEqual(error["error_code"], "TURN_INTERRUPTED")
        self.assertEqual(error["message_id"], "m-dead")

    def test_marking_a_stale_turn_interrupted_ends_credit_status_freshness(self):
        self._dead_streaming_turn()
        with patch.object(credit_status_cache, "invalidate", autospec=True) as invalidate:
            live_turn.mark_turn_interrupted(self.sid)

        invalidate.assert_called_once_with(self.owner)

    def test_freshness_is_ended_for_the_turn_owner_not_the_caller(self):
        self._dead_streaming_turn()
        # Production: a System Manager's stale check passes the owner gate for someone else's turn.
        frappe.set_user("Administrator")
        with patch.object(credit_status_cache, "invalidate", autospec=True) as invalidate:
            live_turn.mark_turn_interrupted(self.sid)

        invalidate.assert_called_once_with(self.owner)

    def test_freshness_fault_never_blocks_the_interrupt(self):
        self._dead_streaming_turn()
        # Production: the cache is Redis, which can fail while the turn is being reconciled.
        with patch.object(credit_status_cache, "invalidate", autospec=True, side_effect=RuntimeError("down")):
            result = live_turn.mark_turn_interrupted(self.sid)

        self.assertTrue(result["interrupted"])
        self.assertEqual(self._assistant_rows()[0].errored, 1)
        self.assertIsNone(live_turn.get(self.sid))

    def test_mark_interrupted_refuses_a_live_turn(self):
        self._dead_streaming_turn(seconds=5)
        self.assertEqual(live_turn.mark_turn_interrupted(self.sid), {"interrupted": False})
        self.assertIsNotNone(live_turn.get(self.sid))
        self.assertEqual(self._assistant_rows(), [])
        self.assertEqual(self.published, [])

    def test_mark_interrupted_twice_ends_the_turn_once(self):
        live_turn.start(self.sid)
        # Two surfaces reconcile together after the restart; both read the same stale entry.
        entry = _aged(self.sid, 181)
        with patch.object(live_turn, "get", return_value=entry):
            first = live_turn.mark_turn_interrupted(self.sid)
            second = live_turn.mark_turn_interrupted(self.sid)
        self.assertTrue(first["interrupted"])
        self.assertEqual(second, {"interrupted": False})
        self.assertEqual(len(self._assistant_rows()), 1)
        self.assertEqual([p["event"] for p in self.published], ["stream_error"])

    def test_mark_interrupted_with_nothing_running(self):
        self.assertEqual(live_turn.mark_turn_interrupted(self.sid), {"interrupted": False})

    def test_a_dead_queued_send_never_touches_the_previous_answer(self):
        frappe.get_doc(
            {
                "doctype": "FAC Chat Message",
                "session_id": self.sid,
                "user": self.owner,
                "role": "assistant",
                "content": "The earlier answer.",
                "message_id": "m-earlier",
            }
        ).insert(ignore_permissions=True)
        live_turn.start(self.sid)
        # The worker died before its relay ran: the starting entry is never written again.
        _aged(self.sid, 181)
        self.assertTrue(live_turn.mark_turn_interrupted(self.sid)["interrupted"])
        earlier = frappe.db.get_value(
            "FAC Chat Message", {"message_id": "m-earlier"}, ["content", "errored"], as_dict=True
        )
        self.assertEqual(earlier.content, "The earlier answer.")
        self.assertFalse(earlier.errored)

    def test_another_user_is_refused(self):
        self._dead_streaming_turn()
        frappe.set_user(self.other)
        with self.assertRaises(frappe.PermissionError):
            live_turn.mark_turn_interrupted(self.sid)
        frappe.set_user(self.owner)
        self.assertIsNotNone(live_turn.get(self.sid))

    def test_it_is_a_post_endpoint_on_the_chat_api_path(self):
        from frappe_assistant_core.chat.api import chat as chat_api

        self.assertIs(chat_api.mark_turn_interrupted, live_turn.mark_turn_interrupted)
        self.assertEqual(
            frappe.allowed_http_methods_for_whitelisted_func[live_turn.mark_turn_interrupted], ["POST"]
        )


class TestRelayAfterInterruption(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.sid = f"beat-relay-{frappe.generate_hash(length=8)}"

    def tearDown(self):
        live_turn.clear(self.sid)
        super().tearDown()

    def _run(self, *, resume=False):
        client = MagicMock()
        client.stream_chat.return_value = iter([])
        with (
            patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client),
            patch("frappe.init"),
            patch("frappe.connect"),
            patch("frappe.set_user"),
            patch("frappe.destroy"),
            patch.object(relay, "is_cancelled", return_value=False),
            patch("frappe.publish_realtime"),
        ):
            # The pool runs a queued relay after the SPA has already marked it interrupted.
            turn = live_turn.start(self.sid)
            live_turn.clear(self.sid, turn)
            if resume:
                relay._relay_ar_interrupt_resume(
                    self.sid, "[]", "Administrator", frappe.local.site, message_id="m1", live_turn_token=turn
                )
            else:
                relay._relay_ar_stream(
                    self.sid,
                    full_prompt="hi",
                    original_message="hi",
                    context=None,
                    message_name=None,
                    user="Administrator",
                    site=frappe.local.site,
                    live_turn_token=turn,
                )
        return client

    def test_relay_does_not_start_after_its_turn_was_interrupted(self):
        client = self._run()
        client.stream_chat.assert_not_called()
        self.assertIsNone(live_turn.get(self.sid))

    def test_relay_stops_once_its_turn_is_marked_interrupted(self):
        closed = []

        def stream(turn_cleared):
            try:
                yield {"event": "stream_start", "data": {"message_id": "m-old"}}
                yield {"event": "stream_chunk", "data": {"content": "Slow first "}}
                # The SPA marked the turn interrupted while AR was slow; the user may already
                # have pressed Retry.
                live_turn.clear(self.sid)
                turn_cleared.append(True)
                yield {
                    "event": "tool_call_start",
                    "data": {"tool_id": "t1", "tool_name": "get_list", "input": {}},
                }
                yield {"event": "stream_chunk", "data": {"content": "answer."}}
                yield {
                    "event": "stream_complete",
                    "data": {"full_response": "Slow first answer.", "message_id": "m-old"},
                }
            finally:
                closed.append(True)

        cleared = []
        client = MagicMock()
        client.stream_chat.return_value = stream(cleared)
        published = []
        turn = live_turn.start(self.sid)
        with (
            patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client),
            patch("frappe.init"),
            patch("frappe.connect"),
            patch("frappe.set_user"),
            patch("frappe.destroy"),
            patch.object(relay, "is_cancelled", return_value=False),
            patch.object(relay, "_update_subscription_cache"),
            patch(
                "frappe.publish_realtime",
                side_effect=lambda event, message, **kw: published.append(dict(message))
                if event == "faco_message_stream"
                else None,
            ),
        ):
            relay._relay_ar_stream(
                self.sid,
                full_prompt="hi",
                original_message="hi",
                context=None,
                message_name=None,
                user="Administrator",
                site=frappe.local.site,
                live_turn_token=turn,
            )
        self.assertEqual(cleared, [True])
        self.assertEqual(closed, [True])
        self.assertIsNone(live_turn.get(self.sid))
        self.assertNotIn("stream_complete", [p["event"] for p in published])
        content = frappe.db.get_value("FAC Chat Message", {"message_id": "m-old"}, "content")
        self.assertNotEqual(content, "Slow first answer.")

    def test_resume_does_not_start_after_its_turn_was_interrupted(self):
        client = self._run(resume=True)
        client.stream_chat.assert_not_called()
        self.assertIsNone(live_turn.get(self.sid))
