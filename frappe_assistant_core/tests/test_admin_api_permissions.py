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
Regression tests for admin API endpoint permissions.

Ensures that non-admin users cannot access admin endpoints.
Ref: https://github.com/buildswithpaul/Frappe_Assistant_Core/issues/105
"""

import unittest

import frappe

from frappe_assistant_core.tests.base_test import BaseAssistantTest


def _strict_only_for(roles, message=False):
    """frappe.only_for replacement that enforces checks even during tests.

    The real frappe.only_for skips all checks when local.flags.in_test is True,
    making it impossible to test permission enforcement in the test runner.
    """
    if frappe.session.user == "Administrator":
        return
    if isinstance(roles, str):
        roles = (roles,)
    if set(roles).isdisjoint(frappe.get_roles()):
        if not message:
            raise frappe.PermissionError
        frappe.throw(
            f"This action is only allowed for {', '.join(roles)}",
            frappe.PermissionError,
        )


class TestAdminAPIPermissions(BaseAssistantTest):
    """Test that admin API endpoints enforce role-based access control."""

    NON_ADMIN_USER = "test_nonadmin@example.com"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._create_non_admin_user()

    @classmethod
    def _create_non_admin_user(cls):
        """Create a non-admin user with only basic roles (no System Manager or Assistant Admin)."""
        if frappe.db.exists("User", cls.NON_ADMIN_USER):
            # Clean up existing user to ensure clean state
            frappe.delete_doc("User", cls.NON_ADMIN_USER, force=True)
            frappe.db.commit()

        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": cls.NON_ADMIN_USER,
                "first_name": "Test",
                "last_name": "NonAdmin",
                "enabled": 1,
                "new_password": "test_password_123",
                "user_type": "Website User",
            }
        )
        user.insert(ignore_permissions=True)
        frappe.db.commit()

        # Remove any auto-assigned roles except All and Guest
        frappe.db.sql(
            """DELETE FROM `tabHas Role`
            WHERE parent = %s AND role NOT IN ('All', 'Guest')""",
            cls.NON_ADMIN_USER,
        )
        frappe.db.commit()

        # Clear role cache for this user
        frappe.clear_cache(user=cls.NON_ADMIN_USER)

    @classmethod
    def tearDownClass(cls):
        """Clean up test user."""
        frappe.set_user("Administrator")
        if frappe.db.exists("User", cls.NON_ADMIN_USER):
            frappe.delete_doc("User", cls.NON_ADMIN_USER, force=True)
            frappe.db.commit()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _assert_blocked_for_non_admin(self, func, *args, **kwargs):
        """Assert that calling func as a non-admin user raises PermissionError.

        Directly monkeypatches frappe.only_for to bypass the in_test skip
        that frappe applies during test runs.
        """
        import sys

        frappe.set_user(self.NON_ADMIN_USER)
        frappe.clear_cache(user=self.NON_ADMIN_USER)
        original = frappe.only_for
        frappe.only_for = _strict_only_for
        try:
            with self.assertRaises(frappe.PermissionError):
                func(*args, **kwargs)
        finally:
            frappe.only_for = original

    def _assert_allowed_for_admin(self, func, *args, **kwargs):
        """Assert that calling func as Administrator does NOT raise PermissionError."""
        frappe.set_user("Administrator")
        original = frappe.only_for
        frappe.only_for = _strict_only_for
        try:
            func(*args, **kwargs)
        except frappe.PermissionError:
            self.fail(f"{func.__name__} should be allowed for Administrator but raised PermissionError")
        except Exception:
            # Other errors (e.g. missing tool) are fine — we're only testing auth
            pass
        finally:
            frappe.only_for = original

    # =========================================================================
    # State-changing endpoints (POST-only)
    # =========================================================================

    def test_toggle_tool_blocked_for_non_admin(self):
        """Non-admin users cannot toggle tools. (Ref: Issue #105)"""
        from frappe_assistant_core.api.admin_api import toggle_tool

        self._assert_blocked_for_non_admin(toggle_tool, tool_name="get_document", enabled=False)

    def test_toggle_tool_allowed_for_admin(self):
        """Admin users can toggle tools."""
        from frappe_assistant_core.api.admin_api import toggle_tool

        self._assert_allowed_for_admin(toggle_tool, tool_name="get_document", enabled=True)

    def test_toggle_plugin_blocked_for_non_admin(self):
        """Non-admin users cannot toggle plugins."""
        from frappe_assistant_core.api.admin_api import toggle_plugin

        self._assert_blocked_for_non_admin(toggle_plugin, plugin_name="core", enable=True)

    def test_update_server_settings_blocked_for_non_admin(self):
        """Non-admin users cannot update server settings."""
        from frappe_assistant_core.api.admin_api import update_server_settings

        self._assert_blocked_for_non_admin(update_server_settings, server_enabled=1)

    def test_bulk_toggle_tools_blocked_for_non_admin(self):
        """Non-admin users cannot bulk toggle tools."""
        from frappe_assistant_core.api.admin_api import bulk_toggle_tools

        self._assert_blocked_for_non_admin(bulk_toggle_tools, tool_names=[], enabled=True)

    def test_bulk_toggle_tools_by_category_blocked_for_non_admin(self):
        """Non-admin users cannot bulk toggle tools by category."""
        from frappe_assistant_core.api.admin_api import bulk_toggle_tools_by_category

        self._assert_blocked_for_non_admin(bulk_toggle_tools_by_category, category="read_only", enabled=True)

    def test_update_tool_category_blocked_for_non_admin(self):
        """Non-admin users cannot update tool categories."""
        from frappe_assistant_core.api.admin_api import update_tool_category

        self._assert_blocked_for_non_admin(
            update_tool_category, tool_name="get_document", category="read_only"
        )

    def test_update_tool_role_access_blocked_for_non_admin(self):
        """Non-admin users cannot update tool role access."""
        from frappe_assistant_core.api.admin_api import update_tool_role_access

        self._assert_blocked_for_non_admin(
            update_tool_role_access, tool_name="get_document", role_access_mode="Allow All"
        )

    # =========================================================================
    # Read-only admin endpoints
    # =========================================================================

    def test_get_tool_registry_blocked_for_non_admin(self):
        """Non-admin users cannot view tool registry."""
        from frappe_assistant_core.api.admin_api import get_tool_registry

        self._assert_blocked_for_non_admin(get_tool_registry)

    def test_get_plugin_stats_blocked_for_non_admin(self):
        """Non-admin users cannot view plugin stats."""
        from frappe_assistant_core.api.admin_api import get_plugin_stats

        self._assert_blocked_for_non_admin(get_plugin_stats)

    def test_get_tool_stats_blocked_for_non_admin(self):
        """Non-admin users cannot view tool stats."""
        from frappe_assistant_core.api.admin_api import get_tool_stats

        self._assert_blocked_for_non_admin(get_tool_stats)

    def test_get_tool_configurations_blocked_for_non_admin(self):
        """Non-admin users cannot view tool configurations."""
        from frappe_assistant_core.api.admin_api import get_tool_configurations

        self._assert_blocked_for_non_admin(get_tool_configurations)

    def test_get_available_roles_blocked_for_non_admin(self):
        """Non-admin users cannot view available roles."""
        from frappe_assistant_core.api.admin_api import get_available_roles

        self._assert_blocked_for_non_admin(get_available_roles)

    # =========================================================================
    # Verify admin access works for read-only endpoints
    # =========================================================================

    def test_get_tool_registry_allowed_for_admin(self):
        """Admin users can view tool registry."""
        from frappe_assistant_core.api.admin_api import get_tool_registry

        self._assert_allowed_for_admin(get_tool_registry)

    def test_get_plugin_stats_allowed_for_admin(self):
        """Admin users can view plugin stats."""
        from frappe_assistant_core.api.admin_api import get_plugin_stats

        self._assert_allowed_for_admin(get_plugin_stats)

    def test_get_tool_configurations_allowed_for_admin(self):
        """Admin users can view tool configurations."""
        from frappe_assistant_core.api.admin_api import get_tool_configurations

        self._assert_allowed_for_admin(get_tool_configurations)
