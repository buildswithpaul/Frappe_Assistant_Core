# -*- coding: utf-8 -*-
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
Document Delete Tool for Core Plugin.
Deletes existing Frappe documents.
"""

import frappe
from frappe import _
from typing import Dict, Any
from frappe_assistant_core.core.base_tool import BaseTool


class DocumentDelete(BaseTool):
    """
    Tool for deleting existing Frappe documents.
    
    Provides capabilities for:
    - Deleting document records
    - Checking permissions
    - Handling dependencies and constraints
    """
    
    def __init__(self):
        super().__init__()
        self.name = "delete_document"
        self.description = "Delete an existing Frappe document. Use when users want to remove a record from the system. Always check for dependencies before deletion."
        self.requires_permission = None  # Permission checked dynamically per DocType
        
        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {
                    "type": "string",
                    "description": "The Frappe DocType name (e.g., 'Customer', 'Sales Invoice', 'Item')"
                },
                "name": {
                    "type": "string",
                    "description": "The document name/ID to delete (e.g., 'CUST-00001', 'SINV-00001')"
                },
                "force": {
                    "type": "boolean",
                    "default": False,
                    "description": "Force deletion even if there are dependencies. Use with caution."
                }
            },
            "required": ["doctype", "name"]
        }
    
    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Delete an existing document"""
        doctype = arguments.get("doctype")
        name = arguments.get("name")
        force = arguments.get("force", False)
        
        # Check permission for DocType
        if not frappe.has_permission(doctype, "delete"):
            return {
                "success": False,
                "error": f"Insufficient permissions to delete {doctype} document"
            }
        
        try:
            # Check if document exists
            if not frappe.db.exists(doctype, name):
                return {
                    "success": False,
                    "error": f"{doctype} '{name}' not found",
                    "doctype": doctype,
                    "name": name
                }
            
            # Get document first to check for dependencies and permissions
            try:
                doc = frappe.get_doc(doctype, name)
            except frappe.PermissionError:
                return {
                    "success": False,
                    "error": f"Insufficient permissions to access {doctype} '{name}'",
                    "doctype": doctype,
                    "name": name
                }
            except Exception as get_error:
                return {
                    "success": False,
                    "error": f"Failed to access {doctype} '{name}': {str(get_error) or 'Unknown error accessing document'}",
                    "doctype": doctype,
                    "name": name
                }
            
            # Delete document
            try:
                if force:
                    frappe.delete_doc(doctype, name, force=True)
                else:
                    frappe.delete_doc(doctype, name)
                
                frappe.db.commit()
                
                return {
                    "success": True,
                    "doctype": doctype,
                    "name": name,
                    "message": f"{doctype} '{name}' deleted successfully"
                }
                
            except frappe.LinkExistsError as link_error:
                return {
                    "success": False,
                    "error": f"Cannot delete {doctype} '{name}' because it is linked to other documents. Use force=true to override.",
                    "doctype": doctype,
                    "name": name,
                    "dependency_error": True
                }
            except frappe.PermissionError as perm_error:
                return {
                    "success": False,
                    "error": f"Insufficient permissions to delete {doctype} '{name}': {str(perm_error) or 'Permission denied'}",
                    "doctype": doctype,
                    "name": name,
                    "permission_error": True
                }
            except Exception as delete_error:
                error_msg = str(delete_error) or f"Unknown error occurred while deleting {doctype} '{name}'"
                return {
                    "success": False,
                    "error": error_msg,
                    "doctype": doctype,
                    "name": name,
                    "delete_error": True
                }
            
        except Exception as e:
            error_msg = str(e) or f"Unexpected error occurred while processing delete request for {doctype} '{name}'"
            
            frappe.log_error(
                title=_("Document Delete Error"),
                message=f"Error deleting {doctype} '{name}': {error_msg}"
            )
            
            return {
                "success": False,
                "error": error_msg,
                "doctype": doctype,
                "name": name,
                "general_error": True
            }


# Make sure class name matches file name for discovery
document_delete = DocumentDelete