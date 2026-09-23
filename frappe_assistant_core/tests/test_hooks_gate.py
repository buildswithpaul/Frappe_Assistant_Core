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

"""Tests for the FAC Chat runtime gate.

FAC Chat hooks are now registered unconditionally in hooks.py — there is no
boot-time gate. Each consumer (widget init, /copilot controller, dispatcher,
scheduler handlers) checks the gate at request time so toggling the chat
module on or off takes effect across all workers without `bench restart`.

These tests verify both halves of that contract:
  - The hooks themselves are always present (asset paths, SPA route, etc.)
  - The runtime gate (`chat.gate.is_chat_enabled`) flips with the DB setting
"""

import frappe

from frappe_assistant_core.chat.gate import clear_chat_gate_cache, is_chat_enabled
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestHooksGate(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # Each test starts with chat OFF; mid-test toggles assert both states.
        # IntegrationTestCase rolls back the DB at class teardown.
        frappe.db.set_single_value("Assistant Core Settings", "enable_fac_chat", 0)
        frappe.clear_cache()
        clear_chat_gate_cache()

    def test_chat_assets_always_registered(self):
        """Widget JS + CSS must be in hooks regardless of the chat gate.

        The widget JS itself checks `can_use_faco` at runtime and bails when
        chat is off — so the bundle being included on every Desk page is
        harmless, and it's what lets us toggle without a worker restart.
        """
        from frappe_assistant_core import hooks

        js_entries = list(getattr(hooks, "app_include_js", []) or [])
        css_entries = list(getattr(hooks, "app_include_css", []) or [])
        self.assertTrue(
            any("chat/widget" in entry for entry in js_entries),
            f"Chat widget JS must always be registered; got: {js_entries}",
        )
        self.assertTrue(
            any("chat/widget" in entry for entry in css_entries),
            f"Chat widget CSS must always be registered; got: {css_entries}",
        )

    def test_spa_route_always_registered(self):
        """`/copilot/<path>` must be in website_route_rules unconditionally.

        The controller (`www/copilot.py`) raises PageDoesNotExistError when
        the gate is off, so the route is inert but always present.
        """
        from frappe_assistant_core import hooks

        rules = getattr(hooks, "website_route_rules", []) or []
        self.assertTrue(
            any("copilot" in (r.get("from_route") or "") for r in rules),
            f"Copilot SPA route must always be registered; got: {rules}",
        )

    def test_runtime_gate_reflects_setting_off(self):
        frappe.db.set_single_value("Assistant Core Settings", "enable_fac_chat", 0)
        frappe.clear_cache()
        clear_chat_gate_cache()
        self.assertFalse(is_chat_enabled())

    def test_runtime_gate_reflects_setting_on(self):
        frappe.db.set_single_value("Assistant Core Settings", "enable_fac_chat", 1)
        frappe.clear_cache()
        clear_chat_gate_cache()
        self.assertTrue(is_chat_enabled())

    def test_runtime_gate_picks_up_toggle_without_restart(self):
        """Flipping the DB value mid-request takes effect once the per-request
        cache is cleared — no module reload, no worker restart."""
        frappe.db.set_single_value("Assistant Core Settings", "enable_fac_chat", 0)
        frappe.clear_cache()
        clear_chat_gate_cache()
        self.assertFalse(is_chat_enabled())

        frappe.db.set_single_value("Assistant Core Settings", "enable_fac_chat", 1)
        frappe.clear_cache()
        clear_chat_gate_cache()
        self.assertTrue(is_chat_enabled())

        frappe.db.set_single_value("Assistant Core Settings", "enable_fac_chat", 0)
        frappe.clear_cache()
        clear_chat_gate_cache()
        self.assertFalse(is_chat_enabled())
