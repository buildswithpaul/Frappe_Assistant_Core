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

"""changes_live_code for a DocType's own field conditions and for HTML field markup (#34690).

FAC Cloud skips the card for a write on an approved build plan only when customisation_impact
says it changes no live code, so each case here reads real stored records, not a patched one.
"""

from unittest.mock import patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.customisation import customisation_impact

LIVE = "FAC Field Code Live"
DORMANT = "FAC Field Code Dormant"
HTML_FIELD = "ToDo-fac_field_code_banner"
DATA_FIELD = "ToDo-fac_field_code_email"
OPEN = "eval:doc.status == 'Open'"
BANNER = "<div>{{ doc.status }}</div>"
DB_COUNT = "frappe.database.database.Database.count"


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


FIELDS = [
    {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "Open\nClosed"},
    {"fieldname": "notes", "label": "Notes", "fieldtype": "Data", "depends_on": OPEN},
    {"fieldname": "summary", "label": "Summary", "fieldtype": "Data", "depends_on": "status"},
    {"fieldname": "banner", "label": "Banner", "fieldtype": "HTML", "options": BANNER},
]


def _doctype(name: str, role: str) -> frappe.model.document.Document:
    # Production reaches this when a builder saves a custom DocType whose form shows notes only for
    # open records and a banner; db_insert skips the table it would create (DDL commits).
    return _db_insert(
        {
            "doctype": "DocType",
            "name": name,
            "module": "Custom",
            "custom": 1,
            "fields": [dict(row) for row in FIELDS],
            "permissions": [{"role": role, "read": 1}],
        }
    )


