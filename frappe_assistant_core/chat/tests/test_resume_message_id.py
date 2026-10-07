# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""A resume must name the paused turn's row.

Live round 3 (B3): after the SPA rebuilt its message list the decided card
could sit on an earlier bubble, and submitInterruptDecision sent the resume
with ``message_id`` null. AR then minted a new id, so the decision and the
card were persisted on the wrong row and the rejected card came back on
reload. With no ``message_id``, the endpoint resolves the session's latest
assistant row that holds a pending interaction.
"""

import inspect
import json
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.chat import messages
from frappe_assistant_core.chat.api.chat.relay import _relay_ar_interrupt_resume
from frappe_assistant_core.tests.base_test import BaseAssistantTest

SESSION = "resume-message-id-session"
PENDING_CARD = {"type": "interaction", "id": "call_1", "status": "pending", "interrupts": [{"id": "int1"}]}


class TestResumeNamesThePausedRow(BaseAssistantTest):
    def _row(self, role, message_id=None, blocks=None):
        frappe.get_doc(
            {
                "doctype": "FAC Chat Message",
                "session_id": SESSION,
                "user": frappe.session.user,
                "role": role,
                "content": "x",
                "timestamp": frappe.utils.now(),
                "message_id": message_id,
                "blocks": json.dumps(blocks) if blocks is not None else None,
            }
        ).insert(ignore_permissions=True)

    def _relayed_message_id(self, **kwargs):
        with patch.object(messages._relay_pool, "submit") as submit, patch(
            "frappe_assistant_core.chat.api.settings.can_use_faco", return_value={"can_use": True}
        ), patch.object(messages, "_is_processing_restricted", return_value=False):
            messages.resume_interrupt(
                session_id=SESSION,
                interrupt_response='[{"interruptId": "int1", "response": "approve"}]',
                **kwargs,
            )
        bound = inspect.signature(_relay_ar_interrupt_resume).bind(
            *submit.call_args[0][1:], **submit.call_args[1]
        )
        return bound.arguments.get("message_id")

    def setUp(self):
        super().setUp()
        # An earlier finished answer, then the paused turn's row as the relay
        # persists it on stream_complete(interrupted): the card pending.
        self._row("user")
        self._row("assistant", "m-old", [{"type": "text", "id": "t", "content": "done"}])
        self._row("user")
        self._row(
            "assistant",
            "m-paused",
            [{"type": "tool_call", "id": "call_1", "status": "running"}, PENDING_CARD],
        )

    def test_a_resume_without_a_message_id_continues_the_paused_row(self):
        self.assertEqual(self._relayed_message_id(), "m-paused")

    def test_an_explicit_message_id_is_kept(self):
        self.assertEqual(self._relayed_message_id(message_id="m-given"), "m-given")

    def test_no_paused_row_leaves_it_absent(self):
        frappe.db.delete("FAC Chat Message", {"session_id": SESSION, "message_id": "m-paused"})
        self.assertIsNone(self._relayed_message_id())
