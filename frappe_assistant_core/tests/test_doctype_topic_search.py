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

from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.database.database import Database

from frappe_assistant_core.plugins.core.tools.get_doctype_info import GetDoctypeInfo
from frappe_assistant_core.plugins.core.tools.metadata_tools import MetadataTools
from frappe_assistant_core.tests.base_test import BaseAssistantTest

BOOKING = "FAC Topic Booking"
BOOKING_LINE = "FAC Topic Booking Line"
BOOKING_SETTINGS = "FAC Topic Booking Settings"
TODO_CUSTOM_FIELD = "fac_topic_probe"


@contextmanager
def _ddl_allowed():
    """Let a schema change commit for real, then flush what follows it.

    Creating a DocType or Custom Field issues DDL, which MariaDB commits implicitly; Frappe refuses
    that inside a test transaction. BaseAssistantTest also turns commit() into a no-op, so rows the
    DDL committed would survive a plain delete that is rolled back with the class transaction.
    Database.commit is the real commit that the subclass attribute shadows.
    """
    with patch.object(Database, "check_implicit_commit"):
        yield
    Database.commit(frappe.db)


def _delete_persistently(doctype: str, name: str) -> None:
    with _ddl_allowed():
        frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)


def _drop_todo_probe_column() -> None:
    """Deleting a Custom Field leaves its column behind, so drop it to leave the table as found."""
    with _ddl_allowed():
        frappe.db.sql_ddl(f"alter table `tabToDo` drop column if exists `{TODO_CUSTOM_FIELD}`")


def _doctype_row(topic: str, doctype: str):
    result = MetadataTools.find_doctypes_for_topic(topic)
    return next((row for row in result["doctypes"] if row["doctype"] == doctype), None)


class TestDoctypeTopicSearch(BaseAssistantTest):
    def _make_doctype(self, name: str, fields: list, **overrides) -> str:
        # Production reaches this the way a site admin does: a custom DocType built in the UI
        # (custom=1, module "Custom"), readable by System Manager only.
        with _ddl_allowed():
            frappe.get_doc(
                {
                    "doctype": "DocType",
                    "name": name,
                    "module": "Custom",
                    "custom": 1,
                    "fields": fields,
                    "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
                    **overrides,
                }
            ).insert(ignore_permissions=True)
        self.addCleanup(_delete_persistently, "DocType", name)
        return name

    def _make_booking(self, extra_fields: list = ()) -> str:
        fields = [
            {"fieldname": "booking_date", "fieldtype": "Date", "label": "Booking Date"},
            {"fieldname": "total_amount", "fieldtype": "Currency", "label": "Total Amount"},
            *extra_fields,
        ]
        if "erpnext" in frappe.get_installed_apps():
            fields.append(
                {"fieldname": "client", "fieldtype": "Link", "options": "Customer", "label": "Client"}
            )
        return self._make_doctype(BOOKING, fields)

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
        self._make_booking()

        row = _doctype_row("bookings", BOOKING)

        self.assertIsNotNone(row, "plural topic 'bookings' must find the singular Booking DocType")
        self.assertTrue(row["custom"])
        self.assertIn("total_amount", row["amount_fields"])
        self.assertIn("booking_date", row["date_fields"])
        self.assertFalse(row["is_submittable"])
        if "erpnext" in frappe.get_installed_apps():
            self.assertIn("client", row["party_fields"])

    def test_has_data_is_boolean_never_a_count(self):
        self._make_booking()
        self.assertIs(_doctype_row("booking", BOOKING)["has_data"], False)

        self._add_booking_row()
        self._add_booking_row()

        self.assertIs(_doctype_row("booking", BOOKING)["has_data"], True)

    def test_doctypes_user_cannot_read_are_excluded(self):
        self._make_booking()
        self.assertIsNotNone(_doctype_row("booking", BOOKING))

        self._act_as_user_without_roles()

        self.assertIsNone(_doctype_row("booking", BOOKING))

    def test_child_tables_and_singles_are_excluded(self):
        self._make_booking()
        self._make_doctype(
            BOOKING_LINE, [{"fieldname": "note", "fieldtype": "Data", "label": "Note"}], istable=1
        )
        self._make_doctype(
            BOOKING_SETTINGS, [{"fieldname": "note", "fieldtype": "Data", "label": "Note"}], issingle=1
        )

        names = {row["doctype"] for row in MetadataTools.find_doctypes_for_topic("booking")["doctypes"]}

        self.assertIn(BOOKING, names)
        self.assertNotIn(BOOKING_LINE, names)
        self.assertNotIn(BOOKING_SETTINGS, names)

    def test_custom_fields_on_standard_doctype_are_listed(self):
        with _ddl_allowed():
            create_custom_field(
                "ToDo", {"fieldname": TODO_CUSTOM_FIELD, "fieldtype": "Data", "label": "Probe"}
            )
        self.addCleanup(frappe.clear_cache, doctype="ToDo")
        self.addCleanup(_drop_todo_probe_column)
        self.addCleanup(_delete_persistently, "Custom Field", f"ToDo-{TODO_CUSTOM_FIELD}")

        row = _doctype_row("todo", "ToDo")

        self.assertIsNotNone(row)
        self.assertFalse(row["custom"])
        self.assertIn(TODO_CUSTOM_FIELD, row["custom_fields"])

    def test_fields_above_the_users_permlevel_are_not_disclosed(self):
        self._make_booking(
            [{"fieldname": "margin", "fieldtype": "Currency", "label": "Margin", "permlevel": 1}]
        )

        row = _doctype_row("booking", BOOKING)

        # System Manager holds no permlevel-1 permission row, so the field is out of reach.
        self.assertIn("total_amount", row["amount_fields"])
        self.assertNotIn("margin", row["amount_fields"])

    def test_sensitive_fields_are_not_disclosed(self):
        self._make_booking([{"fieldname": "iban", "fieldtype": "Currency", "label": "IBAN"}])

        row = _doctype_row("booking", BOOKING)

        self.assertNotIn("iban", row["amount_fields"])

    def test_limit_caps_the_number_of_doctypes(self):
        # Frappe ships many "... Log" DocTypes, so the unbounded search has more than two to return.
        self.assertGreater(len(MetadataTools.find_doctypes_for_topic("log")["doctypes"]), 2)

        result = MetadataTools.find_doctypes_for_topic("log", limit=2)

        self.assertEqual(len(result["doctypes"]), 2)

    def test_topic_without_a_match_returns_an_empty_list(self):
        result = MetadataTools.find_doctypes_for_topic("zzzqqqnomatch")

        self.assertEqual(result, {"success": True, "doctypes": []})

    def test_tool_routes_topic_to_the_search(self):
        self._make_booking()

        result = GetDoctypeInfo().execute({"topic": "bookings"})

        self.assertTrue(result["success"])
        self.assertIn(BOOKING, [row["doctype"] for row in result["doctypes"]])

    def test_doctype_argument_still_returns_metadata(self):
        result = GetDoctypeInfo().execute({"doctype": "ToDo"})

        self.assertTrue(result["success"])
        self.assertEqual(result["doctype"], "ToDo")

    def test_neither_doctype_nor_topic_is_an_error(self):
        result = GetDoctypeInfo().execute({})

        self.assertFalse(result["success"])
        self.assertIn("doctype", result["error"])
        self.assertIn("topic", result["error"])
