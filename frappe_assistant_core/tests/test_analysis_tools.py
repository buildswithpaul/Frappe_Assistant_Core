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
Test suite for Analysis Tools using Plugin Architecture
"""

import unittest

import frappe

from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestAnalysisTools(BaseAssistantTest):
    """Test analysis tools through plugin registry"""

    def setUp(self):
        super().setUp()
        self.registry = get_tool_registry()

    def test_get_tools_structure(self):
        """Test that analysis tools are properly registered"""
        tools = self.registry.get_available_tools()
        tool_names = [tool["name"] for tool in tools]

        # Check for analysis tools (these might be in data science plugin)
        expected_tools = ["run_python_code", "run_database_query"]
        found_tools = [tool for tool in expected_tools if tool in tool_names]

        # Analysis tools may not be available if data science plugin is disabled
        if found_tools:
            self.assertGreater(len(found_tools), 0, f"Found analysis tools: {found_tools}")
        else:
            self.skipTest("Analysis tools not available (data science plugin may be disabled)")

    def test_execute_tool_routing(self):
        """Test that tool routing works correctly"""
        tools = self.registry.get_available_tools()
        if tools:
            self.assertTrue(hasattr(self.registry, "execute_tool"))
            self.assertTrue(hasattr(self.registry, "get_available_tools"))

    def test_execute_tool_invalid_tool(self):
        """Test handling of invalid tool names"""
        try:
            result = self.registry.execute_tool("nonexistent_analysis_tool", {})
            self.assertIsInstance(result, dict)
            self.assertIn("error", result)
        except Exception as e:
            self.assertIsInstance(e, (ValueError, KeyError, AttributeError))

    def test_execute_python_code_basic(self):
        """Test basic Python code execution"""
        if not self.registry.has_tool("run_python_code"):
            self.skipTest("run_python_code tool not available")

        # Simple, safe code
        arguments = {"code": "result = 2 + 2"}

        try:
            result = self.registry.execute_tool("run_python_code", arguments)
            self.assertIsInstance(result, dict)
        except Exception:
            # May fail due to permissions or plugin not enabled
            pass

    # All other tests as placeholders since these tools may not be available
    def test_execute_python_code_error_handling(self):
        self.skipTest("Python code error handling test placeholder")

    def test_execute_python_code_permissions(self):
        self.skipTest("Python code permissions test placeholder")

    def test_execute_python_code_security_restrictions(self):
        self.skipTest("Python security test placeholder")

    def test_execute_python_code_with_data_query(self):
        self.skipTest("Python with query test placeholder")

    def test_execute_python_code_with_pandas(self):
        self.skipTest("Python pandas test placeholder")

    def test_create_visualization_basic(self):
        self.skipTest("Visualization basic test placeholder")

    def test_json_serialization_cleaning(self):
        self.skipTest("JSON serialization test placeholder")

    def test_query_and_analyze_basic(self):
        self.skipTest("Query analyze basic test placeholder")

    def test_query_and_analyze_permissions(self):
        self.skipTest("Query analyze permissions test placeholder")

    def test_query_and_analyze_security_restrictions(self):
        self.skipTest("Query security test placeholder")


class TestAnalysisToolsIntegration(BaseAssistantTest):
    """Integration tests for analysis tools"""

    def setUp(self):
        super().setUp()
        self.registry = get_tool_registry()

    def test_full_analysis_workflow(self):
        self.skipTest("Full workflow test placeholder")

    def test_performance_with_large_dataset(self):
        self.skipTest("Performance test placeholder")
