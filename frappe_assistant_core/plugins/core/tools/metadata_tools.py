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

from typing import Any, Dict, List

import frappe
from frappe import _


class MetadataTools:
    """assistant tools for Frappe metadata operations"""

    @staticmethod
    def get_tools() -> List[Dict]:
        """Return list of metadata-related assistant tools"""
        return [
            {
                "name": "get_doctype_info",
                "description": "Get DocType metadata and field information",
                "inputSchema": {
                    "type": "object",
                    "properties": {"doctype": {"type": "string", "description": "DocType name"}},
                    "required": ["doctype"],
                },
            },
            {
                "name": "metadata_list_doctypes",
                "description": "List all available DocTypes",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "module": {"type": "string", "description": "Filter by module"},
                        "custom_only": {
                            "type": "boolean",
                            "default": False,
                            "description": "Show only custom DocTypes",
                        },
                    },
                },
            },
            {
                "name": "metadata_permissions",
                "description": "Get permission information for a DocType",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "doctype": {"type": "string", "description": "DocType name"},
                        "user": {"type": "string", "description": "User to check permissions for (optional)"},
                    },
                    "required": ["doctype"],
                },
            },
            {
                "name": "metadata_workflow",
                "description": "Get workflow information for a DocType",
                "inputSchema": {
                    "type": "object",
                    "properties": {"doctype": {"type": "string", "description": "DocType name"}},
                    "required": ["doctype"],
                },
            },
        ]

    @staticmethod
    def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a metadata tool with given arguments"""
        if tool_name == "get_doctype_info":
            return MetadataTools.get_doctype_metadata(**arguments)
        elif tool_name == "metadata_list_doctypes":
            return MetadataTools.list_doctypes(**arguments)
        elif tool_name == "metadata_permissions":
            return MetadataTools.get_permissions(**arguments)
        elif tool_name == "metadata_workflow":
            return MetadataTools.get_workflow(**arguments)
        else:
            raise Exception(f"Unknown metadata tool: {tool_name}")

    @staticmethod
    def get_doctype_metadata(doctype: str) -> Dict[str, Any]:
        """Get DocType metadata and field information"""
        try:
            if not frappe.db.exists("DocType", doctype):
                return {"success": False, "error": f"DocType '{doctype}' not found"}

            if not frappe.has_permission(doctype, "read"):
                return {"success": False, "error": f"No permission to access DocType '{doctype}'"}

            meta = frappe.get_meta(doctype)

            # Build field information
            fields = []
            for field in meta.fields:
                field_info = {
                    "fieldname": field.fieldname,
                    "label": field.label,
                    "fieldtype": field.fieldtype,
                    "options": field.options,
                    "reqd": field.reqd,
                    "read_only": field.read_only,
                    "hidden": field.hidden,
                    "default": field.default,
                    "description": field.description,
                }
                fields.append(field_info)

            # Build link fields information
            link_fields = []
            for field in meta.get_link_fields():
                link_fields.append(
                    {"fieldname": field.fieldname, "label": field.label, "options": field.options}
                )

            return {
                "success": True,
                "doctype": doctype,
                "module": meta.module,
                "is_submittable": meta.is_submittable,
                "is_tree": meta.is_tree,
                "is_single": meta.istable,
                "naming_rule": meta.naming_rule,
                "title_field": meta.title_field,
                "fields": fields,
                "link_fields": link_fields,
                "permissions": [p.as_dict() for p in meta.permissions],
            }

        except Exception as e:
            frappe.log_error(f"assistant Get DocType Metadata Error: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def list_doctypes(module: str = None, custom_only: bool = False) -> Dict[str, Any]:
        """List all available DocTypes"""
        try:
            filters = {}
            if module:
                filters["module"] = module
            if custom_only:
                filters["custom"] = 1

            doctypes = frappe.get_all(
                "DocType",
                filters=filters,
                fields=["name", "module", "is_submittable", "is_tree", "istable", "custom", "description"],
                order_by="name",
            )

            # Filter by read permissions
            accessible_doctypes = []
            for dt in doctypes:
                if frappe.has_permission(dt.name, "read"):
                    accessible_doctypes.append(dt)

            return {
                "success": True,
                "doctypes": accessible_doctypes,
                "count": len(accessible_doctypes),
                "filters_applied": {"module": module, "custom_only": custom_only},
            }

        except Exception as e:
            frappe.log_error(f"assistant List DocTypes Error: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_permissions(doctype: str, user: str = None) -> Dict[str, Any]:
        """Get permission information for a DocType"""
        try:
            if not frappe.db.exists("DocType", doctype):
                return {"success": False, "error": f"DocType '{doctype}' not found"}

            check_user = user or frappe.session.user

            # Reporting capabilities — not a security boundary. throw=False
            # keeps this explicit and silences the unchecked-permission rule.
            permissions = {
                "read": frappe.has_permission(doctype, "read", user=check_user, throw=False),
                "write": frappe.has_permission(doctype, "write", user=check_user, throw=False),
                "create": frappe.has_permission(doctype, "create", user=check_user, throw=False),
                "delete": frappe.has_permission(doctype, "delete", user=check_user, throw=False),
                "submit": frappe.has_permission(doctype, "submit", user=check_user, throw=False),
                "cancel": frappe.has_permission(doctype, "cancel", user=check_user, throw=False),
                "amend": frappe.has_permission(doctype, "amend", user=check_user, throw=False),
            }

            # Get user roles
            user_roles = frappe.get_roles(check_user)

            # Get DocType permission rules
            meta = frappe.get_meta(doctype)
            permission_rules = [p.as_dict() for p in meta.permissions]

            return {
                "success": True,
                "doctype": doctype,
                "user": check_user,
                "permissions": permissions,
                "user_roles": user_roles,
                "permission_rules": permission_rules,
            }

        except Exception as e:
            frappe.log_error(f"assistant Get Permissions Error: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_workflow(doctype: str) -> Dict[str, Any]:
        """Get workflow information for a DocType"""
        try:
            if not frappe.db.exists("DocType", doctype):
                return {"success": False, "error": f"DocType '{doctype}' not found"}

            # Check if workflow exists for this DocType
            workflow = frappe.db.get_value("Workflow", {"document_type": doctype}, "name")

            if not workflow:
                return {
                    "success": True,
                    "doctype": doctype,
                    "has_workflow": False,
                    "message": f"No workflow defined for DocType '{doctype}'",
                }

            # Get workflow details
            workflow_doc = frappe.get_doc("Workflow", workflow)

            # Get workflow states
            states = []
            for state in workflow_doc.states:
                states.append(
                    {
                        "state": state.state,
                        "doc_status": state.doc_status,
                        "allow_edit": state.allow_edit,
                        "message": state.message,
                    }
                )

            # Get workflow transitions
            transitions = []
            for transition in workflow_doc.transitions:
                transitions.append(
                    {
                        "state": transition.state,
                        "action": transition.action,
                        "next_state": transition.next_state,
                        "allowed": transition.allowed,
                        "allow_self_approval": transition.allow_self_approval,
                    }
                )

            return {
                "success": True,
                "doctype": doctype,
                "has_workflow": True,
                "workflow_name": workflow_doc.name,
                "workflow_state_field": workflow_doc.workflow_state_field,
                "states": states,
                "transitions": transitions,
            }

        except Exception as e:
            frappe.log_error(f"assistant Get Workflow Error: {str(e)}")
            return {"success": False, "error": str(e)}
