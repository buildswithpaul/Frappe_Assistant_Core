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


class TestFACChatTab(BaseAssistantTest):
    """The FAC Chat configuration UI uses a dedicated tab with an explainer."""

    def test_fac_chat_tab_break_exists(self):
        meta = frappe.get_meta("Assistant Core Settings")
        field = meta.get_field("fac_chat_tab")
        self.assertIsNotNone(field, "fac_chat_tab field must exist")
        self.assertEqual(field.fieldtype, "Tab Break")
        self.assertEqual(field.label, "FAC Chat")

    def test_fac_chat_description_html_exists_before_toggle(self):
        meta = frappe.get_meta("Assistant Core Settings")
        desc = meta.get_field("fac_chat_description")
        self.assertIsNotNone(desc, "fac_chat_description field must exist")
        self.assertEqual(desc.fieldtype, "HTML")

        # HTML descriptor must appear AFTER the tab break and BEFORE the toggle.
        order = meta.get("field_order") or [f.fieldname for f in meta.fields]
        tab_idx = order.index("fac_chat_tab")
        desc_idx = order.index("fac_chat_description")
        toggle_idx = order.index("enable_fac_chat")
        self.assertLess(tab_idx, desc_idx, "fac_chat_tab must come before fac_chat_description")
        self.assertLess(desc_idx, toggle_idx, "fac_chat_description must come before enable_fac_chat")

    def test_old_section_break_removed(self):
        meta = frappe.get_meta("Assistant Core Settings")
        # The old fac_chat_section Section Break must no longer exist (we renamed it).
        self.assertIsNone(meta.get_field("fac_chat_section"))
