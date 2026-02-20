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
Base test class for Frappe Assistant Core tests
Provides common setup and utilities for all test classes
"""

import json
import unittest
from unittest.mock import MagicMock, patch

import frappe


class BaseAssistantTest(unittest.TestCase):
    """Base test class with common setup and utilities"""

    @classmethod
    def setUpClass(cls):
        """Set up class-level test environment"""
        # Ensure we're in test mode
        frappe.flags.in_test = True

        # Set default user
        if not hasattr(frappe, "session") or not frappe.session.user:
            frappe.set_user("Administrator")

    def setUp(self):
        """Set up test environment for each test"""
        # Clear any existing test data
        self.clear_test_data()

        # Set test user
        self.test_user = "Administrator"
        frappe.set_user(self.test_user)

        # Ensure plugins are enabled for testing
        self._ensure_plugins_enabled()

    def execute_tool_and_get_result(self, registry, tool_name, arguments):
        """
        Execute a tool via registry and return unwrapped result.

        The registry wraps tool results in a 'result' key, this helper
        extracts the actual tool result for easier testing.
        """
        registry_result = registry.execute_tool(tool_name, arguments)

        # Registry execution should always succeed (unless tool not found)
        self.assertTrue(
            registry_result.get("success"), f"Registry execution failed: {registry_result.get('error')}"
        )

        # Return the actual tool result
        return registry_result.get("result", {})

    def execute_tool_expect_failure(self, registry, tool_name, arguments, expected_error_text=None):
        """
        Execute a tool via registry expecting tool-level failure.
        Returns the tool result for further assertions.
        """
        registry_result = registry.execute_tool(tool_name, arguments)

        # Registry execution should succeed even if tool fails
        self.assertTrue(
            registry_result.get("success"), f"Registry execution failed: {registry_result.get('error')}"
        )

        # Get tool result and verify it failed
        tool_result = registry_result.get("result", {})
        self.assertFalse(
            tool_result.get("success"), f"Tool execution should have failed but succeeded: {tool_result}"
        )

        # Check error message if provided
        if expected_error_text:
            self.assertIn(expected_error_text, tool_result.get("error", ""))

        return tool_result

    def tearDown(self):
        """Clean up after each test"""
        self.clear_test_data()
        self.cleanup_mocks()

    def _ensure_plugins_enabled(self):
        """Ensure core plugins are enabled for testing"""
        try:
            # Check if Assistant Core Settings exists
            if frappe.db.exists("Assistant Core Settings", "Assistant Core Settings"):
                settings = frappe.get_single("Assistant Core Settings")
                enabled_plugins = json.loads(settings.enabled_plugins_list or "[]")

                # Enable core plugin if not already enabled
                if "core" not in enabled_plugins:
                    enabled_plugins.append("core")
                    settings.enabled_plugins_list = json.dumps(enabled_plugins)
                    settings.save(ignore_permissions=True)
                    frappe.db.commit()
            else:
                # Create settings with core plugin enabled
                doc = frappe.get_doc(
                    {
                        "doctype": "Assistant Core Settings",
                        "server_enabled": 0,
                        "enabled_plugins_list": json.dumps(["core"]),
                    }
                )
                doc.insert(ignore_permissions=True)
                frappe.db.commit()

            # Force plugin manager refresh to load enabled plugins
            from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

            plugin_manager = get_plugin_manager()
            plugin_manager.refresh_plugins()

        except Exception as e:
            # Log but don't fail tests if plugin setup fails
            frappe.logger("test").warning(f"Could not ensure plugins enabled: {e}")

    def clear_test_data(self):
        """Clear any test data created during tests"""
        try:
            # Clear test documents if any were created
            test_doctypes = ["Assistant Audit Log"]

            for doctype in test_doctypes:
                if frappe.db.exists("DocType", doctype):
                    frappe.db.sql(f"DELETE FROM `tab{doctype}` WHERE name LIKE 'TEST_%'")

            frappe.db.commit()
        except Exception:
            # Ignore cleanup errors in tests
            pass

    def setup_mocks(self):
        """Set up common mocks for testing"""
        # Store original functions to restore later
        self._original_functions = {}

        # Mock frappe.get_roles to return Administrator by default
        self.mock_get_roles = patch("frappe.get_roles")
        self.mock_get_roles.start()
        frappe.get_roles.return_value = ["Administrator", "System Manager"]

        # Mock frappe.has_permission to return True by default
        self.mock_has_permission = patch("frappe.has_permission")
        self.mock_has_permission.start()
        frappe.has_permission.return_value = True

    def cleanup_mocks(self):
        """Clean up mocks after testing"""
        try:
            if hasattr(self, "mock_get_roles"):
                self.mock_get_roles.stop()
            if hasattr(self, "mock_has_permission"):
                self.mock_has_permission.stop()
        except Exception:
            pass

    def create_test_user(self, email="test@example.com", roles=None):
        """Create a test user for testing"""
        if roles is None:
            roles = ["System Manager"]

        user_doc = frappe.get_doc(
            {"doctype": "User", "email": email, "first_name": "Test", "last_name": "User", "enabled": 1}
        )

        # Add roles
        for role in roles:
            user_doc.append("roles", {"role": role})

        user_doc.insert(ignore_permissions=True)
        return user_doc

    def create_test_document(self, doctype, data):
        """Create a test document"""
        doc = frappe.get_doc(data)
        doc.doctype = doctype
        doc.name = f"TEST_{doc.name}" if hasattr(doc, "name") else None
        doc.insert(ignore_permissions=True)
        return doc

    def assert_success_response(self, response):
        """Assert that response indicates success"""
        self.assertIsInstance(response, dict)
        self.assertTrue(response.get("success"), f"Expected success=True, got: {response}")

    def assert_error_response(self, response, error_message=None):
        """Assert that response indicates error"""
        self.assertIsInstance(response, dict)
        self.assertFalse(response.get("success"), f"Expected success=False, got: {response}")

        if error_message:
            self.assertIn(error_message, response.get("error", ""))

    def assert_has_fields(self, data, required_fields):
        """Assert that data has all required fields"""
        for field in required_fields:
            self.assertIn(field, data, f"Missing required field: {field}")

    def mock_frappe_function(self, function_path, return_value=None, side_effect=None):
        """Helper to mock Frappe functions"""
        patcher = patch(function_path)
        mock = patcher.start()

        if return_value is not None:
            mock.return_value = return_value
        if side_effect is not None:
            mock.side_effect = side_effect

        return mock, patcher

    def simulate_user_context(self, user_email, roles=None):
        """Simulate user context for testing"""
        if roles is None:
            roles = ["System Manager"]

        with patch("frappe.session") as mock_session:
            mock_session.user = user_email
            with patch("frappe.get_roles", return_value=roles):
                yield

    def create_mock_data(self, count=10, prefix="TestDoc"):
        """Create mock data for testing"""
        return [
            {
                "name": f"{prefix}{i}",
                "title": f"Test Document {i}",
                "value": i * 10,
                "creation": f"2024-01-{i:02d}",
                "enabled": i % 2 == 0,
            }
            for i in range(1, count + 1)
        ]

    def assert_tool_response_structure(self, response):
        """Assert standard tool response structure"""
        self.assertIsInstance(response, dict)
        self.assertIn("success", response)

        if response.get("success"):
            # Success responses should not have error
            self.assertNotIn("error", response)
        else:
            # Error responses should have error message
            self.assertIn("error", response)
            self.assertIsInstance(response["error"], str)

    def measure_execution_time(self, func, *args, **kwargs):
        """Measure function execution time"""
        import time

        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time

        return result, execution_time

    def create_test_audit_log(self, tool_name="test_tool", status="Success"):
        """Create a test audit log entry"""
        audit_doc = frappe.get_doc(
            {
                "doctype": "Assistant Audit Log",
                "user": self.test_user,
                "tool_name": tool_name,
                "status": status,
                "operation_id": "TEST_OP_123",
                "execution_time": 1.5,
            }
        )
        audit_doc.insert(ignore_permissions=True)
        return audit_doc

    # NOTE: create_test_connection_log method removed as Assistant Connection Log no longer exists


class MockWebSocketConnection:
    """Mock WebSocket connection for testing"""

    def __init__(self, connection_id="test_conn", user="Administrator"):
        self.connection_id = connection_id
        self.user = user
        self.messages_sent = []
        self.is_closed = False

    async def send(self, message):
        """Mock send method"""
        self.messages_sent.append(message)

    async def close(self, code=None, reason=None):
        """Mock close method"""
        self.is_closed = True

    def is_open(self):
        """Check if connection is open"""
        return not self.is_closed


class TestDataBuilder:
    """Helper class to build test data"""

    @staticmethod
    def user_data(count=5):
        """Build user test data"""
        return [
            {
                "name": f"user{i}@test.com",
                "email": f"user{i}@test.com",
                "first_name": f"User{i}",
                "enabled": 1,
                "creation": f"2024-01-{i:02d}",
            }
            for i in range(1, count + 1)
        ]

    @staticmethod
    def sales_data(count=10):
        """Build sales test data"""
        return [
            {
                "name": f"SINV-{i:04d}",
                "customer": f"Customer {i}",
                "grand_total": 1000 + (i * 100),
                "posting_date": f"2024-01-{i:02d}",
                "status": "Paid" if i % 2 == 0 else "Draft",
            }
            for i in range(1, count + 1)
        ]

    @staticmethod
    def analytics_data(metrics=None):
        """Build analytics test data"""
        if metrics is None:
            metrics = ["cpu_usage", "memory_usage", "response_time"]

        import random

        return {
            metric: {
                "current": random.uniform(10, 90),
                "average": random.uniform(20, 70),
                "peak": random.uniform(70, 95),
            }
            for metric in metrics
        }
