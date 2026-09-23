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

"""Tests for the FAC get_registration_state proxy endpoint.

Pure unittest.TestCase with mocking — no DB access. FrappeTestCase is not
used here because it crashes setUpClass on fiscal-year fixtures on
ERPNext-integrated sites; the FAC test suite convention is mocked
unittest.TestCase (see test_oauth_cors.py).
"""

import unittest
from unittest.mock import MagicMock, call, patch


class RegisterWithArTestCase(unittest.TestCase):
    """Base for tests that drive the real ``register_with_ar``.

    ``frappe.get_single`` is mocked, so every ``settings.*`` write lands on a
    MagicMock. ``store_tenant_secret`` / ``clear_tenant_secret`` are NOT part of
    that mock — ``register_with_ar`` imports them directly and they write
    ``__Auth`` and ``tabSingles`` for the live "FAC Chat Settings" Single.

    These are plain unittest tests: no transaction, no rollback, no blocked
    commit. An unmocked call therefore PERMANENTLY deletes (waitlist branch) or
    overwrites (success branch) the dev site's tenant secret, while the mocked
    settings keep ``registration_status = "Registered"``. ``can_use_faco`` then
    reads Registered-but-no-secret, reports ``not_registered``, and the SPA
    drops the admin back to "Reconnect this site" on every load.
    """

    def setUp(self):
        store = patch("frappe_assistant_core.chat.tenant_credentials.store_tenant_secret")
        clear = patch("frappe_assistant_core.chat.tenant_credentials.clear_tenant_secret")
        self.store_tenant_secret = store.start()
        self.clear_tenant_secret = clear.start()
        self.addCleanup(store.stop)
        self.addCleanup(clear.stop)


class FacGetRegistrationStateTests(unittest.TestCase):
    def test_proxies_and_returns_state(self):
        from frappe_assistant_core.chat.api.settings.registration import get_registration_state

        mock_settings = MagicMock()
        mock_settings.tenant_id = "abc123"

        canned_state = {
            "exists": True,
            "status": "Active",
            "owner_email_masked": "p***@x.com",
            "reregistration": True,
        }

        with patch("frappe.only_for"), patch("frappe.get_single", return_value=mock_settings), patch(
            "frappe.utils.get_url", return_value="https://mysite.example.com"
        ), patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_registration_state",
            return_value=canned_state,
        ) as proxy:
            out = get_registration_state()

        self.assertTrue(out["exists"])
        self.assertEqual(out["owner_email_masked"], "p***@x.com")
        # tenant_id from settings was forwarded to the proxy call
        self.assertEqual(proxy.call_args.kwargs.get("tenant_id"), "abc123")


class FacRegisterWithArReconnectTests(RegisterWithArTestCase):
    """Regression tests for the one-click reconnect dead-end.

    The SPA's handleReconnect() calls register_with_ar(owner_email=None, ...)
    on the reconnect path. The endpoint must resolve the session user's email
    server-side instead of rejecting the call outright.
    """

    REJECTION = "A valid owner email is required."

    def test_null_email_resolves_from_session_user_and_proceeds(self):
        from frappe_assistant_core.chat.api.settings.registration import register_with_ar

        mock_settings = MagicMock()
        mock_settings.tenant_id = "existing-tenant-id"
        mock_settings.fac_cloud_url = "https://assistantruntime.cloud"

        def fake_get_value(doctype, name=None, fieldname=None, *args, **kwargs):
            if doctype == "User":
                self.assertEqual(name, "Administrator")
                self.assertEqual(fieldname, "email")
                return "owner@example.com"
            return None

        mock_register_tenant = MagicMock(
            return_value={
                "tenant_id": "existing-tenant-id",
                "tenant_secret": "s" * 32,
                "subscription": {"plan": "Free", "quota": 50000},
            }
        )

        with patch("frappe.only_for"), patch("frappe.session") as mock_session, patch(
            "frappe.db.get_value", side_effect=fake_get_value
        ) as mock_get_value, patch("frappe.get_single", return_value=mock_settings), patch(
            "frappe.utils.get_url", return_value="https://mysite.example.com"
        ), patch("frappe.form_dict", {}), patch(
            "frappe_assistant_core.chat.fac_cloud_client.register_tenant",
            mock_register_tenant,
        ), patch("frappe_assistant_core.chat.quota_cache.update_from_ar"):
            mock_session.user = "Administrator"

            result = register_with_ar(owner_email=None, terms_version="v1")

        # The null-email rejection must NOT have fired.
        self.assertNotEqual(result.get("error"), self.REJECTION)
        self.assertTrue(result.get("success"))
        self.assertIn(call("User", "Administrator", "email"), mock_get_value.call_args_list)

        # The resolved session email — not None — was forwarded to AR.
        self.assertEqual(mock_register_tenant.call_args.kwargs.get("owner_email"), "owner@example.com")

        # AR's secret is persisted through tenant_credentials — and only ever
        # against the mock, never the live site's __Auth row.
        self.store_tenant_secret.assert_called_once_with("s" * 32)

    def test_unresolvable_email_still_rejected(self):
        """New-registration guard: a session user with no email must still error."""
        from frappe_assistant_core.chat.api.settings.registration import register_with_ar

        with patch("frappe.only_for"), patch("frappe.session") as mock_session, patch(
            "frappe.db.get_value", return_value=None
        ):
            mock_session.user = "Administrator"

            result = register_with_ar(owner_email=None, terms_version="v1")

        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("error"), self.REJECTION)


