# Frappe Assistant Core - restart before the stream starts
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""A worker that is restarting cannot queue a relay; the client is asked to send again.

The turn must then leave nothing behind: no user row, no conversation it never had, and the
composer's uploads still free for the re-send to link.
"""

import base64
import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.chat import live_turn, messages, relay_shutdown
from frappe_assistant_core.chat.api.settings.uploads import upload_message_file
from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import FACChatMessage
from frappe_assistant_core.tests.base_test import BaseAssistantTest

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64).decode()
RESUME = '[{"interruptId": "i1", "response": "approve"}]'


def shut_down_pool() -> ThreadPoolExecutor:
    # A gunicorn worker that is exiting has a shut-down executor; a real shutdown pool reproduces it.
    pool = ThreadPoolExecutor(1)
    pool.shutdown()
    return pool


class TestRestartBeforeStream(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.sid = f"restart-{frappe.generate_hash(length=8)}"
        # Chat access is a seat on FAC Cloud; this site has no AR to ask.
        self.access = patch(
            "frappe_assistant_core.chat.api.settings.can_use_faco", return_value={"can_use": True}
        )
        self.access.start()

    def tearDown(self):
        self.access.stop()
        relay_shutdown._draining.clear()
        live_turn.clear(self.sid)
        super().tearDown()

    def _user_rows(self) -> int:
        return frappe.db.count("FAC Chat Message", {"session_id": self.sid, "role": "user"})

    def assertRetry(self, ack: dict):
        self.assertEqual(ack["status"], "retry")
        self.assertEqual(ack["retry_after"], messages.RESTART_RETRY_AFTER_SECONDS)
        self.assertEqual(ack["retry_after"], 2)

    def test_shut_down_pool_returns_retry_and_saves_no_user_row(self):
        with patch.object(messages, "_relay_pool", shut_down_pool()):
            ack = messages.send_message(session_id=self.sid, message="hi")
        self.assertRetry(ack)
        self.assertEqual(self._user_rows(), 0)
        self.assertFalse(frappe.db.exists("FAC Chat Conversation", self.sid))
        self.assertIsNone(live_turn.get(self.sid))

    def test_draining_refuses_before_saving(self):
        # Task 19's worker-exit hook sets this as gunicorn starts a graceful exit.
        relay_shutdown._draining.set()
        with patch.object(
            FACChatMessage, "create_message", wraps=FACChatMessage.create_message
        ) as create, patch.object(messages._relay_pool, "submit") as submit:
            ack = messages.send_message(session_id=self.sid, message="hi")
        self.assertRetry(ack)
        create.assert_not_called()
        submit.assert_not_called()
        self.assertIsNone(live_turn.get(self.sid))

    def test_continue_returns_retry(self):
        with patch.object(messages, "_relay_pool", shut_down_pool()):
            ack = messages.continue_response(session_id=self.sid, message_id="m1")
        self.assertRetry(ack)
        self.assertIsNone(live_turn.get(self.sid))

    def test_resume_returns_retry(self):
        with patch.object(messages, "_relay_pool", shut_down_pool()):
            ack = messages.resume_interrupt(session_id=self.sid, interrupt_response=RESUME, message_id="m1")
        self.assertRetry(ack)
        self.assertIsNone(live_turn.get(self.sid))

    def test_an_existing_conversation_keeps_its_count(self):
        FACChatMessage.create_message(session_id=self.sid, role="user", content="earlier")
        with patch.object(messages, "_relay_pool", shut_down_pool()):
            messages.send_message(session_id=self.sid, message="hi")
        self.assertEqual(self._user_rows(), 1)
        self.assertEqual(frappe.db.get_value("FAC Chat Conversation", self.sid, "message_count"), 1)

    def test_the_resend_can_still_link_the_upload(self):
        with patch(
            "frappe_assistant_core.chat.api.settings.access.can_use_faco",
            return_value={"can_use": True},
        ):
            upload = upload_message_file(file_data=PNG, file_name="shot.png", content_type="image/png")
        file = upload["file"]
        with patch.object(messages, "_relay_pool", shut_down_pool()):
            messages.send_message(session_id=self.sid, message="hi", file_urls=json.dumps([file["file_url"]]))
        row = frappe.db.get_value(
            "File",
            file["name"],
            ["fac_pending_chat_attachment", "attached_to_doctype", "attached_to_name"],
            as_dict=True,
        )
        self.assertIsNotNone(row)
        self.assertEqual(row.fac_pending_chat_attachment, 1)
        self.assertFalse(row.attached_to_name)

    def test_other_submit_errors_still_raise(self):
        # send_message logs the failure; Error Log is MyISAM and would outlive the rollback.
        with (
            patch.object(messages._relay_pool, "submit", side_effect=RuntimeError("pool full")),
            patch("frappe.log_error") as log_error,
        ):
            with self.assertRaises(frappe.ValidationError):
                messages.send_message(session_id=self.sid, message="hi")
        log_error.assert_called_once()
