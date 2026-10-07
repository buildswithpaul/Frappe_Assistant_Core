"""Live-turn snapshots: lifecycle, write policy and turn ownership."""

from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.block_builder import BlockBuilder
from frappe_assistant_core.chat.api.chat import live_turn
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestLiveTurnModule(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.sid = f"live-{frappe.generate_hash(length=10)}"

    def tearDown(self):
        live_turn.unbind(self.sid)
        live_turn.clear(self.sid)
        super().tearDown()

    def test_start_writes_a_starting_entry_that_keeps_the_rows_content(self):
        turn = live_turn.start(self.sid, message_id="m1")
        entry = live_turn.get(self.sid)
        self.assertEqual(entry["turn"], turn)
        self.assertEqual(entry["status"], "starting")
        self.assertEqual(entry["message_id"], "m1")
        self.assertEqual(entry["seq"], 0)
        self.assertIsNone(entry["blocks"])
        self.assertIsNone(entry["text"])

    def test_get_is_none_when_no_turn_runs(self):
        self.assertIsNone(live_turn.get(self.sid))

    def test_bind_writes_the_builders_state_at_once(self):
        builder = BlockBuilder(existing_blocks=[{"type": "text", "id": "t0", "content": "Part one. "}])
        live = live_turn.bind(self.sid, builder, message_id="m1")
        entry = live_turn.get(self.sid)
        self.assertEqual(entry["turn"], live.turn)
        self.assertEqual(entry["status"], "streaming")
        self.assertEqual(entry["text"], "Part one. ")
        self.assertEqual(entry["blocks"][0]["content"], "Part one. ")

    def test_stamp_numbers_events_from_one_under_the_turn(self):
        live = live_turn.bind(self.sid, BlockBuilder())
        first, second = {"event": "heartbeat"}, {"event": "heartbeat"}
        live.stamp(first)
        live.stamp(second)
        self.assertEqual((first["turn"], first["seq"]), (live.turn, 1))
        self.assertEqual(second["seq"], 2)

    def test_a_block_event_is_written_at_once(self):
        builder = BlockBuilder()
        live = live_turn.bind(self.sid, builder)
        builder.add_tool_call_start("toolu_1", "get_list", {})
        event = {"event": "tool_call_start", "tool_id": "toolu_1"}
        live.stamp(event)
        live.record(event)
        entry = live_turn.get(self.sid)
        self.assertEqual(entry["seq"], 1)
        self.assertEqual(entry["blocks"][-1]["id"], "toolu_1")

    def test_text_chunks_are_written_at_most_every_interval(self):
        builder = BlockBuilder()
        clock = iter([100.0, 100.1, 100.7, 100.7])
        with patch.object(live_turn, "_clock", side_effect=lambda: next(clock)):
            live = live_turn.bind(self.sid, builder)  # write at 100.0
            for chunk in ("Hel", "lo"):
                builder.add_text(chunk)
                event = {"event": "stream_chunk", "chunk": chunk}
                live.stamp(event)
                live.record(event)
        entry = live_turn.get(self.sid)
        # 100.1 skipped (0.1s after the bind write); 100.7 written (one read to decide, one to stamp the write)
        self.assertEqual(entry["seq"], 2)
        self.assertEqual(entry["text"], "Hello")

    def test_a_skipped_chunk_leaves_the_last_written_seq(self):
        builder = BlockBuilder()
        clock = iter([100.0, 100.1])
        with patch.object(live_turn, "_clock", side_effect=lambda: next(clock)):
            live = live_turn.bind(self.sid, builder)
            builder.add_text("Hi")
            event = {"event": "stream_chunk", "chunk": "Hi"}
            live.stamp(event)
            live.record(event)
        self.assertEqual(live_turn.get(self.sid)["seq"], 0)

    def test_text_is_the_text_blocks_including_a_seeded_first_part(self):
        builder = BlockBuilder(existing_blocks=[{"type": "text", "id": "t0", "content": "First. "}])
        live = live_turn.bind(self.sid, builder, message_id="m1")
        builder.add_tool_call_start("toolu_1", "get_list", {})
        builder.add_text("Second.")
        event = {"event": "tool_call_start", "tool_id": "toolu_1"}
        live.stamp(event)
        live.record(event)
        self.assertEqual(live_turn.get(self.sid)["text"], "First. Second.")

    def test_the_open_thinking_block_is_named(self):
        builder = BlockBuilder()
        live = live_turn.bind(self.sid, builder)
        builder.add_thinking("Let me see")
        event = {"event": "thinking", "content": "Let me see"}
        live.stamp(event)
        live.record(event)
        entry = live_turn.get(self.sid)
        self.assertEqual(entry["active_thinking_id"], builder.active_thinking_id)
        self.assertIsNotNone(entry["active_thinking_id"])

    def test_tool_results_are_trimmed_like_the_emitted_event(self):
        builder = BlockBuilder()
        live = live_turn.bind(self.sid, builder)
        builder.add_tool_call_start("toolu_1", "get_list", {})
        builder.add_tool_call_result("toolu_1", "x" * 200_000)
        event = {"event": "tool_call_result", "tool_id": "toolu_1"}
        live.stamp(event)
        live.record(event)
        stored = live_turn.get(self.sid)["blocks"][-1]["result"]
        self.assertLess(len(str(stored)), 200_000)

    def test_a_terminal_event_deletes_the_entry(self):
        for terminal in sorted(live_turn.TERMINAL_EVENTS):
            with self.subTest(terminal=terminal):
                live = live_turn.bind(self.sid, BlockBuilder())
                event = {"event": terminal}
                live.stamp(event)
                live.record(event)
                self.assertIsNone(live_turn.get(self.sid))
                live_turn.unbind(self.sid)

    def test_a_stale_turn_never_clears_a_newer_turn(self):
        # The previous relay's finally runs after the next send's start().
        live_turn.bind(self.sid, BlockBuilder())
        newer = live_turn.start(self.sid)
        live_turn.unbind(self.sid)
        self.assertEqual(live_turn.get(self.sid)["turn"], newer)

    def test_clear_with_a_matching_turn_deletes(self):
        turn = live_turn.start(self.sid)
        live_turn.clear(self.sid, turn)
        self.assertIsNone(live_turn.get(self.sid))

    def test_a_disabled_bind_writes_nothing_and_binds_nothing(self):
        # GDPR-restricted users: nothing about their turn is stored.
        self.assertIsNone(live_turn.bind(self.sid, BlockBuilder(), enabled=False))
        self.assertIsNone(live_turn.current(self.sid))
        self.assertIsNone(live_turn.get(self.sid))

    def test_current_is_the_bound_turn_until_unbind(self):
        live = live_turn.bind(self.sid, BlockBuilder())
        self.assertIs(live_turn.current(self.sid), live)
        live_turn.unbind(self.sid)
        self.assertIsNone(live_turn.current(self.sid))
        self.assertIsNone(live_turn.get(self.sid))
