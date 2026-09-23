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

from unittest.mock import patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestFACChatUserPreferencesDoctype(BaseAssistantTest):
    """The FACO User Preferences DocType is migrated as FAC Chat User Preferences."""

    def test_doctype_registered_with_renamed_name(self):
        meta = frappe.get_meta("FAC Chat User Preferences")
        self.assertEqual(meta.name, "FAC Chat User Preferences")

    def test_doctype_is_not_single(self):
        meta = frappe.get_meta("FAC Chat User Preferences")
        self.assertFalse(meta.issingle)

    def test_doctype_module_is_chat(self):
        meta = frappe.get_meta("FAC Chat User Preferences")
        self.assertEqual(meta.module, "Chat")

    def test_doctype_autoname_preserved(self):
        meta = frappe.get_meta("FAC Chat User Preferences")
        self.assertEqual(meta.autoname, "field:user")

    def test_python_controller_class_renamed(self):
        from frappe_assistant_core.chat.doctype.fac_chat_user_preferences.fac_chat_user_preferences import (
            FACChatUserPreferences,
        )

        # The controller class must be named FACChatUserPreferences, not FACOUserPreferences.
        self.assertEqual(FACChatUserPreferences.__name__, "FACChatUserPreferences")

    def test_user_field_is_unique(self):
        """Autoname 'field:user' requires the user field to be unique."""
        meta = frappe.get_meta("FAC Chat User Preferences")
        user_field = meta.get_field("user")
        self.assertIsNotNone(user_field)
        self.assertTrue(user_field.unique, "user field must be unique for field:user autoname")

    def test_old_faco_user_preferences_name_not_used(self):
        """Safety check: old FACO name must not resolve. Skips if FACO is installed."""
        if "frappe_assistant_copilot" in frappe.get_installed_apps():
            self.skipTest(
                "frappe_assistant_copilot is installed on this site; "
                "'FACO User Preferences' resolves legitimately — skipping safety check."
            )
        with self.assertRaises(frappe.DoesNotExistError):
            frappe.get_meta("FACO User Preferences")

    def test_hide_widget_field_exists_with_default_zero(self):
        """hide_widget Check field exists with default 0 (visible by default)."""
        meta = frappe.get_meta("FAC Chat User Preferences")
        field = meta.get_field("hide_widget")
        self.assertIsNotNone(field, "hide_widget field must exist")
        self.assertEqual(field.fieldtype, "Check")
        # Frappe stores defaults as strings in metadata; compare against "0"
        self.assertEqual(field.default, "0")

    def test_hide_widget_in_preference_allowlist(self):
        """update_user_preference must accept hide_widget."""
        from frappe_assistant_core.chat.api.settings.widget import ALLOWED_PREFERENCE_FIELDS

        self.assertIn("hide_widget", ALLOWED_PREFERENCE_FIELDS)

    def test_hide_widget_round_trip_via_api(self):
        """POSTing hide_widget through the public API persists and reads back."""
        from frappe_assistant_core.chat.api.settings.widget import update_user_preference
        from frappe_assistant_core.chat.doctype.fac_chat_user_preferences.fac_chat_user_preferences import (
            FACChatUserPreferences,
        )

        frappe.set_user("Administrator")
        result = update_user_preference("hide_widget", "1")
        self.assertTrue(result.get("success"), msg=result)

        prefs = FACChatUserPreferences.get_or_create_preferences()
        self.assertEqual(int(prefs.hide_widget), 1)

        # Flip back to 0 and confirm
        result2 = update_user_preference("hide_widget", "0")
        self.assertTrue(result2.get("success"), msg=result2)
        prefs.reload()
        self.assertEqual(int(prefs.hide_widget), 0)

    def test_non_allowlisted_field_still_rejected(self):
        """Regression: the allowlist must still reject non-allowed fields."""
        from frappe_assistant_core.chat.api.settings.widget import update_user_preference

        frappe.set_user("Administrator")
        with self.assertRaises(frappe.ValidationError):
            update_user_preference("privacy_consent_complete", "1")

    def test_hide_widget_surfaced_in_access_preferences(self):
        """_build_access returns hide_widget under preferences."""
        from frappe_assistant_core.chat.api.init import _build_access
        from frappe_assistant_core.chat.doctype.fac_chat_user_preferences.fac_chat_user_preferences import (
            FACChatUserPreferences,
        )

        frappe.set_user("Administrator")
        # Force chat ON so _build_access returns the full payload (not early-return)
        frappe.db.set_single_value("Assistant Core Settings", "enable_fac_chat", 1)
        frappe.db.set_single_value("FAC Chat Settings", "registration_status", "Registered")
        frappe.db.set_single_value("FAC Chat Settings", "tenant_id", "test-tenant-id")
        frappe.db.set_single_value("FAC Chat Settings", "tenant_secret", "test-tenant-secret")
        from frappe_assistant_core.chat.gate import clear_chat_gate_cache

        clear_chat_gate_cache()

        # Set the pref
        prefs = FACChatUserPreferences.get_or_create_preferences()
        prefs.hide_widget = 1
        prefs.save(ignore_permissions=True)

        settings = frappe.get_single("FAC Chat Settings")
        # can_use_faco only reaches the preferences block for a FACO MEMBER —
        # an admin without a seat gets status=no_role and no preferences key.
        # Membership is an AR call, so it is stubbed rather than left to
        # whatever seat the running site happens to hold.
        with patch(
            "frappe_assistant_core.chat.api.settings.access._is_faco_member",
            return_value=True,
        ):
            access = _build_access(settings, "Administrator", ["System Manager"], is_admin=True)
        self.assertIn("preferences", access)
        self.assertEqual(int(access["preferences"]["hide_widget"]), 1)
