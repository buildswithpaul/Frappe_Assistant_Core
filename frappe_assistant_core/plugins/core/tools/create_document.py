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
Document Creation Tool for Core Plugin.
Creates new Frappe documents with validation and permissions.
"""

from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool


class DocumentCreate(BaseTool):
    """
    Tool for creating new Frappe documents.

    Provides capabilities for:
    - Creating documents with field validation
    - Checking required fields
    - Handling permissions
    - Optional document submission
    """

    def __init__(self):
        super().__init__()
        self.name = "create_document"
        self.description = "Create new Frappe documents with proper validation and child table support. Supports all DocTypes including those with child tables. WORKFLOW: First use get_doctype_info to understand the DocType structure, identify required fields and child tables, then create the document with proper field values. Child tables must be provided as arrays of objects. Referenced records (customers, items, warehouses, etc.) must already exist in the system. Use exact field names as shown in DocType metadata. Error responses include specific guidance for resolution. Common use cases: creating Sales Orders with line items, Purchase Orders with items and taxes, customer records, inventory transactions."
        self.requires_permission = None  # Permission checked dynamically per DocType

        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {
                    "type": "string",
                    "description": "The Frappe DocType name (e.g., 'Customer', 'Sales Invoice', 'Item', 'User'). Must match exact DocType name in system.",
                },
                "data": {
                    "type": "object",
                    "description": "Document field data as key-value pairs. Include all required fields for the doctype. Example: {'customer_name': 'ABC Corp', 'customer_type': 'Company'}",
                },
                "submit": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to submit the document after creation (for submittable doctypes like Sales Invoice). Use true only when explicitly requested.",
                },
                "validate_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "Only validate the document without saving it. Use this to test data format and required fields before actual creation.",
                },
            },
            "required": ["doctype", "data"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new document"""
        doctype = arguments.get("doctype")
        data = arguments.get("data", {})
        submit = arguments.get("submit", False)
        validate_only = arguments.get("validate_only", False)

        # Import security validation
        from frappe_assistant_core.core.security_config import (
            filter_sensitive_fields,
            validate_document_access,
        )

        # Validate document access with comprehensive permission checking
        validation_result = validate_document_access(
            user=frappe.session.user,
            doctype=doctype,
            name=None,  # No specific document for create operation
            perm_type="create",
        )

        if not validation_result["success"]:
            return validation_result

        user_role = validation_result["role"]

        try:
            # Filter out sensitive fields that user shouldn't be able to set
            from frappe_assistant_core.core.security_config import ADMIN_ONLY_FIELDS, SENSITIVE_FIELDS

            # Get restricted fields for this role and doctype
            restricted_fields = set()
            restricted_fields.update(SENSITIVE_FIELDS.get("all_doctypes", []))
            restricted_fields.update(SENSITIVE_FIELDS.get(doctype, []))

            if user_role == "Assistant User":
                restricted_fields.update(ADMIN_ONLY_FIELDS.get("all_doctypes", []))
                doctype_admin_fields = ADMIN_ONLY_FIELDS.get(doctype, [])
                if doctype_admin_fields != "*":
                    restricted_fields.update(doctype_admin_fields)

            # Check for attempts to set restricted fields
            restricted_fields_attempted = [field for field in data.keys() if field in restricted_fields]
            if restricted_fields_attempted:
                result = {
                    "success": False,
                    "error": f"Cannot set restricted fields: {', '.join(restricted_fields_attempted)}. These fields require higher privileges.",
                }
                return result

            # Enhanced submit permission checking based on user role
            if submit:
                # Check if user has submit permission for this doctype
                if not frappe.has_permission(doctype, "submit"):
                    result = {
                        "success": False,
                        "error": f"Insufficient permissions to submit {doctype} documents. Current user: {frappe.session.user}",
                    }
                    return result

                # Additional role-based restrictions
                if user_role in ["Assistant User", "Default"]:
                    # For basic users, check if they have explicit submit permission
                    # This allows proper role-based access while maintaining security
                    user_roles = frappe.get_roles(frappe.session.user)
                    meta = frappe.get_meta(doctype)

                    # Check if any of the user's roles have submit permission
                    can_submit = False
                    for perm in meta.permissions:
                        if perm.role in user_roles and perm.submit:
                            can_submit = True
                            break

                    if not can_submit:
                        result = {
                            "success": False,
                            "error": f"Your role does not have submit permission for {doctype} documents. Document will be saved as draft.",
                        }
                        # Don't return error, just disable submit
                        submit = False

            # Create document
            doc = frappe.new_doc(doctype)

            # Get DocType metadata for proper field handling
            meta = frappe.get_meta(doctype)
            table_fields = {f.fieldname: f.options for f in meta.fields if f.fieldtype == "Table"}

            # Validate required fields
            required_fields = [
                f.fieldname for f in meta.fields if f.reqd and not f.default and f.fieldtype != "Table"
            ]
            missing_fields = [f for f in required_fields if f not in data or not data[f]]

            if missing_fields:
                return {
                    "success": False,
                    "error": f"Missing required fields: {', '.join(missing_fields)}",
                    "required_fields": required_fields,
                    "provided_fields": list(data.keys()),
                    "suggestion": f"Use get_doctype_info tool with doctype='{doctype}' to see all required fields and their types",
                    "doctype": doctype,
                }

            # Set field values with proper child table handling
            for field, value in data.items():
                if field in table_fields:
                    # Handle child table fields properly
                    if isinstance(value, list):
                        for row_data in value:
                            if isinstance(row_data, dict):
                                doc.append(field, row_data)
                            else:
                                raise ValueError(
                                    f"Child table '{field}' requires list of dictionaries, got: {type(row_data)}"
                                )
                    else:
                        raise ValueError(f"Child table '{field}' requires a list, got: {type(value)}")
                else:
                    # Handle regular fields
                    setattr(doc, field, value)

            # Handle validation-only mode
            if validate_only:
                # Run validation without saving
                doc.run_method("validate")

                return {
                    "success": True,
                    "validation_passed": True,
                    "doctype": doctype,
                    "message": f"{doctype} data validation passed successfully",
                    "fields_validated": list(data.keys()),
                    "child_tables": list(table_fields.keys()) if table_fields else [],
                    "next_step": "Use create_document with validate_only=false to actually create the document",
                }

            # Save document
            doc.insert()

            # Initialize result with basic information
            result = {
                "success": True,
                "name": doc.name,
                "doctype": doctype,
                "docstatus": doc.docstatus,
                "owner": doc.owner,
                "creation": str(doc.creation),
                "submitted": False,
                "can_submit": False,
            }

            # Submit if requested and allowed
            if submit and doc.docstatus == 0:
                try:
                    doc.submit()
                    result["submitted"] = True
                    result["docstatus"] = 1
                    result["message"] = f"{doctype} '{doc.name}' created and submitted successfully"
                except Exception as e:
                    result["message"] = f"{doctype} '{doc.name}' created as draft. Submit failed: {str(e)}"
                    result["submit_error"] = str(e)
            else:
                result["message"] = f"{doctype} '{doc.name}' created successfully as draft"

            # Check if user can submit this document later
            if doc.docstatus == 0:  # Only for draft documents
                try:
                    result["can_submit"] = frappe.has_permission(doctype, "submit", doc=doc.name)
                except Exception:
                    result["can_submit"] = False

            # Add workflow information if available
            if hasattr(doc, "workflow_state") and doc.workflow_state:
                result["workflow_state"] = doc.workflow_state

            # Add useful next steps information
            if doc.docstatus == 0:
                result["next_steps"] = [
                    "Document is in draft state",
                    "You can update this document using document_update tool",
                    f"Submit permission: {'Available' if result['can_submit'] else 'Not available'}",
                ]
            else:
                result["next_steps"] = [
                    "Document is submitted and cannot be modified",
                    "Use document_get to view the submitted document",
                ]

            # Log successful creation
            return result

        except Exception as e:
            frappe.log_error(
                title=_("Document Creation Error"), message=f"Error creating {doctype}: {str(e)}"
            )

            error_msg = str(e)

            # Provide specific guidance based on error type
            result = {"success": False, "error": error_msg, "doctype": doctype}

            # Add specific guidance for common errors
            if "'dict' object has no attribute 'is_new'" in error_msg:
                result.update(
                    {
                        "error_type": "child_table_handling_error",
                        "guidance": "This error occurs when child table data is not properly formatted. Child tables require lists of dictionaries.",
                        "suggestion": f"1. Use get_doctype_info tool with doctype='{doctype}' to see child table fields\n2. Ensure child table fields are formatted as lists of dictionaries\n3. Example: {{'items': [{{'item_code': 'ITEM001', 'qty': 10}}]}}",
                        "child_tables": list(frappe.get_meta(doctype).get_table_fields()) if doctype else [],
                    }
                )
            elif "does not exist" in error_msg.lower():
                result.update(
                    {
                        "error_type": "validation_error",
                        "guidance": "Referenced record does not exist in the system.",
                        "suggestion": "1. Verify that referenced records (like customers, items, suppliers) exist\n2. Use search_documents tool to find correct record names\n3. Check spelling and exact names",
                    }
                )
            elif "mandatory" in error_msg.lower() or "required" in error_msg.lower():
                result.update(
                    {
                        "error_type": "missing_required_field",
                        "guidance": "Required field is missing or empty.",
                        "suggestion": f"1. Use get_doctype_info tool with doctype='{doctype}' to see all required fields\n2. Ensure all required fields are provided with valid values",
                    }
                )
            elif "permission" in error_msg.lower():
                result.update(
                    {
                        "error_type": "permission_error",
                        "guidance": "Insufficient permissions for this operation.",
                        "suggestion": "Contact your system administrator to grant necessary permissions for this DocType",
                    }
                )
            else:
                result.update(
                    {
                        "error_type": "general_error",
                        "guidance": "Document creation failed due to validation or system error.",
                        "suggestion": f"1. Use get_doctype_info tool with doctype='{doctype}' to understand field requirements\n2. Verify all field values are valid\n3. Check that referenced records exist",
                    }
                )

            # Log failed creation
            return result


# Make sure class name matches file name for discovery
document_create = DocumentCreate
