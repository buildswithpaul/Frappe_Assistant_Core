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
from unittest.mock import patch

import frappe

from frappe_assistant_core.chat.api.field_placement import get_field_placement
from frappe_assistant_core.plugins.core.tools.create_document import DocumentCreate
from frappe_assistant_core.plugins.core.tools.update_document import DocumentUpdate
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.customisation import locate_field, placement_sentence, predict_field_location


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
# ToDo's first field, ahead of every probe tab on both Frappe versions: v15 slots a Tab Break straight
# after its insert_after field (splitting ToDo's standard fields), v16 appends it after the last field.
MOVE_TARGET = "description_and_status"


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
                "data": {"insert_after": MOVE_TARGET},
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

    def test_a_field_on_a_later_tab_in_a_collapsed_section_carries_a_placement_warning(self):
        result = self._create_field(PROBE_SECTION)

        warning = result["placement_warning"]
        self.assertIn("Probe Tab", warning)
        self.assertIn("Probe Section", warning)
        self.assertIn("collapsed", warning)
        self.assertIn("first one", warning)

    def test_a_field_on_the_first_tab_carries_no_placement_warning(self):
        result = self._create_field(MOVE_TARGET)

        self.assertTrue(result["success"], result)
        self.assertNotIn("placement_warning", result)

    def test_prediction_for_a_collapsed_section_on_a_later_tab(self):
        self.assertEqual(
            predict_field_location("ToDo", PROBE_SECTION),
            {"tab": "Probe Tab", "section": "Probe Section", "collapsed": True, "first_tab": False},
        )

    def test_prediction_for_the_first_tab(self):
        location = predict_field_location("ToDo", MOVE_TARGET, "Data")

        self.assertEqual(location["tab"], "Details")
        self.assertTrue(location["first_tab"])
        self.assertFalse(location["collapsed"])

    def test_prediction_matches_where_frappe_places_the_saved_field(self):
        for insert_after in (PROBE_SECTION, MOVE_TARGET, "description", "no_such_field", None):
            with self.subTest(insert_after=insert_after):
                predicted = predict_field_location("ToDo", insert_after)
                self._insert(PROBE_FIELD, "Data", "Where", insert_after)
                try:
                    actual = DocumentUpdate().execute(
                        {"doctype": "Custom Field", "name": f"ToDo-{PROBE_FIELD}", "data": {"label": "Where"}}
                    )["location"]
                finally:
                    frappe.delete_doc(
                        "Custom Field", f"ToDo-{PROBE_FIELD}", force=True, ignore_permissions=True
                    )
                    frappe.clear_cache(doctype="ToDo")
                self.assertEqual(predicted, actual)

    def test_a_position_another_custom_field_holds_is_flagged_as_ambiguous(self):
        # setUp's tab was added after "status", so a second field after "status" ties on idx.
        placement = get_field_placement("ToDo", "status")

        self.assertTrue(placement["ambiguous"])
        self.assertTrue(placement["warning"])
        self.assertEqual(
            placement["sentence"],
            "Will appear next to Status. Its tab and section can only be known once it is saved.",
        )

    def test_an_ambiguous_position_after_an_unlabelled_field_names_no_label(self):
        # column_break_2 has no label; another field already added after it makes the position a tie.
        self._insert(PROBE_FIELD, "Data", "Where", "column_break_2")
        try:
            placement = get_field_placement("ToDo", "column_break_2")
        finally:
            frappe.delete_doc("Custom Field", f"ToDo-{PROBE_FIELD}", force=True, ignore_permissions=True)

        self.assertTrue(placement["ambiguous"])
        self.assertNotIn("None", placement["sentence"])
        self.assertEqual(placement["sentence"], "Its tab and section can only be known once it is saved.")

    def test_a_free_position_is_not_ambiguous(self):
        self.assertFalse(get_field_placement("ToDo", MOVE_TARGET)["ambiguous"])
        self.assertFalse(get_field_placement("ToDo", "no_such_field")["ambiguous"])

    def test_prediction_writes_nothing(self):
        before = frappe.db.count("Custom Field", {"dt": "ToDo"})

        predict_field_location("ToDo", PROBE_SECTION)

        self.assertEqual(frappe.db.count("Custom Field", {"dt": "ToDo"}), before)
        self.assertFalse(frappe.get_meta("ToDo", cached=False).has_field("fac_placement_probe"))

    def test_endpoint_describes_a_hidden_placement_and_warns(self):
        placement = get_field_placement("ToDo", PROBE_SECTION, "Data")

        self.assertEqual(placement["tab"], "Probe Tab")
        self.assertTrue(placement["warning"])
        self.assertEqual(
            placement["sentence"],
            "Will appear on the Probe Tab tab, in the Probe Section section "
            "(collapsed, hidden until someone opens it)",
        )

    def test_endpoint_does_not_warn_for_the_first_tab(self):
        placement = get_field_placement("ToDo", MOVE_TARGET)

        self.assertFalse(placement["warning"])
        self.assertNotIn("collapsed", placement["sentence"])
        self.assertTrue(placement["sentence"].startswith("Will appear on the Details tab"))

    def test_endpoint_is_get_only(self):
        self.assertIn(get_field_placement, frappe.whitelisted)
        self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[get_field_placement], ["GET"])

    def test_endpoint_refused_without_read_permission(self):
        email = "field-placement-outsider@example.com"
        if not frappe.db.exists("User", email):
            frappe.get_doc(
                {"doctype": "User", "email": email, "first_name": "Placement", "send_welcome_email": 0}
            ).insert(ignore_permissions=True)
        try:
            frappe.set_user(email)
            with self.assertRaises(frappe.PermissionError):
                get_field_placement("Customer", PROBE_SECTION)
        finally:
            frappe.set_user("Administrator")
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)

    def test_endpoint_reads_a_child_table_through_a_readable_parent(self):
        email = "field-placement-manager@example.com"
        if not frappe.db.exists("User", email):
            user = frappe.get_doc(
                {"doctype": "User", "email": email, "first_name": "Placement", "send_welcome_email": 0}
            ).insert(ignore_permissions=True)
            user.add_roles("System Manager")
        try:
            frappe.set_user(email)
            self.assertIn("sentence", get_field_placement("Has Role", "role"))
        finally:
            frappe.set_user("Administrator")
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)

    def test_endpoint_refuses_a_child_table_when_no_parent_is_readable(self):
        email = "field-placement-outsider2@example.com"
        if not frappe.db.exists("User", email):
            frappe.get_doc(
                {"doctype": "User", "email": email, "first_name": "Placement", "send_welcome_email": 0}
            ).insert(ignore_permissions=True)
        try:
            frappe.set_user(email)
            with self.assertRaises(frappe.PermissionError):
                get_field_placement("Portal Menu Item", "title")
        finally:
            frappe.set_user("Administrator")
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)

    def test_labels_in_the_sentence_are_translated(self):
        with patch("frappe_assistant_core.utils.customisation._", side_effect=lambda t: f"<{t}>"):
            sentence = placement_sentence({"tab": "More Info", "section": None, "collapsed": False})
        self.assertIn("<More Info>", sentence)
