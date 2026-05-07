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
Test suite for Document Tools using Plugin Architecture
Tests document operations through the tool registry
"""

import json
import unittest
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestDocumentTools(BaseAssistantTest):
    """Test document tools through plugin registry"""

    def setUp(self):
        super().setUp()
        self.registry = get_tool_registry()
        self.test_doctype = "ToDo"  # Safe test doctype that always exists

    def test_get_tools_structure(self):
        """Test that document tools are properly registered"""
        tools = self.registry.get_available_tools()
        tool_names = [tool["name"] for tool in tools]

        # Check for core document tools
        expected_tools = [
            "create_document",
            "get_document",
            "update_document",
            "list_documents",
            "delete_document",
        ]
        found_tools = [tool for tool in expected_tools if tool in tool_names]

        self.assertGreater(len(found_tools), 0, f"Should find document tools. Available: {tool_names}")

    def test_create_document_basic(self):
        """Test basic document creation"""
        if not self.registry.has_tool("create_document"):
            self.skipTest("create_document tool not available")

        # Test with minimal valid data
        arguments = {"doctype": self.test_doctype, "data": {"description": "Test ToDo created by test suite"}}

        try:
            result = self.registry.execute_tool("create_document", arguments)
            self.assertIsInstance(result, dict)

            # Should have success status
            if "success" in result:
                if result.get("success"):
                    # New format: name is directly in result, not nested under "data"
                    self.assertIn("name", result)
                else:
                    # Failed creation should have error message
                    self.assertIn("error", result)
        except Exception as e:
            # Tool execution should not raise unhandled exceptions
            self.fail(f"Tool execution raised exception: {str(e)}")

    def test_get_document_basic(self):
        """Test basic document retrieval"""
        if not self.registry.has_tool("get_document"):
            self.skipTest("get_document tool not available")

        # Try to get Administrator user (should always exist)
        arguments = {"doctype": "User", "name": "Administrator"}

        try:
            result = self.registry.execute_tool("get_document", arguments)
            self.assertIsInstance(result, dict)

            if "success" in result and result.get("success"):
                # Document data is directly in result for successful gets
                self.assertIn("name", result)
                self.assertEqual(result["name"], "Administrator")
        except Exception as e:
            self.fail(f"Tool execution raised exception: {str(e)}")

    def test_list_documents_via_execute_tool(self):
        """Test document listing"""
        if not self.registry.has_tool("list_documents"):
            self.skipTest("list_documents tool not available")

        arguments = {"doctype": "User", "limit": 5, "fields": ["name", "full_name"]}

        try:
            result = self.registry.execute_tool("list_documents", arguments)
            self.assertIsInstance(result, dict)

            if "success" in result and result.get("success"):
                # For list_documents, check if we have documents or results key
                if "documents" in result:
                    self.assertIsInstance(result["documents"], list)
                    if result["documents"]:
                        for doc in result["documents"]:
                            self.assertIn("name", doc)
                elif "results" in result:
                    self.assertIsInstance(result["results"], list)
                    if result["results"]:
                        for doc in result["results"]:
                            self.assertIn("name", doc)
        except Exception as e:
            self.fail(f"Tool execution raised exception: {str(e)}")

    def test_update_document_basic(self):
        """Test basic document update"""
        if not self.registry.has_tool("update_document"):
            self.skipTest("update_document tool not available")

        # Create a test document first
        if self.registry.has_tool("create_document"):
            create_args = {"doctype": self.test_doctype, "data": {"description": "Test ToDo for update"}}
            create_result = self.registry.execute_tool("create_document", create_args)

            if create_result.get("success") and "name" in create_result:
                doc_name = create_result["name"]

                # Now update it
                update_args = {
                    "doctype": self.test_doctype,
                    "name": doc_name,
                    "data": {"description": "Updated description"},
                }

                try:
                    result = self.registry.execute_tool("update_document", update_args)
                    self.assertIsInstance(result, dict)
                except Exception as e:
                    self.fail(f"Update tool execution raised exception: {str(e)}")

    def test_execute_tool_routing(self):
        """Test that tool routing works correctly"""
        # This should pass for any available tool
        tools = self.registry.get_available_tools()
        if tools:
            # Just test that we can call the registry without errors
            self.assertTrue(hasattr(self.registry, "execute_tool"))
            self.assertTrue(hasattr(self.registry, "get_available_tools"))

    def test_execute_tool_invalid_tool(self):
        """Test handling of invalid tool names"""
        try:
            result = self.registry.execute_tool("nonexistent_tool", {})
            # Should return error, not raise exception
            self.assertIsInstance(result, dict)
            self.assertIn("error", result)
        except Exception as e:
            # If it raises exception, it should be a known type
            self.assertIsInstance(e, (ValueError, KeyError, AttributeError))

    def test_create_document_with_submit(self):
        """Test document creation with submission"""
        if not self.registry.has_tool("create_document"):
            self.skipTest("create_document tool not available")

        # Use a simple doctype for testing
        arguments = {
            "doctype": self.test_doctype,
            "data": {"description": "Test ToDo with submit"},
            "submit": False,  # Don't actually submit, just test the parameter
        }

        try:
            result = self.registry.execute_tool("create_document", arguments)
            self.assertIsInstance(result, dict)
        except Exception as e:
            self.fail(f"Tool execution with submit raised exception: {str(e)}")

    def test_create_document_no_permission(self):
        """Test document creation without permission"""
        if not self.registry.has_tool("create_document"):
            self.skipTest("create_document tool not available")

        # Try to create document in a restricted doctype
        with patch("frappe.set_user") as mock_set_user:
            mock_set_user.return_value = None
            frappe.session.user = "Guest"  # Guest has limited permissions

            arguments = {
                "doctype": "User",  # Restricted doctype
                "data": {"email": "test@example.com"},
            }

            try:
                result = self.registry.execute_tool("create_document", arguments)
                self.assertIsInstance(result, dict)
                # Should fail with permission error
                if "success" in result:
                    self.assertFalse(result["success"], "Should fail due to permissions")
            except Exception:
                # Permission exceptions are acceptable
                pass

    def test_get_document_no_permission(self):
        """Test document retrieval without permission"""
        if not self.registry.has_tool("get_document"):
            self.skipTest("get_document tool not available")

        # This test might not be meaningful if Guest can read basic doctypes
        # But we test the error handling path
        arguments = {"doctype": "User", "name": "Administrator"}

        try:
            result = self.registry.execute_tool("get_document", arguments)
            self.assertIsInstance(result, dict)
        except Exception:
            # Permission exceptions are acceptable in tests
            pass

    def test_get_document_nonexistent(self):
        """Test getting a nonexistent document"""
        if not self.registry.has_tool("get_document"):
            self.skipTest("get_document tool not available")

        arguments = {"doctype": self.test_doctype, "name": "NONEXISTENT-DOC-12345"}

        try:
            result = self.registry.execute_tool("get_document", arguments)
            self.assertIsInstance(result, dict)
            # Should return error, not crash
            if "success" in result:
                self.assertFalse(result["success"], "Should fail for nonexistent document")
        except Exception:
            # DoesNotExistError is acceptable
            pass

    def test_update_document_no_permission(self):
        """Test document update without permission"""
        if not self.registry.has_tool("update_document"):
            self.skipTest("update_document tool not available")

        arguments = {
            "doctype": "User",  # Restricted doctype
            "name": "Administrator",
            "data": {"full_name": "Should Not Update"},
        }

        try:
            result = self.registry.execute_tool("update_document", arguments)
            self.assertIsInstance(result, dict)
        except Exception:
            # Permission exceptions are acceptable
            pass

    def test_update_document_rejects_child_doctype(self):
        """Direct updates to a child-table doctype must be rejected with a clear suggestion.

        Saving a child row in isolation bypasses the parent's validate() pipeline,
        leaving parent totals (grand_total, total_qty, etc.) stale. The tool should
        refuse and point the caller at the parent doc.

        The tool registry raises on success=False results, so we exercise the tool
        class directly to inspect the structured error payload.
        """
        from frappe_assistant_core.plugins.core.tools.update_document import DocumentUpdate

        # "DocField" is a built-in child of "DocType" — guaranteed to exist.
        if not frappe.db.exists("DocType", "DocField"):
            self.skipTest("DocField doctype not available in this site")

        existing = frappe.db.get_all("DocField", limit=1, fields=["name"])
        row_name = existing[0].name if existing else "nonexistent-row"

        result = DocumentUpdate().execute(
            {
                "doctype": "DocField",
                "name": row_name,
                "data": {"label": "Should Be Rejected"},
            }
        )

        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("error_type"), "child_doctype_direct_update")
        self.assertEqual(result.get("child_doctype"), "DocField")
        # When the row exists we should get parent-resolution hints back.
        if existing:
            self.assertIn("parent_doctype", result)
            self.assertIn("parent_name", result)
            self.assertIn("parent_table_fieldname", result)
            self.assertIn("suggestion", result)


class TestDocumentToolsIntegration(BaseAssistantTest):
    """Integration tests for document tools"""

    def setUp(self):
        super().setUp()
        self.registry = get_tool_registry()

    def test_document_lifecycle(self):
        """Test complete document lifecycle"""
        if not all(
            self.registry.has_tool(tool) for tool in ["create_document", "get_document", "update_document"]
        ):
            self.skipTest("Required document tools not available")

        doctype = "ToDo"

        # Create
        create_args = {"doctype": doctype, "data": {"description": "Lifecycle test document"}}

        try:
            create_result = self.registry.execute_tool("create_document", create_args)

            if not (create_result.get("success") and "name" in create_result):
                self.skipTest("Could not create test document")

            doc_name = create_result["name"]

            # Read
            get_args = {"doctype": doctype, "name": doc_name}
            get_result = self.registry.execute_tool("get_document", get_args)

            if get_result.get("success"):
                self.assertEqual(get_result["name"], doc_name)

            # Update
            update_args = {
                "doctype": doctype,
                "name": doc_name,
                "data": {"description": "Updated description"},
            }
            update_result = self.registry.execute_tool("update_document", update_args)
            self.assertIsInstance(update_result, dict)

        except Exception as e:
            self.fail(f"Document lifecycle test failed: {str(e)}")

    def test_error_handling_scenarios(self):
        """Test various error scenarios"""
        # Test with invalid arguments
        invalid_tests = [
            ("create_document", {}),  # Missing required fields
            ("get_document", {"doctype": "User"}),  # Missing name
            ("list_documents", {}),  # Missing doctype
        ]

        for tool_name, args in invalid_tests:
            if self.registry.has_tool(tool_name):
                try:
                    result = self.registry.execute_tool(tool_name, args)
                    # Should return error dict, not crash
                    self.assertIsInstance(result, dict)
                except Exception:
                    # Exceptions are also acceptable for invalid input
                    pass


class _FakeChildRow:
    """Stand-in for a Frappe child docrow. Captures field updates and a stable name."""

    def __init__(self, name=None, **fields):
        self.name = name
        for k, v in fields.items():
            setattr(self, k, v)

    def set(self, key, value):
        setattr(self, key, value)


class _FakeDoc:
    """Stand-in for a Frappe parent doc. Holds named child-table lists and supports
    the subset of the doc API used by _apply_child_table_update."""

    def __init__(self, tables):
        # tables: dict[fieldname] -> list[_FakeChildRow]
        self._tables = {k: list(v) for k, v in tables.items()}

    def get(self, field):
        return self._tables.get(field)

    def set(self, field, value):
        self._tables[field] = list(value)

    def append(self, field, row_data):
        # Mirror Frappe's behavior: append a new row built from a dict.
        if not isinstance(row_data, dict):
            raise TypeError(f"append expected dict, got {type(row_data).__name__}")
        # Strip control keys before constructing the row.
        clean = {k: v for k, v in row_data.items() if k not in ("_delete",)}
        new_row = _FakeChildRow(**clean)
        self._tables.setdefault(field, []).append(new_row)
        return new_row

    def remove(self, row):
        for rows in self._tables.values():
            if row in rows:
                rows.remove(row)
                return
        raise ValueError("row not found in any table")


class TestApplyChildTableUpdate(unittest.TestCase):
    """Unit tests for _apply_child_table_update — DB-independent."""

    def _import_helper(self):
        from frappe_assistant_core.plugins.core.tools.update_document import (
            _apply_child_table_update,
        )

        return _apply_child_table_update

    def test_replace_mode_clears_and_appends(self):
        helper = self._import_helper()
        doc = _FakeDoc(
            {
                "items": [
                    _FakeChildRow(name="r1", item_code="OLD-A", qty=1),
                    _FakeChildRow(name="r2", item_code="OLD-B", qty=2),
                ]
            }
        )
        rows = [{"item_code": "NEW-A", "qty": 10}, {"item_code": "NEW-B", "qty": 20}]

        err = helper(doc, "items", "Sales Order Item", rows, set())

        self.assertIsNone(err)
        items = doc.get("items")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].item_code, "NEW-A")
        self.assertEqual(items[0].qty, 10)
        self.assertEqual(items[1].item_code, "NEW-B")
        # No retained rows from before.
        self.assertNotIn("OLD-A", [getattr(r, "item_code", None) for r in items])

    def test_patch_mode_updates_matched_row_leaves_others(self):
        helper = self._import_helper()
        doc = _FakeDoc(
            {
                "items": [
                    _FakeChildRow(name="r1", item_code="A", qty=1),
                    _FakeChildRow(name="r2", item_code="B", qty=2),
                ]
            }
        )

        err = helper(doc, "items", "Sales Order Item", [{"name": "r1", "qty": 99}], set())

        self.assertIsNone(err)
        items = doc.get("items")
        self.assertEqual(len(items), 2)
        r1 = next(r for r in items if r.name == "r1")
        r2 = next(r for r in items if r.name == "r2")
        self.assertEqual(r1.qty, 99)
        self.assertEqual(r1.item_code, "A")  # untouched scalar preserved
        self.assertEqual(r2.qty, 2)  # other row untouched
        self.assertEqual(r2.item_code, "B")

    def test_patch_mode_appends_unnamed_rows(self):
        helper = self._import_helper()
        doc = _FakeDoc({"items": [_FakeChildRow(name="r1", item_code="A", qty=1)]})

        err = helper(
            doc,
            "items",
            "Sales Order Item",
            [{"name": "r1", "qty": 5}, {"item_code": "NEW", "qty": 7}],
            set(),
        )

        self.assertIsNone(err)
        items = doc.get("items")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].qty, 5)
        self.assertEqual(items[1].item_code, "NEW")
        self.assertEqual(items[1].qty, 7)

    def test_patch_mode_delete_marker_removes_row(self):
        helper = self._import_helper()
        doc = _FakeDoc(
            {
                "items": [
                    _FakeChildRow(name="r1", item_code="A", qty=1),
                    _FakeChildRow(name="r2", item_code="B", qty=2),
                ]
            }
        )

        err = helper(doc, "items", "Sales Order Item", [{"name": "r1", "_delete": True}], set())

        self.assertIsNone(err)
        items = doc.get("items")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].name, "r2")

    def test_delete_marker_without_name_errors(self):
        helper = self._import_helper()
        doc = _FakeDoc({"items": [_FakeChildRow(name="r1", item_code="A", qty=1)]})

        err = helper(doc, "items", "Sales Order Item", [{"_delete": True, "qty": 5}], set())

        self.assertIsNotNone(err)
        self.assertFalse(err["success"])
        self.assertEqual(err["error_type"], "child_row_not_found")

    def test_patch_mode_unknown_name_errors(self):
        helper = self._import_helper()
        doc = _FakeDoc({"items": [_FakeChildRow(name="r1", item_code="A", qty=1)]})

        err = helper(doc, "items", "Sales Order Item", [{"name": "does-not-exist", "qty": 5}], set())

        self.assertIsNotNone(err)
        self.assertFalse(err["success"])
        self.assertEqual(err["error_type"], "child_row_not_found")

    def test_restricted_field_in_child_row_rejected(self):
        helper = self._import_helper()
        doc = _FakeDoc({"items": [_FakeChildRow(name="r1", item_code="A", qty=1)]})

        err = helper(
            doc,
            "items",
            "Sales Order Item",
            [{"name": "r1", "qty": 5, "secret_key": "leak"}],
            {"secret_key"},
        )

        self.assertIsNotNone(err)
        self.assertFalse(err["success"])
        self.assertIn("secret_key", err["error"])
        # Original row untouched on rejection.
        self.assertEqual(doc.get("items")[0].qty, 1)

    def test_value_not_a_list_errors(self):
        helper = self._import_helper()
        doc = _FakeDoc({"items": []})

        err = helper(doc, "items", "Sales Order Item", {"item_code": "A"}, set())

        self.assertIsNotNone(err)
        self.assertFalse(err["success"])
        self.assertEqual(err["error_type"], "child_table_handling_error")

    def test_row_not_a_dict_errors(self):
        helper = self._import_helper()
        doc = _FakeDoc({"items": []})

        err = helper(doc, "items", "Sales Order Item", ["not-a-dict"], set())

        self.assertIsNotNone(err)
        self.assertFalse(err["success"])
        self.assertEqual(err["error_type"], "child_table_handling_error")
