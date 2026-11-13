# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Where a session's old IDs are kept (#34244), through set_column_mapping: FAC's key map unless a
System Manager names a field (old_id_field), and never a question that holds the check."""

import unittest

import frappe

from frappe_assistant_core.tests.ddl_fixtures import committing_ddl
from frappe_assistant_core.tests.test_import_mapping import ImportToolTestCase
from frappe_assistant_core.utils import import_key_setup
from frappe_assistant_core.utils import import_keys as keys


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
class TestOldIdStorage(ImportToolTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.tag = frappe.generate_hash(length=6)
        self.system = f"odoo{self.tag}"  # a system of this test's own: the choice is kept as a default
        self.name_customers_by("Customer Name")
        frappe.defaults.clear_default(key=keys._SYSTEMS_KEY.format(doctype="Customer", fieldname="tax_id"))

    # -- helpers ---------------------------------------------------------------------------------

    def _ids(self, count=4):
        return [f"OD-{self.tag}-{i}" for i in range(count)]

    def _customer(self, tax_id=None):
        return frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": f"Acme {frappe.generate_hash(length=6)}",
                "customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
                "tax_id": tax_id,
            }
        ).insert()

    def _session_of_ids(self, ids, mark=True, system=None):
        """A customers file with an old ID column, uploaded and mapped as FACO does it. Returns the
        session and the mapping's result."""
        rows = "\n".join(f"{key},Cust {self.tag} {i}" for i, key in enumerate(ids))
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "odoo-customers.csv",
                "content": f"id,Customer Name\n{rows}\n".encode(),
                "is_private": 1,
            }
        ).insert()
        started = self._run("start_import_session", {"file_url": file_doc.file_url})
        self.assertTrue(started["success"], started)
        session = started["result"]["session_id"]
        arguments = {"doctype": "Customer"}
        if mark:
            arguments.update(source_key_column="id", source_system=system or self.system)
        return session, self._map(session, {"Customer Name": "customer_name"}, **arguments)

    def _keep_in(self, session, old_id_field):
        return self._map(session, {}, old_id_field=old_id_field)

    # -- the default: the key map, asked of nobody ---------------------------------------------------

    def test_marking_the_column_keeps_the_ids_in_the_key_map_without_a_question(self):
        session, result = self._session_of_ids(self._ids())

        self.assertTrue(result["success"], result)
        old_ids = result["old_ids"]
        self.assertEqual(
            (old_ids["column"], old_ids["system"], old_ids["kept_in"]), ("id", self.system, "key_map")
        )
        self.assertIn("key map", old_ids["message"])
        self.assertNotIn("?", old_ids["message"])  # said, not asked
        self.assertEqual(keys.storage_for("Customer", self.system), {"kind": "key_map"})
        self.assertEqual(keys.choice("Customer", self.system), "key_map")  # later files find the system

    def test_the_dry_run_is_not_held_for_an_answer(self):
        session, _result = self._session_of_ids(self._ids())

        response = self._run("dry_run_import", {"session": session})

        self.assertNotIn("where to keep", str(response))
        self.assertNotIn("old system's IDs", str(response.get("result", {}).get("error", "")))

    def test_a_file_without_an_old_id_column_has_no_old_ids(self):
        session, result = self._session_of_ids(self._ids(), mark=False)

        self.assertNotIn("old_ids", result)
        self.assertIsNone(keys.choice("Customer", self.system))

    def test_the_reply_uses_plain_words_not_internal_ones(self):
        # #34608: "refused_field" reached the model and the user
        _session, result = self._session_of_ids(self._ids())

        self.assertNotIn("refused", str(result["old_ids"]))

    # -- a field that already holds the IDs -----------------------------------------------------------

    def test_a_field_that_holds_the_ids_is_named_with_its_counts(self):
        ids = self._ids()
        for key in ids[:-1]:
            self._customer(tax_id=key)

        _session, result = self._session_of_ids(ids)

        best = result["old_ids"]["existing_fields"][0]
        self.assertEqual((best["fieldname"], best["matched"], best["total"]), ("tax_id", 3, 4))
        self.assertIn("3 of 4 match", result["old_ids"]["message"])
        self.assertEqual(result["old_ids"]["kept_in"], "key_map")  # named, not chosen for the user

    def test_a_system_manager_keeps_them_in_that_field(self):
        ids = self._ids()
        for key in ids:
            self._customer(tax_id=key)
        session, _result = self._session_of_ids(ids)

        result = self._keep_in(session, "tax_id")

        self.assertTrue(result["success"], result)
        self.assertEqual(result["old_ids"]["kept_in"], "tax_id")
        self.assertEqual(keys.storage_for("Customer", self.system), {"kind": "field", "fieldname": "tax_id"})
        steps = [s.step for s in frappe.get_doc("FAC Import Session", session).steps]
        self.assertIn("Old IDs", steps)

    def test_a_field_that_does_not_hold_the_ids_is_refused_and_nothing_changes(self):
        session, _result = self._session_of_ids(self._ids())

        result = self._keep_in(session, "website")

        self.assertFalse(result["success"], result)
        self.assertEqual(keys.storage_for("Customer", self.system), {"kind": "key_map"})

    def test_the_new_field_cannot_be_chosen_before_it_exists(self):
        session, _result = self._session_of_ids(self._ids())
        self.assertFalse(
            frappe.get_meta("Customer").has_field(keys.FIELD_NAME), "a leftover field on the site"
        )

        self.assertFalse(self._keep_in(session, keys.FIELD_NAME)["success"])

    def test_key_map_moves_them_back_from_a_field(self):
        ids = self._ids()
        for key in ids:
            self._customer(tax_id=key)
        session, _result = self._session_of_ids(ids)
        self._keep_in(session, "tax_id")

        result = self._keep_in(session, "key_map")

        self.assertTrue(result["success"], result)
        self.assertEqual(keys.storage_for("Customer", self.system), {"kind": "key_map"})

    def test_a_field_choice_is_kept_for_later_files_and_not_overwritten(self):
        ids = self._ids()
        for key in ids:
            self._customer(tax_id=key)
        self._keep_in(self._session_of_ids(ids)[0], "tax_id")

        _session, later = self._session_of_ids(self._ids())

        self.assertEqual(later["old_ids"]["kept_in"], "tax_id")
        self.assertEqual(keys.storage_for("Customer", self.system), {"kind": "field", "fieldname": "tax_id"})

    def test_old_id_field_needs_an_old_id_column(self):
        session, _result = self._session_of_ids(self._ids(), mark=False)

        result = self._keep_in(session, "tax_id")

        self.assertFalse(result["success"], result)
        self.assertIn("source_key_column", result["error"])

    # -- only a System Manager changes the site's setting --------------------------------------------

    def test_only_a_system_manager_can_choose_a_field(self):
        # The choice is one setting for every import on the site, and a field choice writes the IDs
        # into that field of each record: an importer without the role gets the key map.
        ids = self._ids()
        for key in ids:
            self._customer(tax_id=key)
        session, _result = self._session_of_ids(ids)
        doc = frappe.get_doc("FAC Import Session", session)
        frappe.set_user(self.make_desk_user("keys-importer"))

        with self.assertRaises(import_key_setup.StorageProblem) as refused:
            import_key_setup.use_field(doc, "tax_id")

        self.assertIn("System Manager", str(refused.exception))
        frappe.set_user("Administrator")
        self.assertEqual(keys.storage_for("Customer", self.system), {"kind": "key_map"})

    def test_matches_count_only_records_the_user_can_read(self):
        # A count over records the user can't see would tell them which IDs exist there.
        ids = self._ids()
        for key in ids:
            self._customer(tax_id=key)
        self.assertTrue(keys.find_fields("Customer", ids))
        frappe.set_user(self.make_desk_user("keys-reader"))  # no read on Customer

        self.assertEqual(keys.find_fields("Customer", ids), [])

    def test_a_user_who_cannot_change_the_session_cannot_choose(self):
        ids = self._ids()
        for key in ids:
            self._customer(tax_id=key)
        session, _result = self._session_of_ids(ids)
        frappe.set_user(self.make_desk_user("keys-other"))

        result = self._keep_in(session, "tax_id")

        self.assertFalse(result["success"], result)
        frappe.set_user("Administrator")
        self.assertEqual(keys.storage_for("Customer", self.system), {"kind": "key_map"})

    # -- the field FAC can add -------------------------------------------------------------------------

    def test_with_no_field_holding_them_the_record_to_add_one_is_given(self):
        _session, result = self._session_of_ids(self._ids())

        record = result["old_ids"]["new_field"]
        self.assertEqual(record["doctype"], "Custom Field")
        data = record["data"]
        self.assertEqual(
            {
                k: data[k]
                for k in ("dt", "fieldname", "label", "fieldtype", "read_only", "search_index", "no_copy")
            },
            {
                "dt": "Customer",
                "fieldname": "fac_old_system_id",
                "label": "Old System ID",
                "fieldtype": "Data",
                "read_only": 1,
                "search_index": 1,
                "no_copy": 1,
            },
        )

    def test_the_new_field_goes_at_the_end_of_the_forms_first_section(self):
        data = import_key_setup.field_record("Customer")["data"]

        fields = [df.fieldname for df in frappe.get_meta("Customer").fields if df.fieldname]
        after = fields.index(data["insert_after"])
        types = {df.fieldname: df.fieldtype for df in frappe.get_meta("Customer").fields}
        self.assertTrue(
            after == len(fields) - 1 or types[fields[after + 1]] in import_key_setup.SECTION_TYPES
        )

    # -- no separate tool -------------------------------------------------------------------------------

    def test_there_is_no_separate_storage_tool(self):
        self.assertIsNone(self.registry.get_tool("choose_old_id_storage"))
        self.assertIn("old_id_field", self.registry.get_tool("set_column_mapping").inputSchema["properties"])


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext")
class TestTheNewFieldIsMadeByCreateDocument(ImportToolTestCase):
    """The record the offer names is a valid create_document input on this version. It is made on
    Note, which nothing else here uses, and removed again: a schema change commits for real."""

    def test_the_offered_record_creates_the_field_and_it_can_hold_an_id(self):
        record = import_key_setup.field_record("Note")
        self.assertFalse(frappe.get_meta("Note").has_field(keys.FIELD_NAME), "a leftover field on the site")
        try:
            with committing_ddl():
                response = self._run("create_document", record)
            self.assertTrue(response["success"], response)
            frappe.clear_cache(doctype="Note")
            meta = frappe.get_meta("Note")
            df = meta.get_field(keys.FIELD_NAME)
            self.assertEqual((df.fieldtype, df.read_only, df.search_index, df.no_copy), ("Data", 1, 1, 1))
            self.assertTrue(frappe.db.has_column("Note", keys.FIELD_NAME))
        finally:
            with committing_ddl():
                name = frappe.db.get_value("Custom Field", {"dt": "Note", "fieldname": keys.FIELD_NAME})
                if name:
                    frappe.delete_doc("Custom Field", name, force=True)
                if frappe.db.has_column("Note", keys.FIELD_NAME):
                    frappe.db.sql_ddl(f"alter table `tabNote` drop column `{keys.FIELD_NAME}`")
            frappe.clear_cache(doctype="Note")
        self.assertFalse(frappe.get_meta("Note").has_field(keys.FIELD_NAME))
