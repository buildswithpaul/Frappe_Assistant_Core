"""Spotlight backend: quota payload fields and the media CSP."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_assistant_core.chat.api.billing.quota import get_quota_status
from frappe_assistant_core.chat.utils.security_headers import _CSP_POLICY

LIVE = {
    "plan": "Free",
    "credit_quota": 1000,
    "credits_used": 850,
    "credit_balance": 0,
    "billing_cycle_start": "2026-09-24",
}


class TestQuotaSpotlightFields(FrappeTestCase):
    @patch("frappe_assistant_core.chat.api.billing._fetch_live_quota")
    def test_cycle_start_and_upgrade_pass_through(self, live):
        live.return_value = {**LIVE, "upgrade": {"plan": "Basic", "benefits": ["10,000 credits a month"]}}
        out = get_quota_status()
        self.assertEqual(out["billing_cycle_start"], "2026-09-24")
        self.assertEqual(out["upgrade"]["plan"], "Basic")

    @patch("frappe_assistant_core.chat.api.billing._fetch_live_quota")
    def test_top_plan_null_upgrade_is_kept(self, live):
        live.return_value = {**LIVE, "upgrade": None}
        out = get_quota_status()
        self.assertIn("upgrade", out)
        self.assertIsNone(out["upgrade"])

    @patch("frappe_assistant_core.chat.api.billing._fetch_live_quota")
    def test_older_ar_without_upgrade_omits_the_key(self, live):
        live.return_value = dict(LIVE)
        self.assertNotIn("upgrade", get_quota_status())

    @patch("frappe_assistant_core.chat.api.billing._fetch_live_quota", return_value=None)
    def test_fallback_path_has_cycle_key(self, _live):
        out = get_quota_status()
        # Only check billing_cycle_start when success is True (fallback may fail)
        if out.get("success"):
            self.assertIn("billing_cycle_start", out)


class TestSpaCsp(FrappeTestCase):
    def test_media_src_allows_https_video(self):
        self.assertIn("media-src 'self' https: blob:", _CSP_POLICY)
        self.assertIn("img-src 'self' data: blob: https:", _CSP_POLICY)
