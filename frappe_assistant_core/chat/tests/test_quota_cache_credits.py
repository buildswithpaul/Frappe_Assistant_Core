"""The quota cache must accumulate CREDITS, not tokens.

Regression guard for the header credit-meter bug: the per-turn fold used to be
fed the raw token count (thousands) while quota_total is the credit quota
(hundreds), so one message pushed quota_used past quota_total and the meter
clamped to 100% ("exhausted"). quota_used mirrors AR's credits_used, so the
whole fold pipeline must stay credit-denominated.
"""

import unittest
from unittest.mock import patch


def _mock_cache(mock_frappe, store):
    mock_frappe.cache.get_value.side_effect = lambda k, expires=True: store.get(k)
    mock_frappe.cache.set_value.side_effect = lambda k, v, expires_in_sec=None: store.__setitem__(k, v)


class TestQuotaCacheCredits(unittest.TestCase):
    @patch("frappe_assistant_core.chat.quota_cache.frappe")
    def test_increment_used_stays_in_credit_units(self, mock_frappe):
        # Basic plan: 500 credit quota, 10 credits already used this cycle.
        store = {"faco_quota_cache": {"quota_total": 500, "quota_used": 10.0}}
        _mock_cache(mock_frappe, store)

        from frappe_assistant_core.chat.quota_cache import get_quota_snapshot, increment_used

        # A heavy message: ~8000 tokens but only ~3.5 credits. Fed credits.
        increment_used(3.5)

        snap = get_quota_snapshot()
        self.assertAlmostEqual(snap["quota_used"], 13.5)
        pct = snap["quota_used"] / snap["quota_total"] * 100
        # NOT exhausted after one message — the whole point of the fix.
        self.assertLess(pct, 100)

    @patch("frappe_assistant_core.chat.quota_cache.frappe")
    def test_increment_used_tolerates_none(self, mock_frappe):
        store = {"faco_quota_cache": {"quota_total": 500, "quota_used": 10.0}}
        _mock_cache(mock_frappe, store)

        from frappe_assistant_core.chat.quota_cache import increment_used

        increment_used(None)  # AR occasionally reports no credits — must not crash
        self.assertAlmostEqual(store["faco_quota_cache"]["quota_used"], 10.0)

    @patch("frappe_assistant_core.chat.api.chat.helpers.frappe")
    def test_update_subscription_cache_forwards_credits_unchanged(self, mock_frappe):
        # The web relay's fold helper must pass credits straight through to the
        # cache — no token substitution, no scaling.
        with patch("frappe_assistant_core.chat.quota_cache.increment_used") as mock_inc, patch(
            "frappe_assistant_core.chat.quota_cache.get_field", return_value=""
        ):
            from frappe_assistant_core.chat.api.chat.helpers import _update_subscription_cache

            _update_subscription_cache(4.0)

        mock_inc.assert_called_once_with(4.0)

    @patch("frappe_assistant_core.chat.api.mobile_stream.frappe")
    def test_mobile_update_subscription_cache_forwards_credits_unchanged(self, mock_frappe):
        with patch("frappe_assistant_core.chat.quota_cache.increment_used") as mock_inc, patch(
            "frappe_assistant_core.chat.quota_cache.get_field", return_value=""
        ):
            from frappe_assistant_core.chat.api.mobile_stream import _update_subscription_cache

            _update_subscription_cache(2.5)

        mock_inc.assert_called_once_with(2.5)
