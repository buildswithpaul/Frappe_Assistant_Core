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
HR_IDS = ["leave_to_approve", "expense_claims_to_approve"]


class TestHrSignalCatalogue(unittest.TestCase):
    """Pure tests: nothing here touches the database."""

    def test_hr_signals_skipped_without_hrms(self):
        signals = [s for s in home_signals.CATALOGUE if s.id in HR_IDS]
        self.assertEqual(len(signals), 2)
        for signal in signals:
            self.assertFalse(home_signals._is_applicable(signal, "x@example.com", ["hr"], ["frappe"]))

    def test_hr_signals_registered_after_stock_with_hr_lens(self):
        ids = [signal.id for signal in home_signals.CATALOGUE]
        stock_last = ids.index("pending_material_requests")
        self.assertEqual(ids[stock_last + 1 : stock_last + 1 + len(HR_IDS)], HR_IDS)
        for signal in home_signals.CATALOGUE[stock_last + 1 :]:
            self.assertEqual(signal.lenses, ("hr",))


@unittest.skipUnless(
    "hrms" in frappe.get_installed_apps() and frappe.db.exists("Company", COMPANY),
    "needs HRMS and the demo company",
)
class TestHrSignals(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addClassCleanup(frappe.clear_cache)

    def setUp(self):
        super().setUp()
        self.user = self.make_throwaway_user("hrmanager", roles=("HR Manager", "Expense Approver"))
        self.other_user = self.make_throwaway_user("otherapprover", roles=("HR Manager",))
        self.employee = self._employee()
        self._assign_holiday_list()
        self.leave_type = self._leave_type()

    def _employee(self) -> str:
        return (
            frappe.get_doc(
                {
                    "doctype": "Employee",
                    "first_name": f"Signal{frappe.generate_hash(length=6)}",
                    "gender": frappe.db.get_value("Gender", {}, "name"),
                    "date_of_birth": "1990-01-01",
                    "date_of_joining": add_days(today(), -400),
                    "company": COMPANY,
                    "status": "Active",
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def _assign_holiday_list(self) -> None:
        # Production path: HR assigns a Holiday List to the employee; leave validation requires one.
        holiday_list = frappe.get_doc(
            {
                "doctype": "Holiday List",
                "holiday_list_name": f"Signal HL {frappe.generate_hash(length=6)}",
                "from_date": add_days(today(), -30),
                "to_date": add_days(today(), 365),
            }
        ).insert(ignore_permissions=True)
        assignment = frappe.get_doc(
            {
                "doctype": "Holiday List Assignment",
                "applicable_for": "Employee",
                "assigned_to": self.employee,
                "holiday_list": holiday_list.name,
                "from_date": add_days(today(), -30),
            }
        ).insert(ignore_permissions=True)
        assignment.submit()

    def _expense_claim_type(self) -> str:
        return (
            frappe.get_doc(
                {
                    "doctype": "Expense Claim Type",
                    "expense_type": f"Signal Expense {frappe.generate_hash(length=6)}",
                    "accounts": [{"company": COMPANY, "default_account": f"GST Expense - {ABBR}"}],
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def _leave_type(self) -> str:
        # Leave without pay needs no allocation, so the application passes HR's balance validation.
        return (
            frappe.get_doc(
                {
                    "doctype": "Leave Type",
                    "leave_type_name": f"Signal LWP {frappe.generate_hash(length=6)}",
                    "is_lwp": 1,
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def _leave(self, approver: str, starts_in_days: int):
        start = add_days(today(), starts_in_days)
        return frappe.get_doc(
            {
                "doctype": "Leave Application",
                "employee": self.employee,
                "leave_type": self.leave_type,
                "company": COMPANY,
                "from_date": start,
                "to_date": start,
                "leave_approver": approver,
                "status": "Open",
            }
        ).insert(ignore_permissions=True)

    def _claim(self, approver: str):
        return frappe.get_doc(
            {
                "doctype": "Expense Claim",
                "employee": self.employee,
                "company": COMPANY,
                "expense_approver": approver,
                "exchange_rate": 1,
                "approval_status": "Draft",
                "expenses": [
                    {
                        "expense_date": today(),
                        "expense_type": self._expense_claim_type(),
                        "amount": 100,
                        "sanctioned_amount": 100,
                    }
                ],
            }
        ).insert(ignore_permissions=True)

    def _count(self, compute) -> int:
        result = compute(self.user, COMPANY)
        return result.count if result else 0

    def test_h1_counts_open_leave_for_approver(self):
        before = self._count(home_signals._leave_to_approve)
        self._leave(self.user, starts_in_days=60)
        result = home_signals._leave_to_approve(self.user, COMPANY)
        self.assertEqual(result.count, before + 1)
        self.assertEqual(result.ask, "Show leave applications waiting for my approval")

    def test_h1_detail_counts_leave_starting_within_three_days(self):
        self._leave(self.user, starts_in_days=2)
        result = home_signals._leave_to_approve(self.user, COMPANY)
        self.assertRegex(result.detail, r"in the next 3 days$")
        self.assertNotIn("None of them", result.detail)
        self._leave(self.user, starts_in_days=90)
        later = home_signals._leave_to_approve(self.user, COMPANY)
        self.assertEqual(later.count, result.count + 1)
        self.assertEqual(later.detail, result.detail)

    def test_h1_ignores_leave_for_other_approver(self):
        before = self._count(home_signals._leave_to_approve)
        self._leave(self.other_user, starts_in_days=2)
        self.assertEqual(self._count(home_signals._leave_to_approve), before)

    def test_h2_counts_draft_claim_for_approver(self):
        before = self._count(home_signals._expense_claims_to_approve)
        self._claim(self.other_user)
        self.assertEqual(self._count(home_signals._expense_claims_to_approve), before)
        self._claim(self.user)
        result = home_signals._expense_claims_to_approve(self.user, COMPANY)
        self.assertEqual(result.count, before + 1)
        self.assertEqual(result.ask, "Show expense claims waiting for my approval")
