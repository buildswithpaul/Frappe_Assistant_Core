# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

import unittest

import frappe
from frappe.utils import add_days, today

from frappe_assistant_core.chat import home_signals
from frappe_assistant_core.tests.base_test import BaseAssistantTest

COMPANY = "Northwind Demo Co"
ABBR = "NDC"
WAREHOUSE = f"Stores - {ABBR}"
REORDER_LEVEL = 10
HSN_CODE = "84713010"
STOCK_IDS = ["below_reorder", "late_purchase_orders", "pending_material_requests"]


@unittest.skipUnless(
    "erpnext" in frappe.get_installed_apps() and frappe.db.exists("Company", COMPANY),
    "needs ERPNext and the demo company",
)
class TestStockSignals(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The defaults cache lives in Redis and survives the class rollback.
        cls.addClassCleanup(frappe.clear_cache)

    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("storekeeper", roles=("Stock Manager", "Purchase Manager"))

    def _item(self, reorder_level: int = REORDER_LEVEL) -> str:
        item = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": f"SIGNAL-STOCK-{frappe.generate_hash(length=8)}",
                "item_name": "Signal stock item",
                "item_group": frappe.db.get_value("Item Group", {"is_group": 0}),
                "stock_uom": "Nos",
                "is_stock_item": 1,
                "gst_hsn_code": HSN_CODE,
                "reorder_levels": [
                    {
                        "warehouse": WAREHOUSE,
                        "warehouse_reorder_level": reorder_level,
                        "warehouse_reorder_qty": 20,
                        "material_request_type": "Purchase",
                    }
                ],
            }
        ).insert(ignore_permissions=True)
        return item.name

    def _receive(self, item: str, qty: int) -> None:
        # Production path: a storekeeper submits a Material Receipt Stock Entry, which writes the Bin.
        entry = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Receipt",
                "company": COMPANY,
                "items": [
                    {
                        "item_code": item,
                        "qty": qty,
                        "basic_rate": 10,
                        "t_warehouse": WAREHOUSE,
                        "expense_account": f"Stock Adjustment - {ABBR}",
                        "cost_center": f"Main - {ABBR}",
                    }
                ],
            }
        )
        entry.insert(ignore_permissions=True)
        entry.submit()

    def _restrict_to_item(self, item: str) -> None:
        # Manufactured: production reaches this when an administrator restricts the storekeeper to
        # certain Items through User Permissions.
        frappe.get_doc(
            {"doctype": "User Permission", "user": self.user, "allow": "Item", "for_value": item}
        ).insert(ignore_permissions=True)
        frappe.clear_cache(user=self.user)

    def _supplier(self) -> str:
        return (
            frappe.get_doc(
                {
                    "doctype": "Supplier",
                    "supplier_name": f"Signal Stock Supplier {frappe.generate_hash(length=6)}",
                    "supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}),
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def _item_row(self, item: str, schedule_date: str) -> dict:
        return {
            "item_code": item,
            "qty": 5,
            "rate": 10,
            "schedule_date": schedule_date,
            "warehouse": WAREHOUSE,
        }

    def _purchase_order(self, item: str, due_days_ago: int = 5):
        # Production path: a buyer submits a Purchase Order whose required date then passes. The date
        # is set directly because validation rejects a required date before the order date.
        order = frappe.get_doc(
            {
                "doctype": "Purchase Order",
                "company": COMPANY,
                "supplier": self._supplier(),
                "currency": "INR",
                "conversion_rate": 1,
                "transaction_date": add_days(today(), -30),
                "schedule_date": add_days(today(), 10),
                "items": [self._item_row(item, add_days(today(), 10))],
            }
        )
        order.insert(ignore_permissions=True)
        order.submit()
        late = add_days(today(), -due_days_ago)
        frappe.db.set_value("Purchase Order", order.name, "schedule_date", late, update_modified=False)
        frappe.db.set_value(
            "Purchase Order Item", order.items[0].name, "schedule_date", late, update_modified=False
        )
        return order

    def _material_request(self, item: str):
        request = frappe.get_doc(
            {
                "doctype": "Material Request",
                "material_request_type": "Purchase",
                "company": COMPANY,
                "transaction_date": today(),
                "schedule_date": add_days(today(), 7),
                "items": [self._item_row(item, add_days(today(), 7))],
            }
        )
        request.insert(ignore_permissions=True)
        request.submit()
        return request

    def _count(self, compute) -> int:
        result = compute(self.user, COMPANY)
        return result.count if result else 0

    def test_k1_counts_item_below_reorder(self):
        before = self._count(home_signals._below_reorder)
        self._receive(self._item(), 2)
        result = home_signals._below_reorder(self.user, None)
        self.assertEqual(result.count, before + 1)
        self.assertEqual(result.ask, "Which items are below their reorder level?")

    def test_k1_ignores_item_above_reorder(self):
        before = self._count(home_signals._below_reorder)
        self._receive(self._item(), REORDER_LEVEL + 5)
        self.assertEqual(self._count(home_signals._below_reorder), before)

    def test_k1_excludes_item_hidden_by_user_permission(self):
        visible, hidden = self._item(), self._item()
        self._receive(visible, 2)
        self._receive(hidden, 2)
        self._restrict_to_item(visible)
        result = home_signals._below_reorder(self.user, None)
        self.assertEqual(result.count, 1)

    def test_k2_counts_late_po(self):
        item = self._item()
        before = self._count(home_signals._late_purchase_orders)
        self._purchase_order(item)
        result = home_signals._late_purchase_orders(self.user, COMPANY)
        self.assertEqual(result.count, before + 1)
        self.assertEqual(result.ask, "Which purchase orders are late from suppliers?")
        self.assertEqual(home_signals._late_purchase_orders(self.user, "Some Other Company").count, 0)

    def test_k2_ignores_order_not_yet_due(self):
        item = self._item()
        before = self._count(home_signals._late_purchase_orders)
        self._purchase_order(item, due_days_ago=-5)
        self.assertEqual(self._count(home_signals._late_purchase_orders), before)

    def test_k3_counts_pending_request(self):
        item = self._item()
        before = self._count(home_signals._pending_material_requests)
        self._material_request(item)
        result = home_signals._pending_material_requests(self.user, COMPANY)
        self.assertEqual(result.count, before + 1)
        self.assertEqual(result.ask, "Show material requests that are still pending")

    def test_stock_signals_registered_after_sales_with_stock_lens(self):
        ids = [signal.id for signal in home_signals.CATALOGUE]
        sales_last = max(ids.index(i) for i in ("quotations_expiring", "late_sales_orders", "stale_leads"))
        self.assertEqual(ids[sales_last + 1 : sales_last + 1 + len(STOCK_IDS)], STOCK_IDS)
        for signal in home_signals.CATALOGUE[sales_last + 1 :]:
            self.assertEqual(signal.lenses, ("stock",))
