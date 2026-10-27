# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""The import key map (#34244): which old-system ID became which ERPNext record, and how an old ID
is found again in a later file or a later session."""

import unittest

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils import import_keys as keys

KEY_MAP = "FAC Import Key Map"


def _leaf_customer_group() -> str:
    return frappe.db.get_value("Customer Group", {"is_group": 0}, "name")


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
class TestKeyMapDocType(BaseAssistantTest):
    """P1.1: the table itself."""

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.tag = frappe.generate_hash(length=6)
        self.key = f"100-{self.tag}"  # a key of this test's own: rows live until the class ends
        self.name_customers_by("Customer Name")

    def _customer(self, label="Acme"):
        return frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": f"{label} {self.tag}",
                "customer_group": _leaf_customer_group(),
            }
        ).insert()

    def _row(self, key=None, system="odoo", doctype="Customer", name=None, **kw):
        key = key or self.key
        return frappe.get_doc(
            {
                "doctype": KEY_MAP,
                "source_system": system,
                "source_key": key,
                "target_doctype": doctype,
                "target_name": name or self._customer().name,
                **kw,
            }
        ).insert(ignore_permissions=True)

    def test_a_row_is_saved_with_its_system_lowercased_and_its_key_trimmed(self):
        row = self._row(key=f"  {self.key} ", system="Odoo")

        self.assertEqual((row.source_system, row.source_key), ("odoo", self.key))

    def test_a_second_row_for_the_same_system_doctype_and_key_is_refused(self):
        self._row(key=self.key)

        with self.assertRaises(frappe.UniqueValidationError):
            self._row(key=self.key)

    def test_the_same_key_may_belong_to_two_systems_and_two_doctypes(self):
        self._row(key=self.key, system="odoo")
        self._row(key=self.key, system="zoho")
        item = frappe.get_doc(
            {"doctype": "Item", "item_code": f"KM-{self.tag}", "item_group": "All Item Groups", **self._hsn()}
        ).insert()
        self._row(key=self.key, system="odoo", doctype="Item", name=item.name)

        self.assertEqual(frappe.db.count(KEY_MAP, {"source_key": self.key}), 3)

    def _hsn(self):
        from frappe_assistant_core.tests.base_test import item_hsn_fields

        return item_hsn_fields()

    def test_deleting_the_record_is_not_blocked_by_its_row(self):
        customer = self._customer()
        self._row(name=customer.name)

        frappe.delete_doc("Customer", customer.name)

        self.assertFalse(frappe.db.exists("Customer", customer.name))

    def test_renaming_the_record_moves_its_row(self):
        customer = self._customer()
        row = self._row(name=customer.name)
        new_name = f"Renamed {self.tag}"

        frappe.rename_doc("Customer", customer.name, new_name, force=True)

        self.assertEqual(frappe.db.get_value(KEY_MAP, row.name, "target_name"), new_name)

    def test_only_a_system_manager_can_open_or_list_the_map(self):
        user = self.make_desk_user("keymap-user")
        self.assert_cannot(user, "read", KEY_MAP)
        self.assert_cannot(user, "write", KEY_MAP)
        self.assert_cannot(user, "create", KEY_MAP)

        self.assertTrue(frappe.has_permission(KEY_MAP, "read", user="Administrator"))

    def test_deleting_the_import_session_keeps_the_rows(self):
        # the session is named as text, not linked, so no delete of it can reach the map
        meta = frappe.get_meta(KEY_MAP)

        self.assertEqual(meta.get_field("import_session").fieldtype, "Data")
        row = self._row(import_session="IMP-2026-99999")
        self.assertTrue(frappe.db.exists(KEY_MAP, row.name))


@unittest.skipUnless("erpnext" in frappe.get_installed_apps(), "needs ERPNext's Customer")
class TestKeysOutliveChatRetention(BaseAssistantTest):
    """P1.8: nothing that keeps an old ID is deleted with a chat or an import session (K-12, K-13)."""

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.tag = frappe.generate_hash(length=6)
        self.system = f"odoo{self.tag}"
        self.name_customers_by("Customer Name")
        keys.set_choice("Customer", self.system, "key_map")
        self.customer = frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": f"Retained {self.tag}",
                "customer_group": _leaf_customer_group(),
            }
        ).insert()
        self.session = f"IMP-RET-{self.tag}"
        keys.record_pairs(self.session, "Customer", self.system, [("100", self.customer.name)])

    def test_the_daily_retention_clean_up_leaves_the_rows(self):
        from frappe_assistant_core.utils import import_retention

        import_retention.purge_old_sessions()
        import_retention.purge([self.session], "Its files were deleted.")

        self.assertEqual(keys.resolve("Customer", self.system, ["100"]), {"100": self.customer.name})

    def test_a_deleted_chat_session_record_does_not_reach_the_rows(self):
        # the rows name the session as text, so no delete of the session can cascade to them
        self.assertEqual(
            frappe.get_all(KEY_MAP, filters={"import_session": self.session}, pluck="target_name"),
            [self.customer.name],
        )

    def test_the_orphan_sweep_runs_daily(self):
        scheduled = frappe.get_hooks("scheduler_events")["cron"]
        self.assertIn(
            "frappe_assistant_core.utils.import_keys.sweep_orphans",
            [method for methods in scheduled.values() for method in methods],
        )

    def test_the_sweep_leaves_a_row_whose_record_is_still_there(self):
        keys.sweep_orphans()

        self.assertEqual(keys.resolve("Customer", self.system, ["100"]), {"100": self.customer.name})
