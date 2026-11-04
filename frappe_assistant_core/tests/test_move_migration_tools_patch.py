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
Tests for the v3_2.move_migration_tools_to_their_plugin patch.

The 14 data migration tools left the core plugin for the migration plugin. A site that had them
keeps FAC Tool Configuration rows naming core, and the new plugin would come up switched off: the
patch moves the rows and switches the plugin on, leaves every other row alone, and runs twice.
"""

import importlib
import json

import frappe

from frappe_assistant_core.patches.v3_2 import move_migration_tools_to_their_plugin as patch
from frappe_assistant_core.plugins.core.plugin import CorePlugin
from frappe_assistant_core.plugins.migration.plugin import MigrationPlugin
from frappe_assistant_core.tests.base_test import BaseAssistantTest

DOCTYPE = "FAC Tool Configuration"
OTHER = "document_action"


class TestMoveMigrationToolsPatch(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # The class transaction rolls these rows back; the registry's Redis cache is not.
        self.addCleanup(self._clear_tool_caches)

    def _clear_tool_caches(self):
        for key in ("fac_tool_config_*", "fac_tool_configurations", "fac_tool_registry_*"):
            frappe.cache.delete_keys(key)

    def _as_before_the_move(self, name):
        """The row a site had while the tool was in core: the sync wrote it then, and never again."""
        old = {"plugin_name": "core", "module_path": f"frappe_assistant_core.plugins.core.tools.{name}.Old"}
        if frappe.db.exists(DOCTYPE, name):
            frappe.db.set_value(DOCTYPE, name, old, update_modified=False)
            return
        frappe.get_doc(
            {
                "doctype": DOCTYPE,
                "tool_name": name,
                "enabled": 1,
                "tool_category": "write",
                "auto_detected_category": "write",
                "category_override": 0,
                "role_access_mode": "Allow All",
                "source_app": "frappe_assistant_core",
                **old,
            }
        ).insert(ignore_permissions=True)

    def test_the_plugin_holds_the_14_tools_and_core_none_of_them(self):
        self.assertEqual(sorted(MigrationPlugin().get_tools()), sorted(patch.TOOLS))
        self.assertEqual(len(patch.TOOLS), 14)
        self.assertFalse(set(patch.TOOLS) & set(CorePlugin().get_tools()))

    def test_every_recorded_module_path_imports_its_tool(self):
        for tool, cls in patch.TOOLS.items():
            module_path, class_name = patch.MODULE.format(tool, cls).rsplit(".", 1)
            self.assertTrue(hasattr(importlib.import_module(module_path), class_name), tool)

    def test_moves_the_rows_to_the_migration_plugin_and_keeps_the_others(self):
        for name in (*patch.TOOLS, OTHER):
            self._as_before_the_move(name)
        other = frappe.db.get_value(DOCTYPE, OTHER, ["plugin_name", "module_path"], as_dict=True)

        patch.execute()

        for name, cls in patch.TOOLS.items():
            row = frappe.db.get_value(DOCTYPE, name, ["plugin_name", "module_path"], as_dict=True)
            self.assertEqual(row.plugin_name, "migration", name)
            self.assertEqual(row.module_path, patch.MODULE.format(name, cls), name)
        self.assertEqual(
            frappe.db.get_value(DOCTYPE, OTHER, ["plugin_name", "module_path"], as_dict=True), other
        )

    def test_switches_the_plugin_on_where_the_site_names_its_plugins(self):
        # A site that chose its plugins before migration existed: its list can't name it yet.
        if frappe.db.exists("FAC Plugin Configuration", "migration"):
            frappe.delete_doc("FAC Plugin Configuration", "migration", ignore_permissions=True, force=True)
        frappe.db.set_single_value(
            "Assistant Core Settings", "enabled_plugins_list", json.dumps(["core", "faco"])
        )

        patch.execute()

        self.assertEqual(frappe.db.get_value("FAC Plugin Configuration", "migration", "enabled"), 1)
        listed = json.loads(frappe.db.get_single_value("Assistant Core Settings", "enabled_plugins_list"))
        self.assertEqual(listed, ["core", "faco", "migration"])

    def test_leaves_an_empty_plugin_list_to_the_sync(self):
        # A fresh install has no list yet; the sync enables every plugin there.
        frappe.db.set_single_value("Assistant Core Settings", "enabled_plugins_list", "[]")

        patch.execute()

        self.assertEqual(frappe.db.get_single_value("Assistant Core Settings", "enabled_plugins_list"), "[]")

    def test_runs_twice(self):
        for name in patch.TOOLS:
            self._as_before_the_move(name)
        frappe.db.set_single_value("Assistant Core Settings", "enabled_plugins_list", json.dumps(["core"]))

        patch.execute()
        patch.execute()

        self.assertEqual(frappe.db.get_value(DOCTYPE, "start_import", "plugin_name"), "migration")
        listed = json.loads(frappe.db.get_single_value("Assistant Core Settings", "enabled_plugins_list"))
        self.assertEqual(listed, ["core", "migration"])
