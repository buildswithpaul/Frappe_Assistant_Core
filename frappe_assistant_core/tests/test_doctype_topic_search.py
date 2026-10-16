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

"""Finding where a topic's data lives: get_doctype_info(topic=...)."""

import unittest
from unittest.mock import patch

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

from frappe_assistant_core.core.security_config import ADMIN_ONLY_FIELDS
from frappe_assistant_core.plugins.core.tools.get_doctype_info import GetDoctypeInfo
from frappe_assistant_core.plugins.core.tools.metadata_tools import MetadataTools
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.tests.ddl_fixtures import committing_ddl

BOOKING = "FAC Topic Booking"
BOOKING_LINE = "FAC Topic Booking Line"
BOOKING_SETTINGS = "FAC Topic Booking Settings"
TODO_CUSTOM_FIELD = "fac_topic_probe"
FIXTURE_DOCTYPES = (BOOKING_LINE, BOOKING_SETTINGS, BOOKING)
HAS_ERPNEXT = "erpnext" in frappe.get_installed_apps()


def _remove_fixtures() -> None:
    """Remove every fixture this module creates; safe when none, some or all exist."""
    # nosemgrep: frappe-setuser — fixture teardown runs as Administrator whatever the test left
    frappe.set_user("Administrator")
    with committing_ddl():
        for doctype in FIXTURE_DOCTYPES:
            if frappe.db.exists("DocType", doctype):
                frappe.delete_doc("DocType", doctype, force=True, ignore_permissions=True)
            # A crash between CREATE TABLE and the DocType commit leaves a table with no row.
            frappe.db.sql_ddl(f"drop table if exists `tab{doctype}`")
        todo_field = f"ToDo-{TODO_CUSTOM_FIELD}"
        if frappe.db.exists("Custom Field", todo_field):
            frappe.delete_doc("Custom Field", todo_field, force=True, ignore_permissions=True)
        # Deleting a Custom Field leaves its column behind.
        frappe.db.sql_ddl(f"alter table `tabToDo` drop column if exists `{TODO_CUSTOM_FIELD}`")
    frappe.clear_cache(doctype="ToDo")


def _doctype_row(topic: str, doctype: str):
    result = MetadataTools.find_doctypes_for_topic(topic, limit=25)
    return next((row for row in result["doctypes"] if row["doctype"] == doctype), None)


def _create_fixtures() -> None:
    """A custom Booking DocType with a child table and a Single, plus a Custom Field on ToDo."""
    # Production reaches this the way a site admin does: custom DocTypes built in the UI
    # (custom=1, module "Custom"), readable by System Manager only.
    permissions = [{"role": "System Manager", "read": 1, "write": 1, "create": 1}]
    note = [{"fieldname": "note", "fieldtype": "Data", "label": "Note"}]
    booking_fields = [
        {"fieldname": "booking_date", "fieldtype": "Date", "label": "Booking Date"},
        {"fieldname": "total_amount", "fieldtype": "Currency", "label": "Total Amount"},
        # System Manager holds no permlevel-1 permission row, so this field is out of reach.
        {"fieldname": "margin", "fieldtype": "Currency", "label": "Margin", "permlevel": 1},
        {"fieldname": "iban", "fieldtype": "Currency", "label": "IBAN"},
    ]
    if HAS_ERPNEXT:
        booking_fields.append(
            {"fieldname": "client", "fieldtype": "Link", "options": "Customer", "label": "Client"}
        )
    with committing_ddl():
        for name, fields, extra in (
            (BOOKING, booking_fields, {}),
            (BOOKING_LINE, note, {"istable": 1}),
            (BOOKING_SETTINGS, note, {"issingle": 1}),
        ):
            frappe.get_doc(
                {
                    "doctype": "DocType",
                    "name": name,
                    "module": "Custom",
                    "custom": 1,
                    "fields": fields,
                    "permissions": permissions,
                    **extra,
                }
            ).insert(ignore_permissions=True)
        create_custom_field("ToDo", {"fieldname": TODO_CUSTOM_FIELD, "fieldtype": "Data", "label": "Probe"})
    frappe.clear_cache(doctype="ToDo")


