# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""set_column_mapping marks the column that holds the old system's ID (#34244, K-1)."""

import frappe

from frappe_assistant_core.tests.test_import_mapping import ImportToolTestCase
from frappe_assistant_core.utils import import_keys
from frappe_assistant_core.utils.import_session import readable_session_file

# Odoo's contact export: its own id first, then the fields to import
ODOO_CSV = "id,First Name,Last Name,E-mail\n42,Ann,Lee,ann@example.com\n"
MAPPING = {"First Name": "first_name", "Last Name": "last_name", "E-mail": "email_ids.email_id"}


class TestSourceKeyColumn(ImportToolTestCase):
    def _session_of(self, session_id):
        return frappe.get_doc("FAC Import Session", session_id)

    def _odoo(self):
        return self._session(ODOO_CSV, "odoo-contacts.csv")

    def test_the_key_column_is_marked_with_its_system(self):
        session = self._odoo()

        result = self._map(session, MAPPING, doctype="Contact", source_key_column="id", source_system="Odoo")

        self.assertTrue(result["success"], result)
        self.assertEqual(import_keys.source_key(self._session_of(session)), {"position": 0, "system": "odoo"})
        self.assertEqual(result["old_ids"]["column"], "id")
        self.assertEqual(result["old_ids"]["system"], "odoo")

    def test_the_key_column_can_be_given_by_position(self):
        session = self._odoo()

        self._map(session, MAPPING, doctype="Contact", source_key_column="0", source_system="odoo")

        self.assertEqual(import_keys.source_key(self._session_of(session))["position"], 0)

    def test_the_key_column_is_not_imported_unless_it_is_mapped_too(self):
        session = self._odoo()

        result = self._map(session, MAPPING, doctype="Contact", source_key_column="id", source_system="odoo")

        self.assertEqual(self._stored_map(session)["0"], "Don't Import")
        self.assertNotIn("id", result["not_imported"])  # not a column FACO couldn't place
        self.assertEqual(result["unmapped_columns"], [])

    def test_a_key_column_mapped_to_a_field_is_imported_and_kept_as_the_key(self):
        session = self._odoo()

        mapping = {**MAPPING, "id": "first_name"}
        mapping.pop("First Name")
        result = self._map(session, mapping, doctype="Contact", source_key_column="id", source_system="odoo")

        self.assertTrue(result["success"], result)
        self.assertEqual(self._stored_map(session)["0"], "first_name")
        self.assertEqual(import_keys.source_key(self._session_of(session))["position"], 0)

    def test_the_system_is_needed(self):
        session = self._odoo()

        result = self._map(session, MAPPING, doctype="Contact", source_key_column="id")

        self.assertFalse(result["success"])
        self.assertTrue(any("source_system" in problem for problem in result["problems"]), result)
        self.assertIsNone(import_keys.source_key(self._session_of(session)))

    def test_a_column_that_is_not_in_the_file_is_refused(self):
        session = self._odoo()

        result = self._map(
            session, MAPPING, doctype="Contact", source_key_column="Nope", source_system="odoo"
        )

        self.assertFalse(result["success"])
        self.assertIsNone(import_keys.source_key(self._session_of(session)))
        self.assertEqual(self._stored_map(session), {})

    def test_the_system_is_kept_when_the_column_is_set_again(self):
        session = self._odoo()
        self._map(session, MAPPING, doctype="Contact", source_key_column="id", source_system="odoo")

        result = self._map(session, {"First Name": "first_name"}, source_key_column="id")

        self.assertTrue(result["success"], result)
        self.assertEqual(import_keys.source_key(self._session_of(session))["system"], "odoo")

    def test_the_key_can_be_set_without_remapping_anything(self):
        session = self._odoo()
        self._map(session, MAPPING, doctype="Contact")

        result = self._map(session, {}, source_key_column="id", source_system="odoo")

        self.assertTrue(result["success"], result)
        self.assertEqual(import_keys.source_key(self._session_of(session))["position"], 0)

    def test_the_key_column_changes_the_fingerprint(self):
        from frappe_assistant_core.utils import import_dry_run

        session = self._odoo()
        self._map(session, MAPPING, doctype="Contact")
        doc = self._session_of(session)
        file_doc = readable_session_file(doc)
        before = import_dry_run.fingerprint(doc, file_doc)

        self._map(session, {}, source_key_column="id", source_system="odoo")
        after = import_dry_run.fingerprint(self._session_of(session), file_doc)

        self.assertNotEqual(before, after)

    def test_another_target_drops_the_key_column(self):
        session = self._odoo()
        self._map(session, MAPPING, doctype="Contact", source_key_column="id", source_system="odoo")

        result = self._map(session, {"First Name": "address_title"}, doctype="Address")

        self.assertTrue(result["success"], result)
        self.assertIsNone(import_keys.source_key(self._session_of(session)))

    def test_the_fixes_keep_the_key_column(self):
        from frappe_assistant_core.utils import import_fixes

        session = self._odoo()
        self._map(session, MAPPING, doctype="Contact", source_key_column="id", source_system="odoo")
        doc = self._session_of(session)

        import_fixes.apply_fixes(doc, {}, [])

        self.assertEqual(import_keys.source_key(doc), {"position": 0, "system": "odoo"})
