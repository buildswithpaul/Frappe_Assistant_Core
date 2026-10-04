"""Regression tests for E2E-1: a Stop mid-stream persisted aborted=1 with
no "(Stopped by user)" marker anywhere — the truncated answer looked like
a crash rather than a deliberate Stop.

Root cause: two independent writers can finalize the same aborted row —
relay.py's own abort finalizer (``_handle_stream_aborted``, live while a
stream is running) and cancel.py's HITL-pause finalizer
(``_abort_pending_interactions``, always run from the cancel_stream
request) — reacting to the same Redis cancel flag from different threads.
Only cancel.py ever appended the marker, and it used to bail out early
whenever the row already had ``aborted=1`` — which is exactly what relay.py
sets when IT wins the race, so the marker was silently never written.

These tests pin both directions of the race:
  * relay.py wins first (the confirmed live scenario) -> cancel.py must
    still add the marker onto relay's already-complete content.
  * cancel.py wins first -> relay.py's own finalizer must add the marker
    itself rather than relying on cancel.py having done it.

cancel.py's read-merge-write runs inside a locking read
(``_update_faco_message_merged`` in relay.py, ``for_update=True``), so
``TestAbortPendingInteractionsMarkerRace`` below runs against real FAC Chat
Message rows rather than a fully-mocked ``frappe`` module: the read+write
spans cancel.py (locates the row) and relay.py (the locked read and the
write), and a whole-module mock of ``cancel_mod.frappe`` does not reach
the second half of that. See test_stop_without_a_named_turn.py's
``TestAbortMergedRetryNeverLosesRelayText`` for the retry-specific coverage
(the deadlock-and-re-read path these tests don't otherwise exercise).
"""

import json
import unittest
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestAbortPendingInteractionsMarkerRace(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("abort-marker-race")
        frappe.set_user(self.user)
        self.sid = f"abort-marker-race-{frappe.generate_hash(length=8)}"

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _row(self, blocks: list, content: str, *, aborted: int = 0, message_id: str | None = None) -> str:
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
                    "aborted": aborted,
                }
            )
            .insert(ignore_permissions=True, ignore_mandatory=not content)
            .name
        )

    def _stored(self, name: str):
        row = frappe.db.get_value("FAC Chat Message", name, ["content", "blocks", "aborted"], as_dict=True)
        return row, (json.loads(row.blocks) if row.blocks else [])

    def test_appends_marker_even_when_relay_already_set_aborted(self):
        # This is the exact shape of the observed bug: relay.py's abort
        # finalizer already wrote aborted=1 + the full partial text, with
        # no marker in blocks. The old code's `if row.get("aborted"):
        # return` bailed out here before ever looking at the marker.
        from frappe_assistant_core.chat.api.chat import cancel as cancel_mod

        name = self._row([{"type": "text", "content": "Today, the"}], "Today, the", aborted=1)

        with patch.object(cancel_mod, "_emit_socket_event"):
            # _is_open_turn also checks for a newer user row; no such row
            # here, so this candidate is still open (aborted, no marker yet).
            cancel_mod._abort_pending_interactions(self.sid, None)

        row, blocks = self._stored(name)
        self.assertTrue(
            any(b.get("type") == "text" and b.get("_abortMarker") for b in blocks),
            "marker block must be appended even though the row was already aborted",
        )
        self.assertTrue(row.content.startswith("Today, the"))
        self.assertIn("Stopped by user", row.content)

    def test_no_op_write_when_marker_already_present(self):
        # The other writer (relay.py, post-fix) already appended the
        # marker to the turn this Stop names. cancel.py must not duplicate
        # it or clobber content: it writes only ``aborted``, which the row
        # does not carry yet. (A Stop that names no turn leaves a row that
        # already carries the marker alone: see _is_open_turn.)
        from frappe_assistant_core.chat.api.chat import cancel as cancel_mod

        blocks_in = [
            {"type": "text", "content": "Today, the"},
            {"type": "text", "content": "\n\n_(Stopped by user)_", "_abortMarker": True},
        ]
        content_in = "Today, the\n\n_(Stopped by user)_"
        name = self._row(blocks_in, content_in, aborted=0, message_id="ar-1")
        before, _ = self._stored(name)
        self.assertEqual(before.aborted, 0)

        with patch.object(cancel_mod, "_emit_socket_event") as emit:
            cancel_mod._abort_pending_interactions(self.sid, "ar-1")

        row, _ = self._stored(name)
        self.assertEqual(row.aborted, 1)
        self.assertEqual((row.content, row.blocks), (before.content, before.blocks))
        emit.assert_not_called()

    def test_returns_and_emits_the_rows_own_message_id_not_the_callers(self):
        # The caller's message_id can be a client-side id with no meaning to
        # another client watching the same session (the SPA's own
        # _requestId, or nothing at all before a turn's stream_start). The
        # stream_aborted event, and the value the caller (cancel_stream)
        # uses to build its own ping, must name AR's own id for the turn —
        # the row's own message_id field — not the caller's.
        from frappe_assistant_core.chat.api.chat import cancel as cancel_mod

        self._row(
            [{"type": "interaction", "status": "pending", "tool_name": "delete_record"}],
            "Today, the",
            message_id="ar-real-id",
        )

        with patch.object(cancel_mod, "_emit_socket_event") as emit:
            # _is_open_turn also checks for a newer user row; no such row
            # here, so this candidate is still open.
            result = cancel_mod._abort_pending_interactions(self.sid, None)

        self.assertEqual(result, "ar-real-id")
        payload = emit.call_args[0][1]
        self.assertEqual(payload["message_id"], "ar-real-id")

    def test_still_resolves_pending_interaction_blocks(self):
        # Unrelated to the marker race — guards that the pre-existing HITL
        # behavior (flip pending interaction cards to aborted) survived
        # the rewrite.
        from frappe_assistant_core.chat.api.chat import cancel as cancel_mod

        name = self._row(
            [{"type": "interaction", "status": "pending", "tool_name": "delete_record"}],
            "",
        )

        with patch.object(cancel_mod, "_emit_socket_event"):
            # _is_open_turn also checks for a newer user row; no such row
            # here, so this candidate is still open.
            cancel_mod._abort_pending_interactions(self.sid, None)

        row, blocks = self._stored(name)
        interaction = next(b for b in blocks if b["type"] == "interaction")
        self.assertEqual(interaction["status"], "aborted")
        self.assertTrue(any(b.get("_abortMarker") for b in blocks))


