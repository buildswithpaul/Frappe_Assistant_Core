"""Models, notifications and membership give AR 3 s, share the breaker, and degrade quietly.

Cache and breaker are the site's real Redis state; only the AR client factory is patched, with
an autospec'd client so a renamed SDK method fails the test.
"""

from unittest.mock import create_autospec, patch

import frappe
from assistant_runtime_sdk import ARTimeoutError, AssistantRuntimeClient

from frappe_assistant_core.chat import ar_breaker
from frappe_assistant_core.chat.api import models, notifications
from frappe_assistant_core.chat.api.settings import access
from frappe_assistant_core.chat.fac_cloud_client import SHORT_CALL_TIMEOUT
from frappe_assistant_core.tests.base_test import BaseAssistantTest

FACTORY = "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client"
NOTIF_FACTORY = "frappe_assistant_core.chat.api.notifications.get_fac_cloud_client"
NOTIF_TITLE = "FAC Notifications"
MODELS = {"models": [{"model_id": "m1", "tier": "Standard"}], "default_model": "m1"}
MEMBER = "short-calls-member@example.com"


def _error_log_count(title):
    return frappe.db.count("Error Log", {"method": title})


class ShortCallsBase(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.client = create_autospec(AssistantRuntimeClient, instance=True)
        self._clear()
        self.addCleanup(self._clear)

    def _clear(self):
        frappe.cache.delete_value(models.MODEL_LIST_KEY)
        frappe.cache.delete_value(f"faco_member:{MEMBER}")
        frappe.cache.delete_value(notifications._cache_key(notifications._ar_user_id(frappe.session.user)))
        for name in (ar_breaker._FAILURES_KEY, ar_breaker._OPEN_KEY, ar_breaker._WAS_OPEN_KEY):
            frappe.cache.delete(ar_breaker._key(name))

    def _open_breaker(self):
        for _ in range(ar_breaker.FAILURE_THRESHOLD):
            ar_breaker.record_failure()


class TestModelList(ShortCallsBase):
    def setUp(self):
        super().setUp()
        patcher = patch(FACTORY, return_value=self.client)
        self.factory = patcher.start()
        self.addCleanup(patcher.stop)
        self.client.list_available_models.return_value = MODELS

    def test_model_list_served_from_cache_for_300s(self):
        first = models.get_available_models()
        self.assertTrue(first["success"])
        models.get_available_models()
        self.assertEqual(self.client.list_available_models.call_count, 1)

    def test_model_list_failure_cached_30s_and_serves_last_good_as_stale(self):
        models.get_available_models()
        # Production reaches this once the 300 s trust window has lapsed; age the entry by hand.
        entry = frappe.cache.get_value(models.MODEL_LIST_KEY)
        entry["at"] -= models.AVAILABLE_MODELS_TTL + 1
        frappe.cache.set_value(models.MODEL_LIST_KEY, entry)
        self.client.list_available_models.side_effect = ARTimeoutError("slow")
        result = models.get_available_models()
        self.assertTrue(result["stale"])
        self.assertEqual(result["models"], MODELS["models"])
        again = models.get_available_models()
        self.assertTrue(again["stale"])
        self.assertEqual(self.client.list_available_models.call_count, 2)

    def test_model_list_failure_without_last_good_keeps_error_shape(self):
        self.client.list_available_models.side_effect = ARTimeoutError("slow")
        self.assertIn("error", models.get_available_models())

    def test_model_list_uses_3s_timeout(self):
        models.get_available_models()
        self.client.list_available_models.assert_called_once_with(timeout=3)
        self.factory.assert_called_once_with(timeout=SHORT_CALL_TIMEOUT)

    def test_open_breaker_skips_model_list_call(self):
        self._open_breaker()
        self.assertIn("error", models.get_available_models())
        self.client.list_available_models.assert_not_called()


class TestNotifications(ShortCallsBase):
    def setUp(self):
        super().setUp()
        for target, kwargs in (
            (NOTIF_FACTORY, {"return_value": self.client}),
            ("frappe_assistant_core.chat.api.notifications.is_chat_enabled", {"return_value": True}),
        ):
            patcher = patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.logs_before = _error_log_count(NOTIF_TITLE)

    def test_notifications_skip_ar_when_breaker_open(self):
        self._open_breaker()
        result = notifications.get_notifications()
        self.assertTrue(result["degraded"])
        self.client.get_notifications.assert_not_called()

    def test_notifications_timeout_writes_no_error_log(self):
        self.client.get_notifications.side_effect = ARTimeoutError("slow")
        result = notifications.get_notifications()
        self.assertTrue(result["degraded"])
        self.assertEqual(_error_log_count(NOTIF_TITLE), self.logs_before)
        self.assertEqual(self.client.get_notifications.call_args.kwargs["timeout"], 3)
        self.assertFalse(ar_breaker.is_open())
        # The timeout counted as one failure: two more reach the threshold of three.
        ar_breaker.record_failure()
        ar_breaker.record_failure()
        self.assertTrue(ar_breaker.is_open())


class TestMembership(ShortCallsBase):
    def setUp(self):
        super().setUp()
        patcher = patch(FACTORY, return_value=self.client)
        self.factory = patcher.start()
        self.addCleanup(patcher.stop)

    def test_membership_unreachable_feeds_the_breaker(self):
        # The SDK returns this marker instead of raising when its request fails.
        self.client.get_user_auth_status.return_value = {"_ar_unreachable": True, "error": "x"}
        for _ in range(ar_breaker.FAILURE_THRESHOLD):
            frappe.cache.delete_value(f"faco_member:{MEMBER}")
            self.assertTrue(access._is_faco_member(MEMBER))
        self.assertTrue(ar_breaker.is_open())

    def test_membership_skips_ar_when_breaker_open_and_fails_open(self):
        self._open_breaker()
        self.assertTrue(access._is_faco_member(MEMBER))
        self.client.get_user_auth_status.assert_not_called()
        self.factory.assert_not_called()
