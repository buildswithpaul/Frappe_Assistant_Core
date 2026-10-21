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

"""update_document never renames: it saves the other changes and says the rename was skipped."""

import frappe

from frappe_assistant_core.plugins.core.tools.update_document import DocumentUpdate
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestUpdateDocumentRename(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # Production reaches a stored record the same way: create_document inserts it.
        self.todo = frappe.get_doc({"doctype": "ToDo", "description": "FAC rename probe"}).insert()

    def _update(self, data: dict, **top_level) -> dict:
        return DocumentUpdate().execute(
            {"doctype": "ToDo", "name": self.todo.name, "data": data, **top_level}
        )

    def test_rename_in_data_is_skipped_and_other_changes_saved(self):
        result = self._update({"description": "FAC rename probe 2", "name": "renamed-todo"})

        self.assertTrue(result["success"], result)
        self.assertEqual(frappe.db.get_value("ToDo", self.todo.name, "description"), "FAC rename probe 2")
        self.assertFalse(frappe.db.exists("ToDo", "renamed-todo"))
        self.assertEqual(result["updated_fields"], ["description"])
        self.assertIn("Rename", result["warning"])
        self.assertIn("Desk", result["warning"])

    def test_new_name_key_is_skipped_too(self):
        result = self._update({"description": "FAC rename probe 3", "new_name": "renamed-todo"})

        self.assertTrue(result["success"], result)
        self.assertEqual(result["updated_fields"], ["description"])
        self.assertIn("Desk", result["warning"])

    def test_top_level_new_name_is_skipped(self):
        result = self._update({"description": "FAC rename probe 4"}, new_name="renamed-todo")

        self.assertTrue(result["success"], result)
        self.assertIn("Desk", result["warning"])

    def test_restating_the_same_name_is_not_a_rename(self):
        result = self._update({"description": "FAC rename probe 5", "name": self.todo.name})

        self.assertTrue(result["success"], result)
        self.assertNotIn("warning", result)

    def test_rename_only_update_is_refused_with_the_desk_alternative(self):
        result = self._update({"name": "renamed-todo"})

        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "rename_not_supported")
        self.assertIn("Rename", result["error"])
        self.assertIn("Desk", result["error"])
        self.assertTrue(frappe.db.exists("ToDo", self.todo.name))
