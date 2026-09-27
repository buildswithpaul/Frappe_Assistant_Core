"""Both quota endpoints must carry the plan's feature flags and the fallback flag.

The knowledge base hides Upload when ``features.knowledge_base`` is false, but
neither the boot payload nor get_quota_status returned ``features``, so the
gate always read "allowed" and a Free tenant was offered an upload that AR
then refused.
"""

from types import SimpleNamespace
from unittest.mock import patch

from frappe_assistant_core.tests.base_test import IntegrationTestCase

SNAPSHOT = "frappe_assistant_core.chat.quota_cache.get_quota_snapshot"
FREE_FEATURES = {"knowledge_base": False}


class TestBootQuotaFeatures(IntegrationTestCase):
    def _build(self, snap):
        from frappe_assistant_core.chat.api.init import _build_quota

        settings = SimpleNamespace(registration_status="Registered")
        with patch(SNAPSHOT, return_value=snap):
            return _build_quota(settings, is_admin=True)

    def test_features_pass_through(self):
        quota = self._build({"plan": "Free", "quota_total": 500, "features": FREE_FEATURES})

        self.assertEqual(quota["features"], FREE_FEATURES)
        self.assertFalse(quota["is_fallback"])

    def test_fallback_is_flagged(self):
        from frappe_assistant_core.chat.quota_cache import _safe_defaults

        self.assertTrue(self._build(_safe_defaults())["is_fallback"])


class TestQuotaStatusFeatures(IntegrationTestCase):
    def _status(self, live=None, snap=None):
        from frappe_assistant_core.chat.api.billing import quota as quota_api

        with patch.object(quota_api, "_fetch_live_quota_dispatch", return_value=live), patch(
            SNAPSHOT, return_value=snap or {"plan": "Free", "quota_total": 0, "quota_used": 0}
        ):
            return quota_api.get_quota_status()

    def test_live_features_pass_through(self):
        live = {"plan": "Free", "credit_quota": 500, "credits_used": 0, "features": FREE_FEATURES}

        status = self._status(live=live)

        self.assertEqual(status["features"], FREE_FEATURES)
        self.assertFalse(status["is_fallback"])

    def test_older_ar_without_features_reads_as_empty(self):
        status = self._status(live={"plan": "Free", "credit_quota": 500, "credits_used": 0})

        self.assertEqual(status["features"], {})

    def test_cached_features_survive_an_ar_blip(self):
        status = self._status(snap={"plan": "Free", "quota_total": 500, "features": FREE_FEATURES})

        self.assertEqual(status["features"], FREE_FEATURES)

    def test_fallback_is_flagged_when_ar_is_unreachable(self):
        from frappe_assistant_core.chat.quota_cache import _safe_defaults

        status = self._status(snap=_safe_defaults())

        self.assertTrue(status["is_fallback"])
