# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Answer ratings and the satisfaction pulse: FAC proxies to AR and local pulse state."""

import json
from unittest.mock import patch

import frappe
from assistant_runtime_sdk import AssistantRuntimeClient
from frappe.utils import add_days, today

from frappe_assistant_core.chat.api import support
from frappe_assistant_core.tests.base_test import BaseAssistantTest

FACO_MEMBER = "frappe_assistant_core.chat.api.settings.access._is_faco_member"
PREFS = "FAC Chat User Preferences"
OWN_MESSAGE = "msg-aaaaaaaaaaaaaaaa"
OTHER_MESSAGE = "msg-bbbbbbbbbbbbbbbb"


def _client_double():
    # create_autospec of the real client: a method the pinned SDK lacks, or a keyword it does
    # not accept, raises here instead of passing as it would on a bare MagicMock.
    from unittest.mock import create_autospec

    return create_autospec(AssistantRuntimeClient, instance=True)


class TestChatFeedback(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.client = _client_double()
        patcher = patch.object(support, "get_fac_cloud_client", return_value=self.client)
        patcher.start()
        self.addCleanup(patcher.stop)
        # production: a seated user on a site with FAC Chat on; each gate test flips one input.
        for target in (
            patch("frappe_assistant_core.chat.api.connections.is_chat_enabled", return_value=True),
            patch(FACO_MEMBER, return_value=True),
        ):
            target.start()
            self.addCleanup(target.stop)
        self.me = self.make_throwaway_user("fbme")
        self.other = self.make_throwaway_user("fbother")
        as_me = patch.dict(frappe.session, {"user": self.me})
        as_me.start()
        self.addCleanup(as_me.stop)

    def _message(self, user, role="assistant", message_id=None, session_id="sess-fb-1"):
        # production: the chat stream persists one FAC Chat Message per turn, owned by the sender.
        return frappe.get_doc(
            {
                "doctype": "FAC Chat Message",
                "session_id": session_id,
                "user": user,
                "role": role,
                "content": "x",
                "message_id": message_id,
            }
        ).insert(ignore_permissions=True)

    def _prefs_date(self):
        return frappe.db.get_value(PREFS, self.me, "feedback_pulse_next")

    def _five_user_messages(self):
        for _i in range(5):
            self._message(self.me, role="user", session_id="sess-fb-pulse")

    def test_sdk_under_test_is_1_16_0(self):
        import assistant_runtime_sdk

        self.assertEqual(assistant_runtime_sdk.__version__, "1.16.0")

    def test_rate_answer_forwards_reasons_list(self):
        self._message(self.me, message_id=OWN_MESSAGE)
        self.client.rate_answer.return_value = {"feedback_id": "F-1"}

        result = support.rate_answer(OWN_MESSAGE, "Down", reasons=json.dumps(["wrong", "slow"]), comment="no")

        self.assertEqual(result, {"feedback_id": "F-1"})
        self.client.rate_answer.assert_called_once_with(
            user_id=support._ar_user(),
            message_id=OWN_MESSAGE,
            reaction="Down",
            reasons=["wrong", "slow"],
            comment="no",
        )

    def test_rate_answer_rejects_message_from_another_users_session(self):
        # production: a crafted request carrying another user's message id.
        self._message(self.other, message_id=OTHER_MESSAGE)

        with self.assertRaises(frappe.PermissionError):
            support.rate_answer(OTHER_MESSAGE, "Up")
        with self.assertRaises(frappe.PermissionError):
            support.withdraw_answer_rating(OTHER_MESSAGE)
        self.client.rate_answer.assert_not_called()
        self.client.withdraw_answer_feedback.assert_not_called()

    def test_withdraw_forwards_for_own_message(self):
        self._message(self.me, message_id=OWN_MESSAGE)
        self.client.withdraw_answer_feedback.return_value = {"withdrawn": True}

        self.assertEqual(support.withdraw_answer_rating(OWN_MESSAGE), {"withdrawn": True})

    def test_rate_answer_ar_failure_is_a_friendly_error(self):
        self._message(self.me, message_id=OWN_MESSAGE)
        self.client.rate_answer.side_effect = RuntimeError("boom")

        with self.assertRaises(frappe.ValidationError):
            support.rate_answer(OWN_MESSAGE, "Up")

    def test_answer_ratings_sends_only_own_session_ids(self):
        self._message(self.me, message_id=OWN_MESSAGE)
        self._message(self.me, role="user", message_id="msg-cccccccccccccccc")
        self._message(self.other, message_id=OTHER_MESSAGE)
        self.client.get_answer_ratings.return_value = {OWN_MESSAGE: {"reaction": "Up", "reasons": []}}

        result = support.answer_ratings("sess-fb-1")

        self.assertEqual(result, {OWN_MESSAGE: {"reaction": "Up", "reasons": []}})
        self.client.get_answer_ratings.assert_called_once_with(
            user_id=support._ar_user(), message_ids=[OWN_MESSAGE]
        )

    def test_answer_ratings_skips_ar_when_no_assistant_messages(self):
        self.assertEqual(support.answer_ratings("sess-fb-empty"), {})
        self.client.get_answer_ratings.assert_not_called()

    def test_submit_pulse_sends_pulse_source(self):
        self._five_user_messages()
        self.client.submit_feedback.return_value = {"feedback_id": "F-2"}

        support.submit_pulse(4, comment="nice", contact_ok=True)

        self.client.submit_feedback.assert_called_once_with(
            user_id=support._ar_user(), rating=4, comment="nice", source="Pulse", contact_ok=True
        )

    def test_pulse_due_after_five_messages_and_empty_date(self):
        self._five_user_messages()
        self.assertEqual(support.pulse_state(), {"due": True})

    def test_pulse_not_due_with_few_messages(self):
        self._message(self.me, role="user")
        self.assertEqual(support.pulse_state(), {"due": False})

    def test_pulse_not_due_before_next_date(self):
        self._five_user_messages()
        # production: mark_pulse_shown / dismiss_pulse write a future date here.
        frappe.get_doc(
            {"doctype": PREFS, "user": self.me, "feedback_pulse_next": add_days(today(), 3)}
        ).insert(ignore_permissions=True)
        self.assertEqual(support.pulse_state(), {"due": False})

    def test_mark_shown_sets_14_days(self):
        support.mark_pulse_shown()
        self.assertEqual(str(self._prefs_date()), add_days(today(), 14))

    def test_dismiss_sets_30_days(self):
        support.dismiss_pulse()
        self.assertEqual(str(self._prefs_date()), add_days(today(), 30))

    def test_rate_answer_forwards_a_real_list_of_reasons(self):
        self._message(self.me, message_id=OWN_MESSAGE)
        self.client.rate_answer.return_value = {"feedback_id": "F-1"}

        support.rate_answer(OWN_MESSAGE, "Down", reasons=["credits"])

        self.assertEqual(self.client.rate_answer.call_args.kwargs["reasons"], ["credits"])

    def _pulse_next(self, offset_days):
        # production: mark_pulse_shown / dismiss_pulse write this date.
        frappe.get_doc(
            {"doctype": PREFS, "user": self.me, "feedback_pulse_next": add_days(today(), offset_days)}
        ).insert(ignore_permissions=True)

    def test_pulse_due_when_next_date_is_today(self):
        self._five_user_messages()
        self._pulse_next(0)
        self.assertEqual(support.pulse_state(), {"due": True})

    def test_pulse_due_when_next_date_is_past(self):
        self._five_user_messages()
        self._pulse_next(-3)
        self.assertEqual(support.pulse_state(), {"due": True})

    def test_answer_ratings_returns_empty_on_ar_failure(self):
        self._message(self.me, message_id=OWN_MESSAGE)
        self.client.get_answer_ratings.side_effect = RuntimeError("outage")

        self.assertEqual(support.answer_ratings("sess-fb-1"), {})

    def test_submit_pulse_refused_before_five_messages(self):
        self._message(self.me, role="user")

        with self.assertRaises(frappe.PermissionError):
            support.submit_pulse(5)
        self.client.submit_feedback.assert_not_called()

    def _calls(self):
        return {
            "rate_answer": lambda: support.rate_answer(OWN_MESSAGE, "Up"),
            "withdraw_answer_rating": lambda: support.withdraw_answer_rating(OWN_MESSAGE),
            "answer_ratings": lambda: support.answer_ratings("sess-fb-1"),
            "submit_pulse": lambda: support.submit_pulse(5),
            "pulse_state": support.pulse_state,
            "mark_pulse_shown": support.mark_pulse_shown,
            "dismiss_pulse": support.dismiss_pulse,
        }

    def test_every_endpoint_refuses_a_caller_without_chat_access(self):
        self._message(self.me, message_id=OWN_MESSAGE)
        self._five_user_messages()
        # production: a Website User or unseated user whose browser calls the endpoints directly.
        with patch(FACO_MEMBER, return_value=False):
            for name, call in self._calls().items():
                with self.subTest(endpoint=name), self.assertRaises(frappe.PermissionError):
                    call()
        self.client.submit_feedback.assert_not_called()

    def test_every_endpoint_refuses_when_chat_is_disabled(self):
        self._message(self.me, message_id=OWN_MESSAGE)
        self._five_user_messages()
        with patch("frappe_assistant_core.chat.api.connections.is_chat_enabled", return_value=False):
            for name, call in self._calls().items():
                with self.subTest(endpoint=name), self.assertRaises(frappe.PermissionError):
                    call()
