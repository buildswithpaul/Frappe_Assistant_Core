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

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from frappe_assistant_core.chat.home_preferences import HOME_SIGNALS_CACHE_KEY, clamp_needs_you_count


class FACChatUserPreferences(Document):
    """FAC Chat User Preferences - Per-user UI settings"""

    def validate(self):
        """Validate preferences"""
        self.validate_keyboard_shortcut()
        self.validate_home_preferences()

    def on_update(self):
        """Drop the cached home payload so the next load reflects any preference change."""
        frappe.cache.hdel(HOME_SIGNALS_CACHE_KEY, self.user)

    def validate_home_preferences(self):
        """Clamp the card count and keep ``hidden_home_signals`` a deduplicated list of known ids."""
        self.needs_you_count = clamp_needs_you_count(cint(self.needs_you_count))
        if not self.has_value_changed("hidden_home_signals"):
            return
        from frappe_assistant_core.chat.home_signals import hideable_signal_ids

        raw = self.hidden_home_signals
        try:
            hidden = json.loads(raw) if raw and raw.strip() else []
        except ValueError:
            hidden = None
        if not isinstance(hidden, list):
            frappe.throw(_("Hidden signals must be a list of signal ids."), frappe.ValidationError)
        known = hideable_signal_ids()
        for signal_id in hidden:
            if not isinstance(signal_id, str) or signal_id not in known:
                frappe.throw(_("Unknown home signal: {0}").format(signal_id), frappe.ValidationError)
        self.hidden_home_signals = json.dumps(list(dict.fromkeys(hidden)))

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
