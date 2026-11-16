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
A field above the user's permlevel must not reach them through a read tool (GitHub #390).

Desk hides such a field: frappe.client.get calls apply_fieldlevel_read_permissions. get_document
and fetch returned doc.as_dict() whole, search_documents matched a text query against the field,
and a global-search hit carried the field's indexed value in its content snippet.
"""

import json
from unittest.mock import patch

import frappe

from frappe_assistant_core.plugins.core.tools.chatgpt_fetch import ChatGPTFetch
from frappe_assistant_core.plugins.core.tools.create_document import DocumentCreate
from frappe_assistant_core.plugins.core.tools.get_document import DocumentGet
from frappe_assistant_core.plugins.core.tools.search_documents import SearchDocuments
from frappe_assistant_core.plugins.core.tools.search_tools import SearchTools
from frappe_assistant_core.plugins.core.tools.update_document import DocumentUpdate
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.permissions import unwritable_fieldnames

USER = "fac.fieldlevel.read@example.com"
# Reads the description through a permlevel-1 rule its role is given in setUp.
READER = "fac.fieldlevel.reader@example.com"
READER_ROLE = "System Manager"
SAVEPOINT = "fac_fieldlevel_read"
SECRET = "ZQXHIDDEN390"
VISIBLE = "zqxopen390@example.com"


class TestFieldLevelReadAccess(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for email, role in ((USER, "Assistant User"), (READER, READER_ROLE)):
            if not frappe.db.exists("User", email):
                frappe.get_doc(
                    {
                        "doctype": "User",
                        "email": email,
                        "first_name": "Fieldlevel Read",
                        "enabled": 1,
                        "send_welcome_email": 0,
                        "roles": [{"role": role}],
                    }
                ).insert(ignore_permissions=True)
        cls.todo = frappe.get_doc(
            {
                "doctype": "ToDo",
                "description": f"Board pay review {SECRET}",
                "sender": VISIBLE,
                "allocated_to": USER,
                "assigned_by": USER,
            }
        ).insert(ignore_permissions=True)

    def setUp(self):
        super().setUp()
        frappe.db.savepoint(SAVEPOINT)
        # Customize Form raising a field's permlevel writes this Property Setter. No role on ToDo
        # has a permlevel-1 rule, so the user reads the ToDo but not its description.
        frappe.make_property_setter(
            {
                "doctype": "ToDo",
                "fieldname": "description",
                "property": "permlevel",
                "value": 1,
                "property_type": "Int",
            },
            validate_fields_for_doctype=False,
        )
        frappe.permissions.add_permission("ToDo", READER_ROLE, 1)
        frappe.permissions.update_permission_property("ToDo", READER_ROLE, 1, "write", 1)
        frappe.clear_cache(doctype="ToDo")

    def tearDown(self):
        # nosemgrep: frappe-setuser — tests run in an isolated transaction
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point=SAVEPOINT)
        frappe.clear_cache(doctype="ToDo")
        super().tearDown()

    def as_user(self, user=USER):
        # nosemgrep: frappe-setuser — tests run in an isolated transaction
        frappe.set_user(user)

    def assertNoSecret(self, result):
        self.assertNotIn(SECRET, json.dumps(result, default=str))

    def test_get_document_leaves_out_a_field_above_the_users_permlevel(self):
        self.as_user()
        result = DocumentGet().execute({"doctype": "ToDo", "name": self.todo.name})
        self.assertTrue(result.get("success"), result)
        self.assertEqual(result["data"].get("sender"), VISIBLE)
        self.assertNoSecret(result)

    def test_fetch_leaves_out_a_field_above_the_users_permlevel(self):
        self.as_user()
        result = ChatGPTFetch().execute({"id": f"ToDo/{self.todo.name}"})
        self.assertIn(VISIBLE, result["text"])
        self.assertNoSecret(result)

    def test_get_document_still_returns_the_field_to_a_user_who_may_read_it(self):
        self.as_user(READER)
        result = DocumentGet().execute({"doctype": "ToDo", "name": self.todo.name})
        self.assertIn(SECRET, result["data"].get("description", ""))

    def test_doctype_search_does_not_match_on_a_hidden_field(self):
        self.as_user()
        result = SearchDocuments().execute({"doctype": "ToDo", "query": SECRET})
        names = [row.get("name") for row in result.get("results") or []]
        self.assertNotIn(self.todo.name, names, result)
        self.assertNotIn("description", result.get("search_fields") or [])

    def test_doctype_search_refuses_a_filter_on_a_hidden_field(self):
        self.as_user()
        result = SearchDocuments().execute(
            {"doctype": "ToDo", "query": "", "filters": {"description": ["like", f"%{SECRET}%"]}}
        )
        self.assertFalse(result.get("success"), result)
        self.assertIn("You do not have permission to query the field description", result.get("error", ""))

    def test_doctype_search_still_matches_readable_fields(self):
        self.as_user(READER)
        result = SearchDocuments().execute({"doctype": "ToDo", "query": SECRET})
        self.assertIn(self.todo.name, [row.get("name") for row in result.get("results") or []])

    def indexed_hit(self, query, content=None):
        content = content or f"Status : Open ||| Description : Board pay review {SECRET}"
        hit = {"doctype": "ToDo", "name": self.todo.name, "content": content}
        with patch("frappe.utils.global_search.search", autospec=True, return_value=[hit]):
            return SearchTools.global_search(query=query, limit=20)

    def test_global_search_shows_none_of_the_index_text_of_a_doctype_with_a_hidden_field(self):
        # The index keeps a field's label from when the record was indexed (a renamed field keeps
        # its old one), and a value may hold the " ||| " separator, so the text cannot be trimmed
        # reliably. The hit is found again in, and shown from, the readable fields only.
        self.as_user()
        content = f"Status : Open ||| Monthly Pay : {SECRET} ||| Description : a ||| bank {SECRET}"
        result = self.indexed_hit("Open", content)
        self.assertEqual([hit["name"] for hit in result["results"]], [self.todo.name])
        self.assertIn("Status : Open", result["results"][0]["content"])
        self.assertNoSecret(result["results"])

    def test_link_search_refuses_a_filter_on_a_hidden_field(self):
        self.as_user()
        result = SearchTools.search_link(
            doctype="ToDo", query="", filters={"description": ["like", f"%{SECRET}%"]}
        )
        self.assertFalse(result.get("success"), result)
        self.assertIn("You do not have permission to query the field description", result.get("error", ""))

    def test_run_python_code_refuses_a_filter_on_a_hidden_field(self):
        from frappe_assistant_core.utils import sandbox_frappe
        from frappe_assistant_core.utils.tool_api import FrappeAssistantAPI

        hidden = {"description": ["like", f"%{SECRET}%"]}
        self.as_user()
        for call in (
            lambda: sandbox_frappe.count("ToDo", hidden),
            lambda: sandbox_frappe.exists("ToDo", hidden),
            lambda: sandbox_frappe.get_value("ToDo", hidden, "name"),
            lambda: sandbox_frappe.get_list("ToDo", filters=hidden, fields=["name"]),
            lambda: sandbox_frappe.get_all("ToDo", or_filters=hidden, fields=["name"]),
        ):
            with self.assertRaises(frappe.PermissionError):
                call()
        result = FrappeAssistantAPI(USER).get_documents("ToDo", filters=hidden, fields=["name"])
        self.assertFalse(result["success"], result)

        self.as_user(READER)
        self.assertEqual(sandbox_frappe.count("ToDo", hidden), 1)

    def test_global_search_snippet_leaves_out_a_hidden_field(self):
        self.as_user()
        result = self.indexed_hit("Open")
        self.assertEqual([hit["name"] for hit in result["results"]], [self.todo.name])
        self.assertIn("Status : Open", result["results"][0]["content"])
        self.assertNoSecret(result["results"])

    def test_global_search_drops_a_hit_matched_only_on_a_hidden_field(self):
        self.as_user()
        result = self.indexed_hit(SECRET)
        self.assertEqual(result["results"], [], result)

    def test_global_search_snippet_is_whole_for_a_user_who_may_read_it(self):
        self.as_user(READER)
        result = self.indexed_hit(SECRET)
        self.assertIn(SECRET, result["results"][0]["content"])

    # Writing. Desk shows no editor for a field above the user's write level, and on save Frappe
    # puts its stored value back (Document.validate_higher_perm_levels).

    def update_as(self, user, **arguments):
        self.as_user(user)
        return DocumentUpdate().execute({"doctype": "ToDo", "name": self.todo.name, **arguments})

    def stored_description(self):
        return frappe.db.get_value("ToDo", self.todo.name, "description")

    def test_edits_on_a_field_the_user_cannot_write_are_refused_before_matching(self):
        # A find that matched (right guess) and one that did not (wrong guess) must read alike,
        # or the reply tells the user what the hidden field holds.
        right = self.update_as(
            USER,
            edits=[{"field": "description", "find": "Board pay", "replace": "Board pay"}],
            validate_only=True,
        )
        wrong = self.update_as(
            USER,
            edits=[{"field": "description", "find": "NOPE123", "replace": "NOPE123"}],
            validate_only=True,
        )
        for result in (right, wrong):
            self.assertFalse(result.get("success"), result)
            self.assertEqual(result.get("error_type"), "field_not_writable", result)
            self.assertNotIn("match_count", result)
        self.assertEqual(right["error"], wrong["error"])
        self.assertIn(SECRET, self.stored_description())

    def test_a_write_frappe_keeps_back_is_reported_as_not_applied(self):
        result = self.update_as(USER, data={"description": "overwritten", "priority": "Low"})
        self.assertTrue(result.get("success"), result)
        self.assertEqual(result["updated_fields"], ["priority"])
        self.assertEqual(result["not_applied_fields"], ["description"])
        self.assertNoSecret(result)
        # Frappe's own behaviour is unchanged: the save goes through and the stored value stays.
        self.assertIn(SECRET, self.stored_description())
        self.assertEqual(frappe.db.get_value("ToDo", self.todo.name, "priority"), "Low")

    def test_validate_only_reports_the_field_frappe_would_keep_back(self):
        result = self.update_as(USER, data={"description": "overwritten"}, validate_only=True)
        self.assertTrue(result.get("success"), result)
        self.assertEqual(result["fields_validated"], [])
        self.assertEqual(result["not_applied_fields"], ["description"])

    def test_a_user_with_the_write_level_may_edit_the_field(self):
        result = self.update_as(
            READER, edits=[{"field": "description", "find": "Board pay", "replace": "Board salary"}]
        )
        self.assertTrue(result.get("success"), result)
        self.assertNotIn("not_applied_fields", result)
        self.assertIn("Board salary", self.stored_description())

    def test_a_field_a_hook_lets_through_is_not_reported_as_not_applied(self):
        # Frappe skips a field named in flags.ignore_permlevel_for_fields when it resets values.
        self.as_user()
        doc = frappe.get_doc("ToDo", self.todo.name)
        self.assertEqual(unwritable_fieldnames(doc, ["description"]), ["description"])
        doc.flags.ignore_permlevel_for_fields = ["description"]
        self.assertEqual(unwritable_fieldnames(doc, ["description"]), [])

    # Child rows, creating, importing and charting. READER may read and write ToDo at level 1 but
    # holds no level-1 rule on Contact, so a level-1 Contact Phone field is above its levels.

    def raise_permlevel(self, doctype, fieldname, permlevel=1):
        frappe.make_property_setter(
            {
                "doctype": doctype,
                "fieldname": fieldname,
                "property": "permlevel",
                "value": permlevel,
                "property_type": "Int",
            },
            validate_fields_for_doctype=False,
        )
        frappe.clear_cache(doctype=doctype)
        self.addCleanup(frappe.clear_cache, doctype=doctype)

    def test_a_child_row_write_frappe_puts_back_is_reported_as_not_applied(self):
        self.raise_permlevel("Contact Phone", "phone")
        contact = frappe.get_doc(
            {"doctype": "Contact", "first_name": "FAC 390", "phone_nos": [{"phone": "111"}]}
        ).insert(ignore_permissions=True)
        row = contact.phone_nos[0].name

        self.as_user(READER)
        result = DocumentUpdate().execute(
            {
                "doctype": "Contact",
                "name": contact.name,
                "data": {"phone_nos": [{"name": row, "phone": "999"}]},
            }
        )
        self.assertTrue(result.get("success"), result)
        self.assertEqual(result.get("not_applied_fields"), ["phone_nos.phone"], result)
        self.assertEqual(frappe.db.get_value("Contact Phone", row, "phone"), "111")

    def test_create_does_not_report_back_a_child_value_the_user_cannot_read(self):
        # ERPNext fills such values on save (a Timesheet's costing_rate from Activity Cost); the
        # "overridden" warning returned the saved value, or by its absence confirmed a guess.
        self.raise_permlevel("Contact Phone", "phone")
        contact_class = type(frappe.new_doc("Contact"))
        validate = contact_class.validate
        hidden_phone = "+1 650 390 0390"  # a valid number, as Frappe checks it after validate

        def fill_hidden_value(doc):
            validate(doc)
            doc.phone_nos[0].phone = hidden_phone

        self.as_user(READER)
        with patch.object(contact_class, "validate", autospec=True, side_effect=fill_hidden_value):
            result = DocumentCreate().execute(
                {"doctype": "Contact", "data": {"first_name": "FAC 390", "phone_nos": [{"phone": "123"}]}}
            )
        self.assertTrue(result.get("success"), result)
        self.assertNotIn(hidden_phone, json.dumps(result, default=str))
        self.assertNotIn("warnings", result)

    def test_create_reports_a_field_frappe_resets_as_not_applied(self):
        self.raise_permlevel("ToDo", "priority", permlevel=2)
        self.as_user(READER)
        data = {"description": "FAC 390 create", "priority": "High", "allocated_to": READER}

        checked = DocumentCreate().execute({"doctype": "ToDo", "data": data, "validate_only": True})
        self.assertTrue(checked.get("success"), checked)
        self.assertNotIn("priority", checked["fields_validated"])
        self.assertEqual(checked.get("not_applied_fields"), ["priority"])

        result = DocumentCreate().execute({"doctype": "ToDo", "data": data})
        self.assertTrue(result.get("success"), result)
        self.assertEqual(result.get("not_applied_fields"), ["priority"])
        self.assertEqual(frappe.db.get_value("ToDo", result["name"], "priority"), "Medium")

    def test_import_schema_leaves_out_a_field_the_user_cannot_write(self):
        from frappe_assistant_core.utils.import_mapping import build_import_schema

        self.as_user()
        fields = [field["fieldname"] for field in build_import_schema("ToDo")["fields"]]
        self.assertNotIn("description", fields)
        self.assertIn("priority", fields)

        self.as_user(READER)
        self.assertIn("description", [field["fieldname"] for field in build_import_schema("ToDo")["fields"]])

    def test_dashboard_chart_refuses_a_field_the_user_cannot_read(self):
        from frappe_assistant_core.plugins.visualization.tools.create_dashboard_chart import (
            CreateDashboardChart,
        )

        self.as_user()
        for arguments in (
            {"based_on": "description"},
            {"aggregate_function": "Count", "filters": {"description": ["like", f"%{SECRET}%"]}},
        ):
            result = CreateDashboardChart().execute(
                {"chart_name": "FAC 390 chart", "chart_type": "bar", "doctype": "ToDo", **arguments}
            )
            self.assertFalse(result.get("success"), result)
            self.assertEqual(result.get("error_type"), "field_not_readable", result)
            self.assertIn("description", result["error"])
