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
"""

import json
import unittest
from unittest.mock import MagicMock, patch

import frappe


class TestAbortPendingInteractionsMarkerRace(unittest.TestCase):
    def test_appends_marker_even_when_relay_already_set_aborted(self):
        # This is the exact shape of the observed bug: relay.py's abort
        # finalizer already wrote aborted=1 + the full partial text, with
        # no marker in blocks. The old code's `if row.get("aborted"):
        # return` bailed out here before ever looking at the marker.
        from frappe_assistant_core.chat.api.chat import cancel as cancel_mod

        row = frappe._dict(
            {
                "blocks": json.dumps([{"type": "text", "content": "Today, the"}]),
                "content": "Today, the",
                "aborted": 1,
            }
        )

        with patch.object(cancel_mod, "frappe") as fm, patch.object(cancel_mod, "_emit_socket_event"), patch(
            "frappe_assistant_core.chat.api.chat.relay._set_faco_message_with_retry"
        ) as setter:
            fm.db.get_value.side_effect = ["MSG-1", row]
            cancel_mod._abort_pending_interactions("S1", None)

        setter.assert_called_once()
        name, updates = setter.call_args[0]
        self.assertEqual(name, "MSG-1")
        blocks = json.loads(updates["blocks"])
        self.assertTrue(
            any(b.get("type") == "text" and b.get("_abortMarker") for b in blocks),
            "marker block must be appended even though the row was already aborted",
        )
        self.assertTrue(updates["content"].startswith("Today, the"))
        self.assertIn("Stopped by user", updates["content"])

    def test_no_op_write_when_marker_already_present(self):
        # The other writer (relay.py, post-fix) already appended the
        # marker. cancel.py must not duplicate it or clobber content.
        from frappe_assistant_core.chat.api.chat import cancel as cancel_mod

        row = frappe._dict(
            {
                "blocks": json.dumps(
                    [
                        {"type": "text", "content": "Today, the"},
                        {
                            "type": "text",
                            "content": "\n\n_(Stopped by user)_",
                            "_abortMarker": True,
                        },
                    ]
                ),
                "content": "Today, the\n\n_(Stopped by user)_",
                "aborted": 1,
            }
        )

        with patch.object(cancel_mod, "frappe") as fm, patch.object(
            cancel_mod, "_emit_socket_event"
        ) as emit, patch("frappe_assistant_core.chat.api.chat.relay._set_faco_message_with_retry") as setter:
            fm.db.get_value.side_effect = ["MSG-1", row]
            cancel_mod._abort_pending_interactions("S1", None)

        setter.assert_called_once_with("MSG-1", {"aborted": 1})
        emit.assert_not_called()

    def test_still_resolves_pending_interaction_blocks(self):
        # Unrelated to the marker race — guards that the pre-existing HITL
        # behavior (flip pending interaction cards to aborted) survived
        # the rewrite.
        from frappe_assistant_core.chat.api.chat import cancel as cancel_mod

        row = frappe._dict(
            {
                "blocks": json.dumps(
                    [{"type": "interaction", "status": "pending", "tool_name": "delete_record"}]
                ),
                "content": "",
                "aborted": 0,
            }
        )

        with patch.object(cancel_mod, "frappe") as fm, patch.object(cancel_mod, "_emit_socket_event"), patch(
            "frappe_assistant_core.chat.api.chat.relay._set_faco_message_with_retry"
        ) as setter:
            fm.db.get_value.side_effect = ["MSG-1", row]
            cancel_mod._abort_pending_interactions("S1", None)

        updates = setter.call_args[0][1]
        blocks = json.loads(updates["blocks"])
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
                "S1", "ar-1", "Today, the", block_builder, [], "claude-sonnet-4-6", stream_iter
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
            relay._handle_stream_aborted("S1", "ar-1", "Today, the", block_builder, [], "", stream_iter)

        persisted_blocks = persist.call_args[0][3]
        markers = [b for b in persisted_blocks if b.get("_abortMarker")]
        self.assertEqual(len(markers), 1)


if __name__ == "__main__":
    unittest.main()
