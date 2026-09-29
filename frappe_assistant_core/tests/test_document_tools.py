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
from contextlib import ExitStack
from typing import List
from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.plugins.core.tools.create_document import DocumentCreate
from frappe_assistant_core.plugins.core.tools.submit_document import DocumentSubmit
from frappe_assistant_core.plugins.core.tools.update_document import DocumentUpdate
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

    def test_list_documents_uses_permission_aware_queries_for_data_and_count(self):
        """Regression guard for #189: list_documents must not use permission-bypassing APIs."""
        from frappe_assistant_core.plugins.core.tools.list_documents import DocumentList

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "frappe_assistant_core.core.security_config.validate_document_access",
                    return_value={"success": True, "role": "Default"},
                )
            )
            stack.enter_context(
                patch(
                    "frappe_assistant_core.core.security_config.filter_sensitive_fields",
                    side_effect=lambda doc, _doctype, _role: doc,
                )
            )
            stack.enter_context(
                patch(
                    "frappe_assistant_core.plugins.core.tools.list_documents.frappe.session",
                    MagicMock(user="restricted@example.com"),
                )
            )
            # Employee is not submittable; stubbed so meta loading does not issue
            # queries of its own against the mocked frappe.get_list / frappe.get_all.
            stack.enter_context(
                patch(
                    "frappe_assistant_core.plugins.core.tools.list_documents.frappe.get_meta",
                    return_value=MagicMock(is_submittable=0),
                )
            )
            get_all = stack.enter_context(
                patch(
                    "frappe_assistant_core.plugins.core.tools.list_documents.frappe.get_all",
                    side_effect=AssertionError("frappe.get_all bypasses DocType permissions"),
                )
            )
            db_count = stack.enter_context(
                patch(
                    "frappe_assistant_core.plugins.core.tools.list_documents.frappe.db.count",
                    side_effect=AssertionError("frappe.db.count bypasses DocType permissions"),
                )
            )
            get_list = stack.enter_context(
                patch("frappe_assistant_core.plugins.core.tools.list_documents.frappe.get_list")
            )
            get_list.side_effect = [
                [{"name": "EMP-0001", "employee_name": "Allowed Employee"}],
                [{"count": 1}],
            ]

            result = DocumentList().execute(
                {
                    "doctype": "Employee",
                    "filters": {},
                    "fields": ["name", "employee_name"],
                    "limit": 20,
                }
            )

        self.assertTrue(result.get("success"), result)
        self.assertEqual(result.get("count"), 1)
        self.assertEqual(result.get("total_count"), 1)
        get_all.assert_not_called()
        db_count.assert_not_called()
        self.assertEqual(get_list.call_count, 2)

        data_call = get_list.call_args_list[0]
        self.assertEqual(data_call.args[0], "Employee")
        self.assertEqual(data_call.kwargs["fields"], ["name", "employee_name"])
        self.assertEqual(data_call.kwargs["limit"], 20)
        self.assertFalse(data_call.kwargs["ignore_permissions"])

        count_call = get_list.call_args_list[1]
        self.assertEqual(count_call.args[0], "Employee")
        self.assertEqual(count_call.kwargs["fields"], [{"COUNT": "name", "as": "count"}])
        self.assertEqual(count_call.kwargs["limit"], 1)
        self.assertFalse(count_call.kwargs["ignore_permissions"])

    def test_list_documents_count_falls_back_to_string_form_on_attribute_error(self):
        """Dict-form COUNT isn't supported on Frappe v15; list_documents must fall
        back to the string form, still permission-aware, and still return a count."""
        from frappe_assistant_core.plugins.core.tools.list_documents import DocumentList

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "frappe_assistant_core.core.security_config.validate_document_access",
                    return_value={"success": True, "role": "Default"},
                )
            )
            stack.enter_context(
                patch(
                    "frappe_assistant_core.core.security_config.filter_sensitive_fields",
                    side_effect=lambda doc, _doctype, _role: doc,
                )
            )
            stack.enter_context(
                patch(
                    "frappe_assistant_core.plugins.core.tools.list_documents.frappe.session",
                    MagicMock(user="restricted@example.com"),
                )
            )
            # Employee is not submittable; stubbed so meta loading does not issue
            # queries of its own against the mocked frappe.get_list / frappe.get_all.
            stack.enter_context(
                patch(
                    "frappe_assistant_core.plugins.core.tools.list_documents.frappe.get_meta",
                    return_value=MagicMock(is_submittable=0),
                )
            )
            get_all = stack.enter_context(
                patch(
                    "frappe_assistant_core.plugins.core.tools.list_documents.frappe.get_all",
                    side_effect=AssertionError("frappe.get_all bypasses DocType permissions"),
                )
            )
            db_count = stack.enter_context(
                patch(
                    "frappe_assistant_core.plugins.core.tools.list_documents.frappe.db.count",
                    side_effect=AssertionError("frappe.db.count bypasses DocType permissions"),
                )
            )
            get_list = stack.enter_context(
                patch("frappe_assistant_core.plugins.core.tools.list_documents.frappe.get_list")
            )
            get_list.side_effect = [
                [{"name": "EMP-0001", "employee_name": "Allowed Employee"}],
                AttributeError("dict-form COUNT is not supported on this Frappe version"),
                [{"count": 1}],
            ]

            result = DocumentList().execute(
                {
                    "doctype": "Employee",
                    "filters": {},
                    "fields": ["name", "employee_name"],
                    "limit": 20,
                }
            )

        self.assertTrue(result.get("success"), result)
        self.assertEqual(result.get("count"), 1)
        self.assertEqual(result.get("total_count"), 1)
        get_all.assert_not_called()
        db_count.assert_not_called()
        self.assertEqual(get_list.call_count, 3)

        failed_count_call = get_list.call_args_list[1]
        self.assertEqual(failed_count_call.args[0], "Employee")
        self.assertEqual(failed_count_call.kwargs["fields"], [{"COUNT": "name", "as": "count"}])
        self.assertFalse(failed_count_call.kwargs["ignore_permissions"])

        fallback_count_call = get_list.call_args_list[2]
        self.assertEqual(fallback_count_call.args[0], "Employee")
        self.assertEqual(fallback_count_call.kwargs["fields"], ["count(name) as count"])
        self.assertEqual(fallback_count_call.kwargs["limit"], 1)
        self.assertFalse(fallback_count_call.kwargs["ignore_permissions"])

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

    def test_create_document_no_false_positive_for_set_missing_values_fields(self):
        """Issue #165 follow-up: fields populated by Frappe's set_missing_values()
        during validate() must not be flagged as missing.

        Quotation has reqd fields (conversion_rate, price_list_currency,
        plc_conversion_rate) that new_doc() does NOT populate — they're filled
        by the doctype controller's set_missing_values() during validate(),
        which runs inside doc.insert(). A pre-flight check that inspects
        doc.get(f) before insert() returns false positives for these.
        """
        from frappe_assistant_core.plugins.core.tools.create_document import DocumentCreate

        if not frappe.db.exists("DocType", "Quotation"):
            self.skipTest("Quotation doctype not available (ERPNext not installed)")

        cust = frappe.get_all("Customer", limit=1, pluck="name")
        item = frappe.get_all("Item", filters={"is_sales_item": 1, "disabled": 0}, limit=1, pluck="name")
        if not (cust and item):
            self.skipTest("No Customer/Item available for test")

        result = DocumentCreate().execute(
            {
                "doctype": "Quotation",
                "data": {
                    "quotation_to": "Customer",
                    "party_name": cust[0],
                    "transaction_date": frappe.utils.nowdate(),
                    "items": [{"item_code": item[0], "qty": 1, "rate": 100}],
                },
            }
        )

        # Whichever way it lands (success, or genuine missing field like
        # enquiry_reference per site config), it must NOT report any of the
        # set_missing_values()-populated fields as missing.
        false_positives = {"conversion_rate", "price_list_currency", "plc_conversion_rate"}
        if not result.get("success"):
            missing = set(result.get("missing_fields") or [])
            leaked = missing & false_positives
            self.assertFalse(
                leaked,
                f"set_missing_values() fields incorrectly reported as missing: {leaked}. "
                f"Full error: {result.get('error')}",
            )
            # If it failed, it must be for a different (genuine) reason.
            if missing:
                # Genuine missing field is fine — the structured error shape
                # is the contract here.
                self.assertEqual(result.get("error_type"), "missing_required_field")
                self.assertIn("provided_fields", result)
                self.assertIn("suggestion", result)
        else:
            # Cleanup if the create actually succeeded.
            try:
                frappe.delete_doc("Quotation", result["name"], ignore_permissions=True, force=True)
            except Exception:
                pass

    def test_create_document_mandatory_error_returns_structured_response(self):
        """When Frappe raises MandatoryError, the tool returns the structured
        missing-fields response (not a raw error string).

        ToDo has a single mandatory field (`description`) that is NOT populated
        by set_missing_values, so omitting it reliably triggers MandatoryError
        across sites.
        """
        from frappe_assistant_core.plugins.core.tools.create_document import DocumentCreate

        result = DocumentCreate().execute(
            {
                "doctype": "ToDo",
                "data": {"date": frappe.utils.nowdate()},
            }
        )

        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("success"), f"ToDo create with no description should fail: {result}")
        self.assertEqual(result.get("error_type"), "missing_required_field")
        self.assertIn("description", result.get("missing_fields") or [])
        self.assertEqual(result.get("provided_fields"), ["date"])
        self.assertIn("suggestion", result)

    def test_create_document_generic_exception_does_not_crash_on_translation(self):
        """Regression guard: the local `_, _, fields_part = ...` shadow bug.

        `_` is the translation function imported at module scope. Any local
        `_ = ...` inside execute() makes Python treat `_` as a function-local
        for the entire body, so the later `_("Document Creation Error")` call
        inside frappe.log_error raised UnboundLocalError on paths that didn't
        reach the local assignment first (e.g. the generic Exception branch
        triggered by an invalid Link reference, not by MandatoryError).

        Triggering: pass an invalid `reference_type` link value to ToDo. This
        raises a LinkValidationError (subclass of ValidationError, not
        MandatoryError), routes through the generic `except Exception`, and
        attempts to call `_(\"...\")` for log_error. The test asserts the call
        completes and returns a structured dict, never an UnboundLocalError.
        """
        from frappe_assistant_core.plugins.core.tools.create_document import DocumentCreate

        result = DocumentCreate().execute(
            {
                "doctype": "ToDo",
                "data": {
                    "description": "regression probe",
                    "reference_type": "User",
                    "reference_name": "this-user-definitely-does-not-exist@nowhere.invalid",
                },
            }
        )

        self.assertIsInstance(result, dict)
        # The call must NOT crash with UnboundLocalError no matter what error
        # path is taken. If the create somehow succeeded, that's also fine —
        # the test exists to guard the error path, not to assert a specific
        # validation outcome.
        if not result.get("success"):
            error_msg = str(result.get("error") or "")
            self.assertNotIn("referenced before assignment", error_msg)
            self.assertNotIn("UnboundLocalError", error_msg)
            self.assertIn("error_type", result)
        else:
            # Cleanup if create unexpectedly succeeded.
            try:
                frappe.delete_doc("ToDo", result["name"], ignore_permissions=True, force=True)
            except Exception:
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


