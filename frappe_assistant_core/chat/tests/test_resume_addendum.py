"""A resumed, continued or retried turn sends AR the system-prompt addendum its turn first sent.

AR puts the addendum in the cached system-prompt prefix. A resume that rebuilds the agent (a
zero-retention tenant, or another worker) misses the whole cache when its addendum differs
from the paused turn's, so every path must send the same parts in the same order.
"""

import inspect
import json
import unittest
from unittest.mock import create_autospec, patch

import frappe
from assistant_runtime_sdk.client import AssistantRuntimeClient

from frappe_assistant_core.chat.api.chat import live_turn, messages
from frappe_assistant_core.chat.api.chat import relay as relay_module
from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import FACChatMessage
from frappe_assistant_core.chat.doctype.fac_chat_session_state.fac_chat_session_state import (
    FACChatSessionState,
)
from frappe_assistant_core.chat.embed import page_context
from frappe_assistant_core.tests.base_test import BaseAssistantTest

HELPDESK = [{"app": "helpdesk", "title": "Helpdesk", "route": "/helpdesk"}]
SIGNALS = json.dumps({"recent_errors": {"console": 3, "failed_requests": 1, "newest_age_s": 42}})
PRE_TURN = {"blob": "H4sI-pre", "sig": "sig-pre", "format_version": 1, "turn_seq": 3}
APPROVE = '[{"interruptId": "int1", "response": "approve"}]'


