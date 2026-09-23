"""FAC notification proxy: caching, fallback, honest dismiss status."""

import json
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest

MOD = "frappe_assistant_core.chat.api.notifications"


def _clear_cache_for(user):
    frappe.cache.delete_value(f"fac_notifications:{user}")


class TestGetNotifications(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        from frappe_assistant_core.chat.api.auth import _ar_user_id

        self.user = _ar_user_id("Administrator")
        _clear_cache_for(self.user)

    def _call(self, client):
        from frappe_assistant_core.chat.api import notifications as api

        with patch(f"{MOD}.get_fac_cloud_client", return_value=client), patch(
            f"{MOD}.is_chat_enabled", return_value=True
        ):
            return api.get_notifications()

    def test_fetch_passes_normalized_user_and_caches(self):
        client = MagicMock()
        client.get_notifications.return_value = {"notifications": [{"id": "N1"}]}
        result = self._call(client)
        client.get_notifications.assert_called_once_with(user_id=self.user, timeout=5)
        self.assertEqual(result["user"], self.user)
        self.assertEqual(result["notifications"], [{"id": "N1"}])
        self.assertNotIn("degraded", result)
        # second call served from cache — client not called again
        result2 = self._call(client)
        self.assertEqual(client.get_notifications.call_count, 1)
        self.assertEqual(result2["notifications"], [{"id": "N1"}])
        self.assertNotIn("degraded", result2)

    def test_failure_negative_caches_fallback(self):
        client = MagicMock()
        client.get_notifications.side_effect = RuntimeError("AR down")
        frappe.db.set_single_value("FAC Chat Settings", "cached_notifications", json.dumps([{"id": "FB1"}]))
        result = self._call(client)
        # normalized: missing dismissible/dismissed/created_at fail closed
        self.assertEqual(
            result["notifications"],
            [{"id": "FB1", "dismissible": False, "dismissed": False, "created_at": ""}],
        )
        self.assertIs(result["degraded"], True)
        # failure result was cached: second call does NOT retry AR, and the
        # cached response still carries degraded — a cache hit must not
        # lose track of the fact the underlying data is stale.
        result2 = self._call(client)
        self.assertEqual(client.get_notifications.call_count, 1)
        self.assertIs(result2["degraded"], True)

    def test_empty_fallback_on_unset_blob_is_also_degraded(self):
        client = MagicMock()
        client.get_notifications.side_effect = RuntimeError("AR down")
        frappe.db.set_single_value("FAC Chat Settings", "cached_notifications", None)
        result = self._call(client)
        self.assertEqual(result["notifications"], [])
        self.assertIs(result["degraded"], True)

    def test_gate_off_returns_empty(self):
        from frappe_assistant_core.chat.api import notifications as api

        with patch(f"{MOD}.is_chat_enabled", return_value=False):
            self.assertEqual(api.get_notifications()["notifications"], [])


class TestFallbackNotificationNormalization(BaseAssistantTest):
    """Guards against a stale/pre-fix heartbeat blob: the cron cache can
    hold rows shaped exactly like the old 7-key heartbeat dict, with no
    `dismissible` key at all. Missing `dismissible` must fail closed —
    never treated as dismissible by omission — especially for outages."""

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        from frappe_assistant_core.chat.api.auth import _ar_user_id

        self.user = _ar_user_id("Administrator")
        _clear_cache_for(self.user)

    def test_heartbeat_shaped_outage_normalizes_non_dismissible(self):
        # Exact 7-key shape the pre-fix heartbeat.py emitted — no
        # dismissible, no dismissed, no created_at.
        heartbeat_shaped = {
            "id": "N1",
            "title": "Outage",
            "message": "Degraded",
            "type": "outage",
            "action_label": None,
            "action_url": None,
            "priority": "high",
        }
        client = MagicMock()
        client.get_notifications.side_effect = RuntimeError("AR down")
        frappe.db.set_single_value(
            "FAC Chat Settings", "cached_notifications", json.dumps([heartbeat_shaped])
        )
        result = self._call(client)
        [notif] = result["notifications"]
        self.assertIs(notif["dismissible"], False)
        self.assertIs(notif["dismissed"], False)

    def test_corrupt_blob_degrades_to_empty_and_logs(self):
        frappe.db.set_single_value("FAC Chat Settings", "cached_notifications", "{not json")
        with patch(f"{MOD}.frappe.log_error") as mock_log:
            from frappe_assistant_core.chat.api import notifications as api

            self.assertEqual(api._fallback_notifications(), [])
            mock_log.assert_called_once()

    def test_fallback_row_with_explicit_dismissible_true_is_preserved(self):
        shaped = {
            "id": "N2",
            "title": "Feature",
            "message": "m",
            "type": "feature",
            "action_label": None,
            "action_url": None,
            "priority": "normal",
            "dismissible": True,
            "dismissed": False,
            "created_at": "2026-01-01 00:00:00",
        }
        client = MagicMock()
        client.get_notifications.side_effect = RuntimeError("AR down")
        frappe.db.set_single_value("FAC Chat Settings", "cached_notifications", json.dumps([shaped]))
        result = self._call(client)
        [notif] = result["notifications"]
        self.assertIs(notif["dismissible"], True)

    def _call(self, client):
        from frappe_assistant_core.chat.api import notifications as api

        with patch(f"{MOD}.get_fac_cloud_client", return_value=client), patch(
            f"{MOD}.is_chat_enabled", return_value=True
        ):
            return api.get_notifications()


class TestDismissNotification(BaseAssistantTest):
    def test_honest_status_on_ar_failure(self):
        from frappe_assistant_core.chat.api import notifications as api

        client = MagicMock()
        client.dismiss_notification.side_effect = RuntimeError("AR down")
        with patch(f"{MOD}.get_fac_cloud_client", return_value=client), patch(
            f"{MOD}.is_chat_enabled", return_value=True
        ):
            result = api.dismiss_notification(notification_id="N1")
        self.assertEqual(result["status"], "local_only")

    def test_success_status_and_cache_cleared(self):
        from frappe_assistant_core.chat.api import notifications as api
        from frappe_assistant_core.chat.api.auth import _ar_user_id

        user = _ar_user_id("Administrator")
        frappe.cache.set_value(f"fac_notifications:{user}", "[]", expires_in_sec=60)
        client = MagicMock()
        client.dismiss_notification.return_value = {"status": "dismissed"}
        with patch(f"{MOD}.get_fac_cloud_client", return_value=client), patch(
            f"{MOD}.is_chat_enabled", return_value=True
        ):
            result = api.dismiss_notification(notification_id="N1")
        self.assertEqual(result["status"], "dismissed")
        self.assertIsNone(frappe.cache.get_value(f"fac_notifications:{user}", expires=True))
