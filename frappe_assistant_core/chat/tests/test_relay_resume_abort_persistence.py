"""_persist_resume_cycle backs both the resume funnel's stream_complete
persistence and its Stop-mid-resume abort path. full_response passed
into it only ever holds the CURRENT resume cycle's text — one logical
turn can span several resume cycles. It must therefore APPEND to
whatever the row already holds rather than replacing it, and must not
clobber a row a concurrent cancel_stream already marked ``aborted``.

Before this helper existed, the abort branch called the send funnel's
_handle_stream_aborted -> _persist_partial_assistant_turn, which writes
``content = partial_response`` outright (see
test_relay_partial_persistence.py's own assertion that that helper
replaces, by design, for the send funnel where full_response holds the
whole turn). Reusing it here silently discarded everything earlier
resume cycles had already persisted, and skipped the aborted guard the
completion path has, letting it race a concurrent HITL-abort write from
cancel.py.
"""

import unittest
from unittest.mock import MagicMock, patch

import frappe


class TestPersistResumeCycleAppendsRatherThanReplaces(unittest.TestCase):
    def test_appends_this_cycles_text_to_existing_content(self):
        from frappe_assistant_core.chat.api.chat import relay

        block_builder = MagicMock()
        block_builder.snapshot.return_value = []
        row = frappe._dict(
            {"content": "earlier cycle's answer", "tool_calls": None, "aborted": 0, "credits_used": 0}
        )

        with patch.object(relay, "_find_assistant_msg_by_message_id", return_value="MSG-1"), patch(
            "frappe.db.get_value", return_value=row
        ), patch.object(relay, "_set_faco_message_with_retry") as setter:
            relay._persist_resume_cycle(
                "S1",
                "ar-1",
                "ar-1",
                "this cycle's new text",
                block_builder,
                [],
                aborted=True,
            )

        setter.assert_called_once()
        updates = setter.call_args[0][1]
        self.assertIn("earlier cycle's answer", updates["content"])
        self.assertIn("this cycle's new text", updates["content"])
        self.assertEqual(updates["aborted"], 1)

    def test_skips_persist_when_row_already_aborted(self):
        # cancel.py's _abort_pending_interactions may have already written
        # the "(Stopped by user)" marker onto this row moments earlier —
        # this must not clobber it with this cycle's (possibly stale) text.
        from frappe_assistant_core.chat.api.chat import relay

        block_builder = MagicMock()
        block_builder.snapshot.return_value = []
        row = frappe._dict(
            {
                "content": "earlier text\n\n_(Stopped by user)_",
                "tool_calls": None,
                "aborted": 1,
                "credits_used": 0,
            }
        )

        with patch.object(relay, "_find_assistant_msg_by_message_id", return_value="MSG-1"), patch(
            "frappe.db.get_value", return_value=row
        ), patch.object(relay, "_set_faco_message_with_retry") as setter:
            relay._persist_resume_cycle(
                "S1",
                "ar-1",
                "ar-1",
                "text that would clobber the marker",
                block_builder,
                [],
                aborted=True,
            )

        setter.assert_not_called()

    def test_no_existing_row_returns_none(self):
        from frappe_assistant_core.chat.api.chat import relay

        block_builder = MagicMock()

        with patch.object(relay, "_find_assistant_msg_by_message_id", return_value=None), patch.object(
            relay, "_set_faco_message_with_retry"
        ) as setter:
            result = relay._persist_resume_cycle(
                "S1", "ar-1", "ar-1", "text", block_builder, [], aborted=True
            )

        self.assertIsNone(result)
        setter.assert_not_called()


if __name__ == "__main__":
    unittest.main()
