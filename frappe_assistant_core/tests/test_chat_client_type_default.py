# Frappe Assistant Core - Chat client_type default tests
# Copyright (C) 2026 Paul Clinton
# AGPL-3.0 License

"""A turn that does not say which client sent it is offered no browser tools.

The chat app ("spa") is now offered the page screenshot, so an omitted client_type can no longer
default to "spa": a caller with no page panel (a script, an older client) would be offered a tool
nothing can answer. Omitted means "api", which FAC Cloud's profile blocks every browser tool for.
The widget and the chat app always send their own client_type.
"""

from unittest.mock import patch

from frappe_assistant_core.chat.api.chat import messages as messages_mod
from frappe_assistant_core.tests.base_test import BaseAssistantTest

_MOD = "frappe_assistant_core.chat.api.chat.messages"


def _accepting_endpoint():
    """Patch what the resume and continue endpoints check before they queue the relay."""
    return [
        patch(f"{_MOD}._assert_session_owner", autospec=True),
        patch(
            "frappe_assistant_core.chat.api.settings.can_use_faco",
            autospec=True,
            return_value={"can_use": True},
        ),
        patch(f"{_MOD}.clear_cancel", autospec=True),
        # A restricted user loads no session state, which keeps the database out of the test.
        patch(f"{_MOD}._is_processing_restricted", autospec=True, return_value=True),
        patch(f"{_MOD}._mark_turn_started", autospec=True, return_value=None),
        patch(f"{_MOD}._conversation_addendum", autospec=True, return_value=None),
        patch(f"{_MOD}._paused_message_id", autospec=True, return_value="msg-1"),
    ]


class TestOmittedClientTypeIsApi(BaseAssistantTest):
    def _submitted_client_type(self, call):
        for patcher in _accepting_endpoint():
            patcher.start()
        self.addCleanup(patch.stopall)
        with patch.object(messages_mod._relay_pool, "submit", autospec=True) as submit:
            call()
        args, kwargs = submit.call_args
        # continue_response passes it by name; resume_interrupt positionally, after the relay.
        return kwargs["client_type"] if "client_type" in kwargs else args[5]

    def test_helper(self):
        self.assertEqual(messages_mod._effective_client_type(None), "api")
        self.assertEqual(messages_mod._effective_client_type(""), "api")
        self.assertEqual(messages_mod._effective_client_type("spa"), "spa")
        self.assertEqual(messages_mod._effective_client_type("widget"), "widget")

    def test_continue_without_a_client_type_is_api(self):
        client_type = self._submitted_client_type(
            lambda: messages_mod.continue_response(session_id="sess-1", message_id="msg-1")
        )
        self.assertEqual(client_type, "api")

    def test_resume_without_a_client_type_is_api(self):
        client_type = self._submitted_client_type(
            lambda: messages_mod.resume_interrupt(
                session_id="sess-1",
                interrupt_response='[{"interruptId": "i-1", "response": "approve"}]',
            )
        )
        self.assertEqual(client_type, "api")

    def test_the_chat_app_keeps_its_own(self):
        client_type = self._submitted_client_type(
            lambda: messages_mod.continue_response(session_id="sess-1", message_id="msg-1", client_type="spa")
        )
        self.assertEqual(client_type, "spa")
