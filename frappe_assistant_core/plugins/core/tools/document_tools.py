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

import json
from typing import Any, Dict, List

import frappe
from frappe import _


class DocumentTools:
    """assistant tools for Frappe document operations"""

    @staticmethod
    def get_tools() -> List[Dict]:
        """Return list of document-related assistant tools"""
        return [
            {
                "name": "document_create",
                "description": "Create a new Frappe document (e.g., Customer, Sales Invoice, Item, etc.). Use this when users want to add new records to the system. Always check required fields for the doctype first.",
                "inputSchema": {
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
                    },
                    "required": ["doctype", "data"],
                },
            },
            {
                "name": "document_get",
                "description": "Retrieve detailed information about a specific Frappe document. Use when users ask for details about a particular record they know the name/ID of.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "doctype": {
                            "type": "string",
                            "description": "The Frappe DocType name (e.g., 'Customer', 'Sales Invoice', 'Item')",
                        },
                        "name": {
                            "type": "string",
                            "description": "The document name/ID (e.g., 'CUST-00001', 'SINV-00001'). This is the unique identifier for the document.",
                        },
                    },
                    "required": ["doctype", "name"],
                },
            },
            {
                "name": "document_update",
                "description": "Update/modify an existing Frappe document. Use when users want to change field values in an existing record. Always fetch the document first to understand current values.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "doctype": {
                            "type": "string",
                            "description": "The Frappe DocType name (e.g., 'Customer', 'Sales Invoice', 'Item')",
                        },
                        "name": {
                            "type": "string",
                            "description": "The document name/ID to update (e.g., 'CUST-00001', 'SINV-00001')",
                        },
                        "data": {
                            "type": "object",
                            "description": "Field updates as key-value pairs. Only include fields that need to be changed. Example: {'customer_name': 'Updated Corp Name', 'phone': '+1234567890'}",
                        },
                    },
                    "required": ["doctype", "name", "data"],
                },
            },
            {
                "name": "document_list",
                "description": "Search and list Frappe documents with optional filtering. Use this when users want to find records, get lists of documents, or search for data. This is the primary tool for data exploration and discovery.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "doctype": {
                            "type": "string",
                            "description": "The Frappe DocType to search (e.g., 'Customer', 'Sales Invoice', 'Item', 'User'). Must match exact DocType name.",
                        },
                        "filters": {
                            "type": "object",
                            "default": {},
                            "description": "Search filters as key-value pairs. Examples: {'status': 'Active'}, {'customer_type': 'Company'}, {'creation': ['>', '2024-01-01']}. Use empty {} to get all records.",
                        },
                        "fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific fields to retrieve. Examples: ['name', 'customer_name', 'email'], ['name', 'item_name', 'item_code']. Leave empty to get standard fields.",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 20,
                            "description": "Maximum number of records to return. Use 50+ for comprehensive searches, 5-10 for quick previews.",
                        },
                        "debug": {
                            "type": "boolean",
                            "default": False,
                            "description": "Enable debug mode to troubleshoot when no results are returned despite expecting data.",
                        },
                    },
                    "required": ["doctype"],
                },
            },
        ]

    @staticmethod
    def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a document tool with given arguments"""
        if tool_name == "document_create":
            return DocumentTools.create_document(**arguments)
        elif tool_name == "document_get":
            return DocumentTools.get_document(**arguments)
        elif tool_name == "document_update":
            return DocumentTools.update_document(**arguments)
        elif tool_name == "document_list":
            return DocumentTools.list_documents(**arguments)
        else:
            raise Exception(f"Unknown document tool: {tool_name}")

    @staticmethod
    def create_document(doctype: str, data: Dict[str, Any], submit: bool = False) -> Dict[str, Any]:
        """Create a new Frappe document"""
        try:
            # Validate doctype exists
            if not frappe.db.exists("DocType", doctype):
                return {"success": False, "error": f"DocType '{doctype}' does not exist"}

            # Check permissions
            if not frappe.has_permission(doctype, "create"):
                return {"success": False, "error": f"No create permission for {doctype}"}

            # Ensure doctype is in the data
            if "doctype" not in data:
                data["doctype"] = doctype

            # Create document
            doc = frappe.get_doc(data)
            doc.insert()

            # Submit if requested and document supports it
            if submit and hasattr(doc, "submit") and doc.docstatus == 0:
                doc.submit()

            return {
                "success": True,
                "name": doc.name,
                "doctype": doctype,
                "status": "Submitted" if submit else "Draft",
            }

        except Exception as e:
            frappe.log_error(f"assistant Create Document Error: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_document(doctype: str, name: str) -> Dict[str, Any]:
        """Retrieve a specific document"""
        try:
            if not frappe.db.exists("DocType", doctype):
                return {"success": False, "error": f"DocType '{doctype}' does not exist"}

            if not frappe.has_permission(doctype, "read", doc=name):
                return {"success": False, "error": f"No read permission for {doctype} {name}"}

            doc = frappe.get_doc(doctype, name)
            return {"success": True, "doctype": doctype, "name": name, "data": doc.as_dict()}

        except Exception as e:
            frappe.log_error(f"assistant Get Document Error: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_document(doctype: str, name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing document"""
        try:
            if not frappe.db.exists("DocType", doctype):
                return {"success": False, "error": f"DocType '{doctype}' does not exist"}

            if not frappe.has_permission(doctype, "write", doc=name):
                return {"success": False, "error": f"No write permission for {doctype} {name}"}

            doc = frappe.get_doc(doctype, name)
            doc.update(data)
            doc.save()

            return {
                "success": True,
                "doctype": doctype,
                "name": name,
                "message": "Document updated successfully",
            }

        except Exception as e:
            frappe.log_error(f"assistant Update Document Error: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def list_documents(
        doctype: str,
        filters: Dict[str, Any] = None,
        fields: List[str] = None,
        limit: int = 20,
        debug: bool = False,
    ) -> Dict[str, Any]:
        """List documents with filters"""
        try:
            if not frappe.db.exists("DocType", doctype):
                return {"success": False, "error": f"DocType '{doctype}' does not exist"}

            # Check basic read permission
            if not frappe.has_permission(doctype, "read"):
                return {"success": False, "error": f"No read permission for {doctype}"}

            # Get total count first to debug
            try:
                total_count = frappe.db.count(doctype, filters or {})
            except Exception as e:
                return {"success": False, "error": f"Error counting documents: {str(e)}"}

            # Use safer field selection
            safe_fields = fields or ["name"]
            if "name" not in safe_fields:
                safe_fields.append("name")

            # Try to add common fields if they exist
            try:
                meta = frappe.get_meta(doctype)
                for field_name in ["creation", "modified", "owner", "modified_by"]:
                    if (
                        meta.has_field(field_name) and field_name not in safe_fields and len(safe_fields) < 10
                    ):  # Limit fields to avoid issues
                        safe_fields.append(field_name)
            except Exception as e:
                frappe.log_error(f"Error accessing meta for {doctype}: {str(e)}")

            # Try the query with progressively simpler approaches
            documents = []
            error_details = []

            # Attempt 1: Full query as intended
            try:
                documents = frappe.get_all(
                    doctype,
                    filters=filters or {},
                    fields=safe_fields,
                    limit=limit,
                    order_by="modified desc" if "modified" in safe_fields else "name desc",
                )
            except Exception as e:
                error_details.append(f"Full query failed: {str(e)}")

                # Attempt 2: Try with just name field
                try:
                    documents = frappe.get_all(
                        doctype, filters=filters or {}, fields=["name"], limit=limit, order_by="name desc"
                    )
                    safe_fields = ["name"]  # Update to reflect what worked
                except Exception as e2:
                    error_details.append(f"Name-only query failed: {str(e2)}")

                    # Attempt 3: Try with no filters
                    try:
                        documents = frappe.get_all(
                            doctype, fields=["name"], limit=limit, order_by="name desc"
                        )
                        safe_fields = ["name"]
                        filters = {}  # Clear filters since they caused issues
                    except Exception as e3:
                        error_details.append(f"No-filter query failed: {str(e3)}")

            # Build response with debug info
            response = {
                "success": True,
                "doctype": doctype,
                "documents": documents,
                "results": documents,  # Add results key for API compatibility
                "count": len(documents),
                "total_in_db": total_count,
                "fields_returned": safe_fields,
                "filters_applied": filters or {},
            }

            # Add debug information if requested
            if debug or error_details or (len(documents) == 0 and total_count > 0):
                response["debug_info"] = {
                    "permission_check_passed": True,
                    "errors_encountered": error_details if error_details else None,
                    "user": frappe.session.user,
                    "user_roles": frappe.get_roles(),
                    "doctype_permissions": {
                        # Reporting capabilities to the caller — not a security
                        # boundary. Enforcement happens via the read check
                        # earlier in list_documents; these booleans just tell
                        # the LLM what actions it could take next.
                        "read": frappe.has_permission(doctype, "read", throw=False),
                        "write": frappe.has_permission(doctype, "write", throw=False),
                        "create": frappe.has_permission(doctype, "create", throw=False),
                        "delete": frappe.has_permission(doctype, "delete", throw=False),
                    },
                    "query_attempts": len(error_details) + 1,
                    "final_fields_used": safe_fields,
                }

            # Add warning if no documents returned but some exist in DB
            if len(documents) == 0 and total_count > 0:
                response["warning"] = (
                    f"No documents returned but {total_count} exist in database. Possible permission or filter issues."
                )
                response["suggestion"] = "Try without filters or with simpler field selection."

            return response

        except Exception as e:
            frappe.log_error(f"assistant List Documents Error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "debug": {"doctype": doctype, "filters": filters, "fields": fields},
            }
