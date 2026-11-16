# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""The mapping review card and the import approval card (#34415): read and changed by the chat,
through the same tools the model uses."""

import frappe

from frappe_assistant_core.chat.api import imports
from frappe_assistant_core.tests.test_import_run import MAPPING, ImportRunCase
from frappe_assistant_core.utils.import_mapping import session_mapping


class TestImportReviewApi(ImportRunCase):
    def _mapped(self):
        lines = [",".join([*MAPPING, "Region"]), f"Alpha {self.tag},{self.group},Company,South"]
        file_doc = self._file("customers.csv", ("\n".join(lines) + "\n").encode())
        session = self._run("start_import_session", {"file_url": file_doc.file_url})["result"]["session_id"]
        mapped = self._run(
            "set_column_mapping", {"session": session, "mapping": MAPPING, "doctype": "Customer"}
        )
        self.assertTrue(mapped["success"], mapped)
        return session

    def test_the_review_lists_each_column_with_its_values_field_and_status(self):
        session = self._mapped()

        review = imports.mapping_review(session)

        by_column = {c["column"]: c for c in review["columns"]}
        self.assertEqual(by_column["Customer Name"]["field"], "customer_name")
        self.assertEqual(by_column["Customer Name"]["status"], "mapped")
        self.assertEqual(by_column["Customer Name"]["samples"], [f"Alpha {self.tag}"])
        self.assertEqual(by_column["Region"]["status"], "unmapped")
        self.assertIn("territory", {o["value"] for o in review["options"]})
        self.assertTrue(review["editable"])
        self.assertEqual(review["doctype"], "Customer")

    def test_a_dropdown_change_is_saved_through_set_column_mapping(self):
        session = self._mapped()
        region = next(
            c["position"] for c in imports.mapping_review(session)["columns"] if c["column"] == "Region"
        )

        reply = imports.set_mapping_column(session, region, "territory")

        self.assertTrue(reply["success"], reply)
        self.assertEqual(
            session_mapping(frappe.get_doc("FAC Import Session", session))[str(region)], "territory"
        )
        row = next(c for c in reply["review"]["columns"] if c["column"] == "Region")
        self.assertEqual((row["field"], row["status"]), ("territory", "mapped"))
        # audited as the model's own call is
        self.assertTrue(frappe.db.exists("Assistant Audit Log", {"tool_name": "set_column_mapping"}))

    def test_a_field_the_mapping_refuses_is_said_and_nothing_changes(self):
        session = self._mapped()
        before = session_mapping(frappe.get_doc("FAC Import Session", session))

        reply = imports.set_mapping_column(session, 0, "no_such_field_at_all")

        self.assertFalse(reply["success"], reply)
        self.assertTrue(reply["error"] or reply["problems"])
        self.assertEqual(session_mapping(frappe.get_doc("FAC Import Session", session)), before)

    def test_another_users_session_is_refused(self):
        session = self._mapped()
        frappe.set_user(self.make_throwaway_user("other", roles=("Desk User",)))
        try:
            for call in (
                lambda: imports.mapping_review(session),
                lambda: imports.set_mapping_column(session, 0, "customer_name"),
                lambda: imports.import_card(session),
            ):
                with self.assertRaises((frappe.PermissionError, frappe.DoesNotExistError)):
                    call()
        finally:
            frappe.set_user("Administrator")

    def test_an_update_s_card_has_the_old_and_new_values(self):
        # PR #392, F6: "Update 1 Customer records" with counts only; the values that change were
        # shown only if the model chose to, though the dry run had them
        session = self._mapped()
        doc = frappe.get_doc("FAC Import Session", session)
        preview = {
            "records_changing": 7,
            "fields_changing": 9,
            "by_field": {"Mobile No": 7, "Territory": 2},
            "samples": [
                {
                    "row": 2,
                    "record": "CUST-0001",
                    "changes": [
                        {
                            "field": "mobile_no",
                            "label": "Mobile No",
                            "old": "98450 11111",
                            "new": "98450 22222",
                        },
                        {"field": "territory", "label": "Territory", "old": None, "new": "Karnataka"},
                    ],
                },
                {
                    "row": 3,
                    "record": "CUST-0002",
                    "changes": [
                        {"field": "mobile_no", "label": "Mobile No", "old": "1" * 300, "new": "2"},
                    ],
                },
            ],
        }
        frappe.db.set_value(
            "FAC Import Session",
            session,
            {
                "import_type": "Update Existing Records",
                "validation_summary": frappe.as_json({"ready": 7, "update": preview}),
            },
        )

        changes = imports.import_card(doc.name)["changes"]

        self.assertEqual((changes["records"], changes["fields"]), (7, 9))
        self.assertEqual(changes["by_field"], {"Mobile No": 7, "Territory": 2})
        first = changes["samples"][0]
        self.assertEqual(first["record"], "CUST-0001")
        self.assertEqual(
            first["changes"][0], {"label": "Mobile No", "old": "98450 11111", "new": "98450 22222"}
        )
        self.assertEqual(first["changes"][1]["old"], "")
        self.assertLessEqual(len(changes["samples"][1]["changes"][0]["old"]), 81)  # a long value is cut

    def test_a_new_records_card_has_no_changes(self):
        self.assertIsNone(imports.import_card(self._mapped())["changes"])

    def test_the_approval_card_has_the_file_records_and_mapping(self):
        session = self._mapped()

        card = imports.import_card(session)

        self.assertEqual(
            (card["file_name"], card["doctype"], card["update"]), ("customers.csv", "Customer", False)
        )
        self.assertIn("Customer Name → Customer Name", card["mapping"])
        self.assertFalse(card["submit"])
        self.assertEqual(card["left_out"], 0)
