# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""A company with the standard chart, and the client's chart as a mapped import session (#34422). A base for
the chart tests, with no tests of its own."""

import frappe

from frappe_assistant_core.tests.test_import_run import ImportRunCase

ACCOUNT_MAPPING = {
    "Name": "account_name",
    "Number": "account_number",
    "Parent": "parent_account",
    "Type": "account_type",
    "Group": "is_group",
}
HEADER = "Name,Number,Parent,Type,Root,Group"

#: The client's chart: four roots, banks, cash, debtors, creditors, sales and rent.
CLIENT_CHART = [
    "Client Assets,,,,,",
    "Client Banks,,Client Assets,,,",
    "HDFC Current,1010,Client Banks,,,",
    "Client Cash Box,1020,Client Assets,,,",
    "Client Debtors,,Client Assets,,,",
    "Acme Customers,1100,Client Debtors,,,",
    "Client Liabilities,,,,,",
    "Client Creditors,,Client Liabilities,,,",
    "Vendor Pool,2100,Client Creditors,,,",
    "Client Income,,,,,",
    "Product Sales,4000,Client Income,,,",
    "Client Expenses,,,,,",
    "Office Rent,5000,Client Expenses,,,",
]


class ChartCase(ImportRunCase):
    def setUp(self):
        super().setUp()
        self.abbr = "T" + frappe.generate_hash(length=4).upper()
        self.company = f"Chart Co {self.tag}"
        frappe.get_doc(
            {
                "doctype": "Company",
                "company_name": self.company,
                "abbr": self.abbr,
                "default_currency": "JPY",
                "country": "Japan",
                "create_chart_of_accounts_based_on": "Standard Template",
                "chart_of_accounts": "Standard",
            }
        ).insert()
        frappe.db.delete("DefaultValue", {"defkey": ["like", "fac_old_id::Account::%"]})
        self.system = f"chart{self.tag}"

    def _chart(self, rows=None, header=HEADER, mapping=None, name="chart.csv"):
        """The client's chart opened and mapped to Account fields, as the user does with set_column_mapping."""
        content = "\n".join([header, *(CLIENT_CHART if rows is None else rows)]) + "\n"
        started = self._run("start_import_session", {"file_url": self._file(name, content.encode()).file_url})
        self.assertTrue(started["success"], started)
        session = started["result"]["session_id"]
        mapped = self._run(
            "set_column_mapping",
            {"session": session, "doctype": "Account", "mapping": mapping or ACCOUNT_MAPPING},
        )
        self.assertTrue(mapped["success"], mapped)
        return session

    def _check(self, session, **arguments):
        checked = self._run("dry_run_import", {"session": session, "chart": arguments})
        self.assertTrue(checked["success"], checked)
        return checked["result"]

    def _account(self, name):
        return frappe.db.get_value(
            "Account",
            {"company": self.company, "account_name": name},
            ["name", "parent_account", "root_type", "account_type", "is_group", "account_number"],
            as_dict=True,
        )

    def _clear_references(self):
        """What the company's own setup puts outside the chart that points at its accounts (tax templates,
        item tax templates, the modes of payment's cash account), removed: a replace is refused while they
        are there."""
        for doctype in (
            "Sales Taxes and Charges Template",
            "Purchase Taxes and Charges Template",
            "Item Tax Template",
        ):
            for name in frappe.get_all(doctype, filters={"company": self.company}, pluck="name"):
                frappe.delete_doc(doctype, name, force=True)
        frappe.db.delete("Mode of Payment Account", {"company": self.company})

    def _make_a_ledger_entry(self):
        """A submitted journal entry between a cash and an equity account of the company."""

        def leaf(**filters):
            return frappe.get_all(
                "Account", filters={"company": self.company, "is_group": 0, **filters}, pluck="name", limit=1
            )[0]

        entry = frappe.get_doc(
            {
                "doctype": "Journal Entry",
                "company": self.company,
                "posting_date": frappe.utils.today(),
                "accounts": [
                    {"account": leaf(account_type="Cash"), "debit_in_account_currency": 10},
                    {"account": leaf(root_type="Equity"), "credit_in_account_currency": 10},
                ],
            }
        ).insert()
        entry.submit()
