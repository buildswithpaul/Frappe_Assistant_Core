# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Old-system IDs (#34244): where they are kept, how a field that holds them is found, how an ID is
resolved and recorded.

Field storage is tested on Customer.tax_id, a standard field: adding a real custom field in a test
would change the site's tables for good.
"""

import unittest

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils import compat
from frappe_assistant_core.utils import import_keys as keys

KEY_MAP = "FAC Import Key Map"


def _leaf_customer_group() -> str:
    return frappe.db.get_value("Customer Group", {"is_group": 0}, "name")


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
class TestKeyResolver(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.tag = frappe.generate_hash(length=6)
        self.name_customers_by("Customer Name")
        self.system = f"odoo{self.tag}"  # a system of this test's own: the choice is kept as a default
        # which systems share tax_id is kept as a default too: start each test with none
        frappe.defaults.clear_default(key=keys._SYSTEMS_KEY.format(doctype="Customer", fieldname="tax_id"))

    def _customer(self, label="Acme", tax_id=None):
        doc = frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": f"{label} {frappe.generate_hash(length=5)}",
                "customer_group": _leaf_customer_group(),
                "tax_id": tax_id,
            }
        )
        return doc.insert()

    def _keep_in_field(self, fieldname="tax_id", system=None):
        keys.set_choice("Customer", system or self.system, f"field:{fieldname}")

    def _keep_in_map(self, system=None):
        keys.set_choice("Customer", system or self.system, "key_map")

    # -- the numbers a file holds --------------------------------------------------------------

    def test_an_id_is_compared_as_text(self):
        self.assertEqual(keys.normalise(100.0), "100")
        self.assertEqual(keys.normalise("100.0"), "100")
        self.assertEqual(keys.normalise(" 100 "), "100")
        self.assertEqual(keys.normalise("00100"), "00100")
        self.assertEqual(keys.normalise("1.5"), "1.5")
        self.assertEqual(keys.normalise(None), "")

    def test_distinct_keys_drop_empty_and_repeated_ones(self):
        self.assertEqual(keys.distinct_keys([100, "100.0", "", None, 101, " 101"]), ["100", "101"])

    # -- the choice ----------------------------------------------------------------------------

    def test_nothing_is_chosen_until_someone_chooses(self):
        self.assertIsNone(keys.storage_for("Customer", self.system))

    def test_the_choice_is_kept_per_doctype_and_system(self):
        self._keep_in_field()

        self.assertEqual(keys.storage_for("Customer", self.system), {"kind": "field", "fieldname": "tax_id"})
        self.assertEqual(
            keys.storage_for("Customer", self.system.upper()), keys.storage_for("Customer", self.system)
        )
        self.assertIsNone(keys.storage_for("Supplier", self.system))
        self.assertIsNone(keys.storage_for("Customer", "zoho" + self.tag))

    def test_a_refused_field_means_the_key_map(self):
        keys.set_choice("Customer", self.system, "refused_field")

        self.assertEqual(keys.storage_for("Customer", self.system), {"kind": "key_map"})

    def test_a_second_system_in_the_same_field_is_prefixed_the_first_is_not(self):
        other = "zoho" + self.tag
        self._keep_in_field()
        self._keep_in_field(system=other)

        self.assertEqual(keys.field_value("Customer", self.system, "100"), "100")
        self.assertEqual(keys.field_value("Customer", other, "100"), f"{other}:100")

    # -- finding a field that holds the IDs ------------------------------------------------------

    def test_a_field_that_may_hold_ids_is_told_by_its_name_or_label(self):
        for fieldname, label in (
            ("legacy_code", "Legacy Code"),
            ("external_id", "External ID"),
            ("fac_old_system_id", None),
            ("ref", "Ref"),
        ):
            with self.subTest(fieldname=fieldname):
                self.assertTrue(keys.looks_like_id(fieldname, label))
        for fieldname, label in (
            ("mobile_no", "Mobile No"),
            ("customer_name", "Customer Name"),
            ("website", None),
        ):
            with self.subTest(fieldname=fieldname):
                self.assertFalse(keys.looks_like_id(fieldname, label))

    def test_the_standard_fields_a_doctype_may_use_are_listed(self):
        names = {f[0] for f in keys._candidate_fields("Customer")}
        self.assertIn("tax_id", names)
        self.assertEqual("gstin" in names, compat.has_india_compliance())
        self.assertIn("item_code", {f[0] for f in keys._candidate_fields("Item")})
        self.assertIn("account_number", {f[0] for f in keys._candidate_fields("Account")})

    def test_a_field_holding_all_the_ids_is_found_with_its_counts(self):
        ids = [f"T-{self.tag}-{i}" for i in range(5)]
        for key in ids:
            self._customer(tax_id=key)

        found = {f["fieldname"]: f for f in keys.find_fields("Customer", ids)}

        self.assertEqual((found["tax_id"]["matched"], found["tax_id"]["total"]), (5, 5))
        self.assertTrue(found["tax_id"]["standard"])

    def test_a_standard_field_holding_some_of_the_ids_is_found_and_one_holding_few_is_not(self):
        ids = [f"S-{self.tag}-{i}" for i in range(5)]
        for key in ids[:3]:
            self._customer(tax_id=key)
        self.assertEqual(keys.find_fields("Customer", ids)[0]["matched"], 3)

        self.assertEqual(keys.find_fields("Customer", ids + [f"X-{i}" for i in range(10)]), [])

    def test_an_id_found_on_two_records_makes_the_field_unsafe(self):
        ids = [f"D-{self.tag}-{i}" for i in range(2)]
        self._customer(tax_id=ids[0])
        self._customer(tax_id=ids[0])
        self._customer(tax_id=ids[1])

        self.assertEqual(keys.find_fields("Customer", ids), [])

    def test_numbers_that_excel_read_as_floats_still_match(self):
        number = str(9_000_000 + int(self.tag, 16) % 1_000_000)
        self._customer(tax_id=number)

        found = keys.find_fields("Customer", [float(number)])

        self.assertEqual(found[0]["matched"], 1)

    def test_no_ids_find_no_field(self):
        self.assertEqual(keys.find_fields("Customer", [None, "", " "]), [])

    # -- resolving ---------------------------------------------------------------------------------

    def test_ids_resolve_through_the_field(self):
        a = self._customer(tax_id=f"R-{self.tag}-1")
        self._keep_in_field()

        result = keys.resolve("Customer", self.system, [f"R-{self.tag}-1", f"R-{self.tag}-9"])

        self.assertEqual(result, {f"R-{self.tag}-1": a.name, f"R-{self.tag}-9": None})

    def test_ids_resolve_through_the_key_map(self):
        a = self._customer()
        self._keep_in_map()
        keys.record_pairs("IMP-X", "Customer", self.system, [(100.0, a.name)])

        self.assertEqual(keys.resolve("Customer", self.system, ["100", 101]), {"100": a.name, "101": None})

    def test_nothing_resolves_before_a_choice(self):
        self._customer(tax_id=f"N-{self.tag}")

        self.assertEqual(keys.resolve("Customer", self.system, [f"N-{self.tag}"]), {f"N-{self.tag}": None})

    def test_the_chosen_place_decides_not_the_other_one(self):
        in_field = self._customer(tax_id=f"B-{self.tag}")
        in_map = self._customer()
        frappe.get_doc(
            {
                "doctype": KEY_MAP,
                "source_system": self.system,
                "source_key": f"B-{self.tag}",
                "target_doctype": "Customer",
                "target_name": in_map.name,
            }
        ).insert(ignore_permissions=True)
        self._keep_in_field()

        self.assertEqual(
            keys.resolve("Customer", self.system, [f"B-{self.tag}"]), {f"B-{self.tag}": in_field.name}
        )

    def test_a_second_systems_ids_resolve_only_for_that_system(self):
        other = "zoho" + self.tag
        first = self._customer(tax_id=f"P-{self.tag}")
        second = self._customer(tax_id=f"{other}:P-{self.tag}")
        self._keep_in_field()
        self._keep_in_field(system=other)

        self.assertEqual(
            keys.resolve("Customer", self.system, [f"P-{self.tag}"]), {f"P-{self.tag}": first.name}
        )
        self.assertEqual(keys.resolve("Customer", other, [f"P-{self.tag}"]), {f"P-{self.tag}": second.name})

    def test_a_record_the_user_cannot_read_is_not_found(self):
        a = self._customer(tax_id=f"U-{self.tag}")
        self._keep_in_field()
        user = self.make_desk_user("keys-nobody")
        self.assert_cannot(user, "read", "Customer", a.name)
        key = f"U-{self.tag}"

        self.assertEqual(keys.resolve("Customer", self.system, [key], user=user), {key: None})
        self._keep_in_map()
        keys.record_pairs(None, "Customer", self.system, [(key, a.name)])
        self.assertEqual(keys.resolve("Customer", self.system, [key], user=user), {key: None})
        self.assertEqual(keys.resolve("Customer", self.system, [key]), {key: a.name})

    # -- recording ------------------------------------------------------------------------------------

    def test_recording_into_a_field_sets_the_field_and_a_repeat_adds_nothing(self):
        a = self._customer()
        self._keep_in_field()
        key = f"W-{self.tag}"

        first = keys.record_pairs("IMP-X", "Customer", self.system, [(key, a.name)])
        again = keys.record_pairs("IMP-X", "Customer", self.system, [(key, a.name)])

        self.assertEqual(first, {"written": [key], "conflicts": []})
        self.assertEqual(again, first)
        self.assertEqual(frappe.db.get_value("Customer", a.name, "tax_id"), key)

    def test_an_id_already_on_another_record_is_a_conflict_in_a_field(self):
        key = f"C-{self.tag}"
        a, b = self._customer(tax_id=key), self._customer()
        self._keep_in_field()

        result = keys.record_pairs("IMP-X", "Customer", self.system, [(key, b.name)])

        self.assertEqual(result, {"written": [], "conflicts": [key]})
        self.assertEqual(frappe.db.get_value("Customer", a.name, "tax_id"), key)
        self.assertFalse(frappe.db.get_value("Customer", b.name, "tax_id"))

    def test_recording_into_the_map_writes_one_row_and_a_repeat_adds_nothing(self):
        a = self._customer()
        self._keep_in_map()

        keys.record_pairs("IMP-1", "Customer", self.system, [("100", a.name)])
        keys.record_pairs("IMP-1", "Customer", self.system, [("100", a.name)])

        rows = frappe.get_all(
            KEY_MAP,
            filters={"source_system": self.system},
            fields=["source_key", "target_name", "import_session", "how"],
        )
        self.assertEqual(
            rows, [{"source_key": "100", "target_name": a.name, "import_session": "IMP-1", "how": "Imported"}]
        )

    def test_an_id_naming_a_record_that_still_exists_is_a_conflict_in_the_map(self):
        a, b = self._customer(), self._customer()
        self._keep_in_map()
        keys.record_pairs("IMP-1", "Customer", self.system, [("100", a.name)])

        result = keys.record_pairs("IMP-2", "Customer", self.system, [("100", b.name)])

        self.assertEqual(result, {"written": [], "conflicts": ["100"]})
        self.assertEqual(keys.resolve("Customer", self.system, ["100"]), {"100": a.name})

    def test_an_id_naming_a_deleted_record_is_taken_again(self):
        a, b = self._customer(), self._customer()
        self._keep_in_map()
        keys.record_pairs("IMP-1", "Customer", self.system, [("100", a.name)])
        frappe.delete_doc("Customer", a.name)

        result = keys.record_pairs("IMP-2", "Customer", self.system, [("100", b.name)])

        self.assertEqual(result, {"written": ["100"], "conflicts": []})
        self.assertEqual(keys.resolve("Customer", self.system, ["100"]), {"100": b.name})

    def test_nothing_is_recorded_before_a_choice(self):
        a = self._customer()

        result = keys.record_pairs("IMP-1", "Customer", self.system, [("100", a.name)])

        self.assertEqual(result, {"written": [], "conflicts": []})
        self.assertFalse(frappe.db.exists(KEY_MAP, {"source_system": self.system}))

    def test_undo_removes_only_that_sessions_rows(self):
        a, b = self._customer(), self._customer()
        self._keep_in_map()
        first, second = f"IMP-U1-{self.tag}", f"IMP-U2-{self.tag}"
        keys.record_pairs(first, "Customer", self.system, [("100", a.name)])
        keys.record_pairs(second, "Customer", self.system, [("101", b.name)])

        self.assertEqual(keys.remove_for_session(first), 1)

        self.assertEqual(keys.resolve("Customer", self.system, ["100", "101"]), {"100": None, "101": b.name})

    def test_the_sweep_removes_rows_whose_record_is_gone_and_keeps_the_rest(self):
        a, b = self._customer(), self._customer()
        self._keep_in_map()
        keys.record_pairs("IMP-1", "Customer", self.system, [("100", a.name), ("101", b.name)])
        frappe.delete_doc("Customer", a.name)

        keys.sweep_orphans()

        self.assertEqual(
            frappe.get_all(KEY_MAP, filters={"source_system": self.system}, pluck="source_key"), ["101"]
        )
