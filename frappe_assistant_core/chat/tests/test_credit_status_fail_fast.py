"""get_my_credit_status asks AR at most once, and degrades to a stale or unavailable answer.

The cache and breaker are the site's real Redis state; only the AR client factory is patched,
with an autospec'd client so a renamed SDK method fails the test.
"""

from unittest.mock import create_autospec, patch

import frappe
from assistant_runtime_sdk import ARAPIError, ARTimeoutError, AssistantRuntimeClient

from frappe_assistant_core.chat import ar_breaker, credit_status_cache
from frappe_assistant_core.chat.api import users
from frappe_assistant_core.chat.fac_cloud_client import SHORT_CALL_TIMEOUT
from frappe_assistant_core.chat.tests.sdk_errors import sdk_http_error
from frappe_assistant_core.tests.base_test import BaseAssistantTest

FACTORY = "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client"
TITLE = "FACO User Management Error"
STATUS = {"monthly_credit_limit": 100, "credits_used_this_month": 7}


def _error_log_count():
    return frappe.db.count("Error Log", {"method": TITLE})


class TestCreditStatusFailFast(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.user = frappe.session.user
        self._clear()
        self.addCleanup(self._clear)
        self.logs_before = _error_log_count()
        self.client = create_autospec(AssistantRuntimeClient, instance=True)
        self.client.get_my_credit_status.return_value = STATUS
        # Production reaches a seated user through AR's get_user_auth_status answering Active.
        self.client.get_user_auth_status.return_value = {"user_exists": True, "user_status": "Active"}
        patcher = patch(FACTORY, return_value=self.client)
        self.factory = patcher.start()
        self.addCleanup(patcher.stop)

    def _clear(self):
        frappe.cache.delete_value(credit_status_cache._key(self.user))
        frappe.cache.delete_value(f"faco_member:{self.user}")
        frappe.cache.delete_value(f"faco_member_last:{self.user}")
        for name in (ar_breaker._FAILURES_KEY, ar_breaker._OPEN_KEY, ar_breaker._WAS_OPEN_KEY):
            frappe.cache.delete(ar_breaker._key(name))

    def tearDown(self):
        # Error Log is MyISAM, so a test's rows survive the rollback.
        for name in frappe.get_all("Error Log", filters={"method": TITLE}, pluck="name")[
            : _error_log_count() - self.logs_before
        ]:
            frappe.delete_doc("Error Log", name, force=True)
        super().tearDown()

    def test_fresh_cache_skips_ar(self):
        credit_status_cache.put(self.user, STATUS)
        self.assertEqual(users.get_my_credit_status(), STATUS)
        self.factory.assert_not_called()

    def test_miss_calls_ar_once_and_caches(self):
        self.assertEqual(users.get_my_credit_status(), STATUS)
        self.assertEqual(users.get_my_credit_status(), STATUS)
        self.assertEqual(self.client.get_my_credit_status.call_count, 1)

    def test_timeout_returns_stale_and_logs_nothing(self):
        # Production reaches a stale entry once 45 s have passed (or a turn invalidated it).
        credit_status_cache.put(self.user, STATUS)
        credit_status_cache.invalidate(self.user)
        # A slow AR raises ARTimeoutError out of the SDK's requests call.
        self.client.get_my_credit_status.side_effect = ARTimeoutError("slow")
        result = users.get_my_credit_status()
        self.assertTrue(result["stale"])
        self.assertEqual(result["monthly_credit_limit"], 100)
        self.assertEqual(_error_log_count(), self.logs_before)
        self.assertEqual(self.client.get_my_credit_status.call_count, 1)

    def test_no_cache_and_failure_returns_unavailable(self):
        self.client.get_my_credit_status.side_effect = ARTimeoutError("slow")
        self.assertEqual(users.get_my_credit_status(), {"unavailable": True})

    def test_breaker_open_makes_no_ar_call(self):
        for _ in range(ar_breaker.FAILURE_THRESHOLD):
            ar_breaker.record_failure()
        self.assertEqual(users.get_my_credit_status(), {"unavailable": True})
        self.client.get_my_credit_status.assert_not_called()

    def test_non_transport_failure_writes_one_error_log(self):
        self.client.get_my_credit_status.side_effect = ARAPIError("nope", status_code=400)
        result = users.get_my_credit_status()
        self.assertIn("error", result)
        self.assertEqual(_error_log_count(), self.logs_before + 1)
        self.assertEqual(self.client.get_my_credit_status.call_count, 1)

    def test_503_serves_stale_counts_for_the_breaker_and_logs_nothing(self):
        # An AR restart or overload answers 502/503 at once through the proxy.
        credit_status_cache.put(self.user, STATUS)
        credit_status_cache.invalidate(self.user)
        self.client.get_my_credit_status.side_effect = sdk_http_error(503, retry_after="5")
        result = users.get_my_credit_status()
        self.assertTrue(result["stale"])
        self.assertEqual(_error_log_count(), self.logs_before)
        for _ in range(ar_breaker.FAILURE_THRESHOLD - 1):
            users.get_my_credit_status()
        self.assertTrue(ar_breaker.is_open())

    def test_other_failure_serves_stale_with_one_error_log(self):
        credit_status_cache.put(self.user, STATUS)
        credit_status_cache.invalidate(self.user)
        self.client.get_my_credit_status.side_effect = ARAPIError("nope", status_code=400)
        result = users.get_my_credit_status()
        self.assertTrue(result["stale"])
        self.assertEqual(_error_log_count(), self.logs_before + 1)

    def test_client_is_built_with_3s_timeout(self):
        users.get_my_credit_status()
        # One call builds the client for the membership check, one for credit status; both use 3 s.
        self.assertGreaterEqual(self.factory.call_count, 1)
        for call in self.factory.call_args_list:
            self.assertEqual(call.kwargs, {"timeout": SHORT_CALL_TIMEOUT})
        self.assertEqual(SHORT_CALL_TIMEOUT, 3)

    def test_turn_completion_invalidates_but_keeps_value(self):
        credit_status_cache.put(self.user, STATUS)
        credit_status_cache.invalidate(self.user)
        entry = credit_status_cache.get(self.user)
        self.assertFalse(credit_status_cache.is_fresh(entry))
        self.assertEqual(entry["value"], STATUS)
        self.client.get_my_credit_status.side_effect = ARTimeoutError("slow")
        self.assertTrue(users.get_my_credit_status()["stale"])
