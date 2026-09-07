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


class TestFACChatSettingsDoctype(BaseAssistantTest):
    """The FACO Settings DocType is migrated as FAC Chat Settings."""

    def test_doctype_registered_with_renamed_name(self):
        meta = frappe.get_meta("FAC Chat Settings")
        self.assertEqual(meta.name, "FAC Chat Settings")

    def test_doctype_is_single(self):
        meta = frappe.get_meta("FAC Chat Settings")
        self.assertTrue(meta.issingle)

    def test_doctype_module_is_chat(self):
        meta = frappe.get_meta("FAC Chat Settings")
        self.assertEqual(meta.module, "Chat")

    def test_singleton_instance_loads(self):
        doc = frappe.get_single("FAC Chat Settings")
        self.assertIsNotNone(doc)

    def test_python_controller_class_renamed(self):
        from frappe_assistant_core.chat.doctype.fac_chat_settings.fac_chat_settings import (
            FACChatSettings,
        )

        # The controller class must be named FACChatSettings, not FACOSettings.
        self.assertEqual(FACChatSettings.__name__, "FACChatSettings")

    def test_old_faco_settings_name_not_used(self):
        """A safety check: the old FACO Settings DocType name must NOT resolve
        in a FAC-only environment. Skipped when frappe_assistant_copilot is
        installed on the same site (FACO registers its own DocType legitimately).
        """
        import frappe.utils

        if "frappe_assistant_copilot" in frappe.get_installed_apps():
            self.skipTest(
                "frappe_assistant_copilot is installed on this site; "
                "'FACO Settings' resolves legitimately — skipping safety check."
            )
        # frappe.get_meta() raises DoesNotExistError if the doctype is missing.
        with self.assertRaises(frappe.DoesNotExistError):
            frappe.get_meta("FACO Settings")
