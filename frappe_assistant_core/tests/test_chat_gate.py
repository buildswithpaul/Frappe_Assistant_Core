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

from frappe_assistant_core.chat.gate import clear_chat_gate_cache, is_chat_enabled
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestChatGate(BaseAssistantTest):
    def test_enable_fac_chat_default_false(self):
        # The field has no JSON default, so a fresh row defaults to 0/None.
        # We set explicitly to mirror the install-time state, then verify.
        frappe.db.set_single_value("Assistant Core Settings", "enable_fac_chat", 0)
        settings = frappe.get_single("Assistant Core Settings")
        self.assertFalse(bool(settings.enable_fac_chat))

    def test_enable_fac_chat_field_exists(self):
        meta = frappe.get_meta("Assistant Core Settings")
        self.assertIsNotNone(meta.get_field("enable_fac_chat"))


class TestChatGateHelper(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # Each test starts with chat OFF; IntegrationTestCase rolls back the
        # DB at class teardown so the dev DB is never permanently modified.
        frappe.db.set_single_value("Assistant Core Settings", "enable_fac_chat", 0)
        frappe.clear_cache()
        clear_chat_gate_cache()

    def test_is_chat_enabled_false_by_default(self):
        self.assertFalse(is_chat_enabled())

    def test_is_chat_enabled_true_when_set(self):
        frappe.db.set_single_value("Assistant Core Settings", "enable_fac_chat", 1)
        frappe.clear_cache()
        clear_chat_gate_cache()
        self.assertTrue(is_chat_enabled())

    def test_clear_chat_gate_cache_resets_state(self):
        # First call populates frappe.local cache with False.
        self.assertFalse(is_chat_enabled())
        # Flip the underlying value AND drop Frappe's db value_cache so only
        # frappe.local._fac_chat_enabled is acting as a cache.
        frappe.db.set_single_value("Assistant Core Settings", "enable_fac_chat", 1)
        frappe.clear_cache()
        # frappe.local cache should still report False (stale).
        self.assertFalse(is_chat_enabled(), "frappe.local cache must persist until explicitly cleared")
        # Now clear our cache and re-read; should observe the new value.
        clear_chat_gate_cache()
        self.assertTrue(is_chat_enabled())

    def test_is_chat_enabled_fail_safe_when_field_missing(self):
        # Mid-migration (upgrading from a FAC build that predates the
        # `enable_fac_chat` field) get_single_value raises ValidationError.
        # The gate must treat that as OFF, not propagate — otherwise the
        # wildcard doc_events dispatcher crashes every doc save during migrate.
        clear_chat_gate_cache()
        with patch.object(
            frappe.db,
            "get_single_value",
            side_effect=frappe.ValidationError("Field enable_fac_chat does not exist"),
        ):
            self.assertFalse(is_chat_enabled())

    def test_fail_safe_result_is_not_cached(self):
        # The transient OFF from a missing field must NOT be cached, so once the
        # migration adds the field the real value is read on the next call.
        clear_chat_gate_cache()
        with patch.object(
            frappe.db,
            "get_single_value",
            side_effect=frappe.ValidationError("Field enable_fac_chat does not exist"),
        ):
            self.assertFalse(is_chat_enabled())
        # Field "now exists" and is enabled — no manual cache clear needed.
        frappe.db.set_single_value("Assistant Core Settings", "enable_fac_chat", 1)
        frappe.clear_cache()
        self.assertTrue(
            is_chat_enabled(),
            "transient fail-safe False must not be cached past the missing-field window",
        )
