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

"""
FAC Chat User Preferences - Per-user UI settings.

Note: Quota management is handled by AR, not locally.
"""

import frappe
from frappe import _
from frappe.model.document import Document


class FACChatUserPreferences(Document):
    """FAC Chat User Preferences - Per-user UI settings"""

    def validate(self):
        """Validate preferences"""
        self.validate_keyboard_shortcut()

    def validate_keyboard_shortcut(self):
        """Ensure keyboard shortcut is valid format"""
        # Migrate Ctrl+K → Ctrl+Shift+K (conflicts with Frappe's search)
        if self.keyboard_shortcut == "Ctrl+K":
            self.keyboard_shortcut = "Ctrl+Shift+K"

        if self.enable_keyboard_shortcut and self.keyboard_shortcut:
            # Basic validation - should contain at least one modifier
            valid_modifiers = ["Ctrl", "Alt", "Shift", "Meta", "Cmd"]
            if not any(mod in self.keyboard_shortcut for mod in valid_modifiers):
                frappe.msgprint(_("Keyboard shortcut should include a modifier key (Ctrl, Alt, Shift, etc.)"))

    @staticmethod
    def get_or_create_preferences(user=None):
        """Get or create user preferences"""
        if not user:
            user = frappe.session.user

        # Check if preferences exist
        if frappe.db.exists("FAC Chat User Preferences", user):
            return frappe.get_doc("FAC Chat User Preferences", user)

        # Create new preferences (UI settings only)
        doc = frappe.get_doc({"doctype": "FAC Chat User Preferences", "user": user})
        doc.insert(ignore_permissions=True)
        return doc
