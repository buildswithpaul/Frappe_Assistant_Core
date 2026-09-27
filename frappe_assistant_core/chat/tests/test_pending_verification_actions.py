# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Resend, change-email, local status and verify completion while pending.

Every test replaces ``frappe.get_single`` and the ``tenant_credentials``
writers: the dev site holds a live registered tenant, and an unmocked
registration write destroys its secret (see test_fac_get_registration_state).
FrappeTestCase adds a rollback on top, in case one ever slips through.
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

REG = "frappe_assistant_core.chat.api.settings.registration"
CLIENT = "frappe_assistant_core.chat.fac_cloud_client"
SITE = "https://mysite.example.com"
TOKEN = "pending-token-" + "x" * 30


class _Settings:
    """A stand-in for FAC Chat Settings that records what was saved."""

    def __init__(self, status="Pending Email Verification", tenant_id="tenant-1", pending_token=TOKEN):
        self.registration_status = status
        self.tenant_id = tenant_id
        self.tenant_secret = None
        self._pending_token = pending_token
        self.flags = frappe._dict()
        self.save = MagicMock()

    def get_password(self, fieldname, raise_exception=True):
        assert fieldname == "pending_verification_token"
        return self._pending_token


class PendingVerificationTestCase(FrappeTestCase):
    def setUp(self):
        super().setUp()
        self.settings = _Settings()
        for target, attr in (
            ("frappe_assistant_core.chat.tenant_credentials.store_tenant_secret", "store_secret"),
            ("frappe_assistant_core.chat.tenant_credentials.clear_tenant_secret", "clear_secret"),
            ("frappe_assistant_core.chat.quota_cache.clear", "clear_quota"),
            ("frappe.get_single", "get_single"),
            ("frappe.only_for", "only_for"),
            ("frappe.utils.get_url", "get_url"),
        ):
            patcher = patch(target)
            setattr(self, attr, patcher.start())
            self.addCleanup(patcher.stop)
        self.get_single.return_value = self.settings
        self.get_url.return_value = SITE

    def assert_registration_untouched(self):
        self.assertEqual(self.settings.registration_status, "Pending Email Verification")
        self.settings.save.assert_not_called()
        self.store_secret.assert_not_called()
        self.clear_secret.assert_not_called()


class RegisterStoresPendingTokenTests(PendingVerificationTestCase):
    def _register(self, ar_result):
        from frappe_assistant_core.chat.api.settings.registration import register_with_ar

        with patch(f"{CLIENT}.register_tenant", return_value=ar_result), patch(
            "frappe_assistant_core.chat.api.auth._ar_user_id", return_value="owner@example.com"
        ), patch("frappe.form_dict", {}):
            return register_with_ar(owner_email="owner@example.com", terms_version="v1")

    def test_new_pending_tenant_keeps_ars_token(self):
        self.settings = _Settings(status="Not Registered", tenant_id=None, pending_token=None)
        self.get_single.return_value = self.settings

        out = self._register({"tenant_id": "tenant-1", "verification_pending": True, "pending_token": TOKEN})

        self.assertTrue(out["verification_pending"])
        self.assertEqual(self.settings.pending_verification_token, TOKEN)
        self.settings.save.assert_called()
        self.clear_secret.assert_called_once()

    def test_re_registration_without_a_token_keeps_the_one_for_the_same_tenant(self):
        self.settings.pending_verification_token = "*****"

        self._register({"tenant_id": "tenant-1", "verification_pending": True})

        self.assertEqual(self.settings.pending_verification_token, "*****")

    def test_a_different_tenant_drops_a_stale_token(self):
        self.settings.pending_verification_token = "*****"

        self._register({"tenant_id": "tenant-2", "verification_pending": True})

        self.assertIsNone(self.settings.pending_verification_token)


