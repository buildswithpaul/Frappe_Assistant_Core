# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
list_documents(group_by=..., aggregate=[...]): totals computed by the database, over only
the records the user may read, so the model never has to add up listed rows itself.

Runs against a real custom submittable DocType and real records. Nothing here is mocked.
"""

from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.database.database import Database

from frappe_assistant_core.core.security_config import ADMIN_ONLY_FIELDS
from frappe_assistant_core.plugins.core.tools.list_documents import DocumentList, aggregate_query_fields
from frappe_assistant_core.tests.base_test import BaseAssistantTest

SALE = "FAC Group Sale"
REGION_ALLOWED = "India"
REGION_OTHER = "Germany"


@contextmanager
def _committing_ddl():
    """Run schema changes that commit for real, and commit nothing else (see test_doctype_topic_search)."""
    frappe.db.rollback()
    try:
        with patch.object(Database, "check_implicit_commit"):
            yield
    finally:
        Database.commit(frappe.db)


def _remove_fixture() -> None:
    # nosemgrep: frappe-setuser — fixture teardown runs as Administrator whatever the test left
    frappe.set_user("Administrator")
    with _committing_ddl():
        if frappe.db.exists("DocType", SALE):
            frappe.delete_doc("DocType", SALE, force=True, ignore_permissions=True)
        # A crash between CREATE TABLE and the DocType commit leaves a table with no row.
        frappe.db.sql_ddl(f"drop table if exists `tab{SALE}`")


def _create_fixture() -> None:
    # Production reaches this the way a site admin does: a custom submittable DocType built in the
    # UI (custom=1, module "Custom"), with System Manager the only role that can touch it.
    permissions = [
        {
            "role": "System Manager",
            "read": 1,
            "write": 1,
            "create": 1,
            "submit": 1,
            "cancel": 1,
        },
        {"role": "Assistant User", "read": 1},
    ]
    fields = [
        {"fieldname": "region", "fieldtype": "Link", "options": "Country", "label": "Region"},
        {"fieldname": "details_section", "fieldtype": "Section Break", "label": "Details"},
        {"fieldname": "category", "fieldtype": "Data", "label": "Category"},
        {"fieldname": "amount", "fieldtype": "Currency", "label": "Amount"},
        {"fieldname": "quantity", "fieldtype": "Int", "label": "Quantity"},
        # System Manager holds no permlevel-1 permission row, so this field is out of reach.
        {"fieldname": "margin", "fieldtype": "Currency", "label": "Margin", "permlevel": 1},
        # Named in SENSITIVE_FIELDS["all_doctypes"].
        {"fieldname": "iban", "fieldtype": "Currency", "label": "IBAN"},
    ]
    with _committing_ddl():
        frappe.get_doc(
            {
                "doctype": "DocType",
                "name": SALE,
                "module": "Custom",
                "custom": 1,
                "is_submittable": 1,
                "fields": fields,
                "permissions": permissions,
            }
        ).insert(ignore_permissions=True)


class TestListDocumentsGroupBy(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Registered before anything is created, so a failure midway still cleans up.
        cls.addClassCleanup(_remove_fixture)
        # A crashed earlier run may have left the fixture behind.
        _remove_fixture()
        _create_fixture()

    def setUp(self):
        super().setUp()
        # The class shares one transaction, so rows from an earlier test would leak into these totals.
        frappe.db.delete(SALE)

    def _sale(self, region, category, amount, quantity=1, submit=True, cancel=False):
        doc = frappe.get_doc(
            {
                "doctype": SALE,
                "region": region,
                "category": category,
                "amount": amount,
                "quantity": quantity,
                "iban": 1,
            }
        ).insert(ignore_permissions=True)
        if submit or cancel:
            doc.submit()
        if cancel:
            doc.cancel()
        return doc

    def _seed(self):
        self._sale(REGION_ALLOWED, "Hardware", 100.50, 2)
        self._sale(REGION_ALLOWED, "Hardware", 200, 3)
        self._sale(REGION_ALLOWED, "Services", 50, 1)
        self._sale(REGION_OTHER, "Hardware", 1000, 10)
        self._sale(REGION_OTHER, "Services", 400, 4)

    def _run(self, **arguments):
        return DocumentList().execute({"doctype": SALE, **arguments})

    @staticmethod
    def _by_group(result):
        return {row["group_value"]: row for row in result["rows"]}

    def test_sum_grouped_by_field(self):
        self._seed()

        result = self._run(
            group_by="category",
            aggregate=[
                {"function": "sum", "field": "amount"},
                {"function": "count", "field": "name"},
                {"function": "avg", "field": "quantity"},
                {"function": "max", "field": "amount"},
            ],
        )

        self.assertTrue(result["success"], result)
        self.assertEqual(result["group_by"], "category")
        self.assertEqual(result["row_count"], 2)
        rows = self._by_group(result)
        self.assertAlmostEqual(rows["Hardware"]["sum_amount"], 1300.50)
        self.assertEqual(rows["Hardware"]["count_name"], 3)
        self.assertAlmostEqual(rows["Hardware"]["avg_quantity"], 5.0)
        self.assertAlmostEqual(rows["Hardware"]["max_amount"], 1000)
        self.assertAlmostEqual(rows["Services"]["sum_amount"], 450)
        self.assertEqual(rows["Services"]["count_name"], 2)

    def test_group_by_alone_counts_records_per_group(self):
        self._seed()

        result = self._run(group_by="region")

        self.assertTrue(result["success"], result)
        rows = self._by_group(result)
        self.assertEqual(rows[REGION_ALLOWED]["count_name"], 3)
        self.assertEqual(rows[REGION_OTHER]["count_name"], 2)

    def test_aggregate_without_group_by_returns_one_total_row(self):
        self._seed()

        result = self._run(aggregate=[{"function": "sum", "field": "amount"}])

        self.assertTrue(result["success"], result)
        self.assertIsNone(result["group_by"])
        self.assertEqual(result["row_count"], 1)
        self.assertAlmostEqual(result["rows"][0]["sum_amount"], 1750.50)
        self.assertNotIn("group_value", result["rows"][0])

    def test_totals_respect_user_permissions(self):
        self._seed()
        user = self.make_throwaway_user("grouper", roles=("System Manager",))
        # An admin restricts the user with a User Permission on the Country link.
        frappe.get_doc(
            {"doctype": "User Permission", "user": user, "allow": "Country", "for_value": REGION_ALLOWED}
        ).insert(ignore_permissions=True)
        # nosemgrep: frappe-setuser — the grouped totals must be computed as the restricted user
        frappe.set_user(user)
        self.addCleanup(frappe.set_user, "Administrator")

        result = self._run(group_by="category", aggregate=[{"function": "sum", "field": "amount"}])

        self.assertTrue(result["success"], result)
        rows = self._by_group(result)
        self.assertAlmostEqual(rows["Hardware"]["sum_amount"], 300.50)
        self.assertAlmostEqual(rows["Services"]["sum_amount"], 50)

    def test_submittable_default_excludes_cancelled_and_draft(self):
        self._sale(REGION_ALLOWED, "Hardware", 100)
        self._sale(REGION_ALLOWED, "Hardware", 20, submit=False)
        self._sale(REGION_ALLOWED, "Hardware", 3, cancel=True)

        result = self._run(group_by="category", aggregate=[{"function": "sum", "field": "amount"}])

        self.assertTrue(result["success"], result)
        self.assertTrue(result["docstatus_defaulted"])
        self.assertEqual(self._by_group(result)["Hardware"]["sum_amount"], 100)

        explicit = self._run(
            group_by="category",
            filters={"docstatus": 2},
            aggregate=[{"function": "sum", "field": "amount"}],
        )
        self.assertFalse(explicit["docstatus_defaulted"])
        self.assertEqual(self._by_group(explicit)["Hardware"]["sum_amount"], 3)

    def test_group_by_restricted_field_is_refused(self):
        self._seed()
        user = self.make_throwaway_user("grouper", roles=("System Manager",))
        # nosemgrep: frappe-setuser — permlevel is judged for the acting user
        frappe.set_user(user)
        self.addCleanup(frappe.set_user, "Administrator")

        # Frappe v16 also rejects these in get_list, but v15 would run them: our own message is the proof.
        expected = {
            "margin": "permission to read the field",  # permlevel 1, above the user's access
            "iban": "restricted",  # SENSITIVE_FIELDS
        }
        for restricted, message in expected.items():
            with self.subTest(field=restricted):
                result = self._run(group_by=restricted)
                self.assertFalse(result["success"])
                self.assertIn(message, result["error"])

        summed = self._run(aggregate=[{"function": "sum", "field": "margin"}])
        self.assertFalse(summed["success"])
        self.assertIn("permission to read the field", summed["error"])

    def test_sum_of_non_numeric_field_is_refused(self):
        self._seed()

        for field in ("category", "region", "name"):
            with self.subTest(field=field):
                result = self._run(aggregate=[{"function": "sum", "field": field}])
                self.assertFalse(result["success"])
                self.assertIn("numeric", result["error"])

    def test_unknown_function_or_field_is_refused(self):
        self._seed()
        # Each is refused by our own validation, not left for the database to reject.
        cases = {
            "unknown function": (
                {"aggregate": [{"function": "median", "field": "amount"}]},
                "Unknown aggregate",
            ),
            "unknown aggregate field": ({"aggregate": [{"function": "sum", "field": "nope"}]}, "not a field"),
            "layout field": ({"group_by": "details_section"}, "not a field"),
            "unknown group_by": ({"group_by": "nope"}, "not a field"),
            "injection in field": (
                {"aggregate": [{"function": "sum", "field": "amount) from tabUser -- "}]},
                "not a valid field name",
            ),
            "injection in group_by": (
                {"group_by": "category`; drop table tabUser; -- "},
                "not a valid field name",
            ),
            "too many aggregates": ({"aggregate": [{"function": "count", "field": "name"}] * 6}, "at most 5"),
        }
        for label, (arguments, expected) in cases.items():
            with self.subTest(label):
                result = self._run(**arguments)
                self.assertFalse(result["success"], result)
                self.assertIn(expected, result["error"])

    def test_limit_reports_when_groups_were_cut_off(self):
        self._seed()

        result = self._run(group_by="category", limit=1)

        self.assertTrue(result["success"], result)
        self.assertEqual(result["row_count"], 1)
        self.assertTrue(result["has_more"])

    def test_v15_string_form_quotes_each_validated_field(self):
        specs = [
            {"function": "sum", "field": "amount", "alias": "sum_amount"},
            {"function": "count", "field": "name", "alias": "count_name"},
        ]

        self.assertEqual(
            aggregate_query_fields(specs, "category", v16_form=False),
            ["category", "sum(`amount`) as sum_amount", "count(`name`) as count_name"],
        )
        self.assertEqual(
            aggregate_query_fields(specs, None, v16_form=True),
            [{"SUM": "amount", "as": "sum_amount"}, {"COUNT": "name", "as": "count_name"}],
        )

    def test_wholly_admin_only_doctype_is_refused_for_an_assistant_user(self):
        self._seed()
        user = self.make_throwaway_user("assistant", roles=("Assistant User",))
        # nosemgrep: frappe-setuser — the refusal depends on the acting user's FAC role
        frappe.set_user(user)
        self.addCleanup(frappe.set_user, "Administrator")
        aggregate = [{"function": "sum", "field": "amount"}]

        readable = self._run(group_by="category", aggregate=aggregate)
        self.assertTrue(readable["success"], readable)  # the role can otherwise read the DocType

        # FAC ships ADMIN_ONLY_FIELDS entries of "*" (Email Domain, System Settings, ...); the fixture
        # is added to that same dict, so the Assistant User sees exactly what a shipped entry does.
        with patch.dict(ADMIN_ONLY_FIELDS, {SALE: "*"}):
            result = self._run(group_by="category", aggregate=aggregate)

        self.assertFalse(result["success"])
        self.assertIn("restricted", result["error"])
        self.assertNotIn("rows", result)

    def test_virtual_doctype_is_refused(self):
        self._seed()
        real_get_meta = frappe.get_meta
        meta = real_get_meta(SALE)

        def virtual_meta(doctype, *args, **kwargs):
            return meta if doctype == SALE else real_get_meta(doctype, *args, **kwargs)

        # A virtual DocType is one an app backs with its own controller; the tool only reads the
        # meta flag, so the fixture's cached meta carries it for the duration of the call.
        with patch.object(meta, "is_virtual", 1), patch("frappe.get_meta", side_effect=virtual_meta):
            result = self._run(group_by="category", aggregate=[{"function": "sum", "field": "amount"}])

        self.assertFalse(result["success"])
        self.assertIn("virtual", result["error"])
        self.assertNotIn("rows", result)
