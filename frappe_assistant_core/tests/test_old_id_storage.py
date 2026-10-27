# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""choose_old_id_storage (#34244, K-2 to K-4): where a session's old IDs are kept, asked before the
dry run: a field that holds them, a new Old System ID field, or FAC's key map."""

import unittest

import frappe

from frappe_assistant_core.tests.ddl_fixtures import committing_ddl
from frappe_assistant_core.tests.test_import_mapping import ImportToolTestCase
from frappe_assistant_core.utils import import_key_setup
from frappe_assistant_core.utils import import_keys as keys
from frappe_assistant_core.utils.tool_category_detector import detect_tool_category


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
class TestChooseOldIdStorage(ImportToolTestCase):
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
        """A customers file with an old ID column, uploaded and mapped as FACO does it."""
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
        self._map(session, {"Customer Name": "customer_name"}, **arguments)
        return session

    def _choose(self, session, **arguments):
        return self._run("choose_old_id_storage", {"session": session, **arguments})

    # -- what to ask ---------------------------------------------------------------------------------

    def test_a_field_that_holds_the_ids_is_offered_with_its_counts(self):
        ids = self._ids()
        for key in ids[:-1]:
            self._customer(tax_id=key)
        session = self._session_of_ids(ids)

        result = self._choose(session)["result"]

        self.assertEqual(result["offer"], "existing_field")
        best = result["existing_fields"][0]
        self.assertEqual((best["fieldname"], best["matched"], best["total"]), ("tax_id", 3, 4))
        self.assertIn("3 of 4 match", result["question"])
        self.assertEqual(
            (result["doctype"], result["system"], result["column"]), ("Customer", self.system, "id")
        )

    def test_with_no_field_holding_them_a_new_field_is_offered_with_the_record_to_create(self):
        session = self._session_of_ids(self._ids())

        result = self._choose(session)["result"]

        self.assertEqual(result["offer"], "new_field")
        record = result["new_field"]
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
        self.assertIn("Old System ID", result["question"])
        self.assertIn("key map", result["question"])

    def test_the_new_field_goes_at_the_end_of_the_forms_first_section(self):
        data = import_key_setup.field_record("Customer")["data"]

        fields = [df.fieldname for df in frappe.get_meta("Customer").fields if df.fieldname]
        after = fields.index(data["insert_after"])
        types = {df.fieldname: df.fieldtype for df in frappe.get_meta("Customer").fields}
        self.assertTrue(
            after == len(fields) - 1 or types[fields[after + 1]] in import_key_setup.SECTION_TYPES
        )

    def test_a_session_with_no_old_id_column_has_nothing_to_choose(self):
        session = self._session_of_ids(self._ids(), mark=False)

        response = self._choose(session)

        self.assertFalse(response["success"], response)
        self.assertIn("source_key_column", response["error"])

    # -- the answer -------------------------------------------------------------------------------

    def test_using_a_field_that_holds_the_ids_records_it(self):
        ids = self._ids()
        for key in ids:
            self._customer(tax_id=key)
        session = self._session_of_ids(ids)

        response = self._choose(session, use="field", fieldname="tax_id")

        self.assertTrue(response["success"], response)
        self.assertEqual(keys.storage_for("Customer", self.system), {"kind": "field", "fieldname": "tax_id"})
        steps = [s.step for s in frappe.get_doc("FAC Import Session", session).steps]
        self.assertIn("Old IDs", steps)

    def test_a_field_that_does_not_hold_the_ids_is_refused(self):
        session = self._session_of_ids(self._ids())

        response = self._choose(session, use="field", fieldname="website")

        self.assertFalse(response["success"], response)
        self.assertIsNone(keys.storage_for("Customer", self.system))

    def test_the_new_field_cannot_be_chosen_before_it_exists(self):
        session = self._session_of_ids(self._ids())
        self.assertFalse(
            frappe.get_meta("Customer").has_field(keys.FIELD_NAME), "a leftover field on the site"
        )

        response = self._choose(session, use="field", fieldname=keys.FIELD_NAME)

        self.assertFalse(response["success"], response)

    def test_a_field_choice_needs_a_fieldname(self):
        session = self._session_of_ids(self._ids())

        self.assertFalse(self._choose(session, use="field")["success"])

    def test_refusing_a_field_keeps_the_ids_in_the_key_map(self):
        session = self._session_of_ids(self._ids())

        response = self._choose(session, use="key_map")

        self.assertTrue(response["success"], response)
        self.assertEqual(keys.storage_for("Customer", self.system), {"kind": "key_map"})
        self.assertIn("key map", response["result"]["message"])

    def test_the_answer_is_not_asked_again_in_a_later_session(self):
        self._choose(self._session_of_ids(self._ids()), use="key_map")

        result = self._choose(self._session_of_ids(self._ids()))["result"]

        self.assertIsNone(result["offer"])
        self.assertEqual(result["storage"], "refused_field")

    def test_another_source_system_is_asked_separately(self):
        self._choose(self._session_of_ids(self._ids()), use="key_map")

        result = self._choose(self._session_of_ids(self._ids(), system="zoho" + self.tag))["result"]

        self.assertEqual(result["offer"], "new_field")

    def test_an_unknown_use_is_refused(self):
        session = self._session_of_ids(self._ids())

        self.assertFalse(self._choose(session, use="somewhere")["success"])

    def test_a_user_who_cannot_change_the_session_cannot_choose(self):
        session = self._session_of_ids(self._ids())
        frappe.set_user(self.make_desk_user("keys-other"))

        response = self._choose(session, use="key_map")

        self.assertFalse(response["success"], response)
        self.assertIsNone(keys.storage_for("Customer", self.system))

    # -- the check waits for the answer -------------------------------------------------------------

    def test_the_dry_run_is_refused_until_the_answer_is_given(self):
        session = self._session_of_ids(self._ids())

        refused = self._run("dry_run_import", {"session": session})

        self.assertFalse(refused["success"], refused)
        self.assertIn("choose_old_id_storage", refused["error"])
        self._choose(session, use="key_map")
        allowed = self._run("dry_run_import", {"session": session})
        self.assertNotIn("choose_old_id_storage", str(allowed))

    def test_a_file_without_an_old_id_column_is_checked_as_before(self):
        session = self._session_of_ids(self._ids(), mark=False)

        response = self._run("dry_run_import", {"session": session})

        self.assertNotIn("choose_old_id_storage", str(response))

    # -- the tool -----------------------------------------------------------------------------------

    def test_the_tool_is_registered_and_writes_no_business_data(self):
        tool = self.registry.get_tool("choose_old_id_storage")

        self.assertIsNotNone(tool)
        self.assertEqual(detect_tool_category(tool), "read_only")


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