class TestDocumentToolsAsNonAdminUser(BaseAssistantTest):
    """The write tools as a user who is not a System Manager.

    Frappe's ToDo permission hook lets such a user create a ToDo only when it
    names them (`allocated_to` or `assigned_by`). The DocType-level check still
    passes, so the refusal comes from `doc.insert()` as a PermissionError with no
    message: Frappe keeps the reason in `frappe.flags.error_message`.

    Every test acts as its own throwaway user and tags its rows with a unique
    string, and `tearDown` deletes both. `frappe.log_error` is stubbed for the
    whole class so no Error Log rows are written; tests read `self.log_error`.
    """

    def setUp(self):
        super().setUp()
        self.tag = f"cd-test-{frappe.generate_hash(length=8)}"
        self.users: List[str] = []
        self.acting_user = frappe.session.user
        self.non_admin = self._make_user(self.tag, roles=["Desk User"])
        frappe.flags.pop("error_message", None)
        self.addCleanup(lambda: frappe.flags.pop("error_message", None))
        log_error = patch("frappe.log_error")
        self.log_error = log_error.start()
        self.addCleanup(log_error.stop)

    def tearDown(self):
        # nosemgrep: frappe-setuser — tests run in an isolated transaction
        frappe.set_user(self.acting_user)
        for name in frappe.get_all("ToDo", filters={"description": ["like", f"%{self.tag}%"]}, pluck="name"):
            frappe.delete_doc("ToDo", name, force=True, ignore_permissions=True)
        for email in self.users:
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        super().tearDown()

    def _make_user(self, local_part: str, roles: List[str]) -> str:
        email = f"{local_part}@example.com"
        frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": "CD Test",
                "enabled": 1,
                "send_welcome_email": 0,
                "roles": [{"role": role} for role in roles],
            }
        ).insert(ignore_permissions=True)
        self.users.append(email)
        return email

    def _act_as(self, user: str) -> None:
        # nosemgrep: frappe-setuser — tests run in an isolated transaction
        frappe.set_user(user)

    def _todo_owned_by_administrator(self) -> str:
        return (
            frappe.get_doc(
                {"doctype": "ToDo", "description": f"{self.tag} theirs", "allocated_to": "Administrator"}
            )
            .insert()
            .name
        )

    def _create_todo(self, **data) -> dict:
        return DocumentCreate().execute({"doctype": "ToDo", "data": {"description": self.tag, **data}})

    def _todos_made_by_this_test(self) -> bool:
        return bool(frappe.db.exists("ToDo", {"description": ["like", f"%{self.tag}%"]}))

    def _precheck_passes(self):
        """Let the FAC pre-check pass, so the refusal has to come from Frappe itself."""
        return patch(
            "frappe_assistant_core.core.security_config.validate_document_access",
            return_value={"success": True, "role": "Default"},
        )

    def test_user_todo_that_names_nobody_is_created_for_them(self):
        self._act_as(self.non_admin)

        for label, extra in (("omitted", {}), ("blank", {"allocated_to": ""})):
            with self.subTest(allocated_to=label):
                result = self._create_todo(description=f"{self.tag} {label}", **extra)

                self.assertTrue(result.get("success"), result)
                self.assertEqual(result["owner"], self.non_admin)
                self.assertEqual(frappe.db.get_value("ToDo", result["name"], "allocated_to"), self.non_admin)

    def test_user_todo_assigned_by_themselves_stays_unallocated(self):
        self._act_as(self.non_admin)

        result = self._create_todo(assigned_by=self.non_admin)

        self.assertTrue(result.get("success"), result)
        self.assertFalse(frappe.db.get_value("ToDo", result["name"], "allocated_to"))

    def test_user_cannot_create_a_todo_assigned_by_someone_else(self):
        """Only a ToDo that names nobody gets the default: one assigned by someone else is still refused."""
        self._act_as(self.non_admin)

        result = self._create_todo(assigned_by="Administrator")

        self.assertFalse(result.get("success"), result)
        self.assertEqual(result.get("error_type"), "permission_error")
        self.assertTrue(result.get("error"), result)
        self.assertFalse(self._todos_made_by_this_test())

    def test_user_cannot_create_a_todo_for_someone_else(self):
        self._act_as(self.non_admin)

        result = self._create_todo(allocated_to="Administrator")

        self.assertFalse(result.get("success"), result)
        self.assertEqual(result.get("error_type"), "permission_error")
        self.assertTrue(result.get("error"), result)
        self.assertNotIn("<", result["error"])
        self.assertNotIn("  ", result["error"])
        self.assertTrue(self.log_error.call_args.kwargs["message"].endswith(result["error"]))
        self.assertFalse(self._todos_made_by_this_test())

    def test_users_who_may_create_todos_keep_them_unallocated(self):
        system_manager = self._make_user(f"{self.tag}-sm", roles=["System Manager"])

        for user in ("Administrator", system_manager):
            with self.subTest(user=user):
                self._act_as(user)

                result = self._create_todo(description=f"{self.tag} {user}")

                self.assertTrue(result.get("success"), result)
                self.assertFalse(frappe.db.get_value("ToDo", result["name"], "allocated_to"))

    def test_validate_only_reports_a_refusal_the_real_create_would_hit(self):
        self._act_as(self.non_admin)

        result = DocumentCreate().execute(
            {
                "doctype": "ToDo",
                "data": {"description": self.tag, "allocated_to": "Administrator"},
                "validate_only": True,
            }
        )

        self.assertFalse(result.get("success"), result)
        self.assertEqual(result.get("error_type"), "permission_error")
        self.assertTrue(result.get("error"), result)

    def test_validate_only_passes_for_the_todo_the_real_create_accepts(self):
        self._act_as(self.non_admin)

        result = DocumentCreate().execute(
            {"doctype": "ToDo", "data": {"description": self.tag}, "validate_only": True}
        )

        self.assertTrue(result.get("success"), result)
        self.assertTrue(result.get("validation_passed"))
        self.assertFalse(self._todos_made_by_this_test())

    def test_message_less_failure_is_returned_and_logged_with_its_type(self):
        with patch("frappe.new_doc", side_effect=RuntimeError()):
            result = self._create_todo()

        self.assertFalse(result.get("success"), result)
        self.assertEqual(result.get("error"), "RuntimeError")
        self.assertEqual(self.log_error.call_args.kwargs["message"], "Error creating ToDo: RuntimeError")

    def test_create_says_why_a_follow_up_submit_was_refused(self):
        refusal = frappe.new_doc("ToDo")

        with patch(
            "frappe.model.document.Document.submit",
            side_effect=lambda: refusal.raise_no_permission_to("submit"),
        ):
            result = DocumentCreate().execute(
                {"doctype": "ToDo", "data": {"description": self.tag}, "submit": True}
            )

        self.assertTrue(result.get("success"), result)
        self.assertTrue(result.get("submit_error"), result)
        self.assertNotIn("<", result["submit_error"])
        self.assertTrue(result["message"].endswith(result["submit_error"]), result)

    def test_update_of_someone_elses_todo_is_refused_with_a_reason(self):
        """Passes unfixed by design: it pins the pre-check path; the next test pins the recovered message."""
        todo = self._todo_owned_by_administrator()
        self._act_as(self.non_admin)

        result = DocumentUpdate().execute(
            {"doctype": "ToDo", "name": todo, "data": {"description": f"{self.tag} edited"}}
        )

        self.assertFalse(result.get("success"), result)
        self.assertTrue(result.get("error"), result)

    def test_update_says_why_frappe_refused_the_save(self):
        todo = self._todo_owned_by_administrator()
        self._act_as(self.non_admin)

        with self._precheck_passes():
            result = DocumentUpdate().execute(
                {"doctype": "ToDo", "name": todo, "data": {"description": f"{self.tag} edited"}}
            )

        self.assertFalse(result.get("success"), result)
        self.assertTrue(result.get("error"), result)
        self.assertNotIn("<", result["error"])
        self.assertTrue(self.log_error.call_args.kwargs["message"].endswith(result["error"]))

    def test_submit_says_why_frappe_refused_the_submit(self):
        refusal = frappe.new_doc("ToDo")
        refusing_doc = MagicMock(docstatus=0, workflow_state=None)
        refusing_doc.submit.side_effect = lambda: refusal.raise_no_permission_to("submit")

        with ExitStack() as stack:
            stack.enter_context(self._precheck_passes())
            stack.enter_context(patch("frappe.db.exists", return_value=True))
            stack.enter_context(patch("frappe.get_doc", return_value=refusing_doc))
            stack.enter_context(patch("frappe.get_meta", return_value=MagicMock(is_submittable=1)))
            result = DocumentSubmit().execute({"doctype": "ToDo", "name": "any"})

        self.assertFalse(result.get("success"), result)
        self.assertTrue(result.get("error"), result)
        self.assertNotIn("<", result["error"])
        self.assertTrue(self.log_error.call_args.kwargs["message"].endswith(result["error"]))


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
