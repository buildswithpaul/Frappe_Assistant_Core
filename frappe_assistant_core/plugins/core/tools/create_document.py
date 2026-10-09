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

from frappe_assistant_core.core.base_tool import BaseTool, exception_message, permission_error_result
from frappe_assistant_core.utils.savepoint import (
    open_savepoint,
    release_savepoint,
    rollback_to_savepoint,
)

from .child_tables import ChildRowError, child_table_fields, normalize_child_rows, restricted_row_keys

# The submit after a create runs inside this savepoint, so a refused submit leaves the draft.
_SUBMIT_SAVEPOINT = "fac_create_document_submit"


def _default_todo_allocation(doc: Any) -> None:
    """Allocate a ToDo that names nobody to the session user, if Frappe would refuse it otherwise.

    Before Frappe v16.32.0 / v15.119.0, a user may create a ToDo only when it names them
    (``allocated_to`` or ``assigned_by`` is that user), unless they hold a role, such as
    System Manager, that grants ToDo create. A non-admin user's plain "add a ToDo" therefore
    has to be a personal one; a ToDo Frappe already accepts is left exactly as it was written.

    From those releases the function changes nothing: frappe/frappe#41869 added
    ``or doc.owner == user`` to that rule, and a user owns every document they create.
    """
    if doc.doctype != "ToDo" or doc.allocated_to or doc.assigned_by:
        return

    if not doc.has_permission("create"):
        doc.allocated_to = frappe.session.user


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
        self.description = "Create new Frappe documents with proper validation and child table support. Supports all DocTypes including those with child tables. WORKFLOW: First use get_doctype_info to understand the DocType structure, identify required fields and child tables, then create the document with proper field values. Child tables must be provided as arrays of objects; a Table MultiSelect field also accepts an array of its link values (e.g. ['user@example.com']). Referenced records (customers, items, warehouses, etc.) must already exist in the system. Use exact field names as shown in DocType metadata. Error responses include specific guidance for resolution. Common use cases: creating Sales Orders with line items, Purchase Orders with items and taxes, customer records, inventory transactions."
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
                    "description": "Whether to submit the document after creation (for submittable doctypes like Sales Invoice). Use true only when explicitly requested. If the DocType has an active Workflow, the document is created as a draft instead; move it on with run_workflow.",
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
            get_restricted_fields,
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
            # Fields this role may not set; child rows are screened against their own doctype below
            restricted_fields = get_restricted_fields(doctype, user_role)

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

            # Get DocType metadata for proper field handling. Table and Table MultiSelect
            # are both child tables; matching only "Table" left a Table MultiSelect value
            # to be set raw, and the insert failed on .is_new() (#291).
            meta = frappe.get_meta(doctype)
            table_fields = child_table_fields(meta)

            # Build and screen every child table before touching the document. Frappe
            # keeps a new row's own owner and creation, so an unscreened row could
            # forge them; rows answer to their child doctype's restricted fields.
            child_rows = {}
            for field, value in data.items():
                if field not in table_fields:
                    continue
                rows = normalize_child_rows(table_fields[field], value)
                child_doctype = table_fields[field].options
                violating = restricted_row_keys(rows, get_restricted_fields(child_doctype, user_role))
                if violating:
                    return {
                        "success": False,
                        "error": (
                            f"Cannot set restricted child-table fields: {', '.join(violating)} "
                            f"in {child_doctype}. These fields require higher privileges."
                        ),
                        "field": field,
                    }
                child_rows[field] = rows

            # Create document
            doc = frappe.new_doc(doctype)

            for field, value in data.items():
                if field in child_rows:
                    for row in child_rows[field]:
                        # append writes into the dict it is given; child_rows stays the input
                        doc.append(field, dict(row))
                else:
                    setattr(doc, field, value)

            _default_todo_allocation(doc)

            # Required-field checks are deferred to Frappe's own validation pipeline
            # via doc.insert()/doc.run_method("validate"). A pre-flight check here is
            # unreliable: many "reqd" fields (e.g. Quotation.conversion_rate,
            # price_list_currency, plc_conversion_rate) are populated by the
            # doctype controller's set_missing_values() during validate(), which has
            # not yet run when we'd inspect doc.get(f). MandatoryError is caught
            # below and translated into the same structured error shape.

            # Handle validation-only mode
            if validate_only:
                # insert() refuses a document this user may not create, so say so here
                # instead of reporting a validation the real create would then fail.
                doc.check_permission("create")

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

            # Capture input child-table values for post-save comparison (issue #181).
            # The normalized rows, so a Table MultiSelect value compares as its row.
            input_child_values = child_rows

            # Save document
            doc.insert()
            # Check for silently overridden field values
            warnings = []
            for field, input_rows in input_child_values.items():
                saved_rows = doc.get(field) or []
                for idx, input_row in enumerate(input_rows):
                    if idx >= len(saved_rows):
                        break
                    saved_row = saved_rows[idx]
                    for key, input_val in input_row.items():
                        saved_val = getattr(saved_row, key, None)
                        if saved_val is not None and str(saved_val) != str(input_val):
                            # Skip numeric false positives (1 vs 1.0, 100 vs 100.0)
                            try:
                                if float(str(saved_val)) == float(str(input_val)):
                                    continue
                            except (ValueError, TypeError):
                                pass
                            warnings.append(
                                {
                                    "child_table": field,
                                    "row_idx": idx,
                                    "field": key,
                                    "requested": input_val,
                                    "saved": str(saved_val),
                                    "reason": "Value was overridden by ERPNext validation logic",
                                }
                            )
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
            from frappe.model.workflow import get_workflow_name

            workflow_name = get_workflow_name(doctype) if submit and doc.docstatus == 0 else None
            if workflow_name:
                # Submitting directly skips the workflow's approval steps: Frappe validates the
                # workflow before it sets the submitted state. The draft goes through run_workflow.
                submit_error = (
                    f"{doctype} has an active Workflow ('{workflow_name}'), so it is submitted "
                    "through the workflow, not directly"
                )
                result["message"] = f"{doctype} '{doc.name}' created as draft. Not submitted: {submit_error}"
                result["submit_error"] = submit_error
                result["workflow"] = workflow_name
                result["suggestion"] = (
                    f"Use run_workflow on {doctype} '{doc.name}' to move it through its workflow."
                )
            elif submit and doc.docstatus == 0:
                # Frappe writes docstatus=1 before on_submit, so without this a submit refused
                # partway would be committed as a submitted document with half its postings,
                # under a message that says it is a draft.
                marks = open_savepoint(_SUBMIT_SAVEPOINT)
                try:
                    doc.submit()
                except Exception as e:
                    rollback_to_savepoint(_SUBMIT_SAVEPOINT, marks, doctype, doc.name)
                    doc.reload()
                    submit_error = exception_message(e)
                    result["message"] = (
                        f"{doctype} '{doc.name}' created as draft. Submit failed: {submit_error}"
                    )
                    result["submit_error"] = submit_error
                else:
                    release_savepoint(_SUBMIT_SAVEPOINT)
                    result["submitted"] = True
                    result["docstatus"] = 1
                    result["message"] = f"{doctype} '{doc.name}' created and submitted successfully"
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
            # Add warnings if any fields were silently overridden
            if warnings:
                result["warnings"] = warnings

            return result

        except ChildRowError as e:
            return {**e.as_result(), "doctype": doctype}
        except frappe.MandatoryError as e:
            # Frappe raises MandatoryError after set_missing_values() has run, so the
            # missing fieldnames here are genuine — not the false positives we'd see
            # from a pre-flight `reqd`-flag check on the raw input. Format:
            #   "[<doctype>, <name>]: <fieldname1>, <fieldname2>, ..."
            # Don't bind `_` here — `_` is the translation function imported at
            # module scope. Any local `_ = ...` would shadow it for the entire
            # function body, raising UnboundLocalError at the later `_("...")`
            # call inside the generic-Exception branch on paths that route
            # through the function before reaching that local assignment.
            error_msg = str(e)
            try:
                fields_part = error_msg.partition(": ")[2]
                missing = [f.strip() for f in fields_part.split(",") if f.strip()]
            except Exception:
                missing = []

            return {
                "success": False,
                "error": (
                    f"Missing required fields: {', '.join(missing)}"
                    if missing
                    else f"Missing required fields. Raw error: {error_msg}"
                ),
                "error_type": "missing_required_field",
                "doctype": doctype,
                "missing_fields": missing,
                "provided_fields": list(data.keys()),
                "suggestion": (
                    f"Use get_doctype_info tool with doctype='{doctype}' to see all required "
                    f"fields and supply values for: {', '.join(missing)}."
                    if missing
                    else f"Use get_doctype_info tool with doctype='{doctype}' to see all required fields."
                ),
            }
        except frappe.PermissionError as e:
            # Frappe raises this with no message and keeps the reason in
            # frappe.flags.error_message; exception_message() recovers it.
            error_msg = exception_message(e, _("Insufficient permission to create {0}").format(doctype))
            frappe.log_error(
                title=_("Document Creation Error"), message=f"Error creating {doctype}: {error_msg}"
            )

            return permission_error_result(doctype, error_msg)
        except Exception as e:
            error_msg = exception_message(e)
            frappe.log_error(
                title=_("Document Creation Error"), message=f"Error creating {doctype}: {error_msg}"
            )

            # Provide specific guidance based on error type
            result = {"success": False, "error": error_msg, "doctype": doctype}

            # Add specific guidance for common errors
            if "'dict' object has no attribute 'is_new'" in error_msg:
                result.update(
                    {
                        "error_type": "child_table_handling_error",
                        "guidance": "This error occurs when child table data is not properly formatted. Child tables require lists of dictionaries; a Table MultiSelect also accepts a list of its link values.",
                        "suggestion": f"1. Use get_doctype_info tool with doctype='{doctype}' to see child table fields\n2. Ensure child table fields are formatted as lists of dictionaries\n3. Example: {{'items': [{{'item_code': 'ITEM001', 'qty': 10}}]}}",
                        # Fieldnames: DocField objects reach the client as their str() repr
                        "child_tables": list(child_table_fields(frappe.get_meta(doctype))) if doctype else [],
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
            elif "permission" in error_msg.lower():
                return permission_error_result(doctype, error_msg)
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
