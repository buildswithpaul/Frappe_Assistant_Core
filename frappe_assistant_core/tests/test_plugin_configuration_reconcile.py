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
Tests for reading plugin settings from FAC Plugin Configuration rows (#34662).

The rows were never read: `table_exists` adds the `tab` prefix itself, so the check that
guarded the read was always False and production read only the legacy
`Assistant Core Settings.enabled_plugins_list`. The patch makes the rows agree with that list,
which stays authoritative, so no site changes which plugins it has on.
"""

import json

import frappe

from frappe_assistant_core.patches.v3_4 import reconcile_plugin_configuration as patch
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.plugin_manager import PluginDiscovery, PluginPersistence

ROWS = "FAC Plugin Configuration"


class TestPluginConfigurationReconcile(BaseAssistantTest):
    def _legacy_list(self, plugins):
        # Production wrote this field through the settings form / save_enabled_plugins.
        frappe.db.set_single_value("Assistant Core Settings", "enabled_plugins_list", json.dumps(plugins))
        frappe.clear_document_cache("Assistant Core Settings")

    def _row(self, name, enabled):
        # The admin toggle inserts a row per plugin; save_plugin_state also commits, so it is
        # not called here and the row is inserted directly inside the test transaction.
        if frappe.db.exists(ROWS, name):
            frappe.db.set_value(ROWS, name, "enabled", enabled)
            return
        frappe.get_doc(
            {"doctype": ROWS, "plugin_name": name, "display_name": name.title(), "enabled": enabled}
        ).insert(ignore_permissions=True)

    def _no_rows(self):
        frappe.db.delete(ROWS)

    def _enabled_rows(self):
        return set(frappe.get_all(ROWS, filters={"enabled": 1}, pluck="plugin_name"))

    def test_table_exists_check_reads_rows(self):
        self._legacy_list(["core"])
        self._row("migration", 1)
        self.assertIn("migration", PluginPersistence().load_enabled_plugins())

    def test_reconcile_keeps_what_was_on(self):
        self._legacy_list(["core", "migration"])
        self._row("migration", 0)
        patch.execute()
        self.assertEqual(frappe.db.get_value(ROWS, "migration", "enabled"), 1)
        self.assertEqual(PluginPersistence().load_enabled_plugins(), {"core", "migration"})

    def test_reconcile_creates_missing_rows(self):
        self._legacy_list(["core", "faco"])
        self._no_rows()
        patch.execute()
        self.assertEqual(
            set(frappe.get_all(ROWS, pluck="plugin_name")), set(PluginDiscovery().discover_plugins())
        )
        self.assertEqual(self._enabled_rows(), {"core", "faco"})

    def test_reconcile_turns_off_what_the_list_omits(self):
        self._legacy_list(["core"])
        self._row("migration", 1)
        patch.execute()
        self.assertEqual(frappe.db.get_value(ROWS, "migration", "enabled"), 0)

    def test_reconcile_keeps_core_on_when_the_list_omits_it(self):
        self._legacy_list(["migration"])
        self._no_rows()
        patch.execute()
        self.assertEqual(self._enabled_rows(), {"core", "migration"})

    def test_reconcile_leaves_rows_alone_without_a_legacy_list(self):
        # A fresh install has no list; the after_migrate sync owns its rows.
        self._legacy_list([])
        self._row("migration", 1)
        patch.execute()
        self.assertEqual(frappe.db.get_value(ROWS, "migration", "enabled"), 1)

    def test_core_on_without_rows(self):
        self._legacy_list(["migration"])
        self._no_rows()
        self.assertIn("core", PluginPersistence().load_enabled_plugins())
