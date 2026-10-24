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

"""Tests for the test_as_user permission check tool."""

import json
from unittest.mock import patch

import frappe
from frappe import _

from frappe_assistant_core.plugins.core.tools.test_as_user import TestAsUser
from frappe_assistant_core.tests.base_test import BaseAssistantTest

SENTINEL = "SENTINEL-description-4f9a2c"


def _hook_that_msgprints(doc, ptype, user, debug=False):
    """Stand-in for an app's has_permission hook."""


class TestTestAsUser(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        self.tool = TestAsUser()
        # A user with no role is what a builder checks before granting one;
        # production reaches it by creating a user without roles.
        self.nobody = self.make_throwaway_user("nobody")
        # The owner rule is reached in production when a user creates a ToDo.
        self.own_todo = self._make_todo(self.nobody, "own")
        self.other_todo = self._make_todo("Administrator", SENTINEL)

    def _make_todo(self, owner: str, description: str) -> str:
        todo = frappe.get_doc({"doctype": "ToDo", "description": description, "allocated_to": owner})
        todo.insert(ignore_permissions=True)
        frappe.db.set_value("ToDo", todo.name, "owner", owner)
        return todo.name

    def _run(self, checks: list, user: str | None = None) -> dict:
        return self.tool.execute({"user": user or self.nobody, "checks": checks})

    def test_refused_read_has_fixed_reason_and_roles(self):
        result = self._run([{"ptype": "read", "doctype": "ToDo", "name": self.other_todo}])
        row = result["results"][0]
        self.assertTrue(result["success"])
        self.assertEqual(row["outcome"], "refused")
        self.assertEqual(row["reason"], f"{self.nobody} may not read this ToDo.")
        self.assertTrue(row["roles_that_allow"])

    def test_owner_rule_allows_own_record(self):
        row = self._run([{"ptype": "read", "doctype": "ToDo", "name": self.own_todo}])["results"][0]
        self.assertEqual(row["outcome"], "allowed")
        self.assertIsNone(row["reason"])

    def test_doctype_level_answer_without_name(self):
        row = self._run([{"ptype": "create", "doctype": "Role"}])["results"][0]
        self.assertEqual(row["outcome"], "refused")
        self.assertEqual(row["reason"], f"{self.nobody} may not create Role records.")

    def test_child_doctype_with_parent_is_answered(self):
        # A System Manager is how a builder's own account reads Has Role rows of a User.
        manager = self.make_throwaway_user("manager", roles=("System Manager",))
        row = self._run([{"ptype": "read", "doctype": "Has Role", "parent_doctype": "User"}], user=manager)[
            "results"
        ][0]
        self.assertEqual(row["outcome"], "allowed")

    def test_unknown_doctype_and_missing_record_error_then_continue(self):
        results = self._run(
            [
                {"ptype": "read", "doctype": "No Such DocType"},
                {"ptype": "read", "doctype": "ToDo", "name": "no-such-todo"},
                {"ptype": "read", "doctype": "ToDo", "name": self.own_todo},
            ]
        )["results"]
        self.assertEqual([r["outcome"] for r in results], ["error", "error", "allowed"])
        self.assertEqual([r["check"] for r in results], [1, 2, 3])
        self.assertEqual(results[0]["reason"], "DocType No Such DocType does not exist.")
        self.assertEqual(results[1]["reason"], "ToDo no-such-todo does not exist.")

    def test_invalid_ptype_is_an_error_row(self):
        row = self._run([{"ptype": "fly", "doctype": "ToDo"}])["results"][0]
        self.assertEqual(row["outcome"], "error")

    def test_missing_and_disabled_user_check_nothing(self):
        checks = [{"ptype": "read", "doctype": "ToDo"}]
        missing = self._run(checks, user="nobody-here@example.com")
        self.assertFalse(missing["success"])
        self.assertNotIn("results", missing)

        # Production reaches this by a System Manager unticking Enabled on the User form.
        frappe.db.set_value("User", self.nobody, "enabled", 0)
        disabled = self._run(checks)
        self.assertFalse(disabled["success"])
        self.assertNotIn("results", disabled)

    def test_user_is_canonicalised(self):
        result = self._run([{"ptype": "read", "doctype": "ToDo"}], user=self.nobody.upper())
        self.assertEqual(result["user"], self.nobody)

    def test_check_count_is_bounded(self):
        check = {"ptype": "read", "doctype": "ToDo"}
        self.assertFalse(self._run([])["success"])
        self.assertFalse(self._run([check] * 21)["success"])

    def test_result_never_contains_record_values(self):
        result = self._run(
            [
                {"ptype": "read", "doctype": "ToDo", "name": self.other_todo},
                {"ptype": "read", "doctype": "ToDo", "name": self.own_todo},
            ]
        )
        self.assertNotIn(SENTINEL, json.dumps(result))

    def test_hook_messages_are_not_left_in_message_log(self):
        hook_path = f"{__name__}._hook_that_msgprints"
        real_get_hooks = frappe.get_hooks

        def get_hooks(hook=None, *args, **kwargs):
            if hook == "has_permission":
                return {"ToDo": [hook_path]}
            return real_get_hooks(hook, *args, **kwargs)

        # Any installed app can register a has_permission hook in hooks.py, and
        # hooks msgprint to explain a denial; this registers one for ToDo.
        with (
            patch(hook_path, autospec=True, return_value=True) as hook,
            patch.object(frappe, "get_hooks", autospec=True, side_effect=get_hooks),
        ):
            hook.side_effect = lambda **kwargs: frappe.msgprint(_("hook says: secret")) or True
            before = len(frappe.local.message_log)
            self._run([{"ptype": "read", "doctype": "ToDo", "name": self.own_todo}])
            self.assertTrue(hook.called)
        self.assertEqual(len(frappe.local.message_log), before)

    def test_unexpected_failure_is_an_error_row_without_writes(self):
        errors = frappe.db.count("Error Log")
        with patch.object(frappe, "has_permission", autospec=True, side_effect=Exception("boom")):
            row = self._run([{"ptype": "read", "doctype": "ToDo", "name": self.own_todo}])["results"][0]
        self.assertEqual(row["outcome"], "error")
        self.assertEqual((row["ptype"], row["doctype"], row["name"]), ("read", "ToDo", self.own_todo))
        self.assertNotIn("boom", json.dumps(row))
        self.assertEqual(frappe.db.count("Error Log"), errors)

    def test_non_string_name_is_an_error_row(self):
        row = self._run([{"ptype": "read", "doctype": "ToDo", "name": 123}])["results"][0]
        self.assertEqual(row["outcome"], "error")
        self.assertEqual(row["reason"], "name and parent_doctype must be text.")

    def test_single_doctype_is_answered(self):
        row = self._run([{"ptype": "write", "doctype": "System Settings", "name": "ignored"}])["results"][0]
        self.assertEqual(row["outcome"], "refused")
        self.assertIsNone(row["name"])
        self.assertEqual(row["reason"], f"{self.nobody} may not write System Settings records.")

    def test_user_permission_restricts_to_one_record(self):
        # Production reaches this when a System Manager adds a User Permission for the user.
        manager = self.make_throwaway_user("restricted", roles=("System Manager",))
        frappe.get_doc(
            {"doctype": "User Permission", "user": manager, "allow": "Role", "for_value": "Report Manager"}
        ).insert(ignore_permissions=True)
        results = self._run(
            [
                {"ptype": "read", "doctype": "Role", "name": "Report Manager"},
                {"ptype": "read", "doctype": "Role", "name": "Website Manager"},
            ],
            user=manager,
        )["results"]
        self.assertEqual([r["outcome"] for r in results], ["allowed", "refused"])

    def test_share_grants_read_on_a_record_not_owned(self):
        # Production reaches this when the owner shares the record with the user.
        frappe.share.add("ToDo", self.other_todo, self.nobody, read=1)
        row = self._run([{"ptype": "read", "doctype": "ToDo", "name": self.other_todo}])["results"][0]
        self.assertEqual(row["outcome"], "allowed")

    def test_child_roles_come_from_the_parent(self):
        row = self._run([{"ptype": "read", "doctype": "Has Role", "parent_doctype": "User"}])["results"][0]
        self.assertIn("System Manager", row["roles_that_allow"])

    def test_non_system_manager_is_refused(self):
        # nosemgrep: frappe-setuser — tests run in an isolated transaction
        frappe.set_user(self.nobody)
        try:
            response = self.tool._safe_execute(
                {"user": self.nobody, "checks": [{"ptype": "read", "doctype": "ToDo"}]}
            )
        finally:
            # nosemgrep: frappe-setuser — tests run in an isolated transaction
            frappe.set_user("Administrator")
        self.assertFalse(response["success"])
        self.assertEqual(response["error_type"], "PermissionError")

    def test_declares_system_manager_only(self):
        self.assertEqual(self.tool.required_roles, ["System Manager"])

    def test_nothing_is_written(self):
        counts = {dt: frappe.db.count(dt) for dt in ("ToDo", "User", "Error Log", "Version")}
        self._run(
            [
                {"ptype": "write", "doctype": "ToDo", "name": self.other_todo},
                {"ptype": "delete", "doctype": "ToDo", "name": self.own_todo},
                {"ptype": "create", "doctype": "ToDo"},
            ]
        )
        self.assertEqual(counts, {dt: frappe.db.count(dt) for dt in counts})
        self.assertEqual(frappe.db.get_value("ToDo", self.own_todo, "description"), "own")
