# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Auto-approve mode: who is in it, and that a chat turn carries it to the runtime."""

import inspect
import json
from unittest.mock import MagicMock, patch

import frappe
from assistant_runtime_sdk.client import AssistantRuntimeClient

from frappe_assistant_core.chat import approval_mode
from frappe_assistant_core.chat.api.approval_mode import (
    acknowledge_approval_mode,
    get_approval_mode,
    set_approval_mode,
)
from frappe_assistant_core.chat.api.chat import relay as relay_module
from frappe_assistant_core.chat.api.chat.relay import _sdk_composer_kwargs
from frappe_assistant_core.tests.base_test import BaseAssistantTest


def _runtime_offers_the_mode(offers: bool = True) -> None:
    # Production: initialize_spa fetches the runtime's capabilities and caches them here.
    frappe.db.set_single_value(
        "FAC Chat Settings", "cached_capabilities", json.dumps({"features": {"auto_approve": offers}})
    )


class TestApprovalMode(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        if not frappe.db.has_column(approval_mode.PREFERENCES_DOCTYPE, approval_mode.OFF_FIELD):
            self.skipTest("auto_approve_off is not migrated onto this site")
        frappe.db.delete(approval_mode.PREFERENCES_DOCTYPE, {"user": frappe.session.user})
        _runtime_offers_the_mode()

    def mode(self, client_type="spa"):
        return approval_mode.turn_approval_mode(frappe.session.user, client_type)

    def test_a_user_who_never_chose_is_on_but_not_sent_until_they_saw_the_notice(self):
        self.assertEqual(get_approval_mode(), {"available": True, "on": True, "notice_seen": False})
        self.assertIsNone(self.mode())

        self.assertEqual(acknowledge_approval_mode(), {"available": True, "on": True, "notice_seen": True})
        self.assertEqual(self.mode(), "auto")

    def test_switching_it_off_stops_it_and_counts_as_seeing_the_notice(self):
        self.assertEqual(set_approval_mode(on="0"), {"available": True, "on": False, "notice_seen": True})
        self.assertIsNone(self.mode())

        self.assertTrue(set_approval_mode(on="1")["on"])
        self.assertEqual(self.mode(), "auto")

    def test_only_the_client_that_shows_the_switch_sends_it(self):
        acknowledge_approval_mode()

        for client_type in ("widget", "mobile", "raven", "api", None):
            self.assertIsNone(self.mode(client_type), client_type)

    def test_a_runtime_that_does_not_offer_it_gets_nothing(self):
        acknowledge_approval_mode()
        _runtime_offers_the_mode(False)

        self.assertFalse(get_approval_mode()["available"])
        self.assertIsNone(self.mode())

    def test_a_site_that_has_not_migrated_has_no_switch(self):
        # Between deploying the code and running migrate the columns do not exist yet.
        with patch.object(frappe.db, "has_column", return_value=False):
            self.assertEqual(
                approval_mode.state(frappe.session.user),
                {"available": False, "on": True, "notice_seen": False},
            )
            self.assertIsNone(self.mode())


class _Runtime:
    """A runtime client whose stream_chat has the signature of the SDK this app pins."""

    def __init__(self):
        self.sent = None

    def stream_chat(self, *args, **kwargs):
        inspect.signature(AssistantRuntimeClient.stream_chat).bind(self, *args, **kwargs)
        self.sent = kwargs
        return iter(())


_runtime_stream = inspect.signature(AssistantRuntimeClient.stream_chat)


class TestTheTurnCarriesTheMode(BaseAssistantTest):
    def test_the_pinned_sdk_takes_the_mode(self):
        self.assertIn("approval_mode", _runtime_stream.parameters)

    def test_an_sdk_from_before_the_mode_is_sent_none(self):
        def old_stream_chat(*a, web_search=None, thinking_enabled=None, reasoning_effort=None): ...

        self.assertNotIn(
            "approval_mode", _sdk_composer_kwargs(old_stream_chat, None, None, None, approval_mode="auto")
        )

    def relay_patches(self, client):
        return (
            patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client),
            patch("frappe.init"),
            patch("frappe.connect"),
            patch("frappe.set_user"),
            patch("frappe.destroy"),
            patch("frappe.db"),
            patch("frappe_assistant_core.chat.api.chat.relay._emit_socket_event"),
            # Production: the user has the mode on and has seen its notice (TestApprovalMode).
            patch.object(relay_module, "turn_approval_mode", autospec=True, return_value="auto"),
        )

    def test_a_send_and_a_resume_both_send_it(self):
        from contextlib import ExitStack

        for run in (self._send, self._resume):
            client = _Runtime()
            with ExitStack() as stack:
                mode = [stack.enter_context(p) for p in self.relay_patches(client)][-1]
                run(stack)

            self.assertEqual(client.sent["approval_mode"], "auto", run.__name__)
            mode.assert_called_with("u@x.com", "spa")

    def _send(self, stack):
        stack.enter_context(
            patch("frappe_assistant_core.chat.api.chat.relay.is_cancelled", side_effect=[False, True, True])
        )
        stack.enter_context(patch.object(relay_module, "_handle_stream_aborted"))
        relay_module._relay_ar_stream(
            session_id="s1",
            full_prompt="hi",
            original_message="hi",
            context=None,
            message_name=None,
            user="u@x.com",
            site="site",
            client_type="spa",
        )

    def _resume(self, stack):
        stack.enter_context(
            patch("frappe_assistant_core.chat.api.chat.relay.is_cancelled", return_value=False)
        )
        relay_module._relay_ar_interrupt_resume(
            "s1", [{"interruptId": "i1", "response": "approve"}], "u@x.com", "site", client_type="spa"
        )
