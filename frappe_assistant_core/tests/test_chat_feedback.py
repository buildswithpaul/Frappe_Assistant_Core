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
from frappe_assistant_core.chat.doctype.fac_chat_user_preferences.fac_chat_user_preferences import (
    FACChatUserPreferences,
)
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
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Once per class: the rollback is class-wide, so per-test users pile up in one transaction
        # and trip Frappe's "Throttled" limit (more than 60 users created within an hour).
        cls.me = cls.make_throwaway_user(cls, "fbme")
        cls.other = cls.make_throwaway_user(cls, "fbother")

    def setUp(self):
        super().setUp()
        # Each test's messages and pulse dates roll back here, since the two users are shared.
        frappe.db.savepoint("fb_test")
        self.addCleanup(frappe.db.rollback, save_point="fb_test")
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

    def _set_pulse_dates(self, **offsets):
        # production: the pulse endpoints write these dates with db.set_value on earlier days.
        FACChatUserPreferences.get_or_create_preferences(self.me)
        values = {f"feedback_pulse_{key}": add_days(today(), days) for key, days in offsets.items()}
        frappe.db.set_value(PREFS, self.me, values, update_modified=False)

    def _pulse_dates(self):
        return frappe.db.get_value(
            PREFS, self.me, ["feedback_pulse_next", "feedback_pulse_shown", "feedback_pulse_submitted"]
        )

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
        # production: the card's onMounted calls mark_pulse_shown before the user can send.
        support.mark_pulse_shown()
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
        self._set_pulse_dates(next=3)
        self.assertEqual(support.pulse_state(), {"due": False})

    def test_mark_shown_sets_14_days(self):
        self._five_user_messages()
        support.mark_pulse_shown()
        self.assertEqual(str(self._prefs_date()), add_days(today(), 14))
        self.assertEqual(str(frappe.db.get_value(PREFS, self.me, "feedback_pulse_shown")), today())

    def test_mark_shown_does_nothing_when_no_card_is_due(self):
        self._five_user_messages()
        self._set_pulse_dates(next=5, shown=-9)
        before = self._pulse_dates()

        support.mark_pulse_shown()

        self.assertEqual(self._pulse_dates(), before)

    def test_dismiss_sets_30_days(self):
        support.dismiss_pulse()
        self.assertEqual(str(self._prefs_date()), add_days(today(), 30))

    def test_rate_answer_forwards_a_real_list_of_reasons(self):
        self._message(self.me, message_id=OWN_MESSAGE)
        self.client.rate_answer.return_value = {"feedback_id": "F-1"}

        support.rate_answer(OWN_MESSAGE, "Down", reasons=["credits"])

        self.assertEqual(self.client.rate_answer.call_args.kwargs["reasons"], ["credits"])

    def _pulse_next(self, offset_days):
        self._set_pulse_dates(next=offset_days)

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

    def test_submit_pulse_without_a_shown_card_is_refused(self):
        self._five_user_messages()

        with self.assertRaises(frappe.ValidationError):
            support.submit_pulse(4)
        self.client.submit_feedback.assert_not_called()

    def test_second_pulse_for_one_shown_card_is_refused_without_calling_ar(self):
        self._five_user_messages()
        # production: the card's onMounted calls mark_pulse_shown before the user can send.
        support.mark_pulse_shown()
        self.client.submit_feedback.return_value = {"feedback_id": "F-3"}
        support.submit_pulse(4)

        with self.assertRaises(frappe.ValidationError):
            support.submit_pulse(1)
        self.client.submit_feedback.assert_called_once()
        self.assertEqual(str(frappe.db.get_value(PREFS, self.me, "feedback_pulse_submitted")), today())

    def test_dismiss_does_not_reopen_an_answered_card(self):
        self._five_user_messages()
        # production: the card's onMounted calls mark_pulse_shown before the user can send.
        support.mark_pulse_shown()
        self.client.submit_feedback.return_value = {"feedback_id": "F-6"}
        support.submit_pulse(4)
        support.dismiss_pulse()

        with self.assertRaises(frappe.ValidationError):
            support.submit_pulse(2)
        self.client.submit_feedback.assert_called_once()

    def test_pulse_for_a_new_shown_card_is_allowed(self):
        self._five_user_messages()
        # production: the user answered the card shown 15 days ago; today's card is now due.
        self._set_pulse_dates(next=-1, shown=-15, submitted=-15)
        support.mark_pulse_shown()
        self.client.submit_feedback.return_value = {"feedback_id": "F-4"}

        support.submit_pulse(5)

        self.client.submit_feedback.assert_called_once()

    def test_failed_pulse_does_not_use_up_the_card(self):
        self._five_user_messages()
        # production: the card's onMounted calls mark_pulse_shown; AR then fails the send.
        support.mark_pulse_shown()
        self.client.submit_feedback.side_effect = [RuntimeError("outage"), {"feedback_id": "F-5"}]

        with self.assertRaises(frappe.ValidationError):
            support.submit_pulse(3)
        self.assertIsNone(frappe.db.get_value(PREFS, self.me, "feedback_pulse_submitted"))
        support.submit_pulse(3)

        self.assertEqual(self.client.submit_feedback.call_count, 2)

    def test_owner_save_cannot_move_the_pulse_dates(self):
        self._five_user_messages()
        support.mark_pulse_shown()
        self.client.submit_feedback.return_value = {"feedback_id": "F-7"}
        support.submit_pulse(4)
        before = self._pulse_dates()
        # production: the owner PUTs their own prefs doc over /api/resource (role All, if_owner).
        doc = frappe.get_doc(PREFS, self.me)
        doc.update(
            {
                "feedback_pulse_next": add_days(today(), -30),
                "feedback_pulse_shown": add_days(today(), 1),
                "feedback_pulse_submitted": None,
                "needs_you_count": 3,
            }
        )
        doc.save()

        self.assertEqual(self._pulse_dates(), before)
        self.assertEqual(frappe.db.get_value(PREFS, self.me, "needs_you_count"), 3)

    def test_owner_cannot_insert_prefs_with_pulse_dates(self):
        # production: a user who deleted their prefs POSTs a new doc over /api/resource.
        doc = frappe.get_doc(
            {
                "doctype": PREFS,
                "user": self.me,
                "feedback_pulse_shown": today(),
                "feedback_pulse_next": today(),
            }
        ).insert()

        self.assertEqual(self._pulse_dates(), (None, None, None))
        self.assertTrue(doc.name)

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
