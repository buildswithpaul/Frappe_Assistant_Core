# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""AR's low-balance refusal reaches the SPA with its numbers, and "Send anyway" can re-send.

AR refuses a new message it estimates the balance cannot cover with one
``stream_error`` coded ``low_balance``. The user message start_turn saved was
never answered, so the relay removes it: "Send anyway" sends the same text again.
"""

import threading
from contextlib import ExitStack
from unittest.mock import create_autospec, patch

import frappe
from assistant_runtime_sdk.client import AssistantRuntimeClient
from frappe.database.database import Database
from frappe.utils import add_to_date, now_datetime

from frappe_assistant_core.chat.api.chat import messages, relay
from frappe_assistant_core.tests.base_test import BaseAssistantTest

LOW_BALANCE = {
    "error": "Your balance may not cover this message.",
    "error_code": "low_balance",
    "estimate": 12.5,
    "balance": 4.0,
    "scope": "tenant",
}


def _event(name: str, **data) -> dict:
    return {"event": name, "data": data}


def _pending_upload() -> str:
    """A File as the composer's upload leaves it: private and flagged pending until a send links it."""
    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": f"invoices-{frappe.generate_hash(length=6)}.txt",
            "content": "overdue",
            "is_private": 1,
            "fac_pending_chat_attachment": 1,
        }
    ).insert()
    return file_doc.name


