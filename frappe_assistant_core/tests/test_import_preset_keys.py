# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Presets name the column that holds the old system's ID (#34244, K-16): applying one marks it."""

import copy

import frappe

from frappe_assistant_core.tests.test_apply_import_preset import PresetToolCase, xlsx
from frappe_assistant_core.utils import import_keys
from frappe_assistant_core.utils import import_presets as presets

ZOHO_CUSTOMERS = [
    ["Customer ID", "Display Name", "EmailID", "Customer Sub Type"],
    ["46000000000{n}1", "Ravi Traders {tag}", "ravi{tag}@example.com", "business"],
    ["46000000000{n}2", "Mehta Supplies {tag}", "mehta{tag}@example.com", "business"],
]
TALLY_LEDGERS = [
    ["Acme Pvt Ltd"],
    ["Ledgers"],
    [],
    ["Name", "Under", "GSTIN", "Opening Balance"],
    ["Ravi Traders {tag}", "Sundry Debtors", "", "1,000 Dr"],
    ["Mehta Supplies {tag}", "Sundry Creditors", "", "500 Cr"],
    ["HDFC Bank {tag}", "Bank Accounts", "", ""],
]


class TestPresetSourceKeys(PresetToolCase):
    def setUp(self):
        super().setUp()
        # where the IDs of these systems are kept is a site default: start each test with none chosen
        for doctype in ("Customer", "Supplier", "Item", "Account"):
            for system in ("zoho", "tally"):
                frappe.defaults.clear_default(
                    key=import_keys._CHOICE_KEY.format(doctype=doctype, system=system)
                )

    def _applied(self, rows, file_name):
        presets.clear_cache()
        file_doc = self._upload(f"{file_name}-{self.tag}.xlsx", xlsx(self._rows(rows)))
        reply = self.registry.get_tool("start_import_session")._safe_execute({"file_id": file_doc.name})
        self.assertTrue(reply["success"], reply)
        return reply["result"]

    def _session(self, result, target):
        entry = next(s for s in result["sessions"] if s["target"] == target)
        return entry, frappe.get_doc("FAC Import Session", entry["session_id"])

    def _zoho(self, rows=ZOHO_CUSTOMERS):
        return self._applied([[c.replace("{n}", "0") for c in row] for row in rows], "zoho-customers")

    def test_zoho_customers_mark_their_customer_id_as_the_key(self):
        result = self._zoho()

        self.assertEqual(result["preset"]["id"], "zoho_books.customers")
        entry, session = self._session(result, "Customers")
        header = frappe.parse_json(session.sheets)[0]["columns"]
        self.assertEqual(
            import_keys.source_key(session), {"position": header.index("Customer ID"), "system": "zoho"}
        )
        self.assertEqual(entry["old_ids"], {"column": "Customer ID", "system": "zoho"})

    def test_a_preset_keeps_its_ids_in_the_key_map_without_asking(self):
        result = self._zoho()

        entry, session = self._session(result, "Customers")
        self.assertEqual(import_keys.storage_for("Customer", "zoho"), {"kind": "key_map"})
        self.assertIsNone(import_keys.storage_problem(session))  # the dry run is not held for an answer
        self.assertEqual(entry["next"], "dry_run_import")

    def test_a_choice_already_made_for_the_system_is_not_changed_by_a_preset(self):
        import_keys.set_choice("Customer", "zoho", "field:tax_id")

        self._zoho()

        self.assertEqual(
            import_keys.storage_for("Customer", "zoho"), {"kind": "field", "fieldname": "tax_id"}
        )

    def test_the_id_column_is_kept_not_imported_and_not_reported_as_dropped(self):
        result = self._zoho()

        entry, session = self._session(result, "Customers")
        header = frappe.parse_json(session.sheets)[0]["columns"]
        stored = frappe.parse_json(session.template_options)["column_to_field_map"]
        self.assertEqual(stored[str(header.index("Customer ID"))], "Don't Import")
        self.assertNotIn("Customer ID", entry["mapping"]["not_imported"])

    def test_an_export_with_no_ids_marks_no_key(self):
        rows = [
            [c for i, c in enumerate(row) if i != 0] for row in ZOHO_CUSTOMERS
        ]  # the export without its Customer ID column

        entry, session = self._session(self._applied(rows, "zoho-no-ids"), "Customers")

        self.assertIsNone(import_keys.source_key(session))
        self.assertNotIn("old_ids", entry)

    def test_tally_ledgers_use_the_name_as_the_key_and_still_import_it(self):
        result = self._applied(TALLY_LEDGERS, "tally-ledgers")

        for target in ("Customers", "Suppliers"):  # the accounts wait for the company they need
            with self.subTest(target=target):
                entry, session = self._session(result, target)
                header = frappe.parse_json(session.sheets)[0]["columns"]
                self.assertEqual(
                    import_keys.source_key(session), {"position": header.index("Name"), "system": "tally"}
                )
                stored = frappe.parse_json(session.template_options)["column_to_field_map"]
                self.assertNotEqual(stored[str(header.index("Name"))], "Don't Import")

    def test_every_shipped_source_key_is_a_column_of_its_preset(self):
        for preset in presets.load_presets():
            for target in preset["targets"]:
                key = target.get("source_key")
                if key is None:
                    continue
                with self.subTest(preset=preset["id"], target=target["name"]):
                    self.assertIn(key, preset["columns"])
                    self.assertTrue(target.get("doctype"))
                    self.assertTrue((preset.get("source_system") or "").strip())

    def test_every_shipped_preset_of_a_party_item_or_account_list_names_its_key(self):
        for preset in presets.load_presets():
            for target in preset["targets"]:
                if target.get("doctype") in ("Customer", "Supplier", "Item", "Account"):
                    with self.subTest(preset=preset["id"], target=target["name"]):
                        self.assertTrue(target.get("source_key"))

    def test_a_source_key_that_is_not_a_column_is_refused(self):
        preset = copy.deepcopy(next(p for p in presets.load_presets() if p["id"] == "zoho_books.customers"))
        preset["targets"][0]["source_key"] = "No Such Column"

        self.assertIn("source_key", presets.validate_preset(preset))

    def test_a_source_key_on_an_engine_target_is_refused(self):
        preset = copy.deepcopy(
            next(p for p in presets.load_presets() if p["id"] == "tally_prime.trial_balance")
        )
        preset["targets"][0]["source_key"] = preset["targets"][0]["columns"].popitem()[0]

        self.assertIn("source_key", presets.validate_preset(preset))

    def test_the_systems_short_name_must_be_text(self):
        preset = copy.deepcopy(next(p for p in presets.load_presets() if p["id"] == "zoho_books.customers"))
        preset["source_system"] = 5

        self.assertIn("source_system", presets.validate_preset(preset))
