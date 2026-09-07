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

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestBannerDismissalDoctype(BaseAssistantTest):
    """The FAC Chat Banner Dismissal DocType records per-user banner dismissals."""

    def setUp(self):
        super().setUp()
        # Clear any leftover rows for the test user so tests start clean.
        frappe.db.delete("FAC Chat Banner Dismissal", {"user": "Administrator"})

    def tearDown(self):
        frappe.db.delete("FAC Chat Banner Dismissal", {"user": "Administrator"})
        super().tearDown()

    def test_doctype_exists(self):
        meta = frappe.get_meta("FAC Chat Banner Dismissal")
        self.assertEqual(meta.name, "FAC Chat Banner Dismissal")
        self.assertEqual(meta.module, "Chat")

    def test_autoname_uses_user_field(self):
        meta = frappe.get_meta("FAC Chat Banner Dismissal")
        self.assertEqual(meta.autoname, "field:user")

    def test_user_field_is_link_to_user_and_unique(self):
        meta = frappe.get_meta("FAC Chat Banner Dismissal")
        user_field = meta.get_field("user")
        self.assertIsNotNone(user_field, "user field must exist")
        self.assertEqual(user_field.fieldtype, "Link")
        self.assertEqual(user_field.options, "User")
        self.assertTrue(user_field.reqd, "user field must be required")
        self.assertTrue(user_field.unique, "user field must be unique for field:user autoname")

    def test_dismissed_on_field_is_datetime_with_now_default(self):
        meta = frappe.get_meta("FAC Chat Banner Dismissal")
        field = meta.get_field("dismissed_on")
        self.assertIsNotNone(field, "dismissed_on field must exist")
        self.assertEqual(field.fieldtype, "Datetime")

    def test_insert_one_row_per_user_succeeds(self):
        doc = frappe.get_doc({"doctype": "FAC Chat Banner Dismissal", "user": "Administrator"}).insert(
            ignore_permissions=True
        )
        self.assertEqual(doc.user, "Administrator")
        self.assertEqual(doc.name, "Administrator")  # autoname field:user → name == user value
        self.assertIsNotNone(doc.dismissed_on)

    def test_inserting_twice_for_same_user_violates_uniqueness(self):
        frappe.get_doc({"doctype": "FAC Chat Banner Dismissal", "user": "Administrator"}).insert(
            ignore_permissions=True
        )
        # Frappe raises UniqueValidationError (field-level) or DuplicateEntryError (DB-level) for duplicate inserts.
        with self.assertRaises(
            (frappe.exceptions.UniqueValidationError, frappe.exceptions.DuplicateEntryError)
        ):
            frappe.get_doc({"doctype": "FAC Chat Banner Dismissal", "user": "Administrator"}).insert(
                ignore_permissions=True
            )
