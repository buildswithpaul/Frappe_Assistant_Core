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
Document Retrieval Tool for Core Plugin.
Retrieves detailed information about specific Frappe documents.
"""

from typing import Any, Dict, List

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.utils.untrusted_output import fence_document

# Repeated on every child row and already known from the parent, so they only cost tokens (#35274)
CHILD_ROW_BOOKKEEPING = frozenset(
    {
        "owner",
        "creation",
        "modified",
        "modified_by",
        "docstatus",
        "parent",
        "parentfield",
        "parenttype",
        "doctype",
    }
)


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def compact_record(data: Dict[str, Any], fields: List[str] | None = None) -> Dict[str, Any]:
    """``data`` without empty values or child-row bookkeeping; only ``fields`` (and name) when given.

    Zeros stay: an outstanding amount of 0 means paid, not unknown.
    """
    wanted = set(fields) | {"name"} if fields else None
    compact = {}
    for key, value in data.items():
        if _is_empty(value) or (wanted is not None and key not in wanted):
            continue
        if isinstance(value, list):
            value = [_compact_row(row) if isinstance(row, dict) else row for row in value]
        compact[key] = value
    return compact


def _compact_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in row.items() if k not in CHILD_ROW_BOOKKEEPING and not _is_empty(v)}


class DocumentGet(BaseTool):
    """
    Tool for retrieving Frappe documents.

    Provides capabilities for:
    - Fetching complete document data
    - Checking permissions
    - Handling non-existent documents
    """

    def __init__(self):
        super().__init__()
        self.name = "get_document"
        self.description = (
            "Retrieve a specific Frappe document by its name/ID, with its child tables. Empty fields are "
            "left out, so a field that is missing is empty. Pass fields to get only those fields."
        )
        self.requires_permission = None  # Permission checked dynamically per DocType

        self.inputSchema = {
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
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Only these fields (a child table's fieldname returns its rows). Omit for all.",
                },
            },
            "required": ["doctype", "name"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve a specific document"""
        doctype = arguments.get("doctype")
        name = arguments.get("name")

        # SECURITY: Prevent hardcoded Administrator access attempts

        current_user = frappe.session.user
        if name == "Administrator" and current_user != "Administrator":
            return {
                "success": False,
                "error": f"Access denied: Cannot access Administrator record. Current user: {current_user}",
            }

        # Import security validation
        from frappe_assistant_core.core.security_config import validate_document_access
        from frappe_assistant_core.utils.permissions import readable_doc_dict

        # Validate document access with comprehensive permission checking
        validation_result = validate_document_access(
            user=frappe.session.user, doctype=doctype, name=name, perm_type="read"
        )

        if not validation_result["success"]:
            return validation_result

        user_role = validation_result["role"]

        try:
            # Check if document exists
            if not frappe.db.exists(doctype, name):
                result = {"success": False, "error": f"{doctype} '{name}' not found"}
                return result

            # Get document
            doc = frappe.get_doc(doctype, name)

            # Only the fields the user may read: permlevel as on Desk (#390), then FAC's sensitive fields
            filtered_doc = compact_record(readable_doc_dict(doc, user_role), arguments.get("fields"))
            # what a user's file said, kept on the record, reaches the model fenced (#34003)
            filtered_doc = fence_document(doctype, filtered_doc)

            result = {
                "success": True,
                "doctype": doctype,
                "name": name,
                "data": filtered_doc,
                "message": f"{doctype} '{name}' retrieved successfully",
            }

            # Log successful access
            return result

        except Exception as e:
            frappe.log_error(
                title=_("Document Retrieval Error"), message=f"Error retrieving {doctype} '{name}': {str(e)}"
            )

            result = {"success": False, "error": str(e), "doctype": doctype, "name": name}

            # Log failed access
            return result


# Make sure class name matches file name for discovery
document_get = DocumentGet
