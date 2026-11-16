"""Retry re-runs the latest user message from the state before its turn, never a finished one."""

import json
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.chat import live_turn, messages, relay
from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import FACChatMessage
from frappe_assistant_core.chat.doctype.fac_chat_session_state.fac_chat_session_state import (
    FACChatSessionState,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest

PRE_TURN = {"blob": "H4sI-pre", "sig": "sig-pre", "format_version": 1, "turn_seq": 3}
PARTIAL_TURN = {"blob": "H4sI-partial", "sig": "sig-partial", "format_version": 1, "turn_seq": 4}


class TestRetryTurn(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.sid = f"retry-{frappe.generate_hash(length=8)}"
        self.submitted = []
        # Chat access is a seat on FAC Cloud; this site has no AR to ask.
        self.access = patch(
            "frappe_assistant_core.chat.api.settings.can_use_faco", return_value={"can_use": True}
        )
        self.access.start()
        self.submit = patch.object(
            messages._relay_pool, "submit", side_effect=lambda *a, **kw: self.submitted.append((a, kw))
        )
        self.submit.start()

    def tearDown(self):
        self.submit.stop()
        self.access.stop()
        live_turn.clear(self.sid)
        super().tearDown()

    def _user_turn(self, text="What is overdue?", state=PRE_TURN):
        """A sent message as start_turn leaves it: the user row, and the state before its turn."""
        if state:
            FACChatSessionState.upsert(self.sid, frappe.session.user, state)
        row = FACChatMessage.create_message(
            session_id=self.sid,
            role="user",
            content=text,
            context={"type": "Form", "doctype": "Sales Invoice", "name": "SINV-0001", "url": "/app/x"},
        )
        FACChatSessionState.snapshot_pre_turn(self.sid, frappe.session.user, row.name)
        return row

    def _assistant(self, content, *, errored=0, aborted=0, message_id="m-partial", blocks=None):
        row = FACChatMessage.create_message(session_id=self.sid, role="assistant", content=content)
        values = {"errored": errored, "aborted": aborted, "message_id": message_id}
        if blocks is not None:
            values["blocks"] = json.dumps(blocks)
        frappe.db.set_value("FAC Chat Message", row.name, values)
        return row.name

    def _rows(self, role):
        return frappe.get_all(
            "FAC Chat Message", filters={"session_id": self.sid, "role": role}, pluck="name"
        )

    def test_retry_reruns_without_a_new_user_row_and_replaces_the_partial(self):
        user = self._user_turn()
        # An errored partial is what the relay persists when AR's stream fails mid-answer.
        partial = self._assistant("Half an ans", errored=1)

        ack = messages.retry_turn(session_id=self.sid, user_message=user.name)

        self.assertEqual(ack, {"status": "processing", "session_id": self.sid})
        self.assertEqual(self._rows("user"), [user.name])
        self.assertFalse(frappe.db.exists("FAC Chat Message", partial))
        self.assertEqual(len(self.submitted), 1)
        args, kwargs = self.submitted[0]
        self.assertIs(args[0], relay._relay_ar_stream)
        session_id, full_prompt, message, context, message_name = args[1:6]
        self.assertEqual(
            (session_id, full_prompt, message), (self.sid, "What is overdue?", "What is overdue?")
        )
        self.assertEqual(message_name, user.name)
        self.assertEqual(context["doctype"], "Sales Invoice")
        self.assertEqual(context["name"], "SINV-0001")
        self.assertEqual(args[9], [])  # no image attachments

    def test_retry_uses_the_pre_turn_session_state(self):
        user = self._user_turn()
        # The relay upserts a newer blob for the partial turn; the retry must send the snapshot instead.
        FACChatSessionState.upsert(self.sid, frappe.session.user, PARTIAL_TURN)
        self._assistant("Half an ans", errored=1)

        messages.retry_turn(session_id=self.sid, user_message=user.name)

        args, _ = self.submitted[0]
        self.assertEqual(args[12], PRE_TURN)
        self.assertEqual(frappe.db.get_value("FAC Chat Session State", self.sid, "turn_seq"), 3)
        # The retried turn's own state then lands: it is newer than what was restored.
        FACChatSessionState.upsert(self.sid, frappe.session.user, PARTIAL_TURN)
        self.assertEqual(FACChatSessionState.load_wire(self.sid)["blob"], PARTIAL_TURN["blob"])

    def test_retry_refuses_a_completed_turn(self):
        user = self._user_turn()
        done = self._assistant("Three invoices are overdue.", message_id="m-done")

        ack = messages.retry_turn(session_id=self.sid, user_message=user.name)

        self.assertEqual(ack, {"status": "already_complete"})
        self.assertEqual(self.submitted, [])
        self.assertEqual(self._rows("assistant"), [done])
        self.assertEqual(FACChatSessionState.load_wire(self.sid)["blob"], PRE_TURN["blob"])

    def test_retry_refuses_a_completed_turn_whose_answer_is_only_tools(self):
        user = self._user_turn()
        # A turn that only ran tools (or made an artifact) finishes with no text of its own.
        done = self._assistant(
            "",
            message_id="m-tools",
            blocks=[{"type": "tool_call", "id": "t1", "tool_name": "create_document", "status": "success"}],
        )

        ack = messages.retry_turn(session_id=self.sid, user_message=user.name)

        self.assertEqual(ack, {"status": "already_complete"})
        self.assertEqual(self.submitted, [])
        self.assertEqual(self._rows("assistant"), [done])

    def test_two_concurrent_retries_run_once(self):
        user = self._user_turn()
        self._assistant("Half an ans", errored=1)
        second = []
        clicked = []
        restore = FACChatSessionState.restore_pre_turn

        def restore_while_another_tab_retries(session_id, user_message):
            # The widget and the chat app both show Retry; the second click lands mid-retry.
            if not clicked:
                clicked.append(True)
                second.append(messages.retry_turn(session_id=self.sid, user_message=user.name))
            return restore(session_id, user_message)

        with patch.object(
            FACChatSessionState, "restore_pre_turn", side_effect=restore_while_another_tab_retries
        ):
            first = messages.retry_turn(session_id=self.sid, user_message=user.name)
        after = messages.retry_turn(session_id=self.sid, user_message=user.name)

        self.assertEqual(first["status"], "processing")
        self.assertEqual(second, [{"status": "running"}])
        self.assertEqual(after, {"status": "running"})
        self.assertEqual(len(self.submitted), 1)

    def test_retry_rebuilds_the_page_line_of_a_widget_message(self):
        user = self._user_turn()
        # The widget in Helpdesk stored its page as a "Page" context; start_turn wrote its prompt line.
        frappe.db.set_value(
            "FAC Chat Message",
            user.name,
            {
                "context_type": "Page",
                "context_url": "/helpdesk/tickets/1",
                "context_doctype": None,
                "context_name": None,
            },
        )
        self._assistant("Half an ans", errored=1)
        with patch.object(
            messages, "render_page_context", return_value="\n\n## Page Context\n\nHelpdesk"
        ) as render:
            messages.retry_turn(session_id=self.sid, user_message=user.name)
        render.assert_called_once_with({"type": "app_page", "path": "/helpdesk/tickets/1"})
        args, _ = self.submitted[0]
        self.assertIn("## Page Context", args[10])

    def test_retry_refuses_a_running_turn(self):
        user = self._user_turn()
        # start_turn writes this entry before queueing the relay; a fresh entry is a turn still running.
        live_turn.start(self.sid)

        ack = messages.retry_turn(session_id=self.sid, user_message=user.name)

        self.assertEqual(ack, {"status": "running"})
        self.assertEqual(self.submitted, [])

    def test_retry_ends_a_dead_turn_first(self):
        user = self._user_turn()
        live_turn.start(self.sid)
        entry = live_turn.get(self.sid)
        # The worker died before the relay ran: the starting entry is never written again.
        entry["last_progress_at"] -= live_turn.STARTING_STALE_SECONDS + 1
        frappe.cache().set_value(live_turn._key(self.sid), entry, expires_in_sec=60)

        with patch("frappe.publish_realtime"):
            ack = messages.retry_turn(session_id=self.sid, user_message=user.name)

        self.assertEqual(ack["status"], "processing")
        self.assertEqual(self._rows("assistant"), [])
        self.assertEqual(len(self.submitted), 1)

    def test_retry_only_the_latest_message(self):
        first = self._user_turn("first")
        self._assistant("First answer.", errored=1)
        self._user_turn("second")

        with self.assertRaises(frappe.ValidationError) as raised:
            messages.retry_turn(session_id=self.sid, user_message=first.name)
        self.assertIn("Only the latest message can be retried", str(raised.exception))
        self.assertEqual(self.submitted, [])

    def test_first_turn_retry_restores_an_empty_state(self):
        user = self._user_turn(state=None)
        # The relay stored the failed first turn's state.
        FACChatSessionState.upsert(self.sid, frappe.session.user, PARTIAL_TURN)
        self._assistant("Half an ans", errored=1)

        messages.retry_turn(session_id=self.sid, user_message=user.name)

        args, _ = self.submitted[0]
        self.assertIsNone(args[12])
        self.assertIsNone(FACChatSessionState.load_wire(self.sid))
        self.assertEqual(frappe.db.get_value("FAC Chat Session State", self.sid, "turn_seq"), 0)

    def test_a_turn_with_no_snapshot_cannot_be_retried(self):
        # A message sent before this release has no pre-turn snapshot.
        row = FACChatMessage.create_message(session_id=self.sid, role="user", content="old")
        self._assistant("Half an ans", errored=1)

        with self.assertRaises(frappe.ValidationError) as raised:
            messages.retry_turn(session_id=self.sid, user_message=row.name)
        self.assertIn("This turn can no longer be retried", str(raised.exception))
        self.assertEqual(self.submitted, [])

    def test_start_turn_snapshots_the_state_before_the_turn(self):
        FACChatSessionState.upsert(self.sid, frappe.session.user, PRE_TURN)

        messages.send_message(session_id=self.sid, message="hello")

        row = frappe.db.get_value(
            "FAC Chat Session State",
            self.sid,
            ["pre_turn_message", "pre_turn_blob", "pre_turn_sig", "pre_turn_seq"],
            as_dict=True,
        )
        self.assertEqual(row.pre_turn_message, self._rows("user")[0])
        self.assertEqual((row.pre_turn_blob, row.pre_turn_sig, row.pre_turn_seq), ("H4sI-pre", "sig-pre", 3))

    def test_a_restarting_worker_asks_for_the_retry_again(self):
        user = self._user_turn()
        self._assistant("Half an ans", errored=1)
        # Task 19's worker-exit hook sets draining as gunicorn starts a graceful exit.
        with patch.object(messages.relay_shutdown, "is_draining", return_value=True):
            ack = messages.retry_turn(session_id=self.sid, user_message=user.name)
        self.assertEqual(ack["status"], "retry")
        self.assertEqual(len(self._rows("assistant")), 1)
