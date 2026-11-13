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
from frappe_assistant_core.plugins.core.tools.get_document import DocumentGet
from frappe_assistant_core.plugins.core.tools.search_documents import SearchDocuments
from frappe_assistant_core.plugins.core.tools.search_tools import SearchTools
from frappe_assistant_core.plugins.core.tools.update_document import DocumentUpdate
from frappe_assistant_core.tests.base_test import BaseAssistantTest

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

    def indexed_hit(self, query):
        content = f"Status : Open ||| Description : Board pay review {SECRET}"
        hit = {"doctype": "ToDo", "name": self.todo.name, "content": content}
        with patch("frappe.utils.global_search.search", return_value=[hit]):
            return SearchTools.global_search(query=query, limit=20)

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
