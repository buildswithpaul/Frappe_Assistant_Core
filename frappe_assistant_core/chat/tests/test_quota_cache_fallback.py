"""The quota fallback is a guess made while AR was unreachable. It must never
be cached, and every client must be able to tell it apart from a real plan.

Caching it kept "Unknown plan · Unlimited" on a new signup's plan card for the
whole 24h TTL. The direct seed path had stopped caching it, but set_field and
increment_used still read the fallback and wrote it straight back — and
increment_used runs on every chat turn.

Redis is replaced by a dict here; nothing touches the real cache or database.
"""

import unittest
from unittest.mock import MagicMock, patch

from frappe_assistant_core.chat import quota_cache

CLIENT = "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client"


def _cache(store):
    cache = MagicMock()
    cache.get_value.side_effect = lambda k, expires=True: store.get(k)
    cache.set_value.side_effect = lambda k, v, expires_in_sec=None: store.__setitem__(k, v)
    cache.delete_value.side_effect = lambda k: store.pop(k, None)
    return cache


def _client(info=None, error=None):
    client = MagicMock()
    if error:
        client.get_tenant_info.side_effect = error
    else:
        client.get_tenant_info.return_value = info
    return client


TENANT_INFO = {
    "subscription": {
        "plan": "Free",
        "credit_quota": 500,
        "credits_used": 12,
        "features": {"knowledge_base": False},
    },
    "preferred_model": "",
}


class TestQuotaFallbackNeverPersisted(unittest.TestCase):
    def setUp(self):
        self.store = {}
        patcher = patch.object(quota_cache.frappe, "cache", _cache(self.store))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _ar_down(self):
        return patch(CLIENT, return_value=_client(error=ConnectionError("AR down")))

    def test_fallback_is_marked(self):
        with self._ar_down():
            snap = quota_cache.get_quota_snapshot()

        self.assertTrue(snap["is_fallback"])
        self.assertNotIn(quota_cache.CACHE_KEY, self.store)

    def test_set_field_does_not_persist_a_fallback(self):
        with self._ar_down():
            quota_cache.set_field("cached_capabilities", "{}")

        self.assertNotIn(quota_cache.CACHE_KEY, self.store)

    def test_increment_used_does_not_persist_a_fallback(self):
        with self._ar_down():
            quota_cache.increment_used(3.5)

        self.assertNotIn(quota_cache.CACHE_KEY, self.store)

    def test_update_from_ar_replaces_the_fallback_with_real_figures(self):
        with self._ar_down():
            quota_cache.update_from_ar({"plan": "Free", "credit_quota": 0, "credits_used": 0})

        cached = self.store[quota_cache.CACHE_KEY]
        self.assertEqual(cached["plan"], "Free")
        self.assertEqual(cached["quota_total"], 0)
        self.assertNotIn("is_fallback", cached)

    def test_update_from_ar_keeps_the_billing_cycle_start(self):
        with self._ar_down():
            quota_cache.update_from_ar(
                {"plan": "Free", "credit_quota": 10, "billing_cycle_start": "2026-09-24"}
            )

        self.assertEqual(self.store[quota_cache.CACHE_KEY]["billing_cycle_start"], "2026-09-24")

    def test_real_seed_is_cached_with_features(self):
        with patch(CLIENT, return_value=_client(TENANT_INFO)):
            snap = quota_cache.get_quota_snapshot()

        self.assertFalse(snap.get("is_fallback"))
        self.assertEqual(self.store[quota_cache.CACHE_KEY]["features"], {"knowledge_base": False})

    def test_a_failed_seed_is_not_retried_immediately(self):
        client = _client(error=ConnectionError("AR down"))
        with patch(CLIENT, return_value=client):
            quota_cache.get_quota_snapshot()
            quota_cache.get_quota_snapshot()
            quota_cache.increment_used(1)

        self.assertEqual(client.get_tenant_info.call_count, 1)

    def test_seed_retries_once_the_backoff_expires(self):
        client = _client(error=ConnectionError("AR down"))
        with patch(CLIENT, return_value=client):
            quota_cache.get_quota_snapshot()
            self.store.pop(quota_cache.SEED_FAILED_KEY)
            client.get_tenant_info.side_effect = None
            client.get_tenant_info.return_value = TENANT_INFO
            snap = quota_cache.get_quota_snapshot()

        self.assertEqual(snap["plan"], "Free")
        self.assertFalse(snap.get("is_fallback"))

    def test_clear_also_forgets_a_failed_seed(self):
        self.store[quota_cache.SEED_FAILED_KEY] = True

        quota_cache.clear()

        self.assertNotIn(quota_cache.SEED_FAILED_KEY, self.store)


class TestSummarize(unittest.TestCase):
    def test_features_pass_through(self):
        view = quota_cache.summarize(
            {"plan": "Free", "quota_total": 500, "features": {"knowledge_base": False}}
        )

        self.assertEqual(view["features"], {"knowledge_base": False})
        self.assertFalse(view["is_fallback"])

    def test_absent_features_read_as_empty(self):
        self.assertEqual(quota_cache.summarize({"quota_total": 500})["features"], {})

    def test_fallback_is_surfaced_and_real_unlimited_is_not(self):
        fallback = quota_cache.summarize(quota_cache._safe_defaults())
        unlimited = quota_cache.summarize({"plan": "Enterprise", "quota_total": -1})

        self.assertTrue(fallback["is_fallback"])
        self.assertTrue(unlimited["is_unlimited"])
        self.assertFalse(unlimited["is_fallback"])


if __name__ == "__main__":
    unittest.main()
