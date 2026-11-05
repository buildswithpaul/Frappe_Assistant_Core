# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
A tool restricted to listed roles can also list users.

On "Restrict to Listed Roles" a user gets the tool when they have a listed role or are listed
themselves; System Managers always get it. A tool a user can't use is neither listed nor run.
"""

import frappe

from frappe_assistant_core.api.admin_api import get_tool_configurations, update_tool_role_access
from frappe_assistant_core.assistant_core.doctype.fac_tool_configuration.fac_tool_configuration import (
    get_tool_access_status,
)
from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.tests.base_test import BaseAssistantTest

TOOL = "create_document"
RESTRICTED = "Restrict to Listed Roles"
SELLERS, STORES = "FAC Test Sellers", "FAC Test Stores"


class ToolUserAccessCase(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        for role in (SELLERS, STORES):
            if not frappe.db.exists("Role", role):
                frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
                    ignore_permissions=True
                )
        self.listed = self._user("fac-tua-listed@example.com", [SELLERS])
        self.other = self._user("fac-tua-other@example.com", [SELLERS])
        self.store = self._user("fac-tua-store@example.com", [STORES])
        self.manager = self._user("fac-tua-manager@example.com", ["System Manager"])

    def tearDown(self):
        frappe.set_user("Administrator")
        get_tool_registry().clear_cache()
        super().tearDown()

    def _user(self, email, roles):
        if not frappe.db.exists("User", email):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": email,
                    "first_name": email.split("@")[0],
                    "send_welcome_email": 0,
                }
            ).insert(ignore_permissions=True)
        user = frappe.get_doc("User", email)
        user.set("roles", [])
        user.add_roles(*roles)
        return email

    def _config(self, mode, roles=(), users=()):
        # What Save on the tool's card writes (update_tool_role_access), set directly
        if not frappe.db.exists("FAC Tool Configuration", TOOL):
            frappe.get_doc(
                {"doctype": "FAC Tool Configuration", "tool_name": TOOL, "plugin_name": "core", "enabled": 1}
            ).insert(ignore_permissions=True)
        doc = frappe.get_doc("FAC Tool Configuration", TOOL)
        doc.role_access_mode = mode
        doc.set("role_access", [{"role": role, "allow_access": 1} for role in roles])
        doc.set("user_access", [{"user": user, "allow_access": 1} for user in users])
        doc.save(ignore_permissions=True)
        get_tool_registry().clear_cache()
        return doc

    def _sees(self, user):
        return get_tool_registry()._is_tool_accessible(TOOL, user)

    def test_a_listed_user_gets_the_tool(self):
        self._config(RESTRICTED, roles=[STORES], users=[self.listed])
        self.assertTrue(self._sees(self.listed))
        self.assertFalse(self._sees(self.other))

    def test_a_listed_role_still_gets_the_tool(self):
        self._config(RESTRICTED, roles=[STORES], users=[self.listed])
        self.assertTrue(self._sees(self.store))

    def test_users_only_without_roles(self):
        self._config(RESTRICTED, users=[self.listed])
        self.assertEqual((self._sees(self.listed), self._sees(self.store)), (True, False))

    def test_system_manager_always_gets_the_tool(self):
        self._config(RESTRICTED, users=[self.listed])
        self.assertTrue(self._sees(self.manager))

    def test_allow_all_ignores_the_lists(self):
        self._config("Allow All", users=[self.listed])
        self.assertTrue(self._sees(self.other))

    def test_a_tool_the_user_cant_use_cant_be_run(self):
        self._config(RESTRICTED, users=[self.listed])
        frappe.set_user(self.other)
        with self.assertRaisesRegex(PermissionError, "not accessible"):
            get_tool_registry().execute_tool(TOOL, {"doctype": "ToDo", "data": {"description": "x"}})

    def test_restricted_needs_a_role_or_a_user(self):
        with self.assertRaises(frappe.ValidationError):
            self._config(RESTRICTED)

    def test_tool_access_status_agrees(self):
        self._config(RESTRICTED, users=[self.listed])
        self.assertTrue(get_tool_access_status(TOOL, self.listed)["has_access"])
        self.assertFalse(get_tool_access_status(TOOL, self.other)["has_access"])

    def test_the_card_saves_roles_and_users(self):
        self._config("Allow All")
        result = update_tool_role_access(
            TOOL, RESTRICTED, roles=[{"role": STORES}], users=frappe.as_json([{"user": self.listed}])
        )
        self.assertTrue(result["success"], result)
        doc = frappe.get_doc("FAC Tool Configuration", TOOL)
        self.assertEqual(
            ([r.role for r in doc.role_access], [u.user for u in doc.user_access]), ([STORES], [self.listed])
        )

        # Removing every role keeps the users
        result = update_tool_role_access(TOOL, RESTRICTED, roles=[], users=[{"user": self.listed}])
        self.assertTrue(result["success"], result)
        doc.reload()
        self.assertEqual(
            ([r.role for r in doc.role_access], [u.user for u in doc.user_access]), ([], [self.listed])
        )

    def test_the_tool_list_shows_the_users(self):
        self._config(RESTRICTED, users=[self.listed])
        tool = next(t for t in get_tool_configurations()["tools"] if t["name"] == TOOL)
        self.assertEqual([u["user"] for u in tool["user_access"]], [self.listed])
