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
Test suite for Search Tools using Plugin Architecture
"""

import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestSearchTools(BaseAssistantTest):
    """Test search tools through plugin registry"""

    def setUp(self):
        super().setUp()
        self.registry = get_tool_registry()

    def test_get_tools_structure(self):
        """Test that search tools are properly registered"""
        tools = self.registry.get_available_tools()
        tool_names = [tool["name"] for tool in tools]

        # Check for search tools
        expected_tools = ["search_documents"]
        found_tools = [tool for tool in expected_tools if tool in tool_names]

        self.assertGreater(len(found_tools), 0, f"Should find search tools. Available: {tool_names}")

    def test_execute_tool_routing(self):
        """Test that tool routing works correctly"""
        tools = self.registry.get_available_tools()
        if tools:
            self.assertTrue(hasattr(self.registry, "execute_tool"))
            self.assertTrue(hasattr(self.registry, "get_available_tools"))

    def test_execute_tool_invalid_tool(self):
        """Test handling of invalid tool names"""
        try:
            result = self.registry.execute_tool("nonexistent_search_tool", {})
            self.assertIsInstance(result, dict)
            self.assertIn("error", result)
        except Exception as e:
            self.assertIsInstance(e, (ValueError, KeyError, AttributeError))

    def test_search_documents_basic(self):
        """Test basic document search"""
        if not self.registry.has_tool("search_documents"):
            self.skipTest("search_documents tool not available")

        arguments = {"query": "Admin"}

        try:
            result = self.registry.execute_tool("search_documents", arguments)
            self.assertIsInstance(result, dict)
        except Exception:
            # Search may fail for various reasons
            pass

    # Placeholder tests for other search functionality
    def test_search_documents_with_filters(self):
        self.skipTest("Search with filters test placeholder")

    def test_global_search_uses_permission_aware_query(self):
        """Regression guard for #189: global_search (behind the search_documents
        tool) must use frappe.get_list, not the permission-bypassing get_all."""
        from frappe_assistant_core.plugins.core.tools import search_tools

        with ExitStack() as stack:
            # Make exactly one doctype exist and be readable so a single query
            # runs. global_search calls frappe.db.exists("DocType", <doctype>),
            # so the doctype name is the second positional arg.
            stack.enter_context(
                patch.object(
                    search_tools.frappe.db,
                    "exists",
                    side_effect=lambda *a, **k: "Employee" in a,
                )
            )
            stack.enter_context(
                patch.object(
                    search_tools.frappe,
                    "has_permission",
                    side_effect=lambda doctype, *a, **k: doctype == "Employee",
                )
            )
            get_all = stack.enter_context(
                patch.object(
                    search_tools.frappe,
                    "get_all",
                    side_effect=AssertionError("frappe.get_all bypasses DocType permissions"),
                )
            )
            get_list = stack.enter_context(patch.object(search_tools.frappe, "get_list"))
            get_list.return_value = [{"name": "EMP-0001"}]

            result = search_tools.SearchTools.global_search(query="EMP", limit=20)

        self.assertTrue(result.get("success"), result)
        get_all.assert_not_called()
        self.assertTrue(get_list.called, "global_search must query via frappe.get_list")
        for call in get_list.call_args_list:
            self.assertFalse(
                call.kwargs.get("ignore_permissions", True),
                "global_search must pass ignore_permissions=False",
            )

    def test_search_doctype_uses_permission_aware_query(self):
        """Regression guard for #189: search_doctype (behind the search_doctype
        tool) must use frappe.get_list, not the permission-bypassing get_all."""
        from frappe_assistant_core.plugins.core.tools import search_tools

        with ExitStack() as stack:
            stack.enter_context(patch.object(search_tools.frappe.db, "exists", return_value=True))
            stack.enter_context(patch.object(search_tools.frappe, "has_permission", return_value=True))
            # Minimal meta stub: one searchable Data field, no title field.
            meta = MagicMock()
            meta.title_field = None
            field = MagicMock(fieldtype="Data", hidden=False, fieldname="employee_name")
            meta.fields = [field]
            stack.enter_context(patch.object(search_tools.frappe, "get_meta", return_value=meta))
            get_all = stack.enter_context(
                patch.object(
                    search_tools.frappe,
                    "get_all",
                    side_effect=AssertionError("frappe.get_all bypasses DocType permissions"),
                )
            )
            get_list = stack.enter_context(patch.object(search_tools.frappe, "get_list"))
            get_list.return_value = [{"name": "EMP-0001", "employee_name": "Allowed"}]

            result = search_tools.SearchTools.search_doctype(doctype="Employee", query="All", limit=20)

        self.assertTrue(result.get("success"), result)
        get_all.assert_not_called()
        self.assertEqual(get_list.call_count, 1)
        call = get_list.call_args_list[0]
        self.assertEqual(call.args[0], "Employee")
        self.assertFalse(call.kwargs.get("ignore_permissions", True))

    def test_search_empty_query(self):
        self.skipTest("Empty query test placeholder")


class TestSearchToolsIntegration(BaseAssistantTest):
    """Integration tests for search tools"""

    def setUp(self):
        super().setUp()
        self.registry = get_tool_registry()

    def test_search_workflow(self):
        self.skipTest("Search workflow test placeholder")
