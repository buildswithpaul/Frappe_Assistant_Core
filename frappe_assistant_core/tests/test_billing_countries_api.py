# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The billing form's country list comes from the site's Country table.

It used to be nine hardcoded countries, so a customer in Nairobi could only
pick "United States" and was invoiced there.
"""

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestBillingCountriesApi(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; tests run in isolated transaction
        frappe.set_user("Administrator")

    def tearDown(self):
        # nosemgrep: frappe-setuser — restore the bootstrap user
        frappe.set_user("Administrator")
        super().tearDown()

    def test_every_country_with_a_code_is_offered(self):
        from frappe_assistant_core.chat.api.billing.combined import get_billing_countries

        countries = get_billing_countries()

        self.assertIn({"code": "KE", "label": "Kenya"}, countries)
        self.assertIn({"code": "US", "label": "United States"}, countries)
        self.assertEqual(len(countries), frappe.db.count("Country", {"code": ["is", "set"]}))

    def test_india_is_first_and_the_rest_are_alphabetical(self):
        from frappe_assistant_core.chat.api.billing.combined import get_billing_countries

        countries = get_billing_countries()

        self.assertEqual(countries[0], {"code": "IN", "label": "India"})
        rest = [c["label"] for c in countries[1:]]
        self.assertEqual(rest, sorted(rest, key=str.lower))

    def test_only_system_managers_can_read_it(self):
        from frappe_assistant_core.chat.api.billing.combined import get_billing_countries

        # nosemgrep: frappe-setuser — exercising the permission check
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            get_billing_countries()
