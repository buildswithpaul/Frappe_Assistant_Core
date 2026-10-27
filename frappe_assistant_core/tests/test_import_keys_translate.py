# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""A later file refers to records by the old system's IDs (#34244, K-6 to K-10): one rule translates
every row before the check, what isn't imported yet is its own group, and nothing is shown that the
user can't read.

The records referred to are Customer Groups (kept in the key map), which the customers file points
at with a Group ID column.
"""

import unittest

import frappe

from frappe_assistant_core.tests.test_import_mapping import ImportToolTestCase
from frappe_assistant_core.utils import import_fixes
from frappe_assistant_core.utils import import_keys as keys
from frappe_assistant_core.utils.import_session import read_sheet_rows, readable_session_file

MAPPING = {"Customer Name": "customer_name", "Group ID": "customer_group", "Customer Type": "customer_type"}
OLD_IDS = {"Group ID": {"doctype": "Customer Group", "source_system": None}}


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
class TestTranslateOldIds(ImportToolTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.tag = frappe.generate_hash(length=6)
        self.system = f"odoo{self.tag}"
        self.name_customers_by("Customer Name")
        # three groups imported "earlier", with the old ID of each kept in the key map
        self.groups = {}
        # the site's other choices for this DocType (other tests', or real ones) are out of the way here
        frappe.db.delete("DefaultValue", {"defkey": ["like", "fac_old_id::Customer Group::%"]})
        keys.set_choice("Customer Group", self.system, "key_map")
        for i in range(3):
            name = f"KG {self.tag} {i}"
            frappe.get_doc(
                {
                    "doctype": "Customer Group",
                    "customer_group_name": name,
                    "parent_customer_group": "All Customer Groups",
                    "is_group": 0,
                }
            ).insert()
            self.groups[f"G-{self.tag}-{i}"] = name
        keys.record_pairs("IMP-EARLIER", "Customer Group", self.system, list(self.groups.items()))

    def _customers_file(self, group_ids, system=None):
        """A customers file whose Group ID column holds old IDs; uploaded, read and mapped."""
        rows = "\n".join(f"Cust {self.tag} {i},{gid},Company" for i, gid in enumerate(group_ids))
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "customers.csv",
                "content": f"Customer Name,Group ID,Customer Type\n{rows}\n".encode(),
                "is_private": 1,
            }
        ).insert()
        started = self._run("start_import_session", {"file_url": file_doc.file_url})
        self.assertTrue(started["success"], started)
        return started["result"]["session_id"]

    def _map_with_translation(self, session, **arguments):
        old_ids = {"Group ID": {"doctype": "Customer Group", "source_system": self.system}}
        return self._map(session, MAPPING, doctype="Customer", old_id_columns=old_ids, **arguments)

    def _doc(self, session):
        return frappe.get_doc("FAC Import Session", session)

    def _rows(self, session):
        doc = self._doc(session)
        return read_sheet_rows(readable_session_file(doc), doc.sheet or None)

    # -- suggesting and setting it -------------------------------------------------------------

    def test_a_column_of_old_ids_is_suggested_when_the_ids_resolve(self):
        session = self._customers_file(self.groups)

        result = self._map(session, MAPPING, doctype="Customer")

        self.assertTrue(result["success"], result)
        (suggestion,) = result["old_id_suggestions"]
        self.assertEqual(
            (suggestion["column"], suggestion["doctype"], suggestion["system"]),
            ("Group ID", "Customer Group", self.system),
        )
        self.assertEqual((suggestion["resolved"], suggestion["total"]), (3, 3))

    def test_a_column_of_plain_names_is_not_suggested(self):
        session = self._customers_file(self.groups.values())

        result = self._map(session, MAPPING, doctype="Customer")

        self.assertNotIn("old_id_suggestions", result)

    def test_the_rule_is_saved_with_the_system_and_reported(self):
        session = self._customers_file(self.groups)

        result = self._map_with_translation(session)

        self.assertTrue(result["success"], result)
        self.assertEqual(
            keys.key_maps(self._doc(session)), {1: {"doctype": "Customer Group", "system": self.system}}
        )
        self.assertEqual(
            result["old_id_columns"], {"Group ID": {"doctype": "Customer Group", "system": self.system}}
        )
        self.assertNotIn("old_id_suggestions", result)

    def test_the_system_can_be_left_out_when_the_site_keeps_one(self):
        session = self._customers_file(self.groups)

        result = self._map(
            session, MAPPING, doctype="Customer", old_id_columns={"Group ID": {"doctype": "Customer Group"}}
        )

        self.assertTrue(result["success"], result)
        self.assertEqual(keys.key_maps(self._doc(session))[1]["system"], self.system)

    def test_with_two_systems_the_user_is_asked_which(self):
        keys.set_choice("Customer Group", "zoho" + self.tag, "key_map")
        session = self._customers_file(self.groups)

        result = self._map(
            session, MAPPING, doctype="Customer", old_id_columns={"Group ID": {"doctype": "Customer Group"}}
        )

        self.assertFalse(result["success"], result)
        self.assertTrue(any("source_system" in p for p in result["problems"]), result)
        self.assertEqual(keys.key_maps(self._doc(session)), {})

    def test_a_system_with_no_kept_ids_is_refused(self):
        session = self._customers_file(self.groups)

        result = self._map(
            session,
            MAPPING,
            doctype="Customer",
            old_id_columns={"Group ID": {"doctype": "Customer Group", "source_system": "nowhere" + self.tag}},
        )

        self.assertFalse(result["success"], result)

    def test_a_column_that_does_not_link_to_that_doctype_is_refused(self):
        session = self._customers_file(self.groups)

        result = self._map(
            session,
            MAPPING,
            doctype="Customer",
            old_id_columns={"Customer Name": {"doctype": "Customer Group", "source_system": self.system}},
        )

        self.assertFalse(result["success"], result)
        self.assertTrue(any("links to" in p for p in result["problems"]), result)

    def test_remapping_the_column_to_another_field_drops_the_rule(self):
        session = self._customers_file(self.groups)
        self._map_with_translation(session)

        self._map(session, {"Group ID": "customer_type", "Customer Type": "Don't Import"})

        self.assertEqual(keys.key_maps(self._doc(session)), {})

    def test_the_rule_survives_other_corrections(self):
        session = self._customers_file(self.groups)
        self._map_with_translation(session)

        self._map(session, {"Customer Type": "customer_type"})

        self.assertIn(1, keys.key_maps(self._doc(session)))

    # -- translating ---------------------------------------------------------------------------------

    def test_every_row_is_translated_to_the_records_name(self):
        session = self._customers_file(self.groups)
        self._map_with_translation(session)

        rows = import_fixes.apply_value_maps(self._doc(session), self._rows(session))

        self.assertEqual([row[1] for row in rows[1:]], list(self.groups.values()))
        self.assertEqual(self._rows(session)[1][1], f"G-{self.tag}-0")  # the file itself is not changed

    def test_the_dry_run_is_ready_after_the_translation(self):
        session = self._customers_file(self.groups)
        self._map_with_translation(session)
        keys.set_choice("Customer", self.system, "key_map")

        checked = self._run("dry_run_import", {"session": session})["result"]

        self.assertEqual(checked["status"], "Ready to Import", checked)
        self.assertEqual(checked["ready"], 3)

    def test_ids_not_imported_yet_are_their_own_group_with_the_fixes(self):
        session = self._customers_file(
            [*self.groups, f"G-{self.tag}-9", f"G-{self.tag}-9", f"G-{self.tag}-8"]
        )
        self._map_with_translation(session)

        checked = self._run("dry_run_import", {"session": session})["result"]

        by_value = {g["value"]: g for g in checked["groups"] if g.get("value")}
        self.assertEqual(set(by_value), {f"G-{self.tag}-9", f"G-{self.tag}-8"})
        group = by_value[f"G-{self.tag}-9"]
        self.assertEqual(group["count"], 2)
        self.assertIn("isn't imported yet", group["message"])
        self.assertEqual(checked["ready"], 3)

    def test_an_unknown_id_can_be_mapped_to_an_existing_record_or_left_out(self):
        unknown = f"G-{self.tag}-9"
        session = self._customers_file([*self.groups, unknown])
        self._map_with_translation(session)
        checked = self._run("dry_run_import", {"session": session})["result"]
        group = next(g["id"] for g in checked["groups"] if g.get("value") == unknown)
        existing = next(iter(self.groups.values()))

        fixed = self._run(
            "dry_run_import",
            {"session": session, "fixes": [{"group": group, "action": "map", "to": existing}]},
        )["result"]

        self.assertEqual(fixed["status"], "Ready to Import", fixed)
        self.assertEqual(fixed["ready"], 4)

    def test_a_later_session_resolves_the_same_ids(self):
        first = self._customers_file(self.groups)
        self._map_with_translation(first)
        second = self._customers_file(self.groups)

        self._map_with_translation(second)

        rows = import_fixes.apply_value_maps(self._doc(second), self._rows(second))
        self.assertEqual([row[1] for row in rows[1:]], list(self.groups.values()))

    def test_a_record_the_user_cannot_read_stays_an_untranslated_id(self):
        session = self._customers_file(self.groups)
        self._map_with_translation(session)
        rows = self._rows(session)
        user = self.make_desk_user("keys-nobody")
        self.assert_cannot(user, "read", "Customer Group", next(iter(self.groups.values())))
        frappe.set_user(user)

        translated = import_fixes.apply_value_maps(self._doc(session), rows)

        frappe.set_user("Administrator")
        self.assertEqual(
            [row[1] for row in translated[1:]], list(self.groups)
        )  # unchanged, and nothing leaked

    # -- repeated keys ------------------------------------------------------------------------------

    def test_a_repeated_key_in_the_file_is_reported_when_it_is_marked(self):
        rows = "\n".join(f"{key},Cust {self.tag} {i}" for i, key in enumerate(["K1", "K2", "K1"]))
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "x.csv",
                "content": f"id,Customer Name\n{rows}\n".encode(),
                "is_private": 1,
            }
        ).insert()
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]

        result = self._map(
            session,
            {"Customer Name": "customer_name"},
            doctype="Customer",
            source_key_column="id",
            source_system=self.system,
        )

        self.assertEqual(result["old_ids"]["duplicates"], [{"key": "K1", "rows": [2, 4]}])


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext")
class TestLinkTargets(ImportToolTestCase):
    def test_a_field_of_the_record_and_a_field_of_a_child_table_link_to_their_doctypes(self):
        mapped = {
            "0": "item_code",
            "1": "item_group",
            "2": "customer_items.customer_name",
            "3": "Don't Import",
        }

        self.assertEqual(keys.link_targets("Item", mapped), {1: "Item Group", 2: "Customer"})

    def test_a_field_that_is_not_a_link_is_left_out(self):
        self.assertEqual(
            keys.link_targets("Customer", {"0": "customer_name", "1": "customer_group"}),
            {1: "Customer Group"},
        )

    def test_an_unknown_table_is_left_out(self):
        self.assertEqual(keys.link_targets("Item", {"0": "nope.customer_name"}), {})
