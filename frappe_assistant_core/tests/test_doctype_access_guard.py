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
Tests for the FAC DocType access guard (issue #249).

Reads defer entirely to frappe.has_permission(); only writes to code-execution and
schema/permission DocTypes are hard-blocked at the FAC layer.
"""

from unittest.mock import patch

from frappe_assistant_core.core.security_config import (
    WRITE_PERM_TYPES,
    WRITE_PROTECTED_DOCTYPES,
    is_doctype_accessible,
    validate_document_access,
)
from frappe_assistant_core.tests.base_test import BaseAssistantTest

LOW_PRIV_ROLE = "Default"


class TestDocTypeAccessGuard(BaseAssistantTest):
    """The guard may only ever deny what Frappe would allow, never the reverse."""

    def test_read_is_allowed_for_write_protected_doctypes(self):
        """A low-privilege role reaches the Frappe permission check on Server Script."""
        for doctype in ("Server Script", "Client Script", "Custom Field", "DocType"):
            with self.subTest(doctype=doctype):
                self.assertTrue(is_doctype_accessible(doctype, LOW_PRIV_ROLE, "read"))

    def test_read_is_allowed_for_previously_blocklisted_doctypes(self):
        """DocTypes dropped from the old read blocklist are no longer special-cased."""
        for doctype in ("Error Log", "System Settings", "Email Queue", "Integration Request"):
            with self.subTest(doctype=doctype):
                self.assertTrue(is_doctype_accessible(doctype, LOW_PRIV_ROLE, "read"))

    def test_read_defaults_when_perm_type_omitted(self):
        """The default perm_type is a read, so it must not block."""
        self.assertTrue(is_doctype_accessible("Server Script", LOW_PRIV_ROLE))

    def test_writes_to_protected_doctypes_are_blocked(self):
        """Every mutating perm type is refused on every write-protected DocType."""
        for doctype in WRITE_PROTECTED_DOCTYPES:
            for perm_type in sorted(WRITE_PERM_TYPES):
                with self.subTest(doctype=doctype, perm_type=perm_type):
                    self.assertFalse(is_doctype_accessible(doctype, LOW_PRIV_ROLE, perm_type))

    def test_assistant_admin_is_not_collapsed_to_assistant_user(self):
        """Pre-#249 both roles indexed into the same blocklist; roles no longer key it."""
        for role in ("Assistant Admin", "Assistant User", "MCP Read Only"):
            with self.subTest(role=role):
                self.assertTrue(is_doctype_accessible("Server Script", role, "read"))
                self.assertFalse(is_doctype_accessible("Server Script", role, "write"))

    def test_system_manager_bypasses_the_write_block(self):
        """System Manager keeps its bypass so existing MCP integrations don't break."""
        self.assertTrue(is_doctype_accessible("Server Script", "System Manager", "write"))

    def test_ordinary_doctypes_are_untouched(self):
        """Business DocTypes are governed by Frappe permissions for reads and writes."""
        for perm_type in ("read", "write", "create", "delete"):
            with self.subTest(perm_type=perm_type):
                self.assertTrue(is_doctype_accessible("Sales Invoice", LOW_PRIV_ROLE, perm_type))


class TestValidateDocumentAccess(BaseAssistantTest):
    """validate_document_access() must hand reads to frappe.has_permission()."""

    def test_read_denial_comes_from_frappe_not_the_blocklist(self):
        """Without a DocPerm the refusal is a permission error, not a role restriction."""
        with patch(
            "frappe_assistant_core.core.security_config.get_user_primary_role",
            return_value=LOW_PRIV_ROLE,
        ), patch("frappe.has_permission", return_value=False):
            result = validate_document_access("someone@example.com", "Server Script", "", "read")

        self.assertFalse(result["success"])
        self.assertIn("Insufficient read permissions", result["error"])

    def test_granted_read_permission_now_takes_effect(self):
        """The reporter's case: a Custom DocPerm granting read is finally honoured."""
        with patch(
            "frappe_assistant_core.core.security_config.get_user_primary_role",
            return_value=LOW_PRIV_ROLE,
        ), patch("frappe.has_permission", return_value=True):
            result = validate_document_access("someone@example.com", "Server Script", "", "read")

        self.assertTrue(result["success"])

    def test_write_is_blocked_before_the_permission_check(self):
        """A DocPerm granting write on Server Script still cannot write over MCP."""
        with patch(
            "frappe_assistant_core.core.security_config.get_user_primary_role",
            return_value=LOW_PRIV_ROLE,
        ), patch("frappe.has_permission", return_value=True) as has_permission:
            result = validate_document_access("someone@example.com", "Server Script", "", "write")

        self.assertFalse(result["success"])
        self.assertIn("blocked over MCP", result["error"])
        has_permission.assert_not_called()
