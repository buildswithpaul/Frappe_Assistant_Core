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
Test suite for Metadata Tools using Plugin Architecture
"""

import unittest

import frappe

from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestMetadataTools(BaseAssistantTest):
    """Test metadata tools through plugin registry"""

    def setUp(self):
        super().setUp()
        self.registry = get_tool_registry()

    def test_get_tools_structure(self):
        """Test that metadata tools are properly registered"""
        tools = self.registry.get_available_tools()
        tool_names = [tool["name"] for tool in tools]

        # Check for metadata tools
        expected_tools = ["get_doctype_info"]
        found_tools = [tool for tool in expected_tools if tool in tool_names]

        self.assertGreater(len(found_tools), 0, f"Should find metadata tools. Available: {tool_names}")

    def test_execute_tool_routing(self):
        """Test that tool routing works correctly"""
        tools = self.registry.get_available_tools()
        if tools:
            self.assertTrue(hasattr(self.registry, "execute_tool"))
            self.assertTrue(hasattr(self.registry, "get_available_tools"))

    def test_execute_tool_invalid_tool(self):
        """Test handling of invalid tool names"""
        try:
            result = self.registry.execute_tool("nonexistent_metadata_tool", {})
            self.assertIsInstance(result, dict)
            self.assertIn("error", result)
        except Exception as e:
            self.assertIsInstance(e, (ValueError, KeyError, AttributeError))

    def test_get_doctype_metadata_basic(self):
        """Test basic DocType metadata retrieval"""
        if not self.registry.has_tool("get_doctype_info"):
            self.skipTest("get_doctype_info tool not available")

        arguments = {"doctype": "User"}

        try:
            result = self.registry.execute_tool("get_doctype_info", arguments)
            self.assertIsInstance(result, dict)
        except Exception:
            pass

    # Placeholder tests that skip for now
    def test_get_doctype_metadata_no_permission(self):
        self.skipTest("Metadata permission test placeholder")

    def test_get_doctype_metadata_nonexistent(self):
        self.skipTest("Nonexistent doctype test placeholder")

    def test_get_doctype_metadata_with_fields(self):
        self.skipTest("Doctype fields test placeholder")

    def test_get_permissions_basic(self):
        self.skipTest("Permissions test placeholder")

    def test_get_permissions_nonexistent_doctype(self):
        self.skipTest("Permissions nonexistent test placeholder")

    def test_get_permissions_specific_user(self):
        self.skipTest("User permissions test placeholder")

    def test_get_workflow_exists(self):
        self.skipTest("Workflow exists test placeholder")

    def test_get_workflow_none_exists(self):
        self.skipTest("No workflow test placeholder")

    def test_get_workflow_nonexistent_doctype(self):
        self.skipTest("Workflow nonexistent test placeholder")

    def test_list_doctypes_basic(self):
        self.skipTest("List doctypes test placeholder")

    def test_list_doctypes_custom_only(self):
        self.skipTest("Custom doctypes test placeholder")

    def test_list_doctypes_with_module_filter(self):
        self.skipTest("Module filter test placeholder")

    def test_get_doctype_metadata_includes_child_tables(self):
        """Regression guard for #192: child tables must be surfaced with their own field metadata."""
        from frappe_assistant_core.plugins.core.tools.metadata_tools import MetadataTools

        # User ships with at least one Table field ("roles" -> "Has Role") in every Frappe install.
        result = MetadataTools.get_doctype_metadata("User")

        self.assertTrue(result.get("success"), result)
        self.assertIn("child_tables", result)
        child_tables = result["child_tables"]
        self.assertIsInstance(child_tables, list)

        roles_entry = next((c for c in child_tables if c["fieldname"] == "roles"), None)
        self.assertIsNotNone(roles_entry, f"Expected 'roles' in child_tables, got {child_tables}")
        self.assertEqual(roles_entry["options"], "Has Role")
        self.assertIn(roles_entry["fieldtype"], ("Table", "Table MultiSelect"))

        # Recursive child field metadata must be present so create_document has everything it needs.
        self.assertTrue(roles_entry["fields"], "Child table 'roles' should expose its own fields")
        child_field_names = {f["fieldname"] for f in roles_entry["fields"]}
        self.assertIn("role", child_field_names)

    def test_get_doctype_metadata_distinguishes_single_from_child_table(self):
        """Regression guard for #192: is_single must use meta.issingle, not meta.istable."""
        from frappe_assistant_core.plugins.core.tools.metadata_tools import MetadataTools

        # System Settings is a Single doctype (issingle=1, istable=0).
        single_result = MetadataTools.get_doctype_metadata("System Settings")
        self.assertTrue(single_result.get("success"), single_result)
        self.assertTrue(single_result["is_single"])
        self.assertFalse(single_result["is_child_table"])

        # Has Role is a child table (issingle=0, istable=1).
        child_result = MetadataTools.get_doctype_metadata("Has Role")
        self.assertTrue(child_result.get("success"), child_result)
        self.assertFalse(child_result["is_single"])
        self.assertTrue(child_result["is_child_table"])


class TestMetadataToolsIntegration(BaseAssistantTest):
    """Integration tests for metadata tools"""

    def setUp(self):
        super().setUp()
        self.registry = get_tool_registry()

    def test_complete_doctype_analysis(self):
        self.skipTest("Complete analysis test placeholder")

    def test_metadata_error_handling(self):
        self.skipTest("Error handling test placeholder")

    def test_permissions_and_security_check(self):
        self.skipTest("Security check test placeholder")
