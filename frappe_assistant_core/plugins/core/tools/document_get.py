"""
Document Retrieval Tool for Core Plugin.
Retrieves detailed information about specific Frappe documents.
"""

import frappe
from frappe import _
from typing import Dict, Any
from frappe_assistant_core.core.base_tool import BaseTool


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
        self.name = "document_get"
        self.description = "Retrieve detailed information about a specific Frappe document. Use when users ask for details about a particular record they know the name/ID of."
        self.requires_permission = None  # Permission checked dynamically per DocType
        
        self.input_schema = {
            "type": "object",
            "properties": {
                "doctype": {
                    "type": "string",
                    "description": "The Frappe DocType name (e.g., 'Customer', 'Sales Invoice', 'Item')"
                },
                "name": {
                    "type": "string",
                    "description": "The document name/ID (e.g., 'CUST-00001', 'SINV-00001'). This is the unique identifier for the document."
                }
            },
            "required": ["doctype", "name"]
        }
    
    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve a specific document"""
        doctype = arguments.get("doctype")
        name = arguments.get("name")
        
        # Import security validation
        from frappe_assistant_core.core.security_config import validate_document_access, filter_sensitive_fields, audit_log_tool_access
        
        # Validate document access with comprehensive permission checking
        validation_result = validate_document_access(
            user=frappe.session.user,
            doctype=doctype,
            name=name,
            perm_type="read"
        )
        
        if not validation_result["success"]:
            audit_log_tool_access(frappe.session.user, self.name, arguments, validation_result)
            return validation_result
        
        user_role = validation_result["role"]
        
        try:
            # Check if document exists
            if not frappe.db.exists(doctype, name):
                result = {
                    "success": False,
                    "error": f"{doctype} '{name}' not found"
                }
                audit_log_tool_access(frappe.session.user, self.name, arguments, result)
                return result
            
            # Get document
            doc = frappe.get_doc(doctype, name)
            
            # Convert to dict
            doc_dict = doc.as_dict()
            
            # Filter sensitive fields based on user role
            filtered_doc = filter_sensitive_fields(doc_dict, doctype, user_role)
            
            result = {
                "success": True,
                "doctype": doctype,
                "name": name,
                "data": filtered_doc,
                "message": f"{doctype} '{name}' retrieved successfully"
            }
            
            # Log successful access
            audit_log_tool_access(frappe.session.user, self.name, arguments, result)
            return result
            
        except Exception as e:
            frappe.log_error(
                title=_("Document Retrieval Error"),
                message=f"Error retrieving {doctype} '{name}': {str(e)}"
            )
            
            result = {
                "success": False,
                "error": str(e),
                "doctype": doctype,
                "name": name
            }
            
            # Log failed access
            audit_log_tool_access(frappe.session.user, self.name, arguments, result)
            return result


# Make sure class name matches file name for discovery
document_get = DocumentGet