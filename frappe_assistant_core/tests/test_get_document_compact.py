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

"""get_document sends only what a record holds (#35274)."""

import frappe

from frappe_assistant_core.plugins.core.tools.get_document import CHILD_ROW_BOOKKEEPING, DocumentGet
from frappe_assistant_core.tests.base_test import BaseAssistantTest


def _is_empty(value):
    return value is None or value == "" or value == [] or value == {}


class TestGetDocumentCompact(BaseAssistantTest):
    """Reads the Administrator user, which exists on every site and has empty fields and role rows."""

    def _read(self, **extra):
        result = DocumentGet().execute({"doctype": "User", "name": "Administrator", **extra})
        self.assertTrue(result.get("success"), result)
        return result["data"]

    def test_empty_values_are_left_out(self):
        full = frappe.get_doc("User", "Administrator").as_dict()
        self.assertTrue(any(_is_empty(v) for v in full.values()), "Administrator should have empty fields")

        data = self._read()

        self.assertFalse([k for k, v in data.items() if _is_empty(v)])

    def test_zeros_are_kept(self):
        full = frappe.get_doc("User", "Administrator").as_dict()
        zeros = [k for k, v in full.items() if v == 0 and not isinstance(v, bool)]
        self.assertTrue(zeros, "Administrator should have zero-valued fields")

        data = self._read()

        self.assertEqual([k for k in zeros if k not in data], [])

    def test_child_rows_drop_bookkeeping_but_keep_name_and_idx(self):
        roles = self._read()["roles"]

        self.assertTrue(roles)
        for row in roles:
            self.assertFalse(CHILD_ROW_BOOKKEEPING & set(row), row)
            self.assertIn("name", row)
            self.assertIn("idx", row)
            self.assertIn("role", row)

    def test_parent_keeps_its_own_bookkeeping(self):
        data = self._read()

        for field in ("owner", "creation", "modified", "docstatus"):
            self.assertIn(field, data)

    def test_fields_returns_only_those_fields_and_the_name(self):
        data = self._read(fields=["email", "roles"])

        self.assertEqual(set(data), {"name", "email", "roles"})
        self.assertTrue(data["roles"])

    def test_fields_never_reveal_more_than_a_full_read(self):
        # Projection runs after readable_doc_dict, so a Password field stays the masked placeholder
        full = self._read()

        data = self._read(fields=["email", "api_secret", "new_password"])

        for key, value in data.items():
            self.assertEqual(value, full.get(key), key)
        if "api_secret" in data:
            self.assertEqual(set(data["api_secret"]), {"*"})
