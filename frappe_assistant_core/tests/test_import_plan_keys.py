# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""A migration plan whose later file refers to an earlier file's records by the old system's IDs
(#34244, K-8): the whole plan is checked up front as if they were there, and each file is
translated just before its own import."""

import unittest

import frappe

from frappe_assistant_core.tests.base_test import item_hsn_fields
from frappe_assistant_core.tests.test_import_run import ImportRunCase
from frappe_assistant_core.utils import import_keys as keys
from frappe_assistant_core.utils import import_plan

SESSION = "FAC Import Session"


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Item Group and Item")
class TestPlanWithOldIds(ImportRunCase):
    def setUp(self):
        super().setUp()
        self.system = f"odoo{self.tag}"
        self.g1, self.g2 = f"PG1 {self.tag}", f"PG2 {self.tag}"
        self.id1, self.id2 = f"GO-{self.tag}-1", f"GO-{self.tag}-2"
        frappe.db.delete("DefaultValue", {"defkey": ["like", "fac_old_id::Item Group::%"]})

    def _mapped(self, file_name, content, doctype, mapping, **arguments):
        started = self._run("start_import_session", {"file_url": self._file(file_name, content).file_url})
        session = started["result"]["session_id"]
        mapped = self._run(
            "set_column_mapping", {"session": session, "mapping": mapping, "doctype": doctype, **arguments}
        )
        self.assertTrue(mapped["success"], mapped)
        return session

    def _files(self, item_group_id=None, item_code=None):
        """The Item Groups file (with the old system's ID of each group) and the Items file, which
        points at its group by that ID."""
        groups = self._mapped(
            "groups.csv",
            f"ID,Name,Parent,Is Group\n{self.id1},{self.g1},All Item Groups,1\n{self.id2},{self.g2},{self.g1},0\n".encode(),
            "Item Group",
            {"Name": "item_group_name", "Parent": "parent_item_group", "Is Group": "is_group"},
            source_key_column="ID",
            source_system=self.system,
        )
        # asked once, before the dry run
        self.assertTrue(self._run("choose_old_id_storage", {"session": groups, "use": "key_map"})["success"])
        self.code = item_code or f"PI-{self.tag}"
        hsn = "".join(f",{code}" for code in item_hsn_fields().values())
        items = self._mapped(
            "items.csv",
            f"Code,Name,Group ID,UOM{',HSN' if hsn else ''}\n{self.code},{self.code},{item_group_id or self.id2},Nos{hsn}\n".encode(),
            "Item",
            {
                "Code": "item_code",
                "Name": "item_name",
                "Group ID": "item_group",
                "UOM": "stock_uom",
                **({"HSN": "gst_hsn_code"} if hsn else {}),
            },
            old_id_columns={"Group ID": {"doctype": "Item Group", "source_system": self.system}},
        )
        return groups, items

    def _plan(self, groups, items):
        plan = self._run("plan_migration", {"sessions": [items, groups], "failure_rule": "leave_out"})[
            "result"
        ]["plan"]
        answered = self._run(
            "plan_questions", {"plan": plan, "answers": [{"id": "plan:failure_rule", "rule": "leave_out"}]}
        )["result"]
        return plan, answered

    def _approve(self, plan):
        figures = {"plan": plan, **import_plan.card_figures(import_plan.get_plan(plan))}
        with self._each_row_commits():
            return self._run("run_migration_plan", figures)

    def test_the_items_file_alone_cannot_find_its_group_yet(self):
        _groups, items = self._files()

        checked = self._run("dry_run_import", {"session": items})["result"]

        self.assertEqual(checked["status"], "Dry Run Failed", checked)
        self.assertIn("isn't imported yet", next(g["message"] for g in checked["groups"] if g.get("value")))

    def test_in_a_plan_the_ids_the_earlier_file_brings_count_as_present(self):
        groups, items = self._files()

        _plan, answered = self._plan(groups, items)

        self.assertTrue(answered["ready"], answered)
        self.assertEqual(frappe.db.get_value(SESSION, items, "status"), "Ready to Import")

    def test_the_names_the_plan_expects_include_the_old_ids_of_its_earlier_files(self):
        groups, items = self._files()
        self._plan(groups, items)

        expected = import_plan.planned_names(frappe.get_doc(SESSION, items))

        self.assertIn(self.id1.casefold(), expected["Item Group"])
        self.assertIn(self.id2.casefold(), expected["Item Group"])

    def test_one_approval_imports_the_groups_then_the_items_translated_to_the_real_names(self):
        groups, items = self._files()
        plan, _answered = self._plan(groups, items)

        response = self._approve(plan)

        self.assertTrue(response["success"], response)
        self.assertEqual(import_plan.get_plan(plan).status, "Completed")
        self.assertEqual(frappe.db.get_value("Item", self.code, "item_group"), self.g2)
        self.assertEqual(
            keys.resolve("Item Group", self.system, [self.id1, self.id2]),
            {self.id1: self.g1, self.id2: self.g2},
        )
        self.assertFalse(frappe.db.exists("Item Group", self.id2))  # no stand-in is left behind

    def test_an_id_no_file_of_the_plan_brings_is_a_question_of_the_plan(self):
        groups, items = self._files(item_group_id=f"GO-{self.tag}-9")

        plan, answered = self._plan(groups, items)

        self.assertFalse(answered["ready"], answered)
        text = frappe.as_json(answered)
        self.assertIn("isn't imported yet", text)
        self.assertIn(f"GO-{self.tag}-9", text)
        self.assertFalse(frappe.db.exists("Item", self.code))
