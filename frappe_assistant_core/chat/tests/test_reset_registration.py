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

"""Reset is clear-only.

Re-registration needs a displayed Terms and Conditions version, which the Desk
form cannot supply — so reset drops credentials and hands off to SPA onboarding
rather than calling ``register_with_ar`` with arguments it cannot satisfy.
"""

import frappe

from frappe_assistant_core.chat.tenant_credentials import (
    read_tenant_secret,
    store_tenant_secret,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest

SECRET = "x" * 48


class TestResetRegistration(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        settings = frappe.get_single("FAC Chat Settings")
        settings.tenant_id = "tenant-under-test"
        settings.registration_status = "Registered"
        settings.save(ignore_permissions=True)
        store_tenant_secret(SECRET)

    def _reset(self) -> dict:
        from frappe_assistant_core.chat.api.settings.registration import reset_registration

        return reset_registration()

    def test_reset_reports_success(self):
        """The bug: reset re-registered without a terms_version and always failed."""
        self.assertTrue(self._reset()["success"])

    def test_reset_clears_tenant_id(self):
        self._reset()
        self.assertFalse(frappe.db.get_single_value("FAC Chat Settings", "tenant_id"))

    def test_reset_clears_the_encrypted_secret(self):
        self._reset()
        self.assertIsNone(read_tenant_secret(raise_exception=False))

    def test_reset_marks_the_site_not_registered(self):
        self._reset()
        self.assertEqual(
            frappe.db.get_single_value("FAC Chat Settings", "registration_status"),
            "Not Registered",
        )

    def test_reset_returns_the_cleared_tenant_id_for_the_audit_trail(self):
        self.assertEqual(self._reset()["previous_tenant_id"], "tenant-under-test")

    def test_reset_does_not_attempt_re_registration(self):
        """Reset must never reach AR — a cleared site has no credentials to sign with."""
        from unittest.mock import patch

        target = "frappe_assistant_core.chat.api.settings.registration.register_with_ar"
        with patch(target) as register:
            self._reset()
        register.assert_not_called()

    def test_admin_stats_alias_behaves_identically(self):
        """Both whitelisted paths are public API; they must not diverge again."""
        from frappe_assistant_core.chat.api.admin_stats import reset_registration as alias

        result = alias()
        self.assertTrue(result["success"])
        self.assertIsNone(read_tenant_secret(raise_exception=False))
        self.assertEqual(
            frappe.db.get_single_value("FAC Chat Settings", "registration_status"),
            "Not Registered",
        )

    def test_reset_is_refused_without_system_manager(self):
        """Frappe v15's only_for() returns early whenever flags.in_test is set,
        so the check it is guarding never runs under tests there. v16 dropped
        that bypass. enforce_only_for_checks clears the flag for the duration,
        which is what makes this assert the same boundary on both."""
        # nosemgrep: frappe-setuser — permission-boundary test, restored below
        frappe.set_user("Guest")
        try:
            with self.enforce_only_for_checks(), self.assertRaises(frappe.PermissionError):
                self._reset()
        finally:
            # nosemgrep: frappe-setuser — test teardown
            frappe.set_user("Administrator")
