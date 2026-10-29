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
Bulk create_document, update_document and delete_document (Redmine #34507).

ToDo is the fixture: a core doctype on v15 and v16 that any test site has, with a Select
field (status) that rejects an unknown value, so one bad record in a batch is easy to make.
"""

import frappe

from frappe_assistant_core.plugins.core.tools.batch import MAX_BATCH_SIZE
from frappe_assistant_core.plugins.core.tools.create_document import DocumentCreate
from frappe_assistant_core.plugins.core.tools.delete_document import DocumentDelete
from frappe_assistant_core.plugins.core.tools.update_document import DocumentUpdate
from frappe_assistant_core.tests.base_test import BaseAssistantTest


def tag():
    return f"FAC bulk {frappe.generate_hash(length=8)}"


def todo(description, **extra):
    return {"description": description, "allocated_to": "Administrator", **extra}


def todos(description):
    return frappe.get_all("ToDo", filters={"description": description}, pluck="name")


def make_todos(count):
    """ToDos written the way Desk writes them, to update or delete in bulk."""
    description = tag()
    return [frappe.get_doc({"doctype": "ToDo", **todo(description)}).insert().name for _ in range(count)]


class TestBulkCreate(BaseAssistantTest):
    def test_records_creates_every_record(self):
        description = tag()
        result = DocumentCreate().execute(
            {"doctype": "ToDo", "records": [todo(description), todo(description), todo(description)]}
        )

        self.assertTrue(result["success"], result)
        self.assertEqual(result["succeeded"], 3)
        self.assertEqual(sorted(entry["name"] for entry in result["results"]), sorted(todos(description)))

    def test_all_or_nothing_saves_nothing_when_one_record_fails(self):
        description = tag()
        result = DocumentCreate().execute(
            {
                "doctype": "ToDo",
                "records": [todo(description), todo(description, status="Not A Status"), todo(description)],
            }
        )

        self.assertFalse(result["success"], result)
        self.assertEqual(result["failed_record"]["index"], 1)
        self.assertTrue(result["all_undone"])
        self.assertEqual(todos(description), [])

    def test_continue_saves_the_records_that_pass(self):
        description = tag()
        result = DocumentCreate().execute(
            {
                "doctype": "ToDo",
                "mode": "continue",
                "records": [todo(description), todo(description, status="Not A Status"), todo(description)],
            }
        )

        self.assertTrue(result["success"], result)
        self.assertEqual((result["succeeded"], result["failed"]), (2, 1))
        self.assertFalse(result["results"][1]["success"])
        self.assertEqual(len(todos(description)), 2)

    def test_validate_only_reports_every_bad_record_and_saves_nothing(self):
        description = tag()
        result = DocumentCreate().execute(
            {
                "doctype": "ToDo",
                "validate_only": True,
                # A dry run checks links but not Select values, so the bad records name no user.
                "records": [
                    todo(description, allocated_to="fac-nobody-1@example.com"),
                    todo(description),
                    todo(description, allocated_to="fac-nobody-2@example.com"),
                ],
            }
        )

        self.assertFalse(result["validation_passed"], result)
        self.assertEqual([entry["success"] for entry in result["results"]], [False, True, False])
        self.assertEqual(todos(description), [])

    def test_each_record_goes_through_the_single_create_path(self):
        # A Table MultiSelect given as plain link values only works through the single path's
        # child-row normalisation (#291); a batch that skipped it would fail on .is_new().
        group = f"FAC bulk {frappe.generate_hash(length=8)}"
        result = DocumentCreate().execute(
            {"doctype": "User Group", "records": [{"name": group, "user_group_members": ["Administrator"]}]}
        )

        self.assertTrue(result["success"], result)
        members = [row.user for row in frappe.get_doc("User Group", group).user_group_members]
        self.assertEqual(members, ["Administrator"])

    def test_refuses_more_than_the_cap(self):
        description = tag()
        result = DocumentCreate().execute(
            {"doctype": "ToDo", "records": [todo(description)] * (MAX_BATCH_SIZE + 1)}
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "invalid_batch")
        self.assertEqual(todos(description), [])

    def test_refuses_a_batch_of_customisations(self):
        # Each customisation write is previewed and approved on its own; a batch would skip that.
        result = DocumentCreate().execute(
            {
                "doctype": "Custom Field",
                "records": [
                    {"dt": "ToDo", "fieldname": "fac_bulk_probe", "label": "Probe", "fieldtype": "Data"}
                ],
            }
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "invalid_batch")
        self.assertFalse(frappe.db.exists("Custom Field", {"dt": "ToDo", "fieldname": "fac_bulk_probe"}))

    def test_refuses_data_and_records_together(self):
        result = DocumentCreate().execute({"doctype": "ToDo", "data": todo(tag()), "records": [todo(tag())]})

        self.assertFalse(result["success"])

    def test_a_single_create_still_works(self):
        description = tag()
        result = DocumentCreate().execute({"doctype": "ToDo", "data": todo(description)})

        self.assertTrue(result["success"], result)
        self.assertEqual(todos(description), [result["name"]])


class TestBulkUpdate(BaseAssistantTest):
    def status(self, name):
        return frappe.db.get_value("ToDo", name, "status")

    def test_names_applies_the_same_change_to_every_record(self):
        names = make_todos(3)
        result = DocumentUpdate().execute({"doctype": "ToDo", "names": names, "data": {"status": "Closed"}})

        self.assertTrue(result["success"], result)
        self.assertEqual([self.status(name) for name in names], ["Closed"] * 3)

    def test_records_applies_a_different_change_to_each_record(self):
        first, second = make_todos(2)
        result = DocumentUpdate().execute(
            {
                "doctype": "ToDo",
                "records": [
                    {"name": first, "data": {"status": "Closed"}},
                    {"name": second, "data": {"status": "Cancelled"}},
                ],
            }
        )

        self.assertTrue(result["success"], result)
        self.assertEqual((self.status(first), self.status(second)), ("Closed", "Cancelled"))

    def test_all_or_nothing_undoes_the_records_already_updated(self):
        first, second = make_todos(2)
        result = DocumentUpdate().execute(
            {"doctype": "ToDo", "names": [first, "FAC-missing-todo", second], "data": {"status": "Closed"}}
        )

        self.assertFalse(result["success"], result)
        self.assertEqual(result["failed_record"]["record"], "FAC-missing-todo")
        self.assertEqual((self.status(first), self.status(second)), ("Open", "Open"))

    def test_continue_updates_the_records_that_pass(self):
        first, second = make_todos(2)
        result = DocumentUpdate().execute(
            {
                "doctype": "ToDo",
                "mode": "continue",
                "names": [first, "FAC-missing-todo", second],
                "data": {"status": "Closed"},
            }
        )

        self.assertEqual((result["succeeded"], result["failed"]), (2, 1))
        self.assertEqual((self.status(first), self.status(second)), ("Closed", "Closed"))

    def test_validate_only_names_checks_every_record_and_saves_nothing(self):
        names = make_todos(2)
        result = DocumentUpdate().execute(
            {"doctype": "ToDo", "names": names, "data": {"status": "Closed"}, "validate_only": True}
        )

        self.assertTrue(result["validation_passed"], result)
        self.assertEqual([entry["record"] for entry in result["results"]], names)
        self.assertEqual([self.status(name) for name in names], ["Open", "Open"])

    def test_validate_only_records_reports_every_bad_record_and_saves_nothing(self):
        first, second = make_todos(2)
        result = DocumentUpdate().execute(
            {
                "doctype": "ToDo",
                "validate_only": True,
                # A dry run checks links but not Select values, so the bad record names no user.
                "records": [
                    {"name": first, "data": {"status": "Closed"}},
                    {"name": second, "data": {"allocated_to": "fac-nobody@example.com"}},
                    {"name": "FAC-missing-todo", "data": {"status": "Closed"}},
                ],
            }
        )

        self.assertFalse(result["validation_passed"], result)
        self.assertEqual([entry["success"] for entry in result["results"]], [True, False, False])
        self.assertEqual((self.status(first), self.status(second)), ("Open", "Open"))
        self.assertEqual(frappe.db.get_value("ToDo", second, "allocated_to"), "Administrator")

    def test_refuses_name_and_names_together(self):
        (name,) = make_todos(1)
        result = DocumentUpdate().execute(
            {"doctype": "ToDo", "name": name, "names": [name], "data": {"status": "Closed"}}
        )

        self.assertFalse(result["success"])
        self.assertEqual(self.status(name), "Open")


class TestBulkDelete(BaseAssistantTest):
    def test_names_deletes_every_record(self):
        names = make_todos(3)
        result = DocumentDelete().execute({"doctype": "ToDo", "names": names})

        self.assertTrue(result["success"], result)
        self.assertFalse(any(frappe.db.exists("ToDo", name) for name in names))

    def test_all_or_nothing_restores_the_records_already_deleted(self):
        first, second = make_todos(2)
        result = DocumentDelete().execute({"doctype": "ToDo", "names": [first, "FAC-missing-todo", second]})

        self.assertFalse(result["success"], result)
        self.assertTrue(frappe.db.exists("ToDo", first))
        self.assertTrue(frappe.db.exists("ToDo", second))

    def test_continue_deletes_the_records_that_pass(self):
        first, second = make_todos(2)
        result = DocumentDelete().execute(
            {"doctype": "ToDo", "mode": "continue", "names": [first, "FAC-missing-todo", second]}
        )

        self.assertEqual((result["succeeded"], result["failed"]), (2, 1))
        self.assertFalse(frappe.db.exists("ToDo", first))
        self.assertFalse(frappe.db.exists("ToDo", second))
