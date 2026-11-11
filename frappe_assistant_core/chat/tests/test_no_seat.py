"""Users without a billed seat cost AR nothing: credit status and notifications answer
{"no_seat": True} from the cached membership status, before any AR call.

Cache and breaker are the site's real Redis state; only the AR client factory is patched, with
an autospec'd client so a renamed SDK method fails the test.
"""

from unittest.mock import create_autospec, patch

import frappe
from assistant_runtime_sdk import ARAPIError, AssistantRuntimeClient

from frappe_assistant_core.chat import ar_breaker, credit_status_cache
from frappe_assistant_core.chat.api import notifications, users
from frappe_assistant_core.chat.api.settings import access
from frappe_assistant_core.tests.base_test import BaseAssistantTest

FACTORY = "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client"
NOTIF_FACTORY = "frappe_assistant_core.chat.api.notifications.get_fac_cloud_client"
CREDIT = {"monthly_credit_limit": 100, "credits_used_this_month": 7}
TITLE = "FACO User Management Error"


def _error_logs():
    return frappe.db.count("Error Log", {"method": ["in", [TITLE, "FACO membership check failed"]]})


class TestNoSeat(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = frappe.session.user
        self.client = create_autospec(AssistantRuntimeClient, instance=True)
        self.client.get_my_credit_status.return_value = CREDIT
        self.client.get_notifications.return_value = {"notifications": [{"id": "N1"}]}
        self._clear()
        self.addCleanup(self._clear)
        self.logs_before = _error_logs()
        for target, kwargs in (
            (FACTORY, {"return_value": self.client}),
            (NOTIF_FACTORY, {"return_value": self.client}),
            ("frappe_assistant_core.chat.api.notifications.is_chat_enabled", {"return_value": True}),
        ):
            patcher = patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _clear(self):
        frappe.cache.delete_value(f"faco_member:{self.user}")
        frappe.cache.delete_value(access._last_known_key(self.user))
        frappe.cache.delete_value(credit_status_cache._key(self.user))
        frappe.cache.delete_value(notifications._cache_key(notifications._ar_user_id(self.user)))
        for name in (ar_breaker._FAILURES_KEY, ar_breaker._OPEN_KEY, ar_breaker._WAS_OPEN_KEY):
            frappe.cache.delete(ar_breaker._key(name))

    def _auth_status(self, result):
        # Production reaches each membership state through AR's get_user_auth_status.
        self.client.get_user_auth_status.return_value = result

    def test_pending_member_gets_no_seat_and_can_still_chat(self):
        # AR reports Pending for an invited user until first use activates them.
        self._auth_status({"user_exists": True, "user_status": "Pending"})
        self.assertEqual(users.get_my_credit_status(), {"no_seat": True})
        self.assertTrue(access._is_faco_member(self.user))
        self.client.get_my_credit_status.assert_not_called()
        self.assertEqual(_error_logs(), self.logs_before)

    def test_non_member_gets_no_seat_without_ar_call(self):
        # AR answers user_exists False for a site user it has no seat for.
        self._auth_status({"user_exists": False})
        self.assertEqual(users.get_my_credit_status(), {"no_seat": True})
        self.assertFalse(access._is_faco_member(self.user))
        self.client.get_my_credit_status.assert_not_called()

    def test_active_member_gets_credit_status(self):
        self._auth_status({"user_exists": True, "user_status": "Active"})
        self.assertEqual(users.get_my_credit_status(), CREDIT)
        self.assertIs(access.has_seat(self.user), True)

    def test_ar_404_reads_as_no_seat_without_error_log(self):
        # AR answers 404 from the credit-status endpoint when the user has no seat, even though
        # the membership cache has not caught up yet.
        self._auth_status({"user_exists": True, "user_status": "Active"})
        self.client.get_my_credit_status.side_effect = ARAPIError("no seat", status_code=404)
        self.assertEqual(users.get_my_credit_status(), {"no_seat": True})
        self.assertEqual(_error_logs(), self.logs_before)
        self.assertEqual(frappe.cache.exists(ar_breaker._FAILURES_KEY), 0)

    def test_unknown_membership_still_tries_ar(self):
        # An unreachable AR makes the SDK return this marker for get_user_auth_status.
        self._auth_status({"_ar_unreachable": True, "error": "x"})
        self.assertIsNone(access.has_seat(self.user))
        self.assertTrue(access._is_faco_member(self.user))
        self.assertEqual(users.get_my_credit_status(), CREDIT)
        self.client.get_my_credit_status.assert_called_once()

    def test_notifications_no_seat(self):
        self._auth_status({"user_exists": False})
        result = notifications.get_notifications()
        self.assertEqual(
            result, {"notifications": [], "user": notifications._ar_user_id(self.user), "no_seat": True}
        )
        self.client.get_notifications.assert_not_called()

    def test_legacy_cached_flag_reads_as_miss(self):
        # A "1"/"0" written by the previous release is still in Redis for up to 60 s after upgrade.
        frappe.cache.set_value(f"faco_member:{self.user}", "0", expires_in_sec=60)
        self._auth_status({"user_exists": True, "user_status": "Active"})
        self.assertEqual(access._faco_member_status(self.user), "Active")
        self.client.get_user_auth_status.assert_called_once()

    def test_status_is_cached_as_the_status_string(self):
        self._auth_status({"user_exists": True, "user_status": "Pending"})
        access._faco_member_status(self.user)
        self.assertEqual(frappe.cache.get_value(f"faco_member:{self.user}"), "Pending")


class TestLastKnownMembership(BaseAssistantTest):
    """A user AR has already answered for keeps that answer while AR is unreachable."""

    def setUp(self):
        super().setUp()
        self.user = "last-known-member@example.com"
        self.client = create_autospec(AssistantRuntimeClient, instance=True)
        self._clear()
        self.addCleanup(self._clear)
        patcher = patch(FACTORY, return_value=self.client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _clear(self):
        frappe.cache.delete_value(f"faco_member:{self.user}")
        frappe.cache.delete_value(access._last_known_key(self.user))
        for name in (ar_breaker._FAILURES_KEY, ar_breaker._OPEN_KEY, ar_breaker._WAS_OPEN_KEY):
            frappe.cache.delete(ar_breaker._key(name))

    def _answer(self, result):
        # Production records this when AR answers get_user_auth_status; the 60 s membership cache
        # then lapses while the last-known copy stays for 24 h.
        self.client.get_user_auth_status.return_value = result
        access._faco_member_status(self.user)
        frappe.cache.delete_value(f"faco_member:{self.user}")

    def _open_breaker(self):
        for _ in range(ar_breaker.FAILURE_THRESHOLD):
            ar_breaker.record_failure()

    def test_breaker_open_after_a_no_stays_out(self):
        self._answer({"user_exists": False})
        self._open_breaker()
        self.assertFalse(access._is_faco_member(self.user))

    def test_breaker_open_after_a_suspension_stays_out(self):
        self._answer({"user_exists": True, "user_status": "Suspended"})
        self._open_breaker()
        self.assertFalse(access._is_faco_member(self.user))

    def test_breaker_open_after_a_yes_stays_in(self):
        self._answer({"user_exists": True, "user_status": "Active"})
        self._open_breaker()
        self.assertTrue(access._is_faco_member(self.user))

    def test_breaker_open_without_history_fails_open_briefly(self):
        self._open_breaker()
        with patch.object(frappe.cache, "set_value", wraps=frappe.cache.set_value) as spy:
            self.assertTrue(access._is_faco_member(self.user))
        [call] = [c for c in spy.call_args_list if c.args[0] == f"faco_member:{self.user}"]
        self.assertEqual(call.kwargs["expires_in_sec"], access._FAILOPEN_TTL)

    def test_transport_failure_after_a_no_stays_out(self):
        self._answer({"user_exists": False})
        # The SDK returns this marker instead of raising when its request fails.
        self.client.get_user_auth_status.return_value = {"_ar_unreachable": True, "error": "x"}
        self.assertFalse(access._is_faco_member(self.user))
        self.assertFalse(ar_breaker.is_open())