class TestFieldCodeOnDocTypes(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Employee can open the live DocType; only System Manager can open the dormant one.
        cls.live = _doctype(LIVE, "Employee")
        cls.dormant = _doctype(DORMANT, "System Manager")

    def setUp(self):
        super().setUp()
        # The DocTypes have no table (see _doctype), and a DocType a builder just saved holds no
        # records, so the record count reads 0.
        counter = patch(DB_COUNT, autospec=True, return_value=0)
        counter.start()
        self.addCleanup(counter.stop)

    def _row(self, fieldname: str, doc=None) -> str:
        return next(row.name for row in (doc or self.live).fields if row.fieldname == fieldname)

    def _stored_fields(self) -> list[dict]:
        """The stored field rows as replace-mode input: every value column, no row names."""
        return [{key: value for key, value in row.items() if value} for row in FIELDS]

    def _changes(self, fields, name: str = LIVE) -> bool:
        r = _impact("update_document", "DocType", {"fields": fields}, name)
        return r["changes_live_code"]

    def test_the_doctypes_are_read_as_live_and_dormant(self):
        self.assertFalse(_impact("update_document", "DocType", {"description": "x"}, LIVE)["dormant"])
        self.assertTrue(_impact("update_document", "DocType", {"description": "x"}, DORMANT)["dormant"])

    def test_editing_adding_or_clearing_a_fields_eval_condition_changes_live_code(self):
        for rows in (
            [{"name": self._row("notes"), "depends_on": "eval:doc.status == 'Closed'"}],
            [{"name": self._row("notes"), "depends_on": ""}],
            [{"name": self._row("notes"), "depends_on": "status"}],
            [{"name": self._row("summary"), "read_only_depends_on": "eval:1"}],
            [
                {"name": self._row("notes")},
                {"fieldname": "extra", "fieldtype": "Data", "mandatory_depends_on": OPEN},
            ],
        ):
            self.assertIs(self._changes(rows), True, rows)

    def test_moving_an_unchanged_condition_to_another_field_changes_live_code(self):
        moved = self._stored_fields()
        moved[1]["depends_on"], moved[2]["depends_on"] = "status", OPEN
        renamed = [{"name": self._row("notes"), "fieldname": "remarks"}]
        for rows in (moved, renamed):
            self.assertIs(self._changes(rows), True, rows)

    def test_removing_a_field_that_holds_code_changes_live_code(self):
        deleted = [{"name": self._row("notes"), "_delete": True}]
        left_out = [row for row in self._stored_fields() if row["fieldname"] != "banner"]
        for rows in (deleted, left_out):
            self.assertIs(self._changes(rows), True, rows)

    def test_fields_that_keep_their_code_do_not_change_live_code(self):
        reordered = list(reversed(self._stored_fields()))
        for rows in (
            self._stored_fields(),
            reordered,
            [{"name": self._row("notes"), "label": "Remarks", "depends_on": OPEN}],
            # A bare fieldname only reads that field; it runs nothing.
            [{"name": self._row("summary"), "depends_on": "notes"}],
            [{"name": self._row("banner"), "options": BANNER}],
            [
                {"name": self._row("notes")},
                {"fieldname": "extra", "fieldtype": "Data", "depends_on": "status"},
            ],
        ):
            self.assertIs(self._changes(rows), False, rows)
        description = _impact("update_document", "DocType", {"description": "x"}, LIVE)
        self.assertIs(description["changes_live_code"], False)

    def test_an_html_fields_markup_changes_live_code(self):
        for rows in (
            [{"name": self._row("banner"), "options": "<script>alert(1)</script>"}],
            [{"name": self._row("summary"), "fieldtype": "HTML", "options": "<b>x</b>"}],
            [
                {"name": self._row("notes")},
                {"fieldname": "help", "fieldtype": "HTML", "options": "<i>Help</i>"},
            ],
        ):
            self.assertIs(self._changes(rows), True, rows)

    def test_rows_that_cannot_be_read_change_live_code(self):
        for rows in ("notes", [{"name": "not-a-stored-row", "depends_on": "status"}]):
            self.assertIs(self._changes(rows), True, rows)

    def test_creating_a_live_doctype_with_code_in_its_fields_changes_live_code(self):
        base = {"custom": 1, "module": "Custom", "permissions": [{"role": "Employee"}]}
        for field in (
            {"fieldname": "notes", "fieldtype": "Data", "depends_on": OPEN},
            {"fieldname": "banner", "fieldtype": "HTML", "options": BANNER},
        ):
            r = _impact("create_document", "DocType", {**base, "name": "New", "fields": [field]})
            self.assertFalse(r["dormant"])
            self.assertIs(r["changes_live_code"], True, field)
        bare = {"fieldname": "notes", "fieldtype": "Data", "depends_on": "status", "options": "Email"}
        r = _impact("create_document", "DocType", {**base, "name": "New", "fields": [bare]})
        self.assertIs(r["changes_live_code"], False)

    def test_a_dormant_doctype_runs_no_live_code(self):
        rows = [{"name": self._row("notes", self.dormant), "depends_on": "eval:1"}]
        r = _impact("update_document", "DocType", {"fields": rows}, DORMANT)
        self.assertIs(r["dormant"], True)
        self.assertIs(r["changes_live_code"], False)
        created = _impact(
            "create_document",
            "DocType",
            {"custom": 1, "permissions": [{"role": "System Manager"}], "fields": [dict(FIELDS[1])]},
        )
        self.assertIs(created["dormant"], True)
        self.assertIs(created["changes_live_code"], False)

    def test_opening_a_dormant_doctype_whose_fields_hold_code_changes_live_code(self):
        # None of its eval: conditions or markup has run for anyone else yet.
        r = _impact("update_document", "DocType", {"permissions": [{"role": "Employee"}]}, DORMANT)
        self.assertIs(r["dormant"], False)
        self.assertIs(r["changes_live_code"], True)


class TestHtmlFieldMarkup(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Production reaches these when a builder adds a banner and an email field to ToDo;
        # db_insert skips the columns they would add (DDL commits).
        for name, fieldname, fieldtype, options in (
            (HTML_FIELD, "fac_field_code_banner", "HTML", BANNER),
            (DATA_FIELD, "fac_field_code_email", "Data", "Email"),
        ):
            _db_insert(
                {
                    "doctype": "Custom Field",
                    "name": name,
                    "dt": "ToDo",
                    "fieldname": fieldname,
                    "label": fieldname,
                    "fieldtype": fieldtype,
                    "options": options,
                }
            )

    def test_editing_a_custom_html_fields_markup_changes_live_code(self):
        for data in ({"options": "<script>alert(1)</script>"}, {"options": ""}):
            r = _impact("update_document", "Custom Field", data, HTML_FIELD)
            self.assertIs(r["changes_live_code"], True, data)
        for data in ({"options": BANNER}, {"label": "Banner"}):
            r = _impact("update_document", "Custom Field", data, HTML_FIELD)
            self.assertIs(r["changes_live_code"], False, data)

    def test_turning_a_custom_field_into_an_html_field_changes_live_code(self):
        r = _impact("update_document", "Custom Field", {"fieldtype": "HTML"}, DATA_FIELD)
        self.assertIs(r["changes_live_code"], True)
        same = _impact("update_document", "Custom Field", {"options": "Phone"}, DATA_FIELD)
        self.assertIs(same["changes_live_code"], False)

    def test_creating_a_custom_html_field_with_markup_changes_live_code(self):
        data = {"dt": "ToDo", "fieldname": "fac_new"}
        html = _impact("create_document", "Custom Field", {**data, "fieldtype": "HTML", "options": BANNER})
        self.assertIs(html["changes_live_code"], True)
        for field in ({"fieldtype": "HTML"}, {"fieldtype": "Data", "options": "Email"}):
            r = _impact("create_document", "Custom Field", {**data, **field})
            self.assertIs(r["changes_live_code"], False, field)

    def test_a_property_setter_on_an_html_fields_options_changes_live_code(self):
        # File's preview_html is a standard HTML field; file_name is Data.
        base = {"doc_type": "File", "doctype_or_field": "DocField"}
        for field_name, prop, value, expected in (
            ("preview_html", "options", BANNER, True),
            ("file_name", "fieldtype", "HTML", True),
            ("file_name", "options", "Email", False),
            ("preview_html", "label", BANNER, False),
        ):
            data = {**base, "field_name": field_name, "property": prop, "value": value}
            r = _impact("create_document", "Property Setter", data)
            self.assertIs(r["changes_live_code"], expected, data)
