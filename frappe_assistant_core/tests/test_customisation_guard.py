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

"""Refusing active Server Scripts on a site where server scripts are switched off (#34355)."""

from unittest.mock import patch

import frappe

from frappe_assistant_core.core.security_config import validate_document_access
from frappe_assistant_core.plugins.core.tools.create_document import DocumentCreate
from frappe_assistant_core.plugins.core.tools.get_doctype_info import GetDoctypeInfo
from frappe_assistant_core.plugins.core.tools.update_document import DocumentUpdate
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.customisation import (
    CUSTOMISATION_DOCTYPES,
    applies_to,
    server_script_guard,
)

SCRIPTS_ENABLED = "frappe_assistant_core.utils.customisation.server_scripts_enabled"
SCRIPT_NAME = "FAC Guard Probe Script"


def _script_data(**overrides) -> dict:
    data = {
        "name": SCRIPT_NAME,
        "script_type": "DocType Event",
        "reference_doctype": "ToDo",
        "doctype_event": "Before Save",
        "script": "pass",
    }
    data.update(overrides)
    return data


class TestServerScriptGuard(BaseAssistantTest):
    def tearDown(self):
        # The tool test must leave no Server Script behind even when it fails
        if frappe.db.exists("Server Script", SCRIPT_NAME):
            frappe.delete_doc("Server Script", SCRIPT_NAME, force=True, ignore_permissions=True)
        super().tearDown()

    def test_customisation_doctypes_include_server_script(self):
        self.assertIn("Server Script", CUSTOMISATION_DOCTYPES)
        self.assertEqual(len(CUSTOMISATION_DOCTYPES), 13)

    def test_create_enabled_server_script_refused_when_disabled(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = server_script_guard("Server Script", _script_data())

        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "server_scripts_disabled")
        self.assertIn("switched off", result["error"])
        self.assertIn("ToDo", result["error"])
        self.assertTrue(result["guidance"])

    def test_create_disabled_server_script_allowed_when_disabled(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            self.assertIsNone(server_script_guard("Server Script", _script_data(disabled=1)))

    def test_update_enabling_server_script_refused_when_disabled(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = server_script_guard("Server Script", {"disabled": 0}, current_disabled=1)

        self.assertEqual(result["error_type"], "server_scripts_disabled")

    def test_string_zero_disabled_counts_as_enabled_on_create(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = server_script_guard("Server Script", _script_data(disabled="0"))

        self.assertEqual(result["error_type"], "server_scripts_disabled")

    def test_string_zero_disabled_counts_as_enabled_on_update(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = server_script_guard("Server Script", {"disabled": "0"}, current_disabled=1)

        self.assertEqual(result["error_type"], "server_scripts_disabled")

    def test_non_event_script_gets_neutral_wording(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = server_script_guard(
                "Server Script", {"script_type": "Scheduler Event", "reference_doctype": "ToDo"}
            )

        self.assertIn("would not run", result["error"])
        self.assertNotIn("ToDo", result["error"])

    def test_update_uses_stored_script_type_for_wording(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = server_script_guard(
                "Server Script",
                {"disabled": 0},
                current_disabled=1,
                current_reference_doctype="ToDo",
                current_script_type="Scheduler Event",
            )

        self.assertEqual(result["error_type"], "server_scripts_disabled")
        self.assertIn("would not run", result["error"])

    def test_update_falls_back_to_stored_reference_doctype(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = server_script_guard(
                "Server Script", {"disabled": 0}, current_disabled=1, current_reference_doctype="ToDo"
            )

        self.assertIn("every ToDo", result["error"])

    def test_update_document_tool_refuses_enabling_script(self):
        # Production reaches this state on a site with scripts off: a script saved disabled
        # earlier (the guard allows it), which the model later tries to switch on.
        with patch(SCRIPTS_ENABLED, return_value=True):
            frappe.get_doc({"doctype": "Server Script", **_script_data(disabled=1)}).insert()

        with patch(SCRIPTS_ENABLED, return_value=False):
            result = DocumentUpdate().execute(
                {"doctype": "Server Script", "name": SCRIPT_NAME, "data": {"disabled": 0}}
            )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "server_scripts_disabled")
        self.assertIn("every ToDo", result["error"])
        self.assertEqual(frappe.db.get_value("Server Script", SCRIPT_NAME, "disabled"), 1)

    def test_update_leaving_server_script_disabled_allowed(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            self.assertIsNone(server_script_guard("Server Script", {"script": "pass"}, current_disabled=1))

    def test_other_doctype_unaffected(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            self.assertIsNone(server_script_guard("Client Script", _script_data()))

    def test_enabled_scripts_allow_everything(self):
        with patch(SCRIPTS_ENABLED, return_value=True):
            self.assertIsNone(server_script_guard("Server Script", _script_data()))

    def test_create_document_tool_returns_guard_error(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = DocumentCreate().execute({"doctype": "Server Script", "data": _script_data()})
            validated = DocumentCreate().execute(
                {"doctype": "Server Script", "data": _script_data(), "validate_only": True}
            )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "server_scripts_disabled")
        self.assertFalse(validated["success"])
        self.assertFalse(frappe.db.exists("Server Script", SCRIPT_NAME))

    def test_get_doctype_info_reports_server_script_flag(self):
        with patch(SCRIPTS_ENABLED, return_value=False):
            result = GetDoctypeInfo().execute({"doctype": "Server Script"})

        self.assertTrue(result["success"])
        self.assertIs(result["server_scripts_enabled"], False)

    def test_get_doctype_info_omits_flag_for_other_doctypes(self):
        result = GetDoctypeInfo().execute({"doctype": "ToDo"})

        self.assertNotIn("server_scripts_enabled", result)


NON_SM_USER = "test-cust-nonsm@example.com"
SM_USER = "test-cust-sm@example.com"
TEST_FIELD = "custom_test_plan_x"
TEST_FIELD_NAME = f"ToDo-{TEST_FIELD}"


def _make_user(email: str, role: str) -> None:
    if frappe.db.exists("User", email):
        return
    user = frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "first_name": "Cust Probe",
            "send_welcome_email": 0,
            "roles": [{"role": role}],
        }
    )
    user.flags.ignore_permissions = True
    user.insert()


class TestAppliesToHelper(BaseAssistantTest):
    def test_maps_each_customisation_doctype_to_its_target_field(self):
        cases = {
            "Custom Field": {"dt": "ToDo"},
            "Property Setter": {"doc_type": "ToDo"},
            "Client Script": {"dt": "ToDo"},
            "Server Script": {"reference_doctype": "ToDo"},
        }
        for doctype, values in cases.items():
            with self.subTest(doctype=doctype):
                result = applies_to(doctype, values)
                self.assertEqual(result["doctype"], "ToDo")
                self.assertTrue(result["url"].endswith("/app/todo/new"))

    def test_slug_uses_hyphens(self):
        result = applies_to("Custom Field", {"dt": "Sales Invoice"})

        self.assertTrue(result["url"].endswith("/app/sales-invoice/new"))

    def test_none_for_other_doctypes_or_missing_target(self):
        self.assertIsNone(applies_to("ToDo", {"dt": "ToDo"}))
        self.assertIsNone(applies_to("Custom Field", {}))


class TestWriteResultLinks(BaseAssistantTest):
    def tearDown(self):
        frappe.flags.in_create_custom_fields = False
        if frappe.db.exists("Custom Field", TEST_FIELD_NAME):
            frappe.delete_doc("Custom Field", TEST_FIELD_NAME, force=True, ignore_permissions=True)
        for name in frappe.get_all("ToDo", filters={"description": "FAC link probe"}, pluck="name"):
            frappe.delete_doc("ToDo", name, force=True, ignore_permissions=True)
        super().tearDown()

    def _create_todo(self) -> dict:
        return DocumentCreate().execute({"doctype": "ToDo", "data": {"description": "FAC link probe"}})

    def test_create_result_has_url(self):
        result = self._create_todo()

        self.assertTrue(result["success"], result)
        self.assertTrue(result["url"].endswith(f"/todo/{result['name']}"))
        self.assertNotIn("applies_to", result)

    def test_custom_field_result_has_applies_to(self):
        # Production adds the ToDo column here; the base class no-ops commit(), which Frappe's
        # DDL needs, so the flag skips only that schema step. The result shape is unaffected.
        frappe.flags.in_create_custom_fields = True
        result = DocumentCreate().execute(
            {
                "doctype": "Custom Field",
                "data": {"dt": "ToDo", "fieldname": TEST_FIELD, "label": "Plan X", "fieldtype": "Data"},
            }
        )

        self.assertTrue(result["success"], result)
        self.assertEqual(result["applies_to"]["doctype"], "ToDo")
        self.assertTrue(result["applies_to"]["url"].endswith("/app/todo/new"))

    def test_update_result_has_url(self):
        name = self._create_todo()["name"]

        result = DocumentUpdate().execute(
            {"doctype": "ToDo", "name": name, "data": {"description": "FAC link probe"}}
        )

        self.assertTrue(result["success"], result)
        self.assertTrue(result["url"].endswith(f"/todo/{name}"))


class TestPlainLanguageErrors(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        _make_user(NON_SM_USER, "Desk User")
        _make_user(SM_USER, "System Manager")

    def tearDown(self):
        frappe.set_user("Administrator")
        for email in (NON_SM_USER, SM_USER):
            if frappe.db.exists("User", email):
                frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        super().tearDown()

    def test_guard_error_is_plain_and_typed(self):
        result = validate_document_access(NON_SM_USER, "Server Script", None, "create")

        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "permission_error")
        self.assertNotIn("over MCP", result["error"])
        self.assertIn("System Manager", result["error"])

    def test_missing_script_manager_named(self):
        frappe.set_user(SM_USER)

        result = DocumentCreate().execute({"doctype": "Server Script", "data": _script_data()})

        self.assertFalse(result["success"])
        self.assertIn("Script Manager", result["error"])
        self.assertEqual(result["error_type"], "permission_error")

    def test_other_missing_permission_does_not_name_script_manager(self):
        result = validate_document_access(NON_SM_USER, "Workflow", None, "read")

        if not result["success"]:
            self.assertNotIn("Script Manager", result["error"])

    def test_validate_only_description_is_honest(self):
        description = DocumentCreate().inputSchema["properties"]["validate_only"]["description"]

        self.assertIn("does not check mandatory fields", description)