class TestSendMessageLowBalance(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("low-balance")
        frappe.set_user(self.user)
        self.sid = f"low-balance-{frappe.generate_hash(length=8)}"

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _start_turn(self, **kwargs):
        """Run start_turn as send_message does and return the relay call it queued."""
        # can_use_faco reads this site's FAC Cloud registration; production only reaches
        # start_turn once it has said yes.
        with patch.object(messages._relay_pool, "submit") as submit, patch(
            "frappe_assistant_core.chat.api.settings.can_use_faco", return_value={"can_use": True}
        ):
            messages.start_turn(self.sid, "Summarise the overdue invoices", **kwargs)
        return submit.call_args

    def _relay(self, queued, events):
        """Run the queued relay against an SDK client that streams ``events``."""
        client = create_autospec(AssistantRuntimeClient, instance=True)
        client.stream_chat.return_value = iter(events)
        emitted = []
        with ExitStack() as stack:
            enter = stack.enter_context
            enter(
                patch(
                    "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
                    return_value=client,
                )
            )
            for name in ("init", "connect", "set_user", "destroy"):
                enter(patch(f"frappe.{name}"))
            enter(patch.object(relay, "is_cancelled", return_value=False))
            enter(
                patch.object(
                    relay, "_emit_socket_event", side_effect=lambda _sid, payload: emitted.append(payload)
                )
            )
            fn, *args = queued.args
            fn(*args, **queued.kwargs)
        return client, emitted

    def _user_messages(self):
        return frappe.get_all(
            "FAC Chat Message", filters={"session_id": self.sid, "role": "user"}, pluck="name"
        )

    def test_low_balance_is_relayed_with_estimate_and_balance(self):
        _client, emitted = self._relay(self._start_turn(), [_event("stream_error", **LOW_BALANCE)])

        error = emitted[-1]
        self.assertEqual(error["event"], "stream_error")
        self.assertEqual(error["error_code"], "low_balance")
        self.assertEqual(error["low_balance"], {"estimate": 12.5, "balance": 4.0, "scope": "tenant"})

    def test_low_balance_removes_the_unanswered_user_message(self):
        # Production saved this row in start_turn before AR refused; created the same way here.
        queued = self._start_turn()
        self.assertEqual(len(self._user_messages()), 1)

        self._relay(queued, [_event("stream_error", **LOW_BALANCE)])

        self.assertEqual(self._user_messages(), [])

    def test_low_balance_hands_the_attachment_back_for_the_resend(self):
        file_name = _pending_upload()
        # Rollback leaves the uploaded bytes on disk.
        self.addCleanup(frappe.delete_doc, "File", file_name, ignore_permissions=True, force=True)
        # The composer uploaded it earlier; the orphan sweep ages pending files by creation.
        frappe.db.set_value(
            "File", file_name, "creation", add_to_date(now_datetime(), days=-2), update_modified=False
        )
        file_url = frappe.db.get_value("File", file_name, "file_url")
        queued = self._start_turn(file_urls=[file_url])
        self.assertEqual(frappe.db.get_value("File", file_name, "fac_pending_chat_attachment"), 0)

        self._relay(queued, [_event("stream_error", **LOW_BALANCE)])

        row = frappe.db.get_value(
            "File", file_name, ["attached_to_name", "fac_pending_chat_attachment", "creation"], as_dict=True
        )
        self.assertFalse(row.attached_to_name)
        self.assertEqual(row.fac_pending_chat_attachment, 1)
        self.assertGreater(row.creation, add_to_date(now_datetime(), hours=-1))

    def test_low_balance_takes_the_message_off_the_conversation_count(self):
        self._relay(self._start_turn(), [_event("stream_error", **LOW_BALANCE)])

        # The row stays: the SPA already added it to Recents from send_message's ack.
        self.assertEqual(frappe.db.get_value("FAC Chat Conversation", self.sid, "message_count"), 0)

    def test_a_refusal_after_the_turn_produced_text_keeps_the_user_message(self):
        # Task 12 refuses before the agent runs; this guards a refusal that ever arrives later.
        self._relay(
            self._start_turn(),
            [
                _event("stream_start", message_id="ar-msg-1"),
                _event("stream_chunk", content="Looking at the invoices"),
                _event("stream_error", **LOW_BALANCE),
            ],
        )

        self.assertEqual(len(self._user_messages()), 1)

    def test_another_refusal_keeps_the_user_message(self):
        self._relay(
            self._start_turn(),
            [_event("stream_error", error="Out of credits", error_code="quota_exhausted")],
        )

        self.assertEqual(len(self._user_messages()), 1)

    def test_send_anyway_reaches_the_sdk_with_the_flag(self):
        client, _emitted = self._relay(
            self._start_turn(confirm_low_balance=True),
            [_event("stream_complete", full_response="Done.", credits_used=0, model="m1")],
        )

        self.assertIs(client.stream_chat.call_args.kwargs.get("confirm_low_balance"), True)

    def test_send_message_forwards_the_flag_from_the_form(self):
        # The SPA posts the flag as 1; the form-encoded Desk widget would post "1".
        with patch.object(messages, "start_turn") as start_turn:
            messages.send_message(session_id=self.sid, message="hi", confirm_low_balance="1")

        self.assertEqual(start_turn.call_args.kwargs.get("confirm_low_balance"), "1")


class TestDiscardOnTheRelaysOwnConnection(BaseAssistantTest):
    """The relay runs in a pool thread on its own connection, as in production.

    send_message's request commits only when it returns, after the relay has started, so the
    relay sees only what start_turn committed before it submitted the relay. This test commits
    for real and cleans up after itself.
    """

    def setUp(self):
        super().setUp()
        self.sid = f"low-balance-own-conn-{frappe.generate_hash(length=8)}"
        # Commit nothing setUp wrote; only the rows below reach the database.
        frappe.db.rollback()
        real_commit = patch.object(frappe.db.__class__, "commit", Database.commit)
        real_commit.start()
        self.addCleanup(real_commit.stop)
        self.addCleanup(self._remove_committed_rows)
        self.file_name = None

    def _remove_committed_rows(self):
        frappe.db.rollback()
        if self.file_name:
            frappe.delete_doc("File", self.file_name, ignore_permissions=True, force=True)
        frappe.db.delete("FAC Chat Message", {"session_id": self.sid})
        frappe.db.delete("FAC Chat Conversation", {"name": self.sid})
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — this test needs a second connection to see the rows

    def _relay_in_its_own_thread(self, fn, *args, **kwargs):
        failure = []

        def run():
            try:
                fn(*args, **kwargs)
            except Exception as e:  # surfaced below; a thread swallows it otherwise
                failure.append(e)

        thread = threading.Thread(target=run)
        thread.start()
        thread.join(timeout=60)
        self.assertFalse(thread.is_alive(), "the relay thread did not finish")
        self.assertEqual(failure, [])

    def test_low_balance_hands_the_attachment_back_from_the_relays_own_connection(self):
        self.file_name = _pending_upload()
        # The upload was its own request, committed before the send.
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — this test needs a second connection to see the rows
        file_url = frappe.db.get_value("File", self.file_name, "file_url")

        client = create_autospec(AssistantRuntimeClient, instance=True)
        client.stream_chat.return_value = iter([_event("stream_error", **LOW_BALANCE)])
        with ExitStack() as stack:
            enter = stack.enter_context
            enter(
                patch(
                    "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
                    return_value=client,
                )
            )
            # can_use_faco reads this site's FAC Cloud registration; production only reaches
            # start_turn once it has said yes.
            enter(
                patch("frappe_assistant_core.chat.api.settings.can_use_faco", return_value={"can_use": True})
            )
            enter(patch.object(relay, "is_cancelled", return_value=False))
            enter(patch.object(relay, "_emit_socket_event"))
            enter(patch.object(messages._relay_pool, "submit", side_effect=self._relay_in_its_own_thread))
            messages.start_turn(self.sid, "Summarise the overdue invoices", file_urls=[file_url])

        # send_message's request ends here and commits.
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — this test needs a second connection to see the rows
        row = frappe.db.get_value(
            "File", self.file_name, ["attached_to_name", "fac_pending_chat_attachment"], as_dict=True
        )
        self.assertFalse(row.attached_to_name)
        self.assertEqual(row.fac_pending_chat_attachment, 1)
        self.assertFalse(frappe.db.exists("FAC Chat Message", {"session_id": self.sid, "role": "user"}))
