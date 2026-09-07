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


class TestFACChatMessageDoctype(BaseAssistantTest):
    """The FACO Message DocType is migrated as FAC Chat Message."""

    def test_doctype_registered_with_renamed_name(self):
        meta = frappe.get_meta("FAC Chat Message")
        self.assertEqual(meta.name, "FAC Chat Message")

    def test_doctype_is_not_single(self):
        meta = frappe.get_meta("FAC Chat Message")
        self.assertFalse(meta.issingle)

    def test_doctype_module_is_chat(self):
        meta = frappe.get_meta("FAC Chat Message")
        self.assertEqual(meta.module, "Chat")

    def test_doctype_autoname_preserved(self):
        meta = frappe.get_meta("FAC Chat Message")
        self.assertEqual(meta.autoname, "format:MSG-{YYYY}-{#####}")

    def test_python_controller_class_renamed(self):
        from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import (
            FACChatMessage,
        )

        # The controller class must be named FACChatMessage, not FACOMessage.
        self.assertEqual(FACChatMessage.__name__, "FACChatMessage")

    def test_old_faco_message_name_not_used(self):
        """Safety check: old FACO name must not resolve. Skips if FACO is installed."""
        if "frappe_assistant_copilot" in frappe.get_installed_apps():
            self.skipTest(
                "frappe_assistant_copilot is installed on this site; "
                "'FACO Message' resolves legitimately — skipping safety check."
            )
        with self.assertRaises(frappe.DoesNotExistError):
            frappe.get_meta("FACO Message")