class FacRegisterWithArWaitlistTests(RegisterWithArTestCase):
    """The at-capacity waitlist response must NOT surface as a hard failure.

    AR returns {"waitlisted": True, ...} when registration is capped. Before the
    fix, register_with_ar had no branch for it, so the payload fell through to
    the generic "Registration failed" return (and wrongly set status=Error).
    """

    def _run_with_ar_response(self, ar_response):
        from frappe_assistant_core.chat.api.settings.registration import register_with_ar

        mock_settings = MagicMock()
        mock_settings.fac_cloud_url = "https://assistantruntime.cloud"

        with patch("frappe.only_for"), patch("frappe.session") as mock_session, patch(
            "frappe.db.get_value", return_value="owner@example.com"
        ), patch("frappe.get_single", return_value=mock_settings), patch(
            "frappe.utils.get_url", return_value="https://mysite.example.com"
        ), patch("frappe.form_dict", {}), patch(
            "frappe_assistant_core.chat.fac_cloud_client.register_tenant",
            MagicMock(return_value=ar_response),
        ), patch("frappe_assistant_core.chat.quota_cache.update_from_ar"):
            mock_session.user = "Administrator"
            result = register_with_ar(owner_email="owner@example.com", terms_version="v1")
        return result, mock_settings

    def test_waitlisted_response_maps_to_waitlisted_not_failure(self):
        result, settings = self._run_with_ar_response(
            {
                "waitlisted": True,
                "waitlist_position": 7,
                "message": "You've been added to our waitlist.",
            }
        )

        # It is a success-shaped waitlist state, NOT a failure.
        self.assertTrue(result.get("success"))
        self.assertTrue(result.get("waitlisted"))
        self.assertEqual(result.get("waitlist_position"), 7)
        self.assertIsNone(result.get("error"))
        # Registration status persisted as Waitlisted, not Error.
        self.assertEqual(settings.registration_status, "Waitlisted")
        # A waitlisted applicant holds no credentials — the branch clears them
        # via the mock, never against the live site's __Auth row.
        self.clear_tenant_secret.assert_called_once_with()
        self.store_tenant_secret.assert_not_called()

    def test_promotion_token_forwarded_to_ar(self):
        from frappe_assistant_core.chat.api.settings.registration import register_with_ar

        mock_settings = MagicMock()
        mock_settings.fac_cloud_url = "https://assistantruntime.cloud"
        mock_register = MagicMock(
            return_value={"tenant_id": "t" * 12, "tenant_secret": "s" * 32, "subscription": {}}
        )

        with patch("frappe.only_for"), patch("frappe.session") as mock_session, patch(
            "frappe.db.get_value", return_value="owner@example.com"
        ), patch("frappe.get_single", return_value=mock_settings), patch(
            "frappe.utils.get_url", return_value="https://mysite.example.com"
        ), patch("frappe.form_dict", {}), patch(
            "frappe_assistant_core.chat.fac_cloud_client.register_tenant", mock_register
        ), patch("frappe_assistant_core.chat.quota_cache.update_from_ar"):
            mock_session.user = "Administrator"
            register_with_ar(
                owner_email="owner@example.com",
                terms_version="v1",
                promotion_token="promo-xyz",
            )

        self.assertEqual(mock_register.call_args.kwargs.get("promotion_token"), "promo-xyz")
        self.store_tenant_secret.assert_called_once_with("s" * 32)


if __name__ == "__main__":
    unittest.main()