class _ResumeAddendumCases:
    """Each path's addendum against start_turn's, for a widget turn sent with ``client_signals``."""

    client_signals = None

    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; runs in an isolated transaction
        frappe.set_user("Administrator")
        self.sid = f"resume-addendum-{frappe.generate_hash(length=8)}"
        self.submitted = []
        patches = [
            # Chat access is a seat on FAC Cloud; this site has no AR to ask.
            patch("frappe_assistant_core.chat.api.settings.can_use_faco", return_value={"can_use": True}),
            patch.object(messages, "_is_processing_restricted", autospec=True, return_value=False),
            patch.object(
                messages._relay_pool,
                "submit",
                autospec=True,
                side_effect=lambda fn, *a, **kw: self.submitted.append((fn, a, kw)),
            ),
            # Production reaches a page line when the widget runs inside an installed Helpdesk.
            patch.object(page_context, "discover_spa_apps", autospec=True, return_value=HELPDESK),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        # the endpoints mark the turn started in Redis, outside the rollback
        live_turn.clear(self.sid)
        super().tearDown()

    def _relay_addendum(self) -> str | None:
        """The addendum the last queued relay was handed, bound against the relay's real signature."""
        fn, args, kwargs = self.submitted[-1]
        return inspect.signature(fn).bind(*args, **kwargs).arguments.get("system_prompt_addendum")

    def _send(self, message="Why does this page fail?", on_page=True) -> str | None:
        messages.send_message(
            session_id=self.sid,
            message=message,
            context=json.dumps({"type": "app_page", "path": "/helpdesk"}) if on_page else None,
            client_signals=self.client_signals if on_page else None,
        )
        sent = self._relay_addendum()
        if on_page:
            # The parts must be present, or the equality the tests assert proves nothing.
            self.assertIn("## Page Context", sent)
            if self.client_signals:
                self.assertIn("## Browser Signals", sent)
        live_turn.clear(self.sid)
        return sent

    def _assistant_row(self, message_id: str):
        """The shell row the relay writes for the turn when its stream starts."""
        row = FACChatMessage.create_message(session_id=self.sid, role="assistant", content="")
        frappe.db.set_value("FAC Chat Message", row.name, "message_id", message_id)
        return row

    def test_resume_sends_the_addendum_the_paused_turn_sent(self):
        sent = self._send()
        self._assistant_row("m-paused")

        messages.resume_interrupt(session_id=self.sid, interrupt_response=APPROVE, message_id="m-paused")

        self.assertEqual(self._relay_addendum(), sent)

    def test_resume_without_a_message_id_sends_the_latest_turns_addendum(self):
        sent = self._send()

        messages.resume_interrupt(session_id=self.sid, interrupt_response=APPROVE)

        self.assertEqual(self._relay_addendum(), sent)

    def test_continue_sends_the_addendum_the_truncated_turn_sent(self):
        sent = self._send()
        self._assistant_row("m-truncated")

        messages.continue_response(session_id=self.sid, message_id="m-truncated")

        self.assertEqual(self._relay_addendum(), sent)

    def test_continue_of_an_earlier_turn_sends_that_turns_addendum(self):
        first = self._send()
        self._assistant_row("m-first")
        # The next message comes from the full SPA: no page, no signals.
        self._send(message="And this one?", on_page=False)
        self._assistant_row("m-second")

        messages.continue_response(session_id=self.sid, message_id="m-first")

        self.assertEqual(self._relay_addendum(), first)

    def test_retry_sends_the_addendum_the_failed_turn_sent(self):
        # A conversation past its first turn has a session state; start_turn snapshots it.
        FACChatSessionState.upsert(self.sid, frappe.session.user, PRE_TURN)
        sent = self._send()
        user_row = messages._latest_user_row(self.sid)
        # An errored partial is what the relay persists when AR's stream fails mid-answer.
        partial = self._assistant_row("m-failed")
        frappe.db.set_value("FAC Chat Message", partial.name, "errored", 1)

        ack = messages.retry_turn(session_id=self.sid, user_message=user_row.name)

        self.assertEqual(ack["status"], "processing")
        self.assertEqual(self._relay_addendum(), sent)


class TestResumeAddendumPageLine(_ResumeAddendumCases, BaseAssistantTest):
    """A widget turn without browser signals: its page line is rebuilt from its stored row."""


@unittest.skipUnless(
    frappe.db.has_column("FAC Chat Message", "client_signals"),
    "client_signals column is not on this site yet: run `bench migrate` to create it",
)
class TestResumeAddendumWithSignals(_ResumeAddendumCases, BaseAssistantTest):
    """A widget turn with recent console errors: its signals sentence is re-sent as well."""

    client_signals = SIGNALS


class TestRelaysHandTheAddendumToTheSdk(BaseAssistantTest):
    """The endpoints are compared at the relay; these prove each relay sends it to AR unchanged."""

    ADDENDUM = "\n\n## Page Context\n\nThe user is on a Helpdesk page."

    def _sdk_addendum(self, run) -> str | None:
        client = create_autospec(AssistantRuntimeClient, instance=True)
        client.stream_chat.return_value = iter(())
        with patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client
        ), patch("frappe.init"), patch("frappe.connect"), patch("frappe.set_user"), patch(
            "frappe.destroy"
        ), patch("frappe.db"), patch.object(
            relay_module, "is_cancelled", side_effect=[False, True, True]
        ), patch.object(relay_module, "_emit_socket_event"), patch.object(
            relay_module, "_handle_stream_aborted"
        ):
            run()
        client.stream_chat.assert_called_once()
        call = client.stream_chat.call_args
        bound = inspect.signature(AssistantRuntimeClient.stream_chat).bind(None, *call.args, **call.kwargs)
        return bound.arguments.get("system_prompt_addendum")

    def test_the_resume_relay_sends_the_addendum(self):
        sent = self._sdk_addendum(
            lambda: relay_module._relay_ar_interrupt_resume(
                "s1", json.loads(APPROVE), "u@x.com", "site", system_prompt_addendum=self.ADDENDUM
            )
        )
        self.assertEqual(sent, self.ADDENDUM)

    def test_the_stream_relay_sends_the_addendum(self):
        sent = self._sdk_addendum(
            lambda: relay_module._relay_ar_stream(
                session_id="s1",
                full_prompt="hi",
                original_message="hi",
                context=None,
                message_name=None,
                user="u@x.com",
                site="site",
                system_prompt_addendum=self.ADDENDUM,
            )
        )
        self.assertEqual(sent, self.ADDENDUM)
