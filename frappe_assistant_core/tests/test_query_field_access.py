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
list_documents must not let a field the user cannot read narrow a query.

A filter, a sort key or a selected expression on such a field gives its value away one query
at a time, from which records match. Frappe v15 does not refuse a filter above the user's
permlevel, and neither Frappe version knows FAC's SENSITIVE_FIELDS. get_doctype_info must not
list those fields either.

Frappe v16 refuses a permlevel filter itself, so on v16 the permlevel tests below fail without the
fix only on FAC's message; the v15 CI run is where they show the leak.
"""

from unittest.mock import patch

import frappe

from frappe_assistant_core.core.field_access import FieldAccessError, check_query_fields, resolve_field
from frappe_assistant_core.plugins.core.tools.list_documents import DocumentList
from frappe_assistant_core.plugins.core.tools.metadata_tools import MetadataTools
from frappe_assistant_core.tests.base_test import BaseAssistantTest

USER = "fac.field.access@example.com"
SAVEPOINT = "fac_field_access"
REFUSED = "You do not have permission to query the field"
NOT_A_FIELD = "is not a field of"
SENSITIVE_DESCRIPTION = {"ToDo": ["description"]}


class TestQueryFieldAccess(BaseAssistantTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not frappe.db.exists("User", USER):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": USER,
                    "first_name": "Field Access",
                    "enabled": 1,
                    "send_welcome_email": 0,
                    "roles": [{"role": "Assistant User"}],
                }
            ).insert(ignore_permissions=True)
        cls.todo = frappe.get_doc(
            {
                "doctype": "ToDo",
                "description": "Renew the supplier contract",
                "priority": "High",
                "allocated_to": USER,
                "assigned_by": USER,
            }
        ).insert(ignore_permissions=True)

    def setUp(self):
        super().setUp()
        frappe.db.savepoint(SAVEPOINT)

    def tearDown(self):
        # nosemgrep: frappe-setuser — tests run in an isolated transaction
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point=SAVEPOINT)
        # The rollback restores the Property Setter rows, not the cached meta built from them.
        frappe.clear_cache(doctype="ToDo")
        super().tearDown()

    def hide_priority(self):
        # Customize Form raising a field's permlevel writes exactly this Property Setter, and no
        # role on ToDo has a permlevel-1 rule, so the user can read ToDo but not its priority.
        frappe.make_property_setter(
            {
                "doctype": "ToDo",
                "fieldname": "priority",
                "property": "permlevel",
                "value": 1,
                "property_type": "Int",
            },
            validate_fields_for_doctype=False,
        )
        frappe.clear_cache(doctype="ToDo")

    def list_as_user(self, **arguments):
        # nosemgrep: frappe-setuser — tests run in an isolated transaction
        frappe.set_user(USER)
        return DocumentList().execute({"doctype": "ToDo", **arguments})

    def assertRefused(self, result, field):
        self.assertFalse(result.get("success"), result)
        self.assertIn(f"{REFUSED} {field}", result.get("error", ""))
        self.assertNotIn("data", result)

    def test_filter_on_a_field_above_the_users_permlevel_is_refused(self):
        self.hide_priority()
        self.assertRefused(self.list_as_user(filters={"priority": "High"}), "priority")

    def test_list_form_filter_and_sort_on_a_hidden_field_are_refused(self):
        # The MCP schema takes filters as an object today; the check must not rely on that,
        # because Frappe accepts list conditions and the schema is the tool's own to widen.
        self.hide_priority()
        self.assertRefused(self.list_as_user(filters=[["priority", "=", "High"]]), "priority")
        self.assertRefused(self.list_as_user(filters=[["ToDo", "priority", "=", "High"]]), "priority")
        self.assertRefused(self.list_as_user(order_by="priority desc"), "priority")

    def test_a_grouped_query_filtering_on_a_hidden_field_is_refused(self):
        self.hide_priority()
        self.assertRefused(self.list_as_user(filters={"priority": "High"}, group_by="status"), "priority")
        result = self.list_as_user(filters={"status": "Open"}, group_by="status")
        self.assertTrue(result.get("success"), result)

    def test_an_expression_over_a_hidden_field_is_refused(self):
        self.hide_priority()
        self.assertRefused(self.list_as_user(fields=["name", "max(priority) as p"]), "priority")
        self.assertRefused(self.list_as_user(fields=["name", "priority as p"]), "priority")

    def test_readable_fields_still_filter_and_sort(self):
        self.hide_priority()
        result = self.list_as_user(
            filters={"status": "Open", "name": self.todo.name},
            fields=["name", "status"],
            order_by="modified desc",
        )
        self.assertTrue(result.get("success"), result)
        self.assertEqual([row["name"] for row in result["data"]], [self.todo.name])

    def test_filter_on_a_fac_sensitive_field_is_refused(self):
        # SENSITIVE_FIELDS lists fields such as Email Account.smtp_password on DocTypes only an
        # administrator usually reads; ToDo stands in because every user reads their own ToDos.
        with patch.dict(
            "frappe_assistant_core.core.security_config.SENSITIVE_FIELDS", {"ToDo": ["description"]}
        ):
            self.assertRefused(
                self.list_as_user(filters={"description": ["like", "%supplier%"]}), "description"
            )

    def test_standard_columns_stay_queryable_for_an_assistant_user(self):
        # ADMIN_ONLY_FIELDS hides creation and docstatus from an Assistant User's results, but
        # filtering on them gives away nothing a Desk list view does not show.
        result = self.list_as_user(filters={"creation": [">", "2000-01-01"], "name": self.todo.name})
        self.assertTrue(result.get("success"), result)
        self.assertEqual(result["count"], 1)

    def test_a_system_manager_may_query_fac_sensitive_fields(self):
        with patch.dict("frappe_assistant_core.core.security_config.SENSITIVE_FIELDS", SENSITIVE_DESCRIPTION):
            check_query_fields("ToDo", "System Manager", filters={"description": "x"})
            with self.assertRaises(FieldAccessError):
                check_query_fields("ToDo", "Assistant User", filters={"description": "x"})

    def test_references_resolve_to_the_doctype_they_name(self):
        self.assertEqual(resolve_field("DocType", "fields.permlevel"), ("DocField", "permlevel"))
        self.assertEqual(resolve_field("DocType", "`tabDocField`.`permlevel`"), ("DocField", "permlevel"))
        self.assertEqual(resolve_field("DocType", "DocField.permlevel"), ("DocField", "permlevel"))
        with self.assertRaises(FieldAccessError):
            resolve_field("DocType", "no_such_link.permlevel")

    def test_a_malformed_reference_is_refused_not_raised(self):
        result = self.list_as_user(filters=[["No Such DocType", "x", "=", 1]])
        self.assertIn("No Such DocType is not a DocType", result["error"])
        self.assertIn(NOT_A_FIELD, self.list_as_user(filters={"no_such_field": 1})["error"])

    def test_a_name_frappe_v15_would_pass_through_is_refused(self):
        # MariaDB reads PRIORITY as priority, and Frappe v15 passes an unknown filter key, or one
        # wrapped in ifnull(...), straight into the SQL.
        self.hide_priority()
        for key in ("PRIORITY", "Priority", "ifnull(priority, '')", "`priority` "):
            result = self.list_as_user(filters={key: "High"})
            self.assertFalse(result.get("success"), (key, result))
            self.assertNotIn("data", result)
        self.assertIn(NOT_A_FIELD, self.list_as_user(filters={"PRIORITY": "High"})["error"])
        self.assertIn(NOT_A_FIELD, self.list_as_user(order_by="PRIORITY desc")["error"])

    def test_a_hidden_field_inside_a_filter_group_is_refused(self):
        # Frappe v16 runs [[a, "or", b]] as one group; see the list-form test for why non-object
        # filters are tested at all.
        with patch.dict("frappe_assistant_core.core.security_config.SENSITIVE_FIELDS", SENSITIVE_DESCRIPTION):
            for filters in (
                [[["description", "like", "%"], "or", ["name", "=", "x"]]],
                [["name", "=", "x"], "or", ["description", "like", "%"]],
            ):
                with self.assertRaises(FieldAccessError, msg=filters):
                    check_query_fields("ToDo", "Assistant User", filters=filters)
            # A group over readable fields still passes.
            check_query_fields(
                "ToDo", "Assistant User", filters=[[["status", "=", "Open"], "or", ["name", "=", "x"]]]
            )

    def test_fields_as_one_string_is_checked(self):
        with patch.dict("frappe_assistant_core.core.security_config.SENSITIVE_FIELDS", SENSITIVE_DESCRIPTION):
            with self.assertRaises(FieldAccessError):
                check_query_fields("ToDo", "Assistant User", fields="name, max(description) as m")

    def test_a_bare_child_table_field_is_checked_against_the_child(self):
        # Frappe v15 retargets a filter on a field the DocType lacks to the child table that has it.
        self.assertEqual(resolve_field("DocType", "permlevel"), ("DocField", "permlevel"))

    def test_get_doctype_info_leaves_out_a_field_the_user_cannot_read(self):
        self.hide_priority()
        # nosemgrep: frappe-setuser — tests run in an isolated transaction
        frappe.set_user(USER)
        result = MetadataTools.get_doctype_metadata("ToDo")
        self.assertTrue(result.get("success"), result)
        fieldnames = {field["fieldname"] for field in result["fields"]}
        self.assertIn("status", fieldnames)
        self.assertNotIn("priority", fieldnames)
