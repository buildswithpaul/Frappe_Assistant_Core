# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Composer mode flags survive the hop from send_message into the relay thread."""

import inspect
import unittest
from unittest.mock import MagicMock, patch

from frappe_assistant_core.chat.api.chat import messages
from frappe_assistant_core.chat.api.chat.relay import (
    _relay_ar_interrupt_resume,
    _relay_ar_stream,
)


class TestFlagCoercion(unittest.TestCase):
    def test_widget_form_encoded_strings_become_booleans(self):
        """The Desk widget posts form-encoded, so booleans arrive as "true"/"false"."""
        self.assertIs(messages._flag("true"), True)
        self.assertIs(messages._flag("false"), False)
        self.assertIs(messages._flag(True), True)
        self.assertIs(messages._flag(None), False)


class TestFlagsReachTheRelay(unittest.TestCase):
    def _bind(self, submit):
        call_args, call_kwargs = submit.call_args[0], submit.call_args[1]
        return inspect.signature(_relay_ar_stream).bind(*call_args[1:], **call_kwargs)

    def _send(self, **flag_kwargs):
        # send_message calls FACChatMessage.create_message() inline (there is
        # no standalone "_persist_user_message" helper in this file), so that
        # is the real call to patch for "persist the user message". can_use_faco
        # is also patched — the house pattern used by test_continue_response.py
        # for these endpoints — so the test doesn't depend on this site's real
        # FAC Cloud registration state.
        user_msg = MagicMock()
        user_msg.name = "MSG-1"
        with patch.object(messages._relay_pool, "submit") as submit, patch(
            "frappe_assistant_core.chat.api.settings.can_use_faco",
            return_value={"can_use": True},
        ), patch(
            "frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message."
            "FACChatMessage.create_message",
            return_value=user_msg,
        ), patch.object(messages, "_is_processing_restricted", return_value=False):
            messages.send_message(session_id="s1", message="hello", **flag_kwargs)
        return self._bind(submit)

    def test_explicit_true_reaches_the_relay_as_true(self):
        bound = self._send(web_search=True, thinking_enabled=True)
        self.assertIs(bound.arguments.get("web_search"), True)
        self.assertIs(bound.arguments.get("thinking_enabled"), True)
        self.assertEqual(bound.arguments.get("session_id"), "s1")

    def test_explicit_false_reaches_the_relay_as_false(self):
        bound = self._send(web_search=False, thinking_enabled=False)
        self.assertIs(bound.arguments.get("web_search"), False)
        self.assertIs(bound.arguments.get("thinking_enabled"), False)

    def test_omitted_flags_reach_the_relay_as_none_not_false(self):
        """Regression: the Desk widget calls send_message without these
        params at all. None must survive through to the relay (and from
        there to the SDK, which omits the wire key on None) so AR reads
        absence as "search available" — not a silently-forced-off turn.
        """
        bound = self._send()
        self.assertIsNone(bound.arguments.get("web_search"))
        self.assertIsNone(bound.arguments.get("thinking_enabled"))


class TestFlagsSurviveResumeAndContinue(unittest.TestCase):
    """Absence is a value the SPA never chooses.

    ``composerModesStore`` defaults ``webSearch: false`` and always sends it
    explicitly, so a resume or continue that forwards nothing reaches AR as
    absence — and AR reads absence as "search available". Every HITL approval
    would silently re-enable web search against a pill the user switched off,
    which can egress agent-composed text to a search provider on a turn the
    user marked search-off.
    """

    def _bind(self, submit, target):
        call_args, call_kwargs = submit.call_args[0], submit.call_args[1]
        return inspect.signature(target).bind(*call_args[1:], **call_kwargs)

    def _patched(self):
        return (
            patch.object(messages._relay_pool, "submit"),
            patch(
                "frappe_assistant_core.chat.api.settings.can_use_faco",
                return_value={"can_use": True},
            ),
            patch.object(messages, "_is_processing_restricted", return_value=False),
        )

    def _resume(self, **flag_kwargs):
        submit_patch, gate_patch, restrict_patch = self._patched()
        with submit_patch as submit, gate_patch, restrict_patch:
            messages.resume_interrupt(
                session_id="s1",
                interrupt_response='[{"interruptId": "i1", "response": "approve"}]',
                **flag_kwargs,
            )
        return self._bind(submit, _relay_ar_interrupt_resume)

    def _continue(self, **flag_kwargs):
        submit_patch, gate_patch, restrict_patch = self._patched()
        with submit_patch as submit, gate_patch, restrict_patch:
            messages.continue_response(session_id="s1", message_id="m1", **flag_kwargs)
        return self._bind(submit, _relay_ar_stream)

    def test_a_resume_forwards_the_turns_flags(self):
        bound = self._resume(web_search=False, thinking_enabled=True)
        self.assertIs(bound.arguments.get("web_search"), False)
        self.assertIs(bound.arguments.get("thinking_enabled"), True)

    def test_a_continue_forwards_the_turns_flags(self):
        bound = self._continue(web_search=False, thinking_enabled=True)
        self.assertIs(bound.arguments.get("web_search"), False)
        self.assertIs(bound.arguments.get("thinking_enabled"), True)

    def test_a_resume_still_lets_absence_stay_absence(self):
        """Non-SPA callers that never set a toggle keep today's behaviour."""
        bound = self._resume()
        self.assertIsNone(bound.arguments.get("web_search"))
        self.assertIsNone(bound.arguments.get("thinking_enabled"))

    def test_a_continue_still_lets_absence_stay_absence(self):
        bound = self._continue()
        self.assertIsNone(bound.arguments.get("web_search"))
        self.assertIsNone(bound.arguments.get("thinking_enabled"))

    def test_the_resume_relay_hands_both_flags_to_the_sdk(self):
        """The kwargs have to survive the last hop too, not just reach the thread."""
        client = MagicMock()
        client.stream_chat.return_value = iter(())
        with patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
            return_value=client,
        ), patch("frappe.init"), patch("frappe.connect"), patch("frappe.set_user"), patch(
            "frappe.destroy"
        ), patch("frappe.db"), patch("frappe_assistant_core.chat.api.chat.relay.clear_cancel"), patch(
            "frappe_assistant_core.chat.api.chat.relay._emit_socket_event"
        ):
            _relay_ar_interrupt_resume(
                "s1",
                [{"interruptId": "i1", "response": "approve"}],
                "u@x.com",
                "site",
                web_search=False,
                thinking_enabled=True,
            )

        kwargs = client.stream_chat.call_args.kwargs
        self.assertIs(kwargs["web_search"], False)
        self.assertIs(kwargs["thinking_enabled"], True)


if __name__ == "__main__":
    unittest.main()
