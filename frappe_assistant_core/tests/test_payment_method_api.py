# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""FAC's proxy endpoints for the self-serve payment-method flow."""

from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestPaymentMethodApi(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; tests run in isolated transaction
        frappe.set_user("Administrator")

    def test_get_payment_instrument_passes_through(self):
        from frappe_assistant_core.chat.api.billing.subscription import (
            get_payment_instrument,
        )

        client = MagicMock()
        client.get_payment_instrument.return_value = {
            "gateway": "razorpay",
            "autopay": {"method": "upi", "display": "paul@okhdfcbank"},
            "update_mode": "swap",
        }

        with patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
            return_value=client,
        ):
            result = get_payment_instrument()

        self.assertTrue(result["success"])
        self.assertEqual(result["autopay"]["display"], "paul@okhdfcbank")
        self.assertEqual(result["update_mode"], "swap")

    def test_update_payment_method_forwards_arguments(self):
        from frappe_assistant_core.chat.api.billing.subscription import (
            update_payment_method,
        )

        client = MagicMock()
        client.update_payment_method.return_value = {
            "update_mode": "settle",
            "razorpay_order_id": "order_1",
        }

        with patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
            return_value=client,
        ):
            result = update_payment_method(payment_method="card", billing_name="Acme")

        client.update_payment_method.assert_called_once_with(payment_method="card", billing_name="Acme")
        self.assertEqual(result["update_mode"], "settle")

    def test_update_payment_method_rejects_an_unknown_method(self):
        from frappe_assistant_core.chat.api.billing.subscription import (
            update_payment_method,
        )

        with self.assertRaises(frappe.ValidationError):
            update_payment_method(payment_method="bitcoin")

    def test_unregistered_site_returns_an_error_not_a_crash(self):
        from frappe_assistant_core.chat.api.billing.subscription import (
            get_payment_instrument,
        )

        with patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client",
            return_value=None,
        ):
            result = get_payment_instrument()

        self.assertIn("error", result)
