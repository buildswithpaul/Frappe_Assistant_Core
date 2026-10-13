# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Project instructions ride system_prompt_addendum on every path that starts or resumes a turn.

AR rebuilds the system prompt on every turn, including a HITL resume and a
truncation continue, so a path that leaves the block off silently drops the
project's instructions for that turn.
"""

import inspect
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.chat import live_turn, messages
from frappe_assistant_core.chat.api.chat.messages import _conversation_addendum
from frappe_assistant_core.chat.api.chat.relay import _relay_ar_interrupt_resume, _relay_ar_stream
from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import FACChatMessage
from frappe_assistant_core.chat.tests.test_chat_projects_api import OTHER_USER, ensure_user, make_project
from frappe_assistant_core.tests.base_test import BaseAssistantTest

SID = "test-project-addendum"
BLOCK = "## Project: Q3 Close"


class _ProjectTestBase(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; runs in an isolated transaction
        frappe.set_user("Administrator")
        ensure_user(OTHER_USER)
        frappe.db.delete("FAC Chat Message", {"session_id": SID})
        frappe.db.delete("FAC Chat Conversation", {"name": SID})
        self.project = make_project("Administrator", instructions="Amounts in INR.")


class TestConversationAddendum(_ProjectTestBase):
    def test_row_project_wins(self):
        FACChatMessage.create_message(SID, "user", "hi", project=self.project)
        self.assertIn(BLOCK, _conversation_addendum(SID, restricted=False))

    def test_row_without_project_ignores_the_param(self):
        FACChatMessage.create_message(SID, "user", "hi")
        self.assertIsNone(_conversation_addendum(SID, restricted=False, project=self.project))

    def test_restricted_user_falls_back_to_the_param(self):
        # Art. 18 restriction persists no messages, so there is no conversation row
        self.assertIn(BLOCK, _conversation_addendum(SID, restricted=True, project=self.project))

    def test_fallback_refuses_another_users_project(self):
        theirs = make_project(OTHER_USER, instructions="leak")
        self.assertIsNone(_conversation_addendum(SID, restricted=True, project=theirs))

    def test_no_instructions_no_block(self):
        bare = make_project("Administrator", title="Bare")
        FACChatMessage.create_message(SID, "user", "hi", project=bare)
        self.assertIsNone(_conversation_addendum(SID, restricted=False))


class TestEndpointsCarryProjectBlock(_ProjectTestBase):
    def tearDown(self):
        # the endpoints mark the turn started in Redis, outside the rollback
        live_turn.clear(SID)
        super().tearDown()

    def _submitted_addendum(self, relay, call):
        """Run ``call`` with the relay pool stubbed; return the addendum the relay receives."""
        with patch.object(messages._relay_pool, "submit", autospec=True) as submit, patch(
            "frappe_assistant_core.chat.api.settings.can_use_faco", return_value={"can_use": True}
        ), patch.object(messages, "_is_processing_restricted", autospec=True, return_value=False):
            call()
        submit.assert_called_once()
        args, kwargs = submit.call_args
        self.assertIs(args[0], relay)
        bound = inspect.signature(relay).bind(*args[1:], **kwargs)
        return bound.arguments.get("system_prompt_addendum")

    def test_send_message_carries_project_block(self):
        addendum = self._submitted_addendum(
            _relay_ar_stream,
            lambda: messages.send_message(session_id=SID, message="hi", project=self.project),
        )
        self.assertIn(BLOCK, addendum)
        self.assertIn("Amounts in INR.", addendum)

    def test_resume_interrupt_carries_project_block(self):
        # The row exists because the turn being resumed was sent through send_message,
        # which created it with this project.
        FACChatMessage.create_message(SID, "user", "hi", project=self.project)
        addendum = self._submitted_addendum(
            _relay_ar_interrupt_resume,
            lambda: messages.resume_interrupt(
                session_id=SID,
                interrupt_response='[{"interruptId": "int1", "response": "approve"}]',
                message_id="m-paused",
            ),
        )
        self.assertIn(BLOCK, addendum)

    def test_continue_response_carries_project_block(self):
        # Same as above: the truncated turn's conversation row was created by send_message.
        FACChatMessage.create_message(SID, "user", "hi", project=self.project)
        addendum = self._submitted_addendum(
            _relay_ar_stream,
            lambda: messages.continue_response(session_id=SID, message_id="m-truncated"),
        )
        self.assertIn(BLOCK, addendum)
