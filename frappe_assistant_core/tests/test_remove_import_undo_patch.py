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
Tests for the v3_2.remove_import_undo_tool_configurations patch (#34002).

The undo tools were removed, so their FAC Tool Configuration rows go, and the patch must
leave every other row alone and be safe to run twice.
"""

import frappe

from frappe_assistant_core.patches.v3_2 import remove_import_undo_tool_configurations as patch
from frappe_assistant_core.tests.base_test import BaseAssistantTest

DOCTYPE = "FAC Tool Configuration"
OTHER = "document_action"


class TestRemoveImportUndoToolConfigurationsPatch(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # The class transaction rolls these rows back; the registry's Redis cache is not.
        self.addCleanup(self._clear_tool_caches)

    def _clear_tool_caches(self):
        for key in ("fac_tool_config_*", "fac_tool_configurations", "fac_tool_registry_*"):
            frappe.cache.delete_keys(key)

    def _make_row(self, name):
        if frappe.db.exists(DOCTYPE, name):
            return
        frappe.get_doc(
            {
                "doctype": DOCTYPE,
                "tool_name": name,
                "plugin_name": "core",
                "enabled": 1,
                "tool_category": "write",
                "auto_detected_category": "write",
                "category_override": 0,
                "role_access_mode": "Allow All",
                "source_app": "frappe_assistant_core",
                "module_path": f"frappe_assistant_core.plugins.core.tools.{name}.Gone",
            }
        ).insert(ignore_permissions=True)

    def test_deletes_the_two_rows_and_keeps_the_others(self):
        for name in (*patch.TOOLS, OTHER):
            self._make_row(name)

        patch.execute()

        for name in patch.TOOLS:
            self.assertFalse(frappe.db.exists(DOCTYPE, name), name)
        self.assertTrue(frappe.db.exists(DOCTYPE, OTHER))

    def test_runs_twice_and_on_a_site_without_the_rows(self):
        for name in patch.TOOLS:
            self._make_row(name)

        patch.execute()
        patch.execute()

        for name in patch.TOOLS:
            self.assertFalse(frappe.db.exists(DOCTYPE, name), name)
