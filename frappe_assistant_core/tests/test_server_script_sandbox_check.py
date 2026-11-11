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

"""Refusing a Server Script that would fail in Frappe's sandbox, before it is saved (#34901).

Frappe's own save only warns on a compile error, and names missing from the sandbox or
blocked attributes such as format fail only when the script runs.
"""

from unittest.mock import patch

import frappe

from frappe_assistant_core.plugins.core.tools.create_document import DocumentCreate
from frappe_assistant_core.plugins.core.tools.update_document import DocumentUpdate
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.customisation import server_script_code_guard
from frappe_assistant_core.utils.sandbox_check import sandbox_problems

SCRIPTS_ENABLED = "frappe_assistant_core.utils.customisation.server_scripts_enabled"
SCRIPT_NAME = "FAC Sandbox Check Probe Script"
CLEAN_SCRIPT = "\n".join(
    [
        'roles = frappe.get_all("Has Role", filters={"parent": frappe.session.user}, pluck="role")',
        'owner = frappe.db.get_value("ToDo", frappe.form_dict.name, "allocated_to")',
        "frappe.flags.fac_seen = True",
        'frappe.response["message"] = json.dumps({"label": f"{owner} has {len(roles)} roles"})',
        "rows = []",
        "rows += [1]",
        "total = 0",
        "total += frappe.utils.flt(doc.grand_total) if doc else 0",
    ]
)


def _script_data(script: str, **overrides) -> dict:
    data = {
        "name": SCRIPT_NAME,
        "script_type": "API",
        "api_method": "fac_sandbox_check_probe",
        "disabled": 1,
        "script": script,
    }
    data.update(overrides)
    return data


class TestSandboxProblems(BaseAssistantTest):
    def test_a_script_using_only_sandbox_names_has_no_problems(self):
        self.assertEqual(sandbox_problems(CLEAN_SCRIPT), [])

    def test_augmented_assignment_to_an_item_is_reported_with_its_line(self):
        problems = sandbox_problems('x = {}\nx["a"] += 1')

        self.assertEqual(len(problems), 1)
        self.assertIn("Line 2", problems[0])
        self.assertIn("Augmented assignment of object items and slices is not allowed", problems[0])

    def test_format_is_reported_with_the_f_string_alternative(self):
        problems = sandbox_problems('label = "{} items".format(3)\nother = "{a}".format_map({})')

        self.assertEqual(len(problems), 2)
        self.assertIn("Line 1", problems[0])
        self.assertIn("format", problems[0])
        self.assertIn("f-string", problems[0])
        self.assertIn("format_map", problems[1])

    def test_a_name_missing_from_the_sandbox_is_reported(self):
        problems = sandbox_problems("if 'HR Manager' in frappe.get_roles():\n    pass")

        self.assertEqual(len(problems), 1)
        self.assertIn("frappe.get_roles", problems[0])
        self.assertIn("Has Role", problems[0])

    def test_a_missing_name_deeper_in_a_namespace_is_reported_once(self):
        problems = sandbox_problems("a = frappe.db.no_such_call()\nb = frappe.db.no_such_call()")

        self.assertEqual(len(problems), 1)
        self.assertIn("frappe.db.no_such_call", problems[0])

    def test_request_data_is_not_checked(self):
        script = "frappe.form_dict.anything\nfrappe.session.data\nfrappe.flags.x"

        self.assertEqual(sandbox_problems(script), [])

    def test_a_local_that_reuses_a_sandbox_name_is_not_checked(self):
        # json is a sandbox namespace; once the script assigns it, it is the script's own value
        self.assertEqual(sandbox_problems("json = doc.as_dict()\njson.items()"), [])

    def test_a_syntax_error_is_reported(self):
        problems = sandbox_problems("def broken(:\n    pass")

        self.assertEqual(len(problems), 1)
        self.assertIn("Line 1", problems[0])


class TestServerScriptCodeGuard(BaseAssistantTest):
    def tearDown(self):
        # The tool tests must leave no Server Script behind even when they fail
        if frappe.db.exists("Server Script", SCRIPT_NAME):
            frappe.delete_doc("Server Script", SCRIPT_NAME, force=True, ignore_permissions=True)
        super().tearDown()

    def _insert(self, script: str):
        # Production reaches a stored bad script from before this check, or from a Desk save,
        # which Frappe lets through with only a warning.
        with patch(SCRIPTS_ENABLED, return_value=True):
            frappe.get_doc({"doctype": "Server Script", **_script_data(script)}).insert()

    def test_create_refuses_a_script_that_fails_the_sandbox_and_saves_nothing(self):
        with patch(SCRIPTS_ENABLED, return_value=True):
            result = DocumentCreate().execute(
                {"doctype": "Server Script", "data": _script_data("frappe.get_roles()")}
            )
            validated = DocumentCreate().execute(
                {
                    "doctype": "Server Script",
                    "data": _script_data("frappe.get_roles()"),
                    "validate_only": True,
                }
            )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "server_script_sandbox")
        self.assertIn("frappe.get_roles", result["error"])
        self.assertFalse(validated["success"])
        self.assertFalse(frappe.db.exists("Server Script", SCRIPT_NAME))

    def test_create_allows_a_clean_script(self):
        with patch(SCRIPTS_ENABLED, return_value=True):
            result = DocumentCreate().execute(
                {"doctype": "Server Script", "data": _script_data(CLEAN_SCRIPT)}
            )

        self.assertTrue(result["success"], result)

    def test_an_edit_that_breaks_the_script_is_refused_and_the_stored_script_kept(self):
        self._insert("label = f'{1} items'")

        with patch(SCRIPTS_ENABLED, return_value=True):
            result = DocumentUpdate().execute(
                {
                    "doctype": "Server Script",
                    "name": SCRIPT_NAME,
                    "edits": [{"field": "script", "find": "f'{1} items'", "replace": "'{} items'.format(1)"}],
                }
            )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "server_script_sandbox")
        self.assertEqual(frappe.db.get_value("Server Script", SCRIPT_NAME, "script"), "label = f'{1} items'")

    def test_switching_on_a_stored_bad_script_is_refused(self):
        self._insert("frappe.get_roles()")

        with patch(SCRIPTS_ENABLED, return_value=True):
            result = DocumentUpdate().execute(
                {"doctype": "Server Script", "name": SCRIPT_NAME, "data": {"disabled": 0}}
            )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "server_script_sandbox")
        self.assertEqual(frappe.db.get_value("Server Script", SCRIPT_NAME, "disabled"), 1)

    def test_switching_off_a_bad_script_is_allowed(self):
        self.assertIsNone(
            server_script_code_guard("Server Script", {"disabled": 1}, current_script="frappe.get_roles()")
        )

    def test_other_doctypes_are_not_checked(self):
        self.assertIsNone(server_script_code_guard("Client Script", {"script": "frappe.get_roles()"}))
