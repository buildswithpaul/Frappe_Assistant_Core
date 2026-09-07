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

"""`owner_email` is resolved, not assumed to already be an address.

A Frappe User's docname is its email for ordinary staff but not for
Administrator — the account most likely to be registering a site. Supplying
`frappe.session.user` used to *defeat* the recovery path rather than use it,
because a truthy non-address skipped the lookup and failed validation.
"""

from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.settings.registration import register_with_ar
from frappe_assistant_core.tests.base_test import BaseAssistantTest

# Returning an empty dict short-circuits every success branch and lands on the
# generic-error return, so no call leaves the process.
AR_STOP = {}


class TestRegisterOwnerEmailIdentity(BaseAssistantTest):
    def _owner_email_sent_to_ar(self, **kwargs) -> str:
        target = "frappe_assistant_core.chat.fac_cloud_client.register_tenant"
        with patch(target, return_value=AR_STOP) as register_tenant:
            register_with_ar(terms_version="1.0", **kwargs)
        register_tenant.assert_called_once()
        return register_tenant.call_args.kwargs["owner_email"]

    def test_a_username_resolves_to_that_users_email(self):
        """Patched rather than read from the site: an untouched install leaves
        Administrator's email as the `admin@example.com` placeholder, which is
        deliberately not resolvable — see the rejection test below."""
        with patch("frappe.db.get_value", return_value="owner@promantia.com"):
            self.assertEqual(
                self._owner_email_sent_to_ar(owner_email="Administrator"),
                "owner@promantia.com",
            )

    def test_a_username_backed_only_by_frappes_placeholder_is_rejected(self):
        """`admin@example.com` is every Frappe site's install fixture and can
        receive no mail, so AR's verification link would go nowhere. Failing
        here beats a registration that silently never completes."""
        with patch("frappe.db.get_value", return_value="admin@example.com"):
            result = register_with_ar(owner_email="Administrator", terms_version="1.0")

        self.assertFalse(result["success"])
        self.assertIn("cannot receive the verification email", result["error"].lower())

    def test_a_real_address_is_passed_through_untouched(self):
        """The SPA collects an address on a form; it need not be a Frappe user."""
        self.assertEqual(
            self._owner_email_sent_to_ar(owner_email="someone@example.com"),
            "someone@example.com",
        )

    def test_an_absent_owner_email_resolves_from_the_session(self):
        with patch("frappe.db.get_value", return_value="owner@promantia.com"):
            self.assertEqual(self._owner_email_sent_to_ar(owner_email=""), "owner@promantia.com")

    def test_a_string_that_is_neither_is_still_rejected(self):
        """Resolution must not become a licence to accept any string."""
        result = register_with_ar(owner_email="not-a-user", terms_version="1.0")
        self.assertFalse(result["success"])
        self.assertIn("valid owner email", result["error"].lower())
