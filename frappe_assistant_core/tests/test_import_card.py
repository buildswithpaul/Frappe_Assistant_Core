# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""The check's one card (live, 2026-11-19, a client's 2,084 projects): six questions one after another,
"exclude rows with missing departments" left 1 row of 2,084, 322 sub-projects named like their main project
could only be left out, and the user was asked to type department names."""

import unittest
from unittest.mock import patch

import frappe

from frappe_assistant_core.tests.test_import_run import ImportRunCase
from frappe_assistant_core.utils import import_fixes

MAPPING = {
    "Project": "project_name",
    "Stage": "status",
    "Department": "department",
    "Company": "company",
    "Project ID": "Don't Import",
}


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Project and Department")
class TestImportCard(ImportRunCase):
    def setUp(self):
        super().setUp()
        self.company = frappe.get_all("Company", pluck="name", limit=1)[0]
        self.abbr = frappe.get_cached_value("Company", self.company, "abbr")
        self.code = "D" + self.tag[:5].upper()  # a department code of the client's

    def _session(self):
        c, t = self.company, self.tag
        lines = [
            "Project ID,Project,Stage,Department,Company,Block",
            f"P1{t},Kolar {t},Finished,{self.code},{c},BL_A",
            f"P1{t}_01,Kolar {t},In process,{self.code},{c},BL_A",
            f"P2{t},Hosur {t},Finished,,{c},BL_B",
        ]
        file_doc = self._file("projects.csv", ("\n".join(lines) + "\n").encode())
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]
        mapped = self._run(
            "set_column_mapping", {"session": session, "doctype": "Project", "mapping": MAPPING}
        )
        self.assertTrue(mapped["success"], mapped)
        return session

    def _check(self, session, **arguments):
        checked = self._run("dry_run_import", {"session": session, **arguments})
        self.assertTrue(checked["success"], checked)
        return checked["result"]

    def _question(self, card, prefix):
        return next(q for q in card["questions"] if q["id"].startswith(prefix))

    def _recommended(self, question):
        return next(o for o in question["options"] if o.get("recommended"))

    def test_the_check_gives_every_choice_on_one_card_with_the_recommended_ones_selected(self):
        card = self._check(self._session())["card"]

        repeated = self._question(card, "duplicate:")
        self.assertIn("Project ID", self._recommended(repeated)["label"])
        self.assertIn(f"Kolar {self.tag} (P1{self.tag}_01)", self._recommended(repeated)["effect"])
        labels = [o["label"] for o in repeated["options"]]
        self.assertTrue(any("in the file" in label for label in labels), labels)  # rename it themselves
        self.assertTrue(any("Ignore these for now" in label for label in labels), labels)

        stage = self._recommended(self._question(card, "option:"))
        self.assertEqual({f["to"] for f in stage["fixes"]}, {"Completed", "Open"})

        department = self._recommended(self._question(card, "missing:"))
        self.assertEqual(
            department["create"],
            [
                {
                    "doctype": "Department",
                    "data": {
                        **department["create"][0]["data"],
                        "department_name": self.code,
                        "company": self.company,
                    },
                }
            ],
        )
        self.assertIn("up to 3 of 3", card["result"])

    def test_the_recommended_answers_keep_every_row(self):
        session = self._session()
        card = self._check(session)["card"]
        fixes = [f for q in card["questions"] for f in self._recommended(q).get("fixes", [])]
        create = [d for q in card["questions"] for d in self._recommended(q).get("create", [])]

        created = self._run("create_document", {"documents": create, "import_session": session})
        self.assertTrue(created["success"], created)
        checked = self._check(session, fixes=fixes)

        self.assertEqual((checked["ready"], checked["failed"]), (3, 0), checked.get("message"))
        self.assertTrue(frappe.db.exists("Department", f"{self.code} - {self.abbr}"))

    def test_a_repeated_name_gets_the_rows_id_and_no_row_is_left_out(self):
        session = self._session()
        card = self._check(session)["card"]
        keep = [
            f
            for q in card["questions"]
            if not q["id"].startswith("missing:")
            for f in self._recommended(q).get("fixes", [])
        ]
        drop = next(o for o in self._question(card, "missing:")["options"] if "empty" in o["label"])

        checked = self._check(session, fixes=keep + drop["fixes"])

        self.assertEqual((checked["ready"], checked["failed"], checked.get("excluded") or 0), (3, 0, 0))
        renamed = import_fixes.renames(frappe.get_doc("FAC Import Session", session))
        self.assertEqual([r["value"] for r in renamed.values()], [f"Kolar {self.tag} (P1{self.tag}_01)"])

    def test_a_column_left_empty_keeps_every_row(self):
        session = self._session()
        card = self._check(session)["card"]
        drop = next(o for o in self._question(card, "missing:")["options"] if "empty" in o["label"])

        checked = self._check(session, fixes=drop["fixes"])

        self.assertNotIn(
            "missing:department", [q["id"] for q in checked.get("card", {}).get("questions", [])]
        )
        self.assertEqual(
            import_fixes.dropped(frappe.get_doc("FAC Import Session", session))[0]["field"], "department"
        )

    def test_a_required_column_is_never_offered_empty(self):
        session = self._session()
        groups = {
            "cause": "Not an allowed option",
            "parent": "Project",
            "field": "project_name",
            "label": "Project Name",
        }
        self.assertIsNone(import_fixes._drop_fix(frappe.get_doc("FAC Import Session", session), groups))

    def test_updating_a_doctype_with_no_records_suggests_new_records(self):
        session = self._session()
        frappe.db.set_value("FAC Import Session", session, "import_type", "Update Existing Records")
        real_count = frappe.db.count

        def no_projects(doctype, *args, **kwargs):
            return (
                0
                if doctype == "Project" and not args and not kwargs
                else real_count(doctype, *args, **kwargs)
            )

        with patch.object(frappe.db, "count", side_effect=no_projects):
            card = import_fixes.card(
                frappe.get_doc("FAC Import Session", session), {"total_rows": 3, "groups": []}, []
            )

        question = card["questions"][0]
        self.assertEqual(question["id"], "import_type")
        self.assertTrue(question["options"][0]["recommended"])

    def test_a_column_that_fits_no_field_is_offered_a_new_field_not_notes(self):
        card = self._check(self._session())["card"]

        columns = self._question(card, "columns")
        self.assertIn("Block", columns["detail"])
        create = self._recommended(columns)["custom_fields"]
        self.assertEqual(create, [{"doctype": "Custom Field", "data": {"dt": "Project", "label": "Block", "fieldtype": "Data"}}])
