# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""A rejected tool's cancel marks its tool row, not its approval card.

AR answers a rejected approval with ``tool_cancelled`` for the gated call.
The approval card carries the same id as that call's ``tool_call`` block and
comes after it, and ``BlockBuilder.add_tool_cancelled`` flipped the last block
with the id, whatever its type. So the saved card read ``cancelled`` instead
of the ``rejected`` the resume had given it, and the tool row was left
``running`` until AR's own result for the call arrived: a turn stopped in
between was saved with the rejected tool still spinning.

The builder tests are pure. The resume tests drive ``_relay_ar_interrupt_resume``
over a fake SDK stream against a real FAC Chat Message row owned by a
throwaway user; the worker-thread Frappe context, the cancel flag, the socket
and the quota cache are stubbed, and the row rolls back with the class.
"""

import json
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.api.block_builder import BlockBuilder
from frappe_assistant_core.chat.api.chat import relay
from frappe_assistant_core.tests.base_test import BaseAssistantTest

TOOL_ID = "toolu_1"
MESSAGE_ID = "msg-rejected-tool"
PAUSED_TEXT = "I will create the ToDo once you approve."
APPROVAL = {
    "id": "int-1",
    "name": "create_document",
    "reason": {"type": "approval", "action": "Create a ToDo"},
}
REJECT = [{"interruptId": "int-1", "response": "rejected"}]
# AR's cancel message for a rejection (approval_hook.py), shortened.
REJECTION = "The user explicitly rejected the create_document action and does not want to proceed."
ANSWER = "Understood, I will not create it."


def _event(name: str, **data) -> dict:
    return {"event": name, "data": data}


RESUMED_START = _event("stream_start", message_id=MESSAGE_ID, resumed=True, zero_retention=False)
TOOL_CANCELLED = _event("tool_cancelled", tool_id=TOOL_ID, tool_name="create_document", message=REJECTION)
# Strands also returns the cancelled call's result, which AR relays after the cancel.
CANCELLED_RESULT = _event("tool_call_result", tool_id=TOOL_ID, result=[{"text": REJECTION}], status="error")


def _paused_builder() -> BlockBuilder:
    """A turn paused at an approval: AR emits tool_call_start before approval_required."""
    builder = BlockBuilder()
    builder.add_text(PAUSED_TEXT)
    builder.add_tool_call_start(TOOL_ID, "create_document", {"doctype": "ToDo"})
    builder.add_approval_required(TOOL_ID, "create_document", {"doctype": "ToDo"}, [APPROVAL])
    return builder


def _only(blocks: list[dict], block_type: str) -> dict:
    (block,) = (b for b in blocks if b.get("type") == block_type and b.get("id") == TOOL_ID)
    return block


class TestAddToolCancelled(unittest.TestCase):
    def test_a_rejected_tools_cancel_marks_the_tool_call_and_keeps_the_card(self):
        builder = _paused_builder()
        builder.resolve_pending_interactions(REJECT)
        card_before = _only(builder.snapshot(), "interaction")

        builder.add_tool_cancelled(TOOL_ID, REJECTION)

        blocks = builder.snapshot()
        card, tool = _only(blocks, "interaction"), _only(blocks, "tool_call")
        self.assertEqual((card["status"], tool["status"]), ("rejected", "cancelled"))
        self.assertEqual(card, card_before)
        self.assertEqual(tool["result"], {"message": REJECTION})
        self.assertTrue(tool["endTime"])

    def test_a_cancel_that_names_no_tool_call_changes_nothing(self):
        """ask_user has no tool_call block, only its question card."""
        builder = BlockBuilder()
        builder.add_tool_call_start("toolu_other", "list_documents", {})
        builder.add_tool_call_start("toolu_q", "ask_user", {})
        question = {
            "id": "int-q",
            "name": "ask_user",
            "reason": {"type": "single_select", "question": "Which?"},
        }
        builder.add_approval_required("toolu_q", "ask_user", {}, [question])
        before = builder.snapshot()

        builder.add_tool_cancelled("toolu_q")
        builder.add_tool_cancelled("toolu_unknown")

        self.assertEqual(builder.snapshot(), before)

    def test_a_tool_cancelled_without_a_card_is_marked_as_before(self):
        """A tool the user blocked is cancelled without asking, so it has no card."""
        builder = BlockBuilder()
        builder.add_tool_call_start(TOOL_ID, "create_document", {})

        builder.add_tool_cancelled(TOOL_ID, "User has blocked this tool (create document)")

        (tool,) = builder.snapshot()
        self.assertEqual(
            (tool["status"], tool["result"]),
            ("cancelled", {"message": "User has blocked this tool (create document)"}),
        )


class TestARejectedResumeKeepsItsCard(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("rejected-tool")
        frappe.set_user(self.user)
        self.sid = f"rejected-tool-{frappe.generate_hash(length=8)}"
        self.row = (
            frappe.get_doc(
                {
                    "doctype": "FAC Chat Message",
                    "session_id": self.sid,
                    "message_id": MESSAGE_ID,
                    "user": self.user,
                    "role": "assistant",
                    "content": PAUSED_TEXT,
                    "blocks": json.dumps(_paused_builder().snapshot()),
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _resume(self, *events, polls=()) -> list[dict]:
        """Run the rejection's resume over AR ``events``; return the socket payloads.

        ``polls`` answers the relay's cancel-flag reads in turn, then False. The
        first read is its check before it calls AR, then one per event.
        """
        answers = iter(polls)
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
            enter(patch.object(relay, "is_cancelled", side_effect=lambda _sid: next(answers, False)))
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
                session_id=self.sid,
                interrupt_response=REJECT,
                user=self.user,
                site=frappe.local.site,
                message_id=MESSAGE_ID,
            )
        return emitted

    def _stored(self) -> list[dict]:
        return json.loads(frappe.db.get_value("FAC Chat Message", self.row, "blocks"))

    def test_a_rejected_resume_saves_the_card_rejected(self):
        emitted = self._resume(
            RESUMED_START,
            TOOL_CANCELLED,
            CANCELLED_RESULT,
            _event("stream_chunk", content=ANSWER),
            _event("stream_complete", full_response=ANSWER, credits_used=1, model="m"),
        )

        for blocks in (self._stored(), emitted[-1]["blocks"]):
            card, tool = _only(blocks, "interaction"), _only(blocks, "tool_call")
            # The tool row ends with AR's own result for the cancelled call.
            self.assertEqual((card["status"], tool["status"]), ("rejected", "error"))
            self.assertNotIn("result", card)

    def test_a_stop_between_the_cancel_and_its_result_leaves_no_tool_running(self):
        emitted = self._resume(
            RESUMED_START, TOOL_CANCELLED, CANCELLED_RESULT, polls=(False, False, False, True)
        )

        self.assertEqual(emitted[-1]["event"], "stream_aborted")
        for blocks in (self._stored(), emitted[-1]["blocks"]):
            card, tool = _only(blocks, "interaction"), _only(blocks, "tool_call")
            self.assertEqual((card["status"], tool["status"]), ("rejected", "cancelled"))
            self.assertEqual(tool["result"], {"message": REJECTION})
        self.assertTrue(frappe.db.get_value("FAC Chat Message", self.row, "aborted"))
