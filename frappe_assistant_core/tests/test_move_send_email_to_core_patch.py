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
Tests for the patch that moves send_email's configuration to the core plugin.

The move hands a capability to sites that had switched it off. The faco plugin was
optional and disabling it took send_email away; the core plugin cannot be disabled,
so without this patch the upgrade would quietly let an assistant send mail from the
site's own Email Account on a site whose administrator had declined that.

The stored plugin matters too: `bulk_toggle_tools_by_category` filters FAC Tool
Configuration on `plugin_name`, so a row left saying "faco" is toggled by the wrong
bulk action in both directions.
"""

import json

import frappe

from frappe_assistant_core.patches.v3_1.move_send_email_to_core_plugin import execute
from frappe_assistant_core.tests.base_test import BaseAssistantTest

DOCTYPE = "FAC Tool Configuration"
PLUGIN_DOCTYPE = "FAC Plugin Configuration"
TOOL = "send_email"


class TestMoveSendEmailToCorePatch(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        if not frappe.db.table_exists(DOCTYPE):
            self.skipTest(f"{DOCTYPE} does not exist on this site")

    def _tool_row(self, enabled: int = 1, plugin_name: str = "faco") -> None:
        """The row after_migrate's sync writes for a discovered tool."""
        if frappe.db.exists(DOCTYPE, TOOL):
            frappe.db.set_value(
                DOCTYPE,
                TOOL,
                {"plugin_name": plugin_name, "enabled": enabled},
                update_modified=False,
            )
            return
        frappe.get_doc(
            {
                "doctype": DOCTYPE,
                "tool_name": TOOL,
                "plugin_name": plugin_name,
                "enabled": enabled,
            }
        ).insert(ignore_permissions=True)

    def _faco_plugin(self, enabled: int) -> None:
        """The row the plugin sync writes; an administrator toggles `enabled`."""
        if frappe.db.exists(PLUGIN_DOCTYPE, "faco"):
            frappe.db.set_value(PLUGIN_DOCTYPE, "faco", "enabled", enabled, update_modified=False)
            return
        frappe.get_doc({"doctype": PLUGIN_DOCTYPE, "plugin_name": "faco", "enabled": enabled}).insert(
            ignore_permissions=True
        )

    def _no_plugin_row(self) -> None:
        """A site whose plugin rows after_migrate has not written yet."""
        frappe.db.delete(PLUGIN_DOCTYPE, {"plugin_name": "faco"})

    def _legacy_plugins(self, plugins) -> None:
        """The pre-DocType record of plugin state, on Assistant Core Settings."""
        value = None if plugins is None else json.dumps(plugins)
        frappe.db.set_single_value("Assistant Core Settings", "enabled_plugins_list", value)

    def _row(self) -> dict:
        return frappe.db.get_value(DOCTYPE, TOOL, ["plugin_name", "enabled", "module_path"], as_dict=True)

    def test_the_stored_plugin_is_corrected(self):
        self._tool_row(enabled=1, plugin_name="faco")
        self._faco_plugin(enabled=1)

        execute()

        self.assertEqual(self._row().plugin_name, "core")

    def test_the_module_path_follows_the_file(self):
        self._tool_row()
        self._faco_plugin(enabled=1)

        execute()

        self.assertEqual(
            self._row().module_path,
            "frappe_assistant_core.plugins.core.tools.send_email.SendEmail",
        )

    def test_a_site_with_faco_enabled_keeps_the_tool_enabled(self):
        self._tool_row(enabled=1)
        self._faco_plugin(enabled=1)

        execute()

        self.assertTrue(self._row().enabled)

    def test_a_site_with_faco_disabled_does_not_gain_the_tool(self):
        """The privilege expansion this patch exists to prevent."""
        self._tool_row(enabled=1)
        self._faco_plugin(enabled=0)

        execute()

        self.assertFalse(self._row().enabled, "send_email became reachable on a site that had it off")

    def test_a_site_with_faco_disabled_still_gets_the_plugin_corrected(self):
        """Disabling the tool must not skip the rest of the fix."""
        self._tool_row(enabled=1)
        self._faco_plugin(enabled=0)

        execute()

        self.assertEqual(self._row().plugin_name, "core")

    def test_a_tool_already_switched_off_stays_off(self):
        self._tool_row(enabled=0)
        self._faco_plugin(enabled=1)

        execute()

        self.assertFalse(self._row().enabled)

    def test_no_plugin_row_and_no_legacy_state_counts_as_enabled(self):
        """Nothing recorded either way is a fresh install, which the sync enables."""
        self._tool_row(enabled=1)
        self._no_plugin_row()
        self._legacy_plugins(None)

        execute()

        self.assertTrue(self._row().enabled)

    def test_legacy_json_that_omits_faco_is_disabled(self):
        """The fail-open path. Patches run BEFORE the after_migrate step that writes
        plugin rows, so on a site upgrading from the legacy JSON era the row is absent
        and that field is the only record of the administrator's choice."""
        self._tool_row(enabled=1)
        self._no_plugin_row()
        self._legacy_plugins(["core", "visualization"])

        execute()

        self.assertFalse(self._row().enabled, "a site that had faco off in legacy JSON gained send_email")

    def test_legacy_json_that_includes_faco_stays_enabled(self):
        self._tool_row(enabled=1)
        self._no_plugin_row()
        self._legacy_plugins(["core", "faco"])

        execute()

        self.assertTrue(self._row().enabled)

    def test_an_empty_legacy_list_counts_as_enabled(self):
        """`not legacy_enabled` is how the sync reads this: a fresh install."""
        self._tool_row(enabled=1)
        self._no_plugin_row()
        self._legacy_plugins([])

        execute()

        self.assertTrue(self._row().enabled)

    def test_unreadable_legacy_json_keeps_the_tool_off(self):
        """Unable to tell: grant nothing. An admin can switch it on in FAC Admin."""
        self._tool_row(enabled=1)
        self._no_plugin_row()
        frappe.db.set_single_value("Assistant Core Settings", "enabled_plugins_list", "{not json")

        execute()

        self.assertFalse(self._row().enabled)

    def test_the_plugin_row_outranks_the_legacy_field(self):
        """Once the row exists it is authoritative, however stale the JSON is."""
        self._tool_row(enabled=1)
        self._faco_plugin(enabled=1)
        self._legacy_plugins(["core"])

        execute()

        self.assertTrue(self._row().enabled)

    def test_a_site_without_a_send_email_row_is_left_alone(self):
        frappe.db.delete(DOCTYPE, {"tool_name": TOOL})

        execute()

        self.assertFalse(frappe.db.exists(DOCTYPE, TOOL))

    def test_the_patch_is_registered(self):
        """An unregistered patch never runs, so the fix would not ship."""
        import pathlib

        patches = (pathlib.Path(frappe.get_app_path("frappe_assistant_core")) / "patches.txt").read_text()

        self.assertIn(
            "frappe_assistant_core.patches.v3_1.move_send_email_to_core_plugin",
            patches,
        )
