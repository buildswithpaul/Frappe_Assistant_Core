# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Coming back from FAC Cloud's checkout page must not show the old plan.

The plan this site shows is cached — in Redis for a day, refreshed every six
hours — so a purchase that has just landed stayed invisible until the next
sync. `verify_checkout_return` asks FAC Cloud about the one session the
customer is returning from and refreshes the cache once it has landed.
"""

from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.fac_cloud_client import ARAPIError, ARConnectionError
from frappe_assistant_core.tests.base_test import BaseAssistantTest

HOSTED = "frappe_assistant_core.chat.api.billing.hosted"
QUOTA = {"plan": "Team", "quota_total": 50000, "quota_used": 10}


def _status(outcome: str, done: bool, **extra) -> dict:
    return {
        "session": "CHK-2026-00001",
        "status": "Completed",
        "purpose": "Subscription",
        "target_plan": "Team",
        "plan": "Team" if outcome == "applied" else "Free",
        "pending_plan": None if outcome == "applied" else "Team",
        "payment_status": "Paid",
        "done": done,
        "outcome": outcome,
        **extra,
    }


class TestVerifyCheckoutReturn(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; tests run in isolated transaction
        frappe.set_user("Administrator")

    def _call(self, client, session="CHK-2026-00001"):
        from frappe_assistant_core.chat.api.billing.hosted import verify_checkout_return

        with patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
            return_value=client,
        ), patch(f"{HOSTED}._refresh_subscription_cache") as refresh, patch(
            f"{HOSTED}._quota_summary", return_value=QUOTA
        ):
            result = verify_checkout_return(session)
        return result, refresh

    def test_a_purchase_that_landed_refreshes_the_cached_plan(self):
        client = MagicMock()
        client.get_checkout_session_status.return_value = _status("applied", True)

        result, refresh = self._call(client)

        client.get_checkout_session_status.assert_called_once_with("CHK-2026-00001")
        refresh.assert_called_once()
        self.assertTrue(result["done"])
        self.assertEqual(result["outcome"], "applied")
        self.assertEqual(result["quota"], QUOTA)
        self.assertEqual(result["plan"], "Team")

    def test_a_purchase_still_settling_is_not_done_and_leaves_the_cache(self):
        client = MagicMock()
        client.get_checkout_session_status.return_value = _status("processing", False)

        result, refresh = self._call(client)

        refresh.assert_not_called()
        self.assertFalse(result["done"])
        self.assertEqual(result["outcome"], "processing")
        self.assertNotIn("quota", result)

    def test_a_cancelled_checkout_is_done_without_a_refresh(self):
        client = MagicMock()
        client.get_checkout_session_status.return_value = _status("cancelled", True)

        result, refresh = self._call(client)

        refresh.assert_not_called()
        self.assertTrue(result["done"])
        self.assertEqual(result["outcome"], "cancelled")

    def test_an_sdk_without_the_method_falls_back_to_a_plain_refresh(self):
        """FAC can run against an SDK release that predates the method."""
        client = MagicMock(spec=["create_hosted_checkout", "get_tenant_info"])

        result, refresh = self._call(client)

        refresh.assert_called_once()
        self.assertTrue(result["done"])
        self.assertEqual(result["outcome"], "unknown")
        self.assertEqual(result["quota"], QUOTA)

    def test_a_runtime_without_the_endpoint_falls_back_to_a_plain_refresh(self):
        """An older FAC Cloud answers an unknown method with Frappe's
        "Failed to get method" validation error."""
        client = MagicMock()
        client.get_checkout_session_status.side_effect = ARAPIError(
            "Failed to get method for command assistant_runtime_payments.api.get_checkout_session_status",
            status_code=417,
        )

        result, refresh = self._call(client)

        refresh.assert_called_once()
        self.assertTrue(result["done"])
        self.assertEqual(result["outcome"], "unknown")

    def test_a_transient_failure_keeps_the_caller_polling(self):
        client = MagicMock()
        client.get_checkout_session_status.side_effect = ARConnectionError("down")

        result, refresh = self._call(client)

        refresh.assert_not_called()
        self.assertFalse(result["done"])
        self.assertEqual(result["outcome"], "processing")
        self.assertTrue(result["error"])

    def test_a_blank_session_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            self._call(MagicMock(), session="")

    def test_only_a_system_manager_may_ask(self):
        from frappe_assistant_core.chat.api.billing.hosted import verify_checkout_return

        # nosemgrep: frappe-setuser — test bootstrap; tests run in isolated transaction
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            verify_checkout_return("CHK-2026-00001")

    def test_it_is_exposed_where_the_spa_calls_it(self):
        from frappe_assistant_core.chat import api

        self.assertTrue(callable(getattr(api, "verify_checkout_return", None)))