class TestHandleStreamAbortedAppendsMarker(unittest.TestCase):
    def test_appends_marker_to_persisted_content_and_blocks(self):
        # The other side of the race: cancel.py may not have run yet (or
        # loses the race), so relay's own finalizer must be self-sufficient
        # rather than depending on cancel.py to add the marker.
        from frappe_assistant_core.chat.api.chat import relay

        block_builder = MagicMock()
        block_builder.snapshot.return_value = [{"type": "text", "content": "Today, the"}]
        stream_iter = MagicMock()

        with patch.object(relay, "_persist_partial_assistant_turn") as persist, patch.object(
            relay, "_emit_socket_event"
        ) as emit:
            relay._handle_stream_aborted(
                "S1", "ar-1", "Today, the", block_builder, [], "claude-sonnet-4-6", stream_iter=stream_iter
            )

        stream_iter.close.assert_called_once()

        persist.assert_called_once()
        persisted_content = persist.call_args[0][2]
        persisted_blocks = persist.call_args[0][3]
        self.assertTrue(persisted_content.startswith("Today, the"))
        self.assertIn("Stopped by user", persisted_content)
        self.assertTrue(any(b.get("_abortMarker") for b in persisted_blocks))

        emit.assert_called_once()
        payload = emit.call_args[0][1]
        self.assertIn("Stopped by user", payload["partial_response"])
        self.assertTrue(any(b.get("_abortMarker") for b in payload["blocks"]))

    def test_does_not_duplicate_an_existing_marker(self):
        # If the block_builder snapshot somehow already carries a marker
        # (e.g. a future code path pre-seeds it), appending must be a
        # no-op rather than stacking a second one.
        from frappe_assistant_core.chat.api.chat import relay

        block_builder = MagicMock()
        block_builder.snapshot.return_value = [
            {"type": "text", "content": "Today, the"},
            {"type": "text", "content": "\n\n_(Stopped by user)_", "_abortMarker": True},
        ]
        stream_iter = MagicMock()

        with patch.object(relay, "_persist_partial_assistant_turn") as persist, patch.object(
            relay, "_emit_socket_event"
        ):
            relay._handle_stream_aborted(
                "S1", "ar-1", "Today, the", block_builder, [], "", stream_iter=stream_iter
            )

        persisted_blocks = persist.call_args[0][3]
        markers = [b for b in persisted_blocks if b.get("_abortMarker")]
        self.assertEqual(len(markers), 1)


if __name__ == "__main__":
    unittest.main()
