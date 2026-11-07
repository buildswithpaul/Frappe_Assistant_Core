import inspect
import unittest
from unittest.mock import patch

from frappe_assistant_core.chat.api.block_builder import BlockBuilder
from frappe_assistant_core.chat.api.chat import relay

_CHANGE = {"tool": "create_document", "doctype": "ToDo", "name": "TD-1", "action": "create", "undo": "delete"}


def _dispatch(builder, changes, message_id="m1"):
    with patch.object(relay, "_emit_socket_event") as emit:
        handled = relay._dispatch_relay_event(
            "changes_made", {"changes": changes}, "s1", builder, ar_message_id=message_id
        )
    return handled, emit


def _changes_blocks(builder):
    return [b for b in builder.snapshot() if b.get("type") == "changes_made"]


class TestRelayChangesMade(unittest.TestCase):
    def test_changes_made_is_relayed_and_persisted_in_stream(self):
        # The main loop hands every event to _dispatch_relay_event first.
        self.assertIn("_dispatch_relay_event(", inspect.getsource(relay._relay_ar_stream))
        builder = BlockBuilder()

        handled, emit = _dispatch(builder, [_CHANGE])

        self.assertTrue(handled)
        emit.assert_called_once()
        self.assertEqual(
            emit.call_args.args[1],
            {"event": "changes_made", "session_id": "s1", "message_id": "m1", "changes": [_CHANGE]},
        )
        (block,) = _changes_blocks(builder)
        self.assertEqual(
            [(c["doctype"], c["name"], c["undone"]) for c in block["changes"]], [("ToDo", "TD-1", False)]
        )

    def test_changes_made_is_relayed_on_resume(self):
        # The resume loop dispatches through the same function, and the event
        # proves AR is running the resumed turn, so it consumes the pause.
        self.assertIn("_dispatch_relay_event(", inspect.getsource(relay._relay_ar_interrupt_resume))
        self.assertIn("changes_made", relay._RESUME_PROGRESS_EVENTS)
        self.assertIn("changes_made", relay._SHARED_RELAY_EVENTS)

    def test_approval_reason_keeps_level(self):
        # Both loops forward the interrupts list whole, so reason["level"] passes.
        for fn in (relay._relay_ar_stream, relay._relay_ar_interrupt_resume):
            self.assertIn('"interrupts": data.get("interrupts", [])', inspect.getsource(fn))
        interrupts = [{"id": "i1", "reason": {"level": "R3", "kind": "write"}}]
        builder = BlockBuilder()
        builder.add_approval_required("t1", "update_document", {}, interrupts)
        card = next(b for b in builder.snapshot() if b.get("type") == "interaction")
        self.assertEqual(card["interrupts"][0]["reason"]["level"], "R3")

    def test_undone_flag_survives_a_later_stream_end_snapshot(self):
        # Production: the stream's pause snapshot stores the block, the user presses Undo
        # (mark_change_undone writes undone=True to the row), then the next stream seeds
        # its BlockBuilder from that row and repeats the same change on the way out.
        row_blocks = [
            {
                "type": "changes_made",
                "id": "cm1",
                "changes": [{**_CHANGE, "undone": True}],
            }
        ]
        builder = BlockBuilder(existing_blocks=row_blocks)

        _dispatch(builder, [_CHANGE, {**_CHANGE, "name": "TD-2"}])

        (block,) = _changes_blocks(builder)
        flags = {c["name"]: c["undone"] for c in block["changes"]}
        self.assertEqual(flags, {"TD-1": True, "TD-2": False})

    def test_empty_or_malformed_changes_add_no_block(self):
        builder = BlockBuilder()
        _dispatch(builder, [{"doctype": "ToDo"}])
        self.assertEqual(_changes_blocks(builder), [])

    def test_malformed_changes_are_dropped_not_raised(self):
        # AR's payload is untrusted: only well-formed create/delete entries may reach the
        # block that gates undo_change, or the socket.
        changes = [
            "x",
            None,
            {"doctype": {}, "name": "a"},
            {"doctype": 5, "name": "a"},
            {"doctype": "Note", "name": "N-1", "action": "delete", "undo": "delete"},
            {"doctype": "Note", "name": "N-2", "action": "create", "undo": "delete"},
        ]
        builder = BlockBuilder()

        handled, emit = _dispatch(builder, changes)

        self.assertTrue(handled)
        (block,) = _changes_blocks(builder)
        self.assertEqual([c["name"] for c in block["changes"]], ["N-2"])
        self.assertEqual([c["name"] for c in emit.call_args.args[1]["changes"]], ["N-2"])

    def test_non_list_or_all_invalid_changes_emit_nothing(self):
        for changes in ({"doctype": "Note"}, "Note", ["x"], None):
            builder = BlockBuilder()
            handled, emit = _dispatch(builder, changes)
            self.assertTrue(handled)
            emit.assert_not_called()
            self.assertEqual(_changes_blocks(builder), [])


if __name__ == "__main__":
    unittest.main()
