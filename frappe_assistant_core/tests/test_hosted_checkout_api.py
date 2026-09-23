# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""FAC's hosted-checkout endpoint: the seat-purchase `invited_by` stamp.

AR validates `invited_by` against the tenant owner and its Active Admins,
so a client-supplied value is an authority claim. This endpoint must
overwrite it with the acting session's AR identity rather than trust or
merely default to whatever the browser sent.
"""

from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat.api.auth import _ar_user_id
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestHostedCheckoutApi(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; tests run in isolated transaction
        frappe.set_user("Administrator")

    def _mock_client(self):
        client = MagicMock()
        client.create_hosted_checkout.return_value = {
            "checkout_url": "https://ar.example.com/checkout?token=x"
        }
        return client

    def test_seat_checkout_overwrites_a_hostile_invited_by(self):
        from frappe_assistant_core.chat.api.billing.hosted import create_hosted_checkout

        client = self._mock_client()
        with patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client):
            create_hosted_checkout(
                "Seat",
                params={"user_id": "hire@x.test", "invited_by": "attacker@x.test"},
                return_url="https://tenant.example.com/settings/users",
            )

        kwargs = client.create_hosted_checkout.call_args.kwargs
        params = kwargs["params"]
        self.assertEqual(params["invited_by"], _ar_user_id("Administrator"))
        self.assertNotEqual(params["invited_by"], "attacker@x.test")
        self.assertEqual(params["user_id"], "hire@x.test")

    def test_seat_checkout_stamps_invited_by_even_when_absent(self):
        from frappe_assistant_core.chat.api.billing.hosted import create_hosted_checkout

        client = self._mock_client()
        with patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client):
            create_hosted_checkout(
                "Seat",
                params={"user_id": "hire@x.test"},
                return_url="https://tenant.example.com/settings/users",
            )

        params = client.create_hosted_checkout.call_args.kwargs["params"]
        self.assertEqual(params["invited_by"], _ar_user_id("Administrator"))

    def test_non_seat_checkout_leaves_invited_by_alone(self):
        from frappe_assistant_core.chat.api.billing.hosted import create_hosted_checkout

        client = self._mock_client()
        with patch("frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client):
            create_hosted_checkout(
                "Credits",
                params={"amount": 500, "invited_by": "attacker@x.test"},
                return_url="https://tenant.example.com/settings/billing",
            )

        params = client.create_hosted_checkout.call_args.kwargs["params"]
        self.assertEqual(params["invited_by"], "attacker@x.test")
        self.assertEqual(params["amount"], 500)
