# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Suggested replies (#35327): the answers a reply offered are stored on it and sent to the browser."""

from unittest.mock import patch

from frappe_assistant_core.chat.api.block_builder import (
    MAX_SUGGESTED_REPLY_CHARS,
    BlockBuilder,
    clean_suggested_replies,
)
from frappe_assistant_core.chat.api.chat import relay
from frappe_assistant_core.tests.base_test import BaseAssistantTest

# What the runtime sends just before stream_complete (assistant_runtime agent/suggested_replies.py).
REPLIES = ["Yes, submit it", "Explain the entries first", "Stop here"]


def _relay(data: dict) -> tuple[list, list]:
    """One event through the relay, as both loops hand it over: the blocks and what was emitted."""
    builder = BlockBuilder()
    builder.add_text("Shall I submit it?")
    with patch.object(relay, "_emit_socket_event", autospec=True) as emit:
        handled = relay._dispatch_relay_event("suggested_replies", data, "s1", builder, ar_message_id="m1")
    assert handled
    return builder.snapshot(), [call.args[1] for call in emit.call_args_list]


class TestSuggestedReplies(BaseAssistantTest):
    def test_the_answers_are_stored_on_the_reply_and_sent_to_the_browser(self):
        blocks, sent = _relay({"replies": REPLIES})

        stored = [b for b in blocks if b["type"] == "suggested_replies"]
        self.assertEqual([b["replies"] for b in stored], [REPLIES])
        self.assertEqual(
            sent,
            [{"event": "suggested_replies", "session_id": "s1", "message_id": "m1", "replies": REPLIES}],
        )

    def test_a_second_set_replaces_the_first(self):
        builder = BlockBuilder()
        builder.set_suggested_replies(["Yes"])
        builder.set_suggested_replies(["No"])

        self.assertEqual(
            [b["replies"] for b in builder.snapshot() if b["type"] == "suggested_replies"], [["No"]]
        )

    def test_malformed_answers_change_nothing(self):
        for replies in (None, "Yes", [], [None, 7, "   "], {"a": 1}):
            blocks, sent = _relay({"replies": replies})

            self.assertFalse([b for b in blocks if b["type"] == "suggested_replies"], replies)
            self.assertEqual(sent, [], replies)

    def test_answers_are_one_line_deduplicated_and_capped(self):
        self.assertEqual(
            clean_suggested_replies(
                [
                    "Yes,\n go ahead",
                    "yes, go ahead",
                    "x" * (MAX_SUGGESTED_REPLY_CHARS + 1),
                    "No",
                    "Later",
                    "Fourth",
                ]
            ),
            ["Yes, go ahead", "No", "Later"],
        )
