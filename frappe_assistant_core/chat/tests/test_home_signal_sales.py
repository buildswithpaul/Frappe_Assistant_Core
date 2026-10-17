# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

import unittest
from unittest.mock import patch

import frappe
from frappe.utils import add_days, today

from frappe_assistant_core.chat import home_signals
from frappe_assistant_core.tests.base_test import BaseAssistantTest

COMPANY = "Northwind Demo Co"
ABBR = "NDC"
ITEM = "NW-OLIVEOIL-5L"
STALE_DAYS = 20


@unittest.skipUnless(
    "erpnext" in frappe.get_installed_apps() and frappe.db.exists("Company", COMPANY),
    "needs ERPNext and the demo company",
)
class TestSalesSignals(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addClassCleanup(frappe.clear_cache)

    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("seller", roles=("Sales Manager",))
        self.customer = (
            frappe.get_doc(
                {
                    "doctype": "Customer",
                    "customer_name": f"Signal Sales Customer {frappe.generate_hash(length=6)}",
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def _item_row(self, delivery_date: str) -> dict:
        return {
            "item_code": ITEM,
            "qty": 1,
            "rate": 100,
            "delivery_date": delivery_date,
            "income_account": f"Sales - {ABBR}",
            "cost_center": f"Main - {ABBR}",
        }

    def _quotation(self, valid_in_days: int):
        # Production path: a salesperson saves and submits a Quotation with a validity date. The
        # ERPNext test helpers are not importable on this site, so the same insert-and-submit is done here.
        quotation = frappe.get_doc(
            {
                "doctype": "Quotation",
                "company": COMPANY,
                "quotation_to": "Customer",
                "party_name": self.customer,
                "currency": "INR",
                "conversion_rate": 1,
                "transaction_date": today(),
                "valid_till": add_days(today(), valid_in_days),
                "items": [self._item_row(add_days(today(), 30))],
            }
        )
        quotation.insert(ignore_permissions=True)
        quotation.submit()
        return quotation

    def _sales_order(self, delivery_days_ago: int = 5):
        # Production path: a salesperson submits a Sales Order whose delivery date then passes.
        # The date is set directly because validation rejects a delivery date before the order date.
        order = frappe.get_doc(
            {
                "doctype": "Sales Order",
                "company": COMPANY,
                "customer": self.customer,
                "currency": "INR",
                "conversion_rate": 1,
                "transaction_date": add_days(today(), -30),
                "delivery_date": add_days(today(), 10),
                "items": [self._item_row(add_days(today(), 10))],
            }
        )
        order.insert(ignore_permissions=True)
        order.submit()
        late = add_days(today(), -delivery_days_ago)
        frappe.db.set_value("Sales Order", order.name, "delivery_date", late, update_modified=False)
        frappe.db.set_value(
            "Sales Order Item", order.items[0].name, "delivery_date", late, update_modified=False
        )
        return order

    def _lead(self, owner: str, untouched_days: int = STALE_DAYS):
        suffix = frappe.generate_hash(length=6)
        lead = frappe.get_doc(
            {
                "doctype": "Lead",
                "first_name": f"Signal{suffix}",
                "email_id": f"signal-{suffix}@example.com",
                "lead_owner": owner,
            }
        ).insert(ignore_permissions=True)
        # Manufactured: production reaches this state when nobody edits the lead for that many days.
        stale = frappe.utils.add_to_date(None, days=-untouched_days)
        frappe.db.set_value("Lead", lead.name, "modified", stale, update_modified=False)
        return lead

    def _count(self, compute) -> int:
        result = compute(self.user, COMPANY)
        return result.count if result else 0

    def test_s1_counts_quotation_expiring_in_3_days(self):
        before = self._count(home_signals._quotations_expiring)
        self._quotation(3)
        result = home_signals._quotations_expiring(self.user, None)
        self.assertEqual(result.count, before + 1)
        self.assertEqual(result.ask, "Which quotations expire in the next 7 days?")

    def test_s1_ignores_quotation_expiring_in_10_days(self):
        before = self._count(home_signals._quotations_expiring)
        self._quotation(10)
        self.assertEqual(self._count(home_signals._quotations_expiring), before)

    def test_s2_counts_undelivered_order_past_date(self):
        before = self._count(home_signals._late_sales_orders)
        self._sales_order()
        result = home_signals._late_sales_orders(self.user, COMPANY)
        self.assertEqual(result.count, before + 1)
        self.assertEqual(result.ask, f"Which sales orders for {COMPANY} are past their delivery date?")
        self.assertEqual(
            home_signals._late_sales_orders(self.user, None).ask,
            "Which sales orders are past their delivery date?",
        )

    def test_s2_ignores_closed_order(self):
        before = self._count(home_signals._late_sales_orders)
        order = self._sales_order()
        frappe.db.set_value("Sales Order", order.name, "status", "Closed", update_modified=False)
        self.assertEqual(self._count(home_signals._late_sales_orders), before)

    def test_s2_is_scoped_to_company(self):
        order = self._sales_order()
        other = home_signals._late_sales_orders(self.user, "Some Other Company")
        self.assertEqual(other.count, 0, order.name)

    def test_s3_counts_lead_owned_by_user_untouched_20_days(self):
        before = self._count(home_signals._stale_leads)
        self._lead(self.user)
        self.assertEqual(self._count(home_signals._stale_leads), before + 1)

    def test_s3_ignores_recently_touched_lead(self):
        before = self._count(home_signals._stale_leads)
        self._lead(self.user, untouched_days=2)
        self.assertEqual(self._count(home_signals._stale_leads), before)

    def test_s3_ignores_lead_owned_by_someone_else(self):
        before = self._count(home_signals._stale_leads)
        lead = self._lead("Administrator")
        # Manufactured: production reaches this when a user creates a lead and assigns it to a colleague.
        frappe.db.set_value("Lead", lead.name, "owner", self.user, update_modified=False)
        self.assertEqual(self._count(home_signals._stale_leads), before)

    @unittest.skipUnless("crm" in frappe.get_installed_apps(), "needs the CRM app")
    def test_s3_counts_open_crm_deal_but_not_a_won_one(self):
        # CRM Deal.status is a Link to CRM Deal Status; the closed ones are those typed Won or Lost.
        before = self._count(home_signals._stale_leads)
        for status in ("Qualification", "Won"):
            suffix = frappe.generate_hash(length=6)
            organization = frappe.get_doc(
                {"doctype": "CRM Organization", "organization_name": f"Signal Org {suffix}"}
            ).insert(ignore_permissions=True)
            deal = frappe.get_doc(
                {
                    "doctype": "CRM Deal",
                    "organization": organization.name,
                    "status": status,
                    "deal_owner": self.user,
                }
            ).insert(ignore_permissions=True)
            frappe.db.set_value(
                "CRM Deal", deal.name, "modified", add_days(today(), -20), update_modified=False
            )
        self.assertEqual(self._count(home_signals._stale_leads), before + 1)

    def test_s3_skips_crm_doctypes_when_crm_absent(self):
        self._lead(self.user)
        counted: list[str] = []
        real_count = home_signals.count_visible

        def spy(doctype, filters, user):
            counted.append(doctype)
            return real_count(doctype, filters, user)

        crm_absent = patch.object(home_signals, "_crm_installed", return_value=False)
        spied = patch.object(home_signals, "count_visible", side_effect=spy)
        logged = patch.object(home_signals.frappe, "log_error")
        with crm_absent, spied, logged as log_error:
            result = home_signals._stale_leads(self.user, None)
        self.assertGreaterEqual(result.count, 1)
        self.assertEqual(counted, ["Lead", "Opportunity"])
        log_error.assert_not_called()
