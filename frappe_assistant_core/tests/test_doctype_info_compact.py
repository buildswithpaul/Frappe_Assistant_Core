# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""get_doctype_info answers with what the model can use, and leaves the rest out.

The tool is called the way MCP calls it, on DocTypes every site has.
"""

import json

from frappe_assistant_core.plugins.core.tools.get_doctype_info import GetDoctypeInfo
from frappe_assistant_core.plugins.core.tools.metadata_tools import (
    OPTIONS_LIMIT,
    MetadataTools,
    compact_field,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestDoctypeInfoIsCompact(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.info = GetDoctypeInfo().execute({"doctype": "User"})
        self.assertTrue(self.info.get("success"), self.info)
        self.fields = {field["fieldname"]: field for field in self.info["fields"]}

    def test_a_field_carries_only_what_is_set(self):
        for field in self.info["fields"]:
            for key, value in field.items():
                self.assertNotIn(value, (None, "", 0, False), f"{field['fieldname']}.{key}")
        self.assertEqual(self.fields["email"].get("reqd"), 1)
        self.assertNotIn("reqd", self.fields["middle_name"])
        self.assertNotIn("hidden", self.fields["middle_name"])

    def test_every_field_keeps_its_name_and_type(self):
        for field in self.info["fields"]:
            self.assertTrue(field.get("fieldname") and field.get("fieldtype"), field)

    def test_column_breaks_are_left_out_and_sections_kept(self):
        types = {field["fieldtype"] for field in self.info["fields"]}
        self.assertNotIn("Column Break", types)
        # A custom field is placed after a section or a tab, so those stay.
        self.assertTrue(types & {"Section Break", "Tab Break"}, types)

    def test_link_field_is_in_fields_with_its_target_and_not_listed_twice(self):
        self.assertNotIn("link_fields", self.info)
        self.assertEqual(self.fields["role_profile_name"]["fieldtype"], "Link")
        self.assertEqual(self.fields["role_profile_name"]["options"], "Role Profile")

    def test_child_table_lists_the_fields_a_row_is_built_from(self):
        roles = next(table for table in self.info["child_tables"] if table["fieldname"] == "roles")
        self.assertEqual(roles["options"], "Has Role")
        self.assertIn("role", [field["fieldname"] for field in roles["fields"]])
        layout = {"Section Break", "Column Break", "Tab Break"}
        self.assertFalse(layout & {field["fieldtype"] for field in roles["fields"]})

    def test_permission_names_the_role_and_its_rights(self):
        self.assertTrue(self.info["permissions"])
        for permission in self.info["permissions"]:
            self.assertFalse(set(permission) - {"role", "rights", "permlevel", "if_owner"}, permission)
            self.assertTrue(permission["role"])
            self.assertIsInstance(permission["rights"], list)
        manager = next(p for p in self.info["permissions"] if p["role"] == "System Manager")
        self.assertIn("read", manager["rights"])

    def test_answer_is_much_smaller_than_the_full_metadata(self):
        full = MetadataTools.get_doctype_metadata("User")
        self.assertLess(len(json.dumps(self.info, default=str)), 0.6 * len(json.dumps(full, default=str)))

    def test_child_doctype_still_says_where_its_rows_live(self):
        info = GetDoctypeInfo().execute({"doctype": "Has Role"})
        self.assertTrue(info["is_child_table"])
        self.assertIn({"doctype": "User", "fieldname": "roles"}, info["parent_doctypes"])

    def test_failure_is_passed_on_as_it_is(self):
        info = GetDoctypeInfo().execute({"doctype": "No Such DocType"})
        self.assertEqual(info, {"success": False, "error": "DocType 'No Such DocType' not found"})


class TestCompactField(BaseAssistantTest):
    def _field(self, **values) -> dict:
        base = dict.fromkeys(("label", "options", "default", "description"))
        return {
            "fieldname": "f",
            "fieldtype": "Select",
            "reqd": 0,
            "read_only": 0,
            "hidden": 0,
            **base,
            **values,
        }

    def test_short_options_are_kept_whole(self):
        field = compact_field(self._field(options="Open\nClosed"))
        self.assertEqual(field, {"fieldname": "f", "fieldtype": "Select", "options": "Open\nClosed"})

    def test_long_options_are_cut_at_a_line_and_say_how_many_there_are(self):
        lines = [f"PORT{number:05d} - Somewhere" for number in range(400)]
        field = compact_field(self._field(options="\n".join(lines)))
        self.assertLessEqual(len(field["options"]), OPTIONS_LIMIT)
        self.assertEqual(field["options"].split("\n")[0], lines[0])
        self.assertIn(field["options"].split("\n")[-1], lines)
        self.assertEqual(field["options_total"], 400)

    def test_set_flags_are_kept(self):
        field = compact_field(self._field(reqd=1, hidden=1, default="Open"))
        self.assertEqual((field["reqd"], field["hidden"], field["default"]), (1, 1, "Open"))
