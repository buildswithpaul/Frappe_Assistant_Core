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

"""Opening a dormant DocType puts the code on it live, so it counts as changes_live_code (#34690).

Custom Fields and Property Setters added while a DocType was dormant ran for nobody and needed no
card. The write that opens it runs all of their code for other people at once. Each case reads real
stored records.
"""

from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.doctype_code import get_code_going_live
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.customisation import customisation_impact
from frappe_assistant_core.utils.field_code import code_on_doctype

WITH_CODE = "FAC Opening With Code"
WITH_SETTER = "FAC Opening With Setter"
PLAIN = "FAC Opening Plain"
LIVE = "FAC Opening Live"
OPEN = "eval:doc.status == 'Open'"
BANNER = "<div>{{ doc.status }}</div>"
DB_COUNT = "frappe.database.database.Database.count"
OTHER_ROLE = {"role": "Employee", "read": 1}


def _impact(tool: str, doctype: str, data: dict | None = None, name: str | None = None) -> dict:
    tool_input = {"doctype": doctype, "data": data or {}}
    if name:
        tool_input["name"] = name
    return customisation_impact(tool, tool_input)


def _db_insert(values: dict) -> frappe.model.document.Document:
    """Write a record and its child rows without the doctype's hooks; rolled back with the test."""
    doc = frappe.get_doc(values)
    doc.set_parent_in_children()
    doc.db_insert()
    for row in doc.get_all_children():
        row.db_insert()
    return doc


def _doctype(name: str, role: str = "System Manager") -> None:
    # Production reaches this when a builder saves a custom DocType that only System Manager can
    # open; db_insert skips the table it would create (DDL commits).
    _db_insert(
        {
            "doctype": "DocType",
            "name": name,
            "module": "Custom",
            "custom": 1,
            "fields": [
                {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "Open\nClosed"},
                {"fieldname": "notes", "label": "Notes", "fieldtype": "Data", "options": "<b>plain</b>"},
            ],
            "permissions": [{"role": role, "read": 1}],
        }
    )


def _custom_field(dt: str, fieldname: str, **values) -> str:
    # Production reaches this when a builder adds a field to the DocType while it is dormant, which
    # needs no card; db_insert skips the column it would add (DDL commits).
    name = f"{dt}-{fieldname}"
    _db_insert({"doctype": "Custom Field", "name": name, "dt": dt, "fieldname": fieldname, **values})
    return name


def _property_setter(doc_type: str, field_name: str, prop: str, value: str) -> str:
    # Production reaches this when Customize Form changes a field of the dormant DocType; db_insert
    # skips the cache hooks.
    name = f"{doc_type}-{field_name}-{prop}"
    _db_insert(
        {
            "doctype": "Property Setter",
            "name": name,
            "doc_type": doc_type,
            "doctype_or_field": "DocField",
            "field_name": field_name,
            "property": prop,
            "property_type": "Data",
            "value": value,
        }
    )
    return name


