# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""An import keeps the old ID of every record it creates (#34244, K-5): in the field, or the key map."""

import unittest

import frappe

from frappe_assistant_core.tests.test_import_run import MAPPING, ImportRunCase
from frappe_assistant_core.utils import import_keys as keys
from frappe_assistant_core.utils import import_run

KEY_MAP = "FAC Import Key Map"


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
class TestImportKeepsOldIds(ImportRunCase):
    def setUp(self):
        super().setUp()
        self.name_customers_by("Customer Name")
        self.system = f"odoo{self.tag}"
        frappe.defaults.clear_default(key=keys._SYSTEMS_KEY.format(doctype="Customer", fieldname="tax_id"))
        self.ids = {key: f"OD-{self.tag}-{i}" for i, key in enumerate(("alpha", "beta", "gamma", "delta"))}

    def _keyed_session(self, storage, left_out=("beta",)):
        """A customers file with an Odoo id column, mapped, its storage chosen, checked, ready."""
        n = self._names()
        lines = ["id," + ",".join(MAPPING)]
        for key in ("alpha", "beta", "gamma", "delta"):
            lines.append(f"{self.ids[key]},{n[key]},{self.group},Company")
        file_doc = self._file("odoo-customers.csv", ("\n".join(lines) + "\n").encode())
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]
        mapped = self._run(
            "set_column_mapping",
            {
                "session": session,
                "mapping": MAPPING,
                "doctype": "Customer",
                "source_key_column": "id",
                "source_system": self.system,
            },
        )
        self.assertTrue(mapped["success"], mapped)
        keys.set_choice("Customer", self.system, storage)
        checked = self._run("dry_run_import", {"session": session})["result"]
        if left_out:
            groups = {g["value"]: g["id"] for g in checked.get("groups", []) if g.get("value")}
            self.assertFalse(groups, "the file was meant to be clean")
        return session, checked

    def _record_of(self, key):
        return keys.resolve("Customer", self.system, [self.ids[key]])[self.ids[key]]

    def _import_all(self, session, checked):
        response = self._import(session, checked)
        self.assertTrue(response["success"], response)
        return response["result"]

    # -- the field ------------------------------------------------------------------------------

    def test_each_created_customer_gets_its_old_id_in_the_field(self):
        session, checked = self._keyed_session("field:tax_id", left_out=())

        with self._each_row_commits():
            result = self._import_all(session, checked)

        self.assertEqual(result["created"], 4, result)
        for key, old_id in self.ids.items():
            name = self._record_of(key)
            self.assertEqual(frappe.db.get_value("Customer", name, "customer_name"), self._names()[key])
            self.assertEqual(frappe.db.get_value("Customer", name, "tax_id"), old_id)

    # -- the key map ------------------------------------------------------------------------------

    def test_each_created_customer_gets_a_key_map_row_matching_the_import_log(self):
        session, checked = self._keyed_session("key_map", left_out=())

        with self._each_row_commits():
            result = self._import_all(session, checked)

        rows = frappe.get_all(
            KEY_MAP,
            filters={"source_system": self.system},
            fields=["source_key", "target_name", "import_session", "how"],
        )
        self.assertEqual(
            {r["source_key"]: r["target_name"] for r in rows},
            {old_id: self._record_of(key) for key, old_id in self.ids.items()},
        )
        self.assertEqual({r["import_session"] for r in rows}, {session})
        data_import = frappe.parse_json(frappe.db.get_value("FAC Import Session", session, "progress"))[
            "data_import"
        ]
        logged = set(
            frappe.get_all(
                "Data Import Log", filters={"data_import": data_import, "success": 1}, pluck="docname"
            )
        )
        self.assertEqual({r["target_name"] for r in rows}, logged)
        self.assertEqual(result["created"], 4)

    def test_recording_the_same_import_again_adds_nothing(self):
        session, checked = self._keyed_session("key_map", left_out=())
        with self._each_row_commits():
            self._import_all(session, checked)
        data_import = frappe.parse_json(frappe.db.get_value("FAC Import Session", session, "progress"))[
            "data_import"
        ]
        before = frappe.db.count(KEY_MAP, {"source_system": self.system})

        again = keys.record(self._doc(session), data_import)

        self.assertEqual(frappe.db.count(KEY_MAP, {"source_system": self.system}), before)
        self.assertEqual(again["conflicts"], [])

    def test_a_row_that_was_left_out_gets_no_key(self):
        n = self._names()
        # one row names a group that doesn't exist: the user leaves it out
        lines = ["id," + ",".join(MAPPING)]
        lines.append(f"{self.ids['alpha']},{n['alpha']},{self.group},Company")
        lines.append(f"{self.ids['beta']},{n['beta']},Nowhere {self.tag},Company")
        file_doc = self._file("odoo-customers.csv", ("\n".join(lines) + "\n").encode())
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]
        self._run(
            "set_column_mapping",
            {
                "session": session,
                "mapping": MAPPING,
                "doctype": "Customer",
                "source_key_column": "id",
                "source_system": self.system,
            },
        )
        keys.set_choice("Customer", self.system, "key_map")
        checked = self._run("dry_run_import", {"session": session})["result"]
        group = next(g["id"] for g in checked["groups"] if g.get("value") == f"Nowhere {self.tag}")
        checked = self._run(
            "dry_run_import",
            {"session": session, "fixes": [{"group": group, "action": "leave_out", "reason": "Closed shop"}]},
        )["result"]

        with self._each_row_commits():
            self._import_all(session, checked)

        self.assertEqual(
            keys.resolve("Customer", self.system, [self.ids["alpha"], self.ids["beta"]]),
            {self.ids["alpha"]: self._record_of("alpha"), self.ids["beta"]: None},
        )

    # -- what changes nothing ------------------------------------------------------------------------

    def test_no_key_is_kept_before_a_choice_nor_for_a_file_without_a_key_column(self):
        session, checked = self._ready_session()  # no old ID column at all

        with self._each_row_commits():
            self._import_all(session, checked)

        self.assertFalse(frappe.db.exists(KEY_MAP, {"source_system": self.system}))

    def test_an_id_already_naming_another_record_is_reported_and_not_overwritten(self):
        session, checked = self._keyed_session("key_map", left_out=())
        other = frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": f"Existing {self.tag}",
                "customer_group": self.group,
            }
        ).insert()
        keys.record_pairs("IMP-OLD", "Customer", self.system, [(self.ids["alpha"], other.name)])

        with self._each_row_commits():
            result = self._import_all(session, checked)

        self.assertEqual(self._record_of("alpha"), other.name)
        step = frappe.get_doc("FAC Import Session", session).steps[-1]
        self.assertEqual(step.step, "Import")
        self.assertIn("already belong to another record", step.message)
        self.assertIn(self.ids["alpha"], step.message)
        self.assertEqual(
            self._record_of("beta"), frappe.db.get_value("Customer", {"customer_name": self._names()["beta"]})
        )

    def test_the_result_recorded_on_the_session_is_unchanged_by_the_keys(self):
        session, checked = self._keyed_session("key_map", left_out=())
        with self._each_row_commits():
            self._import_all(session, checked)

        doc = frappe.get_doc("FAC Import Session", session)

        self.assertEqual(doc.status, "Completed")
        self.assertEqual(doc.steps[-1].step, "Import")
        self.assertTrue(
            import_run.result_of(self._doc(session), frappe.parse_json(doc.progress)["data_import"])
        )
