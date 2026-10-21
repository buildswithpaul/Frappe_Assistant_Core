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

from frappe_assistant_core.plugins.core.tools.create_document import DocumentCreate
from frappe_assistant_core.plugins.core.tools.get_doctype_info import GetDoctypeInfo
from frappe_assistant_core.tests.base_test import BaseAssistantTest
from frappe_assistant_core.utils.customisation import CUSTOMISATION_DOCTYPES, server_script_guard

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
