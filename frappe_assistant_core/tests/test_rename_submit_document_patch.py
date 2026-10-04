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
Tests for the v3_1.rename_submit_document_to_document_action patch.

The tool was renamed, and FAC Tool Configuration rows are named after their tool, so
without the patch the next migrate's _sync_tool_configurations would replace a site's
settings for it with defaults. The patch must carry every setting over, or do nothing.
"""

import frappe
from frappe.utils import get_datetime

from frappe_assistant_core.patches.v3_1 import rename_submit_document_to_document_action as patch
from frappe_assistant_core.tests.base_test import BaseAssistantTest

DOCTYPE = "FAC Tool Configuration"
OLD_MODULE_PATH = "frappe_assistant_core.plugins.core.tools.submit_document.DocumentSubmit"
ROLE_ROWS = [
    {"role": "Accounts User", "allow_access": 1},
    {"role": "Report Manager", "allow_access": 1},
]


class TestRenameSubmitDocumentPatch(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # Each test starts with neither row; the class transaction rolls all of this back.
        for name in (patch.OLD_NAME, patch.NEW_NAME):
            if frappe.db.exists(DOCTYPE, name):
                frappe.delete_doc(DOCTYPE, name, force=True, ignore_permissions=True)
        # The tool registry caches configurations in Redis, which the rollback doesn't undo.
        self.addCleanup(self._clear_tool_caches)

    def _clear_tool_caches(self):
        for key in ("fac_tool_config_*", "fac_tool_configurations", "fac_tool_registry_*"):
            frappe.cache.delete_keys(key)

    def make_row(self, name=patch.OLD_NAME, roles=False, **values):
        if roles:
            # Copies: Frappe adds a "doctype" key to the child-row dicts it is given.
            values.update(
                role_access_mode="Restrict to Listed Roles", role_access=[dict(r) for r in ROLE_ROWS]
            )
        doc = frappe.get_doc(
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
                "module_path": OLD_MODULE_PATH,
                **values,
            }
        )
        doc.insert(ignore_permissions=True)
        return doc

    def row(self, name=patch.NEW_NAME):
        return frappe.db.get_value(DOCTYPE, name, "*", as_dict=True)

    def role_rows(self, parent):
        return frappe.get_all(
            "FAC Tool Role Access",
            filters={"parent": parent, "parenttype": DOCTYPE},
            fields=["role", "allow_access"],
            order_by="role",
        )

    def test_keeps_settings_and_role_rows(self):
        old = self.make_row(enabled=0, roles=True)

        patch.execute()

        self.assertFalse(frappe.db.exists(DOCTYPE, patch.OLD_NAME))
        new = self.row()
        self.assertEqual(
            get_datetime(new.creation), get_datetime(old.creation), "the row must be renamed, not recreated"
        )
        self.assertEqual(new.tool_name, patch.NEW_NAME)
        self.assertEqual(new.enabled, 0)
        self.assertEqual(new.role_access_mode, "Restrict to Listed Roles")
        self.assertEqual(new.module_path, patch.NEW_MODULE_PATH)
        self.assertEqual(self.role_rows(patch.NEW_NAME), ROLE_ROWS)
        self.assertEqual(self.role_rows(patch.OLD_NAME), [])

    def test_recategorizes_without_an_override(self):
        self.make_row()

        patch.execute()

        new = self.row()
        self.assertEqual(new.category_override, 0)
        self.assertEqual(new.tool_category, "privileged")
        self.assertEqual(new.auto_detected_category, "privileged")

    def test_keeps_an_admin_category_override(self):
        self.make_row(category_override=1, tool_category="read_write")

        patch.execute()

        new = self.row()
        self.assertEqual(new.category_override, 1)
        self.assertEqual(new.tool_category, "read_write")
        self.assertEqual(new.module_path, patch.NEW_MODULE_PATH)

    def test_fresh_site_is_skipped(self):
        patch.execute()

        self.assertFalse(frappe.db.exists(DOCTYPE, patch.OLD_NAME))
        self.assertFalse(frappe.db.exists(DOCTYPE, patch.NEW_NAME))

    def test_old_settings_win_over_an_early_default_row(self):
        old = self.make_row(enabled=0, roles=True)
        self.make_row(name=patch.NEW_NAME)

        patch.execute()

        new = self.row()
        self.assertEqual(get_datetime(new.creation), get_datetime(old.creation))
        self.assertEqual(new.enabled, 0)
        self.assertEqual(self.role_rows(patch.NEW_NAME), ROLE_ROWS)

    def test_the_after_migrate_sync_keeps_the_renamed_row(self):
        """Patches run before after_migrate; once renamed, the sync must leave the row alone."""
        from frappe_assistant_core.utils.migration_hooks import _sync_tool_configurations

        old = self.make_row(enabled=0, roles=True)

        patch.execute()
        _sync_tool_configurations()

        new = self.row()
        self.assertEqual(get_datetime(new.creation), get_datetime(old.creation))
        self.assertEqual(new.enabled, 0)
        self.assertEqual(self.role_rows(patch.NEW_NAME), ROLE_ROWS)
