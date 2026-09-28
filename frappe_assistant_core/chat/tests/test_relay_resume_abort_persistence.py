"""_persist_resume_cycle backs both the resume funnel's stream_complete
persistence and its Stop-mid-resume abort path. full_response passed
into it only ever holds the CURRENT resume cycle's text — one logical
turn can span several resume cycles. It must therefore APPEND to
whatever the row already holds rather than replacing it.

A cycle that is NOT itself finalizing a Stop (a clean finish or an error)
must not clobber a row a concurrent cancel_stream already marked
``aborted``. A cycle that IS finalizing a Stop must not skip such a row
either — cancel_stream's own local finalizer can win that exact race —
so it appends its text and reapplies the marker instead of losing the
cycle.

Taking over that row must also never leave an actionable card behind:
AR announces an approved tool only once, so a Stop pressed while it is
still running finalizes the row before this cycle's own snapshot ever
saw the card flip off ``pending``. That snapshot's card is settled
``aborted`` too, the same way cancel_stream settles its own copy, so a
reload never offers Approve/Reject on a turn the user stopped.

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

import json
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

    def test_skips_persist_of_a_non_aborting_cycle_when_the_row_is_already_aborted(self):
        # cancel.py's _abort_pending_interactions may have already written
        # the "(Stopped by user)" marker onto this row moments earlier —
        # a cycle that is NOT itself finalizing a Stop (a clean finish or an
        # error) must not clobber it with this cycle's (possibly stale) text.
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
                errored=True,
            )

        setter.assert_not_called()

    def test_a_stop_finalizing_cycle_still_writes_over_an_already_aborted_row(self):
        # cancel_stream always runs _abort_pending_interactions locally as
        # well as flipping the cancel flag, so IT can mark the row aborted
        # before this resume cycle's own Stop-finalizing call runs. That
        # call must not skip and lose this cycle's text and tool calls — it
        # strips the other writer's marker, appends its own text, and
        # reapplies the marker once.
        from frappe_assistant_core.chat.api.chat import relay

        block_builder = MagicMock()
        block_builder.snapshot.return_value = [{"type": "text", "content": "this cycle's new text"}]
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
        ), patch.object(relay, "_set_faco_message_with_retry") as setter, patch("frappe.utils.now_datetime"):
            # append_abort_marker's marker id reads the system timezone via
            # frappe.utils.now_datetime(); the blanket frappe.db.get_value
            # patch above would otherwise answer that lookup with `row` too.
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
        self.assertEqual(updates["content"], "earlier text\n\nthis cycle's new text\n\n_(Stopped by user)_")
        self.assertEqual(updates["content"].count("Stopped by user"), 1)
        self.assertEqual(updates["aborted"], 1)

    def test_a_stop_while_the_approved_tool_still_runs_never_leaves_a_pending_card(self):
        # RB1: the user approves a card, AR resumes the tool without
        # announcing it again (it is announced only once), so while it runs
        # this cycle's own block_builder has seen nothing past stream_start
        # and heartbeats — its card is still 'pending' in memory. The user
        # presses Stop; cancel_stream's _abort_pending_interactions runs
        # first and marks the DB row aborted with the card settled and the
        # marker written. The relay's poll then calls this Stop-finalizing
        # cycle, which (per the test above) must still write over that row
        # so this cycle's tool row and text survive — but its own snapshot's
        # card must not be allowed to overwrite the DB's settled card back
        # to an actionable 'pending' one.
        from frappe_assistant_core.chat.api.chat import relay

        pending_card = {
            "type": "interaction",
            "id": "card-1",
            "status": "pending",
            "interaction_type": "approval",
        }
        block_builder = MagicMock()
        block_builder.snapshot.return_value = [pending_card]
        row = frappe._dict(
            {
                # cancel_stream already settled and marked this row.
                "content": "earlier text\n\n_(Stopped by user)_",
                "tool_calls": None,
                "aborted": 1,
                "credits_used": 0,
            }
        )

        with patch.object(relay, "_find_assistant_msg_by_message_id", return_value="MSG-1"), patch(
            "frappe.db.get_value", return_value=row
        ), patch.object(relay, "_set_faco_message_with_retry") as setter, patch("frappe.utils.now_datetime"):
            relay._persist_resume_cycle(
                "S1",
                "ar-1",
                "ar-1",
                "",
                block_builder,
                [],
                aborted=True,
            )

        setter.assert_called_once()
        updates = setter.call_args[0][1]
        written_blocks = json.loads(updates["blocks"])
        card_statuses = [b["status"] for b in written_blocks if b.get("type") == "interaction"]
        self.assertNotIn("pending", card_statuses)
        self.assertEqual(card_statuses, ["aborted"])
        self.assertEqual(written_blocks[0]["result"], {"message": "Stopped by user"})
        self.assertEqual(updates["content"].count("Stopped by user"), 1)
        self.assertEqual(updates["aborted"], 1)

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
