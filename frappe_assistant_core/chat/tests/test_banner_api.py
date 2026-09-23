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

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestBannerAPI(BaseAssistantTest):
    """Discovery banner API: should_show_banner + dismiss_banner."""

    def setUp(self):
        super().setUp()
        # Clean baseline: chat disabled, no dismissal row for Administrator.
        # IntegrationTestCase rolls back all DB writes at class teardown.
        frappe.db.set_single_value("Assistant Core Settings", "enable_fac_chat", 0)
        frappe.db.delete("FAC Chat Banner Dismissal", {"user": "Administrator"})
        from frappe_assistant_core.chat.gate import clear_chat_gate_cache

        clear_chat_gate_cache()
        frappe.clear_cache()
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.db.delete("FAC Chat Banner Dismissal", {"user": "Administrator"})
        frappe.set_user("Administrator")
        super().tearDown()

    def test_eligible_admin_sees_banner_initially(self):
        from frappe_assistant_core.chat.api.discovery import should_show_banner

        self.assertTrue(should_show_banner())

    def test_chat_already_enabled_hides_banner(self):
        from frappe_assistant_core.chat.api.discovery import should_show_banner
        from frappe_assistant_core.chat.gate import clear_chat_gate_cache

        frappe.db.set_single_value("Assistant Core Settings", "enable_fac_chat", 1)
        frappe.clear_cache()
        clear_chat_gate_cache()
        self.assertFalse(should_show_banner())

    def test_dismiss_persists_and_hides_banner(self):
        from frappe_assistant_core.chat.api.discovery import dismiss_banner, should_show_banner

        # Pre-dismiss: banner visible
        self.assertTrue(should_show_banner())

        # Dismiss
        result = dismiss_banner()
        self.assertEqual(result.get("dismissed"), True)

        # Post-dismiss: banner hidden, even though chat is still disabled
        self.assertFalse(should_show_banner())

    def test_dismiss_is_idempotent(self):
        from frappe_assistant_core.chat.api.discovery import dismiss_banner

        first = dismiss_banner()
        self.assertEqual(first.get("dismissed"), True)

        # Second call must NOT raise UniqueValidationError; instead returns already_dismissed=True
        second = dismiss_banner()
        self.assertEqual(second.get("already_dismissed"), True)

    def test_non_admin_user_does_not_see_banner(self):
        from frappe_assistant_core.chat.api.discovery import should_show_banner

        # Create a non-System-Manager user with no Assistant Core Settings perm.
        if not frappe.db.exists("User", "test_non_admin@example.com"):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": "test_non_admin@example.com",
                    "first_name": "Non-admin",
                    "send_welcome_email": 0,
                    "roles": [{"role": "Guest"}],
                }
            ).insert(ignore_permissions=True)
        try:
            frappe.set_user("test_non_admin@example.com")
            self.assertFalse(should_show_banner())
        finally:
            frappe.set_user("Administrator")

    def test_dismiss_rejected_for_non_admin(self):
        from frappe_assistant_core.chat.api.discovery import dismiss_banner

        if not frappe.db.exists("User", "test_non_admin@example.com"):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": "test_non_admin@example.com",
                    "first_name": "Non-admin",
                    "send_welcome_email": 0,
                    "roles": [{"role": "Guest"}],
                }
            ).insert(ignore_permissions=True)
        try:
            frappe.set_user("test_non_admin@example.com")
            with self.assertRaises(frappe.PermissionError):
                dismiss_banner()
        finally:
            frappe.set_user("Administrator")
