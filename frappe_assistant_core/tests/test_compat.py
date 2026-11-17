# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""The version helpers (#34419 P0.1): each answers for the site the test runs on, v15 or v16."""

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils import compat


class TestCompat(BaseAssistantTest):
    def test_frappe_major_is_the_installed_major_version(self):
        self.assertEqual(compat.frappe_major(), int(frappe.__version__.split(".")[0]))
        self.assertIn(compat.frappe_major(), (15, 16))

    def test_erpnext_major_is_the_installed_major_version(self):
        import erpnext

        self.assertEqual(compat.erpnext_major(), int(erpnext.__version__.split(".")[0]))

    def test_erpnext_major_is_none_when_erpnext_is_not_installed(self):
        from unittest.mock import patch

        with patch.object(frappe, "get_installed_apps", autospec=True, return_value=["frappe"]):
            self.assertIsNone(compat.erpnext_major())

    def test_major_of_an_unreadable_version_is_none(self):
        self.assertEqual(compat._major("16.52.0"), 16)
        self.assertIsNone(compat._major(None))
        self.assertIsNone(compat._major("develop"))

    def test_india_compliance_is_found_when_installed(self):
        self.assertEqual(compat.has_india_compliance(), "india_compliance" in frappe.get_installed_apps())

    def test_has_field_follows_the_sites_schema(self):
        self.assertTrue(compat.has_field("Customer", "customer_name"))
        self.assertFalse(compat.has_field("Customer", "no_such_field_" + frappe.generate_hash(length=6)))
        # India Compliance adds gstin to Customer
        self.assertEqual(compat.has_field("Customer", "gstin"), compat.has_india_compliance())

    def test_prepare_chart_names_every_account_and_sets_its_currency(self):
        forest = {
            "Assets": {
                "root_type": "Asset",
                "Current Assets": {
                    "Bank": {"account_type": "Bank", "account_number": "1100"},
                    "Cash": {"account_type": "Cash", "account_currency": "USD"},
                },
            },
            "Income": {"root_type": "Income"},
        }
        chart = compat.prepare_chart(forest, "INR")
        bank = chart["Assets"]["Current Assets"]["Bank"]
        self.assertEqual(bank["account_name"], "Bank")
        self.assertEqual(bank["account_currency"], "INR")
        self.assertEqual(bank["account_number"], "1100")
        self.assertEqual(chart["Assets"]["Current Assets"]["Cash"]["account_currency"], "USD")
        self.assertEqual(chart["Assets"]["account_name"], "Assets")
        self.assertEqual(chart["Income"]["account_currency"], "INR")
        # the account's own keys stay as they were, never turned into child accounts
        self.assertEqual(chart["Assets"]["root_type"], "Asset")

    def test_prepare_chart_leaves_the_chart_passed_in_alone(self):
        forest = {"Assets": {"root_type": "Asset", "Bank": {"account_type": "Bank"}}}
        compat.prepare_chart(forest, "INR")
        self.assertNotIn("account_name", forest["Assets"])
        self.assertNotIn("account_currency", forest["Assets"]["Bank"])

    def test_prepare_chart_keeps_an_accounts_own_name(self):
        chart = compat.prepare_chart(
            {"Assets": {"root_type": "Asset", "Bank": {"account_name": "HDFC"}}}, "INR"
        )
        self.assertEqual(chart["Assets"]["Bank"]["account_name"], "HDFC")
