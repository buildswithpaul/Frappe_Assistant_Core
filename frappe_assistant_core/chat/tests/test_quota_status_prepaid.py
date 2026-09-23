"""get_quota_status must state the admission decision, not just the percentage.

The widget used to refuse to send whenever ``percentage_used >= 100``, a figure
derived from the monthly plan quota alone. A tenant who had bought prepaid
credits was therefore walled out of the widget while the SPA — which has no
client-side gate — worked fine, and while AR itself would happily have admitted
the turn (payments/runtime_hooks.py admits whenever the balance is > 0).

So the server now publishes the same two states AR's gate uses:
  * ``in_overage``        — quota spent, prepaid covering  -> allow, notify once
  * ``credits_exhausted`` — quota spent, prepaid gone      -> hard block

``credit_balance`` must be present on BOTH the live and the cached-fallback
paths. It used to be emitted only when AR answered, so an AR blip made the
balance read as absent, which the widget scored as zero — turning a transient
network failure into a hard block for a tenant with credits in hand.
"""

from unittest.mock import patch

from frappe.tests.classes.integration_test_case import IntegrationTestCase


def _live(quota, used, balance):
    return {"credit_quota": quota, "credits_used": used, "credit_balance": balance, "plan": "Individual"}


class TestQuotaStatusPrepaid(IntegrationTestCase):
    def _status(self, live=None, snapshot=None):
        from frappe_assistant_core.chat.api.billing import quota as quota_api

        snap = {"quota_total": 0, "quota_used": 0, "plan": "Free", **(snapshot or {})}
        with patch.object(quota_api, "_fetch_live_quota_dispatch", return_value=live), patch(
            "frappe_assistant_core.chat.quota_cache.get_quota_snapshot", return_value=snap
        ):
            return quota_api.get_quota_status()

    # ---- live path -------------------------------------------------------

    def test_quota_remaining_is_neither_overage_nor_exhausted(self):
        r = self._status(live=_live(500, 100, 0))
        self.assertFalse(r["in_overage"])
        self.assertFalse(r["credits_exhausted"])

    def test_quota_spent_with_prepaid_is_overage_not_exhausted(self):
        """The bug: this tenant was blocked. It must now be admitted."""
        r = self._status(live=_live(500, 500, 25000))
        self.assertTrue(r["in_overage"])
        self.assertFalse(r["credits_exhausted"])
        self.assertEqual(r["credit_balance"], 25000)

    def test_quota_overspent_with_prepaid_is_still_only_overage(self):
        r = self._status(live=_live(500, 900, 25000))
        self.assertTrue(r["in_overage"])
        self.assertFalse(r["credits_exhausted"])

    def test_quota_spent_without_prepaid_is_exhausted(self):
        r = self._status(live=_live(500, 500, 0))
        self.assertFalse(r["in_overage"])
        self.assertTrue(r["credits_exhausted"])

    def test_unlimited_quota_is_never_blocked(self):
        r = self._status(live=_live(-1, 999999, 0))
        self.assertTrue(r["is_unlimited"])
        self.assertFalse(r["in_overage"])
        self.assertFalse(r["credits_exhausted"])

    def test_zero_quota_with_prepaid_is_overage(self):
        """A quota of 0 is spent from the first request — AR's rule exactly."""
        r = self._status(live=_live(0, 0, 500))
        self.assertTrue(r["in_overage"])
        self.assertFalse(r["credits_exhausted"])

    def test_zero_quota_without_prepaid_is_exhausted(self):
        r = self._status(live=_live(0, 0, 0))
        self.assertTrue(r["credits_exhausted"])

    # ---- cached-fallback path (AR unreachable) ---------------------------

    def test_fallback_still_reports_the_cached_balance(self):
        """An AR blip must not read as a zero balance and block a paid tenant."""
        r = self._status(
            live=None,
            snapshot={"quota_total": 500, "quota_used": 500, "credit_balance": 8000},
        )
        self.assertEqual(r["credit_balance"], 8000)
        self.assertTrue(r["in_overage"])
        self.assertFalse(r["credits_exhausted"])

    def test_fallback_without_a_cached_balance_is_exhausted(self):
        r = self._status(
            live=None,
            snapshot={"quota_total": 500, "quota_used": 500},
        )
        self.assertEqual(r["credit_balance"], 0)
        self.assertTrue(r["credits_exhausted"])

    def test_credit_balance_is_always_present(self):
        """Absent is not zero — the widget cannot tell them apart, so never omit."""
        for live, snapshot in (
            (_live(500, 10, 0), None),
            (None, {"quota_total": 500, "quota_used": 10}),
        ):
            with self.subTest(live=bool(live)):
                self.assertIn("credit_balance", self._status(live=live, snapshot=snapshot))
