# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Tests for the continue_response endpoint (continue a truncated response).

Mirrors resume_interrupt's shape: access check, restricted/session_state
computation, then a submit onto the bounded relay pool. The endpoint's own
job is just to require message_id and thread continue_from_message_id /
message_id through to the relay call — the relay's own streaming behavior
is covered elsewhere.
"""

import inspect
import unittest
from unittest.mock import patch


class TestContinueResponseValidation(unittest.TestCase):
    def test_missing_message_id_throws(self):
        import frappe

        from frappe_assistant_core.chat.api.chat.messages import continue_response

        with self.assertRaises(frappe.ValidationError):
            continue_response(session_id="SESSION-1", message_id=None)

    def test_blank_message_id_throws(self):
        import frappe

        from frappe_assistant_core.chat.api.chat.messages import continue_response

        with self.assertRaises(frappe.ValidationError):
            continue_response(session_id="SESSION-1", message_id="")


class TestContinueResponseSubmitsRelay(unittest.TestCase):
    def test_valid_call_submits_relay_task_with_continue_params(self):
        from frappe_assistant_core.chat.api.chat import messages

        access_result = {"can_use": True}
        session_state_stub = {"blob": "signed"}

        with patch(
            "frappe_assistant_core.chat.api.settings.can_use_faco",
            return_value=access_result,
        ), patch.object(messages, "_is_processing_restricted", return_value=False), patch(
            "frappe_assistant_core.chat.doctype.fac_chat_session_state.fac_chat_session_state.FACChatSessionState.load_wire",
            return_value=session_state_stub,
        ), patch.object(messages._relay_pool, "submit") as submit:
            result = messages.continue_response(
                session_id="SESSION-1",
                message_id="MSG-1",
                client_type="spa",
            )

        self.assertEqual(result["status"], "processing")
        self.assertEqual(result["session_id"], "SESSION-1")
        submit.assert_called_once()

        call_args, call_kwargs = submit.call_args
        # First positional arg is the relay function itself.
        relay_fn = call_args[0]
        self.assertEqual(relay_fn, messages._relay_ar_stream)

        # Bind the remaining args/kwargs against the relay fn's own
        # signature so this assertion survives reordering of positional
        # params — the only thing that matters is the named value.
        bound = inspect.signature(relay_fn).bind(*call_args[1:], **call_kwargs)
        bound.apply_defaults()
        self.assertEqual(bound.arguments.get("continue_from_message_id"), "MSG-1")

    def test_access_denied_raises_before_submit(self):
        import frappe

        from frappe_assistant_core.chat.api.chat import messages

        with patch(
            "frappe_assistant_core.chat.api.settings.can_use_faco",
            return_value={"can_use": False, "reason": "Cannot use FACO"},
        ), patch.object(messages._relay_pool, "submit") as submit:
            with self.assertRaises(frappe.ValidationError):
                messages.continue_response(session_id="SESSION-1", message_id="MSG-1")

        submit.assert_not_called()

    def test_restricted_user_skips_session_state_load(self):
        """GDPR Article 18 restricted users never have their state blob
        loaded or stored — same rule as send_message/resume_interrupt."""
        from frappe_assistant_core.chat.api.chat import messages

        with patch(
            "frappe_assistant_core.chat.api.settings.can_use_faco",
            return_value={"can_use": True},
        ), patch.object(messages, "_is_processing_restricted", return_value=True), patch(
            "frappe_assistant_core.chat.doctype.fac_chat_session_state.fac_chat_session_state.FACChatSessionState.load_wire",
        ) as load_wire, patch.object(messages._relay_pool, "submit") as submit:
            messages.continue_response(session_id="SESSION-1", message_id="MSG-1")

        load_wire.assert_not_called()
        submit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
