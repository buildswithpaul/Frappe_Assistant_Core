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

"""Where a new Custom Field shows on its form, reported in the tool result."""

import unittest

import frappe

from frappe_assistant_core.plugins.core.tools.create_document import DocumentCreate
from frappe_assistant_core.plugins.core.tools.update_document import DocumentUpdate
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.customisation import locate_field


def _field(fieldname, fieldtype="Data", label=None, collapsible=0):
    return frappe._dict(fieldname=fieldname, fieldtype=fieldtype, label=label, collapsible=collapsible)


class TestLocateField(unittest.TestCase):
    def test_untabbed_form_has_no_tab_and_is_first(self):
        fields = [_field("a"), _field("sec", "Section Break", "Billing"), _field("b")]

        self.assertEqual(
            locate_field(fields, "b"),
            {"tab": None, "section": "Billing", "collapsed": False, "first_tab": True},
        )

    def test_field_before_first_tab_break_sits_on_details(self):
        fields = [_field("a"), _field("t", "Tab Break", "More Info"), _field("b")]

        self.assertEqual(locate_field(fields, "a")["tab"], "Details")
        self.assertTrue(locate_field(fields, "a")["first_tab"])
        self.assertFalse(locate_field(fields, "b")["first_tab"])

    def test_later_tab_is_not_first_and_collapsed_section_is_reported(self):
        fields = [
            _field("t1", "Tab Break", "Details"),
            _field("a"),
            _field("t2", "Tab Break", "More Info"),
            _field("sec", "Section Break", "Customer PO Details", collapsible=1),
            _field("b"),
        ]

        self.assertEqual(
            locate_field(fields, "b"),
            {"tab": "More Info", "section": "Customer PO Details", "collapsed": True, "first_tab": False},
        )

    def test_new_tab_resets_the_section(self):
        fields = [
            _field("t1", "Tab Break", "Details"),
            _field("sec", "Section Break", "Billing", collapsible=1),
            _field("t2", "Tab Break", "More Info"),
            _field("b"),
        ]

        self.assertEqual(
            locate_field(fields, "b"),
            {"tab": "More Info", "section": None, "collapsed": False, "first_tab": False},
        )

    def test_unlabelled_section_has_no_name(self):
        fields = [_field("sec", "Section Break"), _field("b")]

        self.assertIsNone(locate_field(fields, "b")["section"])

    def test_unknown_field_gives_none(self):
        self.assertIsNone(locate_field([_field("a")], "missing"))


PROBE_TAB = "custom_probe_tab"
PROBE_SECTION = "custom_probe_section"
PROBE_FIELD = "custom_probe_where"


class TestCustomFieldLocationInResults(BaseAssistantTest):
    """Throwaway Custom Fields on ToDo build a Tab Break > collapsible Section Break > field layout.

    Production adds the ToDo column when a Custom Field is saved; the base class no-ops commit(),
    which Frappe's DDL needs, so in_create_custom_fields skips only that step. Location is read from
    meta, which does not depend on the column.
    """

    def setUp(self):
        super().setUp()
        frappe.flags.in_create_custom_fields = True
        self._insert(PROBE_TAB, "Tab Break", "Probe Tab", "status")
        self._insert(PROBE_SECTION, "Section Break", "Probe Section", PROBE_TAB, collapsible=1)

    def tearDown(self):
        for fieldname in (PROBE_FIELD, PROBE_SECTION, PROBE_TAB):
            name = f"ToDo-{fieldname}"
            if frappe.db.exists("Custom Field", name):
                frappe.delete_doc("Custom Field", name, force=True, ignore_permissions=True)
        frappe.flags.in_create_custom_fields = False
        frappe.clear_cache(doctype="ToDo")
        super().tearDown()

    def _insert(self, fieldname, fieldtype, label, insert_after, **extra):
        frappe.get_doc(
            {
                "doctype": "Custom Field",
                "dt": "ToDo",
                "fieldname": fieldname,
                "fieldtype": fieldtype,
                "label": label,
                "insert_after": insert_after,
                **extra,
            }
        ).insert(ignore_permissions=True)

    def _create_field(self, insert_after):
        return DocumentCreate().execute(
            {
                "doctype": "Custom Field",
                "data": {
                    "dt": "ToDo",
                    "fieldname": PROBE_FIELD,
                    "label": "Where",
                    "fieldtype": "Data",
                    "insert_after": insert_after,
                },
            }
        )

    def test_create_reports_the_tab_and_collapsed_section(self):
        result = self._create_field(PROBE_SECTION)

        self.assertTrue(result["success"], result)
        self.assertEqual(
            result["location"],
            {"tab": "Probe Tab", "section": "Probe Section", "collapsed": True, "first_tab": False},
        )

    def test_update_reports_the_new_place_after_a_move(self):
        self._create_field(PROBE_SECTION)

        result = DocumentUpdate().execute(
            {
                "doctype": "Custom Field",
                "name": f"ToDo-{PROBE_FIELD}",
                "data": {"insert_after": "description"},
            }
        )

        self.assertTrue(result["success"], result)
        self.assertEqual(result["location"]["tab"], "Details")
        self.assertTrue(result["location"]["first_tab"])
        self.assertFalse(result["location"]["collapsed"])

    def test_other_doctypes_carry_no_location(self):
        result = DocumentCreate().execute({"doctype": "ToDo", "data": {"description": "FAC location probe"}})
        try:
            self.assertTrue(result["success"], result)
            self.assertNotIn("location", result)
        finally:
            frappe.delete_doc("ToDo", result["name"], force=True, ignore_permissions=True)
