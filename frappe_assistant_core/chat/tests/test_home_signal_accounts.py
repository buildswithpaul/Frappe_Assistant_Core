# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

import unittest

import frappe
from frappe.utils import add_days, today

from frappe_assistant_core.chat import home_signals
from frappe_assistant_core.chat.home_signals import money_summary
from frappe_assistant_core.tests.base_test import BaseAssistantTest

COMPANY = "Northwind Demo Co"
OTHER_COMPANY = "Frappe Assistant Cloud"
ABBR = "NDC"
ITEM = "NW-OLIVEOIL-5L"
ACCOUNTS_IDS = {"overdue_receivables", "payables_due", "unreconciled_bank"}


class TestMoneySummary(unittest.TestCase):
    def test_single_currency_sums(self):
        rows = [
            {"outstanding_amount": 100.0, "currency": "INR"},
            {"outstanding_amount": 50.5, "currency": "INR"},
        ]
        self.assertEqual(money_summary(rows), (150.5, "INR"))

    def test_mixed_currency_returns_none(self):
        rows = [
            {"outstanding_amount": 100.0, "currency": "INR"},
            {"outstanding_amount": 5.0, "currency": "USD"},
        ]
        self.assertEqual(money_summary(rows), (None, None))

    def test_empty_rows(self):
        self.assertEqual(money_summary([]), (None, None))