class ResendOwnerVerificationTests(PendingVerificationTestCase):
    def _resend(self, ar_result):
        from frappe_assistant_core.chat.api.settings.registration import resend_owner_verification

        with patch(f"{CLIENT}.resend_owner_verification", return_value=ar_result) as sdk:
            return resend_owner_verification(), sdk

    def test_sends_the_stored_token(self):
        out, sdk = self._resend({"success": True, "owner_email_masked": "o***@example.com"})

        self.assertTrue(out["success"])
        self.assertEqual(sdk.call_args.kwargs, {"site_url": SITE, "pending_token": TOKEN})
        self.assert_registration_untouched()

    def test_without_a_token_asks_the_screen_to_reconnect(self):
        self.settings._pending_token = None

        out, sdk = self._resend({"success": True})

        self.assertEqual(out, {"success": False, "reconnect_required": True})
        sdk.assert_not_called()
        self.assert_registration_untouched()

    def test_already_verified_asks_the_screen_to_reconnect(self):
        out, _ = self._resend({"success": True, "already_verified": True, "owner_email_masked": "o***@x.com"})

        self.assertFalse(out["success"])
        self.assertTrue(out["already_verified"])
        self.assertTrue(out["reconnect_required"])
        self.assertEqual(out["owner_email_masked"], "o***@x.com")
        self.assert_registration_untouched()

    def test_passes_ars_own_message_through(self):
        out, _ = self._resend(
            {
                "error": "Too many verification emails for this site.",
                "status_code": 429,
                "exc_type": "RateLimitExceededError",
            }
        )

        self.assertEqual(out, {"success": False, "error": "Too many verification emails for this site."})
        self.assert_registration_untouched()

    def test_translates_a_raw_http_string(self):
        out, _ = self._resend(
            {"error": "503 Server Error: SERVICE UNAVAILABLE for url: https://ar/api", "status_code": 503}
        )

        self.assertFalse(out["success"])
        self.assertNotIn("Server Error", out["error"])
        self.assertNotIn("http", out["error"])
        self.assert_registration_untouched()


class ChangePendingOwnerEmailTests(PendingVerificationTestCase):
    def _change(self, address, ar_result=None):
        from frappe_assistant_core.chat.api.settings.registration import change_pending_owner_email

        with patch(
            f"{CLIENT}.change_pending_owner_email", return_value=ar_result or {"success": True}
        ) as sdk:
            return change_pending_owner_email(owner_email=address), sdk

    def test_sends_the_stored_token(self):
        out, sdk = self._change(
            "new@example.com", {"success": True, "owner_email_masked": "n***@example.com"}
        )

        self.assertTrue(out["success"])
        self.assertEqual(
            sdk.call_args.kwargs,
            {"site_url": SITE, "owner_email": "new@example.com", "pending_token": TOKEN},
        )
        self.assert_registration_untouched()

    def test_without_a_token_says_so_and_does_not_call_ar(self):
        self.settings._pending_token = None

        out, sdk = self._change("new@example.com")

        self.assertFalse(out["success"])
        self.assertTrue(out["error"])
        sdk.assert_not_called()

    def test_rejects_an_invalid_address_locally(self):
        out, sdk = self._change("not-an-email")

        self.assertFalse(out["success"])
        sdk.assert_not_called()

    def test_translates_errors_without_marking_the_registration_failed(self):
        out, _ = self._change(
            "new@example.com", {"error": "Connection aborted: timed out", "status_code": None}
        )

        self.assertFalse(out["success"])
        self.assertIn("reach", out["error"])
        self.assert_registration_untouched()


class LocalRegistrationStatusTests(PendingVerificationTestCase):
    def test_reads_settings_without_calling_ar(self):
        from frappe_assistant_core.chat.api.settings.registration import get_local_registration_status

        with patch(f"{CLIENT}.get_registration_state") as remote, patch("requests.post") as post:
            out = get_local_registration_status()

        self.assertEqual(out, {"registration_status": "Pending Email Verification"})
        remote.assert_not_called()
        post.assert_not_called()


class CompleteEmailVerificationTests(PendingVerificationTestCase):
    def _complete(self, verify_payload, secret_result=None):
        from frappe_assistant_core.chat.api.settings.registration import complete_email_verification

        verify = MagicMock()
        verify.raise_for_status.return_value = None
        verify.json.return_value = {"message": verify_payload}
        with patch("requests.post", return_value=verify), patch(
            "assistant_runtime_sdk.client.get_initial_secret",
            return_value=secret_result or {"tenant_secret": "s" * 40},
        ), patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_url", return_value="https://ar"
        ), patch(f"{REG}.get_fac_cloud_url", return_value="https://ar"):
            return complete_email_verification(verification_token="link-token")

    def test_sets_the_tenant_id_ar_verified(self):
        self.settings.tenant_id = None

        out = self._complete({"verified": True, "tenant_id": "tenant-from-ar"})

        self.assertTrue(out["success"])
        self.assertEqual(self.settings.tenant_id, "tenant-from-ar")
        self.assertEqual(self.settings.registration_status, "Registered")
        self.assertIsNone(self.settings.pending_verification_token)
        self.store_secret.assert_called_once_with("s" * 40)

    def test_clears_the_quota_cache(self):
        self._complete({"verified": True, "tenant_id": "tenant-1"})

        self.clear_quota.assert_called_once()

    def test_a_failed_pickup_leaves_the_registration_pending(self):
        out = self._complete({"verified": True, "tenant_id": "tenant-1"}, {"error": "Token already used"})

        self.assertFalse(out["success"])
        self.assert_registration_untouched()