class TestDoctypeTopicSearch(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Registered before anything is created, so a failure midway still cleans up.
        cls.addClassCleanup(_remove_fixtures)
        # A crashed earlier run may have left fixtures behind.
        _remove_fixtures()
        _create_fixtures()

    def _add_booking_row(self) -> None:
        doc = frappe.get_doc({"doctype": BOOKING, "total_amount": 10}).insert(ignore_permissions=True)
        self.addCleanup(frappe.delete_doc, BOOKING, doc.name, force=True, ignore_permissions=True)

    def _act_as_user_without_roles(self) -> None:
        email = self.make_throwaway_user("topicless")
        self.addCleanup(frappe.delete_doc, "User", email, force=True, ignore_permissions=True)
        # nosemgrep: frappe-setuser — test acts as a user who holds no role on the Booking DocType
        frappe.set_user(email)
        self.addCleanup(frappe.set_user, "Administrator")

    def test_topic_finds_custom_doctype(self):
        row = _doctype_row("bookings", BOOKING)

        self.assertIsNotNone(row, "plural topic 'bookings' must find the singular Booking DocType")
        self.assertTrue(row["custom"])
        self.assertIn("total_amount", row["amount_fields"])
        self.assertIn("booking_date", row["date_fields"])
        self.assertFalse(row["is_submittable"])
        if "erpnext" in frappe.get_installed_apps():
            self.assertIn("client", row["party_fields"])

    def test_has_data_is_boolean_never_a_count(self):
        self.assertIs(_doctype_row("booking", BOOKING)["has_data"], False)

        self._add_booking_row()
        self._add_booking_row()

        self.assertIs(_doctype_row("booking", BOOKING)["has_data"], True)

    def test_doctypes_user_cannot_read_are_excluded(self):
        self.assertIsNotNone(_doctype_row("booking", BOOKING))

        self._act_as_user_without_roles()

        self.assertIsNone(_doctype_row("booking", BOOKING))

    def test_child_tables_and_singles_are_excluded(self):
        names = {row["doctype"] for row in MetadataTools.find_doctypes_for_topic("booking")["doctypes"]}

        self.assertIn(BOOKING, names)
        self.assertNotIn(BOOKING_LINE, names)
        self.assertNotIn(BOOKING_SETTINGS, names)

    def test_one_broken_doctype_does_not_fail_the_whole_search(self):
        real_describe = MetadataTools._describe_topic_doctype

        def describe(row, role):
            # Production reaches this when one candidate's table or controller is broken.
            if row.name == "ToDo":
                raise RuntimeError("broken table")
            return real_describe(row, role)

        with patch.object(MetadataTools, "_describe_topic_doctype", side_effect=describe), patch.object(
            frappe, "log_error"
        ) as log_error:
            result = MetadataTools.find_doctypes_for_topic("todo booking", limit=25)

        names = [row["doctype"] for row in result["doctypes"]]
        self.assertTrue(result["success"])
        self.assertIn(BOOKING, names)
        self.assertNotIn("ToDo", names)
        log_error.assert_called_once()

    def test_assistant_user_does_not_see_a_wholly_admin_only_doctype(self):
        user = self.make_throwaway_user("topic-assistant", roles=("Assistant User",))
        # nosemgrep: frappe-setuser — the skip depends on the acting user's FAC role
        frappe.set_user(user)
        self.addCleanup(frappe.set_user, "Administrator")
        self.assertIsNotNone(_doctype_row("todo", "ToDo"), "ToDo must be readable to this role")

        # FAC ships ADMIN_ONLY_FIELDS entries of "*" (Email Domain, System Settings, ...); adding
        # ToDo to that same dict gives the Assistant User exactly what a shipped entry does.
        with patch.dict(ADMIN_ONLY_FIELDS, {"ToDo": "*"}):
            self.assertIsNone(_doctype_row("todo", "ToDo"))

    def test_custom_fields_on_standard_doctype_are_listed(self):
        row = _doctype_row("todo", "ToDo")

        self.assertIsNotNone(row)
        self.assertFalse(row["custom"])
        self.assertIn(TODO_CUSTOM_FIELD, row["custom_fields"])

    def test_fields_above_the_users_permlevel_are_not_disclosed(self):
        row = _doctype_row("booking", BOOKING)

        self.assertIn("total_amount", row["amount_fields"])
        self.assertNotIn("margin", row["amount_fields"])

    def test_sensitive_fields_are_not_disclosed(self):
        row = _doctype_row("booking", BOOKING)

        self.assertIn("total_amount", row["amount_fields"])
        self.assertNotIn("iban", row["amount_fields"])

    @unittest.skipUnless(HAS_ERPNEXT, "ERPNext not installed")
    def test_ies_plural_finds_delivery_note(self):
        self.assertIsNotNone(_doctype_row("deliveries", "Delivery Note"))

    @unittest.skipUnless(HAS_ERPNEXT, "ERPNext not installed")
    def test_entries_finds_journal_entry(self):
        self.assertIsNotNone(_doctype_row("entries", "Journal Entry"))

    def test_es_plural_finds_address(self):
        self.assertIsNotNone(_doctype_row("addresses", "Address"))

    def test_limit_caps_the_number_of_doctypes(self):
        # Frappe ships many "... Log" DocTypes, so the unbounded search has more than two to return.
        self.assertGreater(len(MetadataTools.find_doctypes_for_topic("log")["doctypes"]), 2)

        result = MetadataTools.find_doctypes_for_topic("log", limit=2)

        self.assertEqual(len(result["doctypes"]), 2)

    def test_topic_without_a_match_returns_an_empty_list(self):
        result = MetadataTools.find_doctypes_for_topic("zzzqqqnomatch")

        self.assertEqual(result, {"success": True, "doctypes": []})

    def test_tool_routes_topic_to_the_search(self):
        result = GetDoctypeInfo().execute({"topic": "bookings"})

        self.assertTrue(result["success"])
        self.assertIn(BOOKING, [row["doctype"] for row in result["doctypes"]])

    def test_doctype_argument_still_returns_metadata(self):
        result = GetDoctypeInfo().execute({"doctype": "ToDo"})

        self.assertTrue(result["success"])
        self.assertEqual(result["doctype"], "ToDo")

    def test_description_tells_the_model_when_to_use_topic(self):
        self.assertIn("topic", GetDoctypeInfo().description)
        self.assertIn("no report fits", GetDoctypeInfo().description)

    def test_neither_doctype_nor_topic_is_an_error(self):
        result = GetDoctypeInfo().execute({})

        self.assertFalse(result["success"])
        self.assertIn("doctype", result["error"])
        self.assertIn("topic", result["error"])