@unittest.skipUnless(
    "erpnext" in frappe.get_installed_apps() and frappe.db.exists("Company", COMPANY),
    "needs ERPNext and the demo company",
)
class TestAccountsSignals(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The defaults cache lives in Redis and survives the class rollback.
        cls.addClassCleanup(frappe.clear_cache)

    def setUp(self):
        super().setUp()
        self.customer = self._customer("Signal Overdue Customer")
        self.user = self.make_throwaway_user("accountant", roles=("Accounts Manager",))
        # Manufactured: production reaches this when an administrator restricts the accountant to
        # one Customer through a User Permission; it also isolates the user from other site data.
        frappe.get_doc(
            {"doctype": "User Permission", "user": self.user, "allow": "Customer", "for_value": self.customer}
        ).insert(ignore_permissions=True)
        frappe.clear_cache(user=self.user)

    def _customer(self, name: str) -> str:
        suffix = frappe.generate_hash(length=6)
        return (
            frappe.get_doc({"doctype": "Customer", "customer_name": f"{name} {suffix}"})
            .insert(ignore_permissions=True)
            .name
        )

    def _invoice(self, days_old: int, customer: str | None = None, rate: int = 100, **kwargs):
        # Production path: an accountant saves and submits a Sales Invoice. The ERPNext test helper
        # `create_sales_invoice` cannot be imported on this site (its module creates a Fiscal Year
        # that overlaps an existing one), so the same insert-and-submit is done here.
        posting = add_days(today(), -days_old)
        invoice = frappe.get_doc(
            {
                "doctype": "Sales Invoice",
                "company": COMPANY,
                "customer": customer or self.customer,
                "debit_to": f"Debtors - {ABBR}",
                "currency": "INR",
                "conversion_rate": 1,
                "set_posting_time": 1,
                "posting_date": posting,
                "due_date": posting,
                "cost_center": f"Main - {ABBR}",
                **kwargs,
                "items": [
                    {
                        "item_code": ITEM,
                        "qty": 1,
                        "rate": rate,
                        "income_account": f"Sales - {ABBR}",
                        "expense_account": f"Cost of Goods Sold - {ABBR}",
                        "cost_center": f"Main - {ABBR}",
                    }
                ],
            }
        )
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        invoice.load_from_db()
        return invoice

    def _set_default_company(self, company: str) -> None:
        # Production reaches this when a user has a Company default of their own (Desk user
        # defaults): get_defaults(user) merges it over the global default.
        frappe.defaults.set_user_default("company", company, self.user)
        self.addCleanup(self._clear_default_company)
        frappe.clear_cache(user=self.user)

    def _clear_default_company(self) -> None:
        frappe.defaults.clear_user_default("company", self.user)
        frappe.clear_cache(user=self.user)

    def _a1(self):
        return home_signals._overdue_receivables(self.user, COMPANY)

    def test_a1_counts_invoice_overdue_90_days(self):
        invoice = self._invoice(90, rate=250)
        result = self._a1()
        self.assertEqual(result.count, 1)
        self.assertEqual(result.title, "invoice overdue by 60+ days")
        self.assertEqual(result.amount, invoice.outstanding_amount)
        self.assertEqual(result.currency, "INR")
        name = frappe.db.get_value("Customer", self.customer, "customer_name")
        self.assertTrue(result.detail.endswith(f", all from {name}"), result.detail)
        self.assertEqual(result.ask, f"Show invoices for {COMPANY} overdue by more than 60 days, by customer")
        self.assertEqual(result.action, "Draft payment reminders")

    def test_a1_detail_names_top_two_customers_by_outstanding(self):
        big = self._customer("Big Debtor")
        mid = self._customer("Mid Debtor")
        small = self._customer("Small Debtor")
        for customer in (big, mid, small):
            frappe.get_doc(
                {"doctype": "User Permission", "user": self.user, "allow": "Customer", "for_value": customer}
            ).insert(ignore_permissions=True)
        frappe.clear_cache(user=self.user)
        self._invoice(90, customer=small, rate=10)
        self._invoice(90, customer=big, rate=900)
        self._invoice(90, customer=mid, rate=300)
        detail = self._a1().detail
        self.assertIn(", mostly ", detail)
        names = [frappe.db.get_value("Customer", c, "customer_name") for c in (big, mid, small)]
        self.assertIn(names[0], detail)
        self.assertIn(names[1], detail)
        self.assertNotIn(names[2], detail)
        self.assertLess(detail.index(names[0]), detail.index(names[1]))

    def test_a1_ignores_invoice_overdue_30_days(self):
        self._invoice(30)
        self.assertIsNone(self._a1())

    def test_a1_ignores_paid_invoice(self):
        from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

        invoice = self._invoice(90)
        self.assertEqual(self._a1().count, 1)
        # Production path: an accountant records a Payment Entry against the invoice from its form.
        payment = get_payment_entry("Sales Invoice", invoice.name)
        payment.paid_to = f"Cash - {ABBR}"
        payment.reference_no = "signal-test"
        payment.reference_date = today()
        payment.insert(ignore_permissions=True).submit()
        self.assertEqual(frappe.db.get_value("Sales Invoice", invoice.name, "outstanding_amount"), 0)
        self.assertIsNone(self._a1())

    def test_a1_scopes_to_default_company(self):
        self._invoice(90)
        self.assertEqual(self._a1().count, 1)
        # The payload passes the user's default Company into compute(); another company sees none.
        self.assertIsNone(home_signals._overdue_receivables(self.user, OTHER_COMPANY))
        # With no default company nothing is filtered and the ask does not name one.
        unscoped = home_signals._overdue_receivables(self.user, None)
        self.assertEqual(unscoped.count, 1)
        self.assertEqual(unscoped.ask, "Show invoices overdue by more than 60 days, by customer")

    def test_a1_runs_through_user_default_company(self):
        self._invoice(90)
        self._set_default_company(OTHER_COMPANY)
        payload = home_signals.compute_home_signals(self.user)
        self.assertEqual(payload["company"], OTHER_COMPANY)
        self.assertNotIn("overdue_receivables", {item["id"] for item in payload["items"]})

        self._set_default_company(COMPANY)
        payload = home_signals.compute_home_signals(self.user)
        self.assertEqual(payload["company"], COMPANY)
        self.assertIn("overdue_receivables", {item["id"] for item in payload["items"]})

    def test_a1_mixed_currency_omits_amount(self):
        self._invoice(90)
        usd_account = f"Debtors USD - {ABBR}"
        if not frappe.db.exists("Account", usd_account):
            # Manufactured: production reaches this when a company keeps a receivable account in USD.
            frappe.get_doc(
                {
                    "doctype": "Account",
                    "account_name": "Debtors USD",
                    "parent_account": frappe.db.get_value("Account", f"Debtors - {ABBR}", "parent_account"),
                    "company": COMPANY,
                    "account_type": "Receivable",
                    "account_currency": "USD",
                }
            ).insert(ignore_permissions=True)
        # A customer already booked in INR cannot take a USD receivable, so the USD invoice has its own.
        usd_customer = self._customer("Signal Dollar Customer")
        frappe.get_doc(
            {"doctype": "User Permission", "user": self.user, "allow": "Customer", "for_value": usd_customer}
        ).insert(ignore_permissions=True)
        frappe.clear_cache(user=self.user)
        self._invoice(90, customer=usd_customer, currency="USD", conversion_rate=80, debit_to=usd_account)
        result = self._a1()
        self.assertEqual(result.count, 2)
        self.assertIsNone(result.amount)
        self.assertIsNone(result.currency)
        for symbol in ("INR", "USD", "₹", "$"):
            self.assertNotIn(symbol, result.detail)

    def test_accounts_signals_registered_after_todos(self):
        ids = [signal.id for signal in home_signals.CATALOGUE]
        self.assertEqual(ids[:2], ["approvals", "todos"])
        self.assertEqual(set(ids[2 : 2 + len(ACCOUNTS_IDS)]), ACCOUNTS_IDS)
        for signal in home_signals.CATALOGUE[2 : 2 + len(ACCOUNTS_IDS)]:
            self.assertEqual(signal.lenses, ("accounts",))

    def test_accounts_user_sees_overdue_receivables_first(self):
        self._invoice(90)
        self._set_default_company(COMPANY)
        payload = home_signals.compute_home_signals(self.user)
        self.assertIn("accounts", payload["lenses"])
        self.assertEqual(payload["items"][0]["id"], "overdue_receivables")

    def test_accounts_signals_absent_for_sales_only_user(self):
        self._invoice(90)
        sales_user = self.make_throwaway_user("seller", roles=("Sales Manager",))
        payload = home_signals.compute_home_signals(sales_user)
        self.assertNotIn("accounts", payload["lenses"])
        self.assertFalse(ACCOUNTS_IDS & {item["id"] for item in payload["items"]})

    def _supplier(self) -> str:
        supplier = (
            frappe.get_doc(
                {
                    "doctype": "Supplier",
                    "supplier_name": f"Signal Supplier {frappe.generate_hash(length=6)}",
                    "supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}),
                }
            )
            .insert(ignore_permissions=True)
            .name
        )
        frappe.get_doc(
            {"doctype": "User Permission", "user": self.user, "allow": "Supplier", "for_value": supplier}
        ).insert(ignore_permissions=True)
        frappe.clear_cache(user=self.user)
        return supplier

    def _bill(self, supplier: str, due_in_days: int):
        # Production path: an accountant saves and submits a Purchase Invoice.
        bill = frappe.get_doc(
            {
                "doctype": "Purchase Invoice",
                "company": COMPANY,
                "supplier": supplier,
                "credit_to": f"Creditors - {ABBR}",
                "currency": "INR",
                "set_posting_time": 1,
                "posting_date": today(),
                "bill_no": frappe.generate_hash(length=6),
                "bill_date": add_days(today(), min(due_in_days, 0)),
                "due_date": add_days(today(), due_in_days),
                "cost_center": f"Main - {ABBR}",
                "items": [
                    {
                        "item_code": ITEM,
                        "qty": 1,
                        "rate": 70,
                        "expense_account": f"Cost of Goods Sold - {ABBR}",
                        "cost_center": f"Main - {ABBR}",
                    }
                ],
            }
        )
        bill.insert(ignore_permissions=True)
        bill.submit()
        return bill

    def test_a2_counts_only_bills_due_within_a_week(self):
        supplier = self._supplier()
        self._bill(supplier, due_in_days=3)
        self._bill(supplier, due_in_days=30)
        self._bill(supplier, due_in_days=-3)
        result = home_signals._payables_due(self.user, COMPANY)
        self.assertEqual(result.count, 1)
        self.assertEqual(result.amount, 70)
        self.assertEqual(result.currency, "INR")
        self.assertEqual(result.ask, f"Which purchase invoices for {COMPANY} fall due in the next 7 days?")
        self.assertEqual(result.action, "See what's due")

    def _bank_account(self) -> str:
        bank = frappe.get_doc(
            {"doctype": "Bank", "bank_name": f"Signal Bank {frappe.generate_hash(length=6)}"}
        )
        bank.insert(ignore_permissions=True)
        account = frappe.get_doc(
            {
                "doctype": "Account",
                "account_name": f"Signal Bank {bank.name}",
                "parent_account": f"Bank Accounts - {ABBR}",
                "company": COMPANY,
                "account_type": "Bank",
            }
        ).insert(ignore_permissions=True)
        return (
            frappe.get_doc(
                {
                    "doctype": "Bank Account",
                    "account_name": f"Signal {bank.name}",
                    "bank": bank.name,
                    "account": account.name,
                    "company": COMPANY,
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def test_a3_counts_only_unreconciled_lines(self):
        bank_account = self._bank_account()
        before = home_signals._unreconciled_bank(self.user, COMPANY).count
        self._bank_line(bank_account, "Unreconciled")
        self._bank_line(bank_account, "Reconciled")
        self.assertEqual(home_signals._unreconciled_bank(self.user, COMPANY).count, before + 1)

    def _bank_line(self, bank_account: str, status: str) -> None:
        # Manufactured: production imports bank statements, which insert and submit these rows;
        # status is set directly because reconciliation needs a matched voucher.
        line = frappe.get_doc(
            {
                "doctype": "Bank Transaction",
                "date": today(),
                "bank_account": bank_account,
                "company": COMPANY,
                "deposit": 10,
                "currency": "INR",
            }
        ).insert(ignore_permissions=True)
        line.submit()
        frappe.db.set_value("Bank Transaction", line.name, "status", status, update_modified=False)
