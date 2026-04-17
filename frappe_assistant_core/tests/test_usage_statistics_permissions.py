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

"""Regression tests for usage statistics endpoint permissions."""

from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestUsageStatisticsPermissions(BaseAssistantTest):
    """Ensure usage statistics are restricted to assistant admins."""

    ASSISTANT_USER = "test_assistant_user@example.com"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._create_assistant_user()

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        if frappe.db.exists("User", cls.ASSISTANT_USER):
            frappe.delete_doc("User", cls.ASSISTANT_USER, force=True)
        super().tearDownClass()

    @classmethod
    def _create_assistant_user(cls):
        if frappe.db.exists("User", cls.ASSISTANT_USER):
            frappe.delete_doc("User", cls.ASSISTANT_USER, force=True)

        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": cls.ASSISTANT_USER,
                "first_name": "Assistant",
                "last_name": "User",
                "enabled": 1,
                "new_password": "test_password_123",
                "user_type": "System User",
            }
        )
        user.append("roles", {"role": "Assistant User"})
        user.insert(ignore_permissions=True)
        frappe.clear_cache(user=cls.ASSISTANT_USER)

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def test_admin_usage_statistics_blocked_for_assistant_user(self):
        """Assistant User cannot access admin usage statistics."""
        from frappe_assistant_core.api.admin_api import get_usage_statistics

        frappe.set_user(self.ASSISTANT_USER)
        frappe.clear_cache(user=self.ASSISTANT_USER)

        with self.enforce_only_for_checks():
            with self.assertRaises(frappe.PermissionError):
                get_usage_statistics()

    def test_admin_usage_statistics_allowed_for_admin(self):
        """Administrator can access admin usage statistics."""
        from frappe_assistant_core.api.admin_api import get_usage_statistics

        mock_plugin_manager = MagicMock()
        mock_plugin_manager.get_all_tools.return_value = {"sample_tool": object()}
        audit_stat_counts = [3, 1, 2]  # audit log total, today, this week

        frappe.set_user("Administrator")
        with self.enforce_only_for_checks(), patch(
            "frappe_assistant_core.api.admin.stats.frappe.db.count",
            side_effect=audit_stat_counts,
        ), patch(
            "frappe_assistant_core.api.admin.stats.frappe.db.get_list",
            return_value=[],
        ), patch(
            "frappe_assistant_core.utils.plugin_manager.get_plugin_manager",
            return_value=mock_plugin_manager,
        ):
            response = get_usage_statistics()

        self.assertTrue(response["success"])
        self.assertEqual(response["data"]["audit_logs"]["total"], 3)
        self.assertEqual(response["data"]["tools"]["total"], 1)

    def test_assistant_usage_statistics_blocked_for_assistant_user(self):
        """Assistant User cannot access global usage statistics."""
        from frappe_assistant_core.api.assistant_api import get_usage_statistics

        frappe.set_user(self.ASSISTANT_USER)
        with patch(
            "frappe_assistant_core.api.assistant_api._authenticate_request",
            return_value=self.ASSISTANT_USER,
        ):
            response = get_usage_statistics()

        self.assertFalse(response["success"])
        self.assertIn("administrator permissions required", response["error"])

    def test_assistant_usage_statistics_allowed_for_admin(self):
        """Administrator can access assistant usage statistics."""
        from frappe_assistant_core.api.assistant_api import get_usage_statistics

        mock_plugin_manager = MagicMock()
        mock_plugin_manager.get_all_tools.return_value = {"sample_tool": object()}
        usage_stat_counts = [3, 1, 2, 3, 1, 2]  # connections total/today/week, audit total/today/week

        frappe.set_user("Administrator")
        with self.enforce_only_for_checks(), patch(
            "frappe_assistant_core.api.assistant_api._authenticate_request",
            return_value="Administrator",
        ), patch(
            "frappe_assistant_core.api.assistant_api.frappe.db.count",
            side_effect=usage_stat_counts,
        ), patch(
            "frappe_assistant_core.api.assistant_api.frappe.db.get_list",
            return_value=[],
        ), patch(
            "frappe_assistant_core.utils.plugin_manager.get_plugin_manager",
            return_value=mock_plugin_manager,
        ):
            response = get_usage_statistics()

        self.assertTrue(response["success"])
        self.assertEqual(response["data"]["audit_logs"]["total"], 3)
        self.assertEqual(response["data"]["tools"]["enabled"], 1)