class TestOpeningADormantDocTypeShowsItsCode(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for name in (WITH_CODE, WITH_SETTER, PLAIN):
            _doctype(name)
        _doctype(LIVE, role="Employee")
        cls.region = _custom_field(WITH_CODE, "region", fieldtype="Data", depends_on=OPEN)
        cls.banner = _custom_field(WITH_CODE, "banner", fieldtype="HTML", options=BANNER)
        _custom_field(LIVE, "region", fieldtype="Data", depends_on=OPEN)
        # No code: a bare fieldname condition and a Data field's options run nothing.
        _custom_field(PLAIN, "region", fieldtype="Data", depends_on="status", options="Email")
        cls.condition_setter = _property_setter(WITH_SETTER, "status", "read_only_depends_on", OPEN)
        cls.html_setter = _property_setter(WITH_SETTER, "notes", "fieldtype", "HTML")
        # Production reaches this when a builder gives the dormant DocType a System Manager rule.
        cls.perm = _db_insert(
            {"doctype": "Custom DocPerm", "parent": WITH_CODE, "role": "System Manager", "read": 1}
        ).name

    def setUp(self):
        super().setUp()
        # The DocTypes have no table (see _doctype), and a DocType a builder just saved holds no
        # records, so the record count reads 0.
        counter = patch(DB_COUNT, autospec=True, return_value=0)
        counter.start()
        self.addCleanup(counter.stop)

    def test_the_doctypes_are_read_as_dormant_and_live(self):
        for name in (WITH_CODE, WITH_SETTER, PLAIN):
            self.assertTrue(
                _impact("update_document", "DocType", {"description": "x"}, name)["dormant"], name
            )
        self.assertFalse(_impact("update_document", "DocType", {"description": "x"}, LIVE)["dormant"])

    def test_a_role_on_the_doctype_puts_its_custom_fields_code_live(self):
        for name in (WITH_CODE, WITH_SETTER):
            r = _impact("update_document", "DocType", {"permissions": [OTHER_ROLE]}, name)
            self.assertIs(r["dormant"], False, name)
            self.assertIs(r["changes_live_code"], True, name)

    def test_a_custom_docperm_puts_its_custom_fields_code_live(self):
        for name in (WITH_CODE, WITH_SETTER):
            r = _impact("create_document", "Custom DocPerm", {"parent": name, "role": "Employee", "read": 1})
            self.assertIs(r["dormant"], False, name)
            self.assertIs(r["changes_live_code"], True, name)
        widened = _impact("update_document", "Custom DocPerm", {"role": "Employee"}, self.perm)
        self.assertIs(widened["changes_live_code"], True)

    def test_making_it_a_child_table_puts_its_code_live(self):
        # Any form can embed a child table, and its fields render there.
        r = _impact("update_document", "DocType", {"istable": 1}, WITH_CODE)
        self.assertIs(r["dormant"], False)
        self.assertIs(r["changes_live_code"], True)
        plain = _impact("update_document", "DocType", {"istable": 1}, PLAIN)
        self.assertIs(plain["dormant"], False)
        self.assertIs(plain["changes_live_code"], False)

    def test_opening_a_doctype_with_no_code_on_it_changes_no_live_code(self):
        for tool, doctype, data, name in (
            ("update_document", "DocType", {"permissions": [OTHER_ROLE]}, PLAIN),
            ("create_document", "Custom DocPerm", {"parent": PLAIN, "role": "Employee"}, None),
        ):
            r = _impact(tool, doctype, data, name)
            self.assertIs(r["dormant"], False, doctype)
            self.assertIs(r["changes_live_code"], False, doctype)

    def test_a_system_role_or_a_reachable_doctype_puts_no_code_live(self):
        system = _impact("create_document", "Custom DocPerm", {"parent": WITH_CODE, "role": "System Manager"})
        self.assertIs(system["dormant"], True)
        self.assertIs(system["changes_live_code"], False)
        # LIVE's code went live (and showed its card) when it was opened.
        wider = _impact("create_document", "Custom DocPerm", {"parent": LIVE, "role": "Accounts User"})
        self.assertIs(wider["changes_live_code"], False)

    def test_code_on_doctype_lists_each_custom_field_and_property_setter(self):
        entries = {
            (e["source"], e["name"], e["field"], e["key"], e["code"]) for e in code_on_doctype(WITH_CODE)
        }
        self.assertEqual(
            entries,
            {
                ("Custom Field", self.region, "region", "depends_on", OPEN),
                ("Custom Field", self.banner, "banner", "options", BANNER),
            },
        )
        entries = {
            (e["source"], e["name"], e["field"], e["key"], e["code"]) for e in code_on_doctype(WITH_SETTER)
        }
        self.assertEqual(
            entries,
            {
                ("Property Setter", self.condition_setter, "status", "read_only_depends_on", OPEN),
                # The setter makes notes an HTML field, so its stored options start to render.
                ("Property Setter", self.html_setter, "notes", "options", "<b>plain</b>"),
            },
        )
        self.assertEqual(code_on_doctype(PLAIN), [])

    def test_the_card_reads_the_code_only_while_the_doctype_is_dormant(self):
        fields = {e["field"] for e in get_code_going_live(target=WITH_CODE)}
        self.assertEqual(fields, {"region", "banner"})
        self.assertEqual({e["field"] for e in get_code_going_live(custom_docperm=self.perm)}, fields)
        self.assertEqual(get_code_going_live(target=LIVE), [])
        self.assertEqual(get_code_going_live(target=PLAIN), [])
