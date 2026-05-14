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
Security Configuration for Frappe Assistant Core

This module defines role-based access control, sensitive field filtering,
and security policies following Frappe Framework standards.
"""

from typing import Any, Dict, List, Optional, Set

import frappe

# Basic Core tools available to ALL users (document permissions will control access)
BASIC_CORE_TOOLS = [
    # Essential document operations
    "document_create",
    "document_get",
    "document_update",
    "document_list",
    # Search and discovery
    "search_global",
    "search_doctype",
    "search_link",
    # Basic reporting
    "report_execute",
    "report_list",
    "report_columns",
    # Basic metadata
    "metadata_doctype",
    # Visualizations
    "create_visualization",
    # Basic analysis
    "analyze_frappe_data",
    # Basic workflow
    "workflow_status",
    "workflow_list",
]

# Role-based tool access matrix
ROLE_TOOL_ACCESS = {
    "System Manager": {
        # System Managers have access to ALL tools
        "allowed_tools": "*",  # Wildcard for all tools
        "restricted_tools": [],
        "description": "Full access to all assistant tools including dangerous operations",
    },
    "Assistant Admin": {
        "allowed_tools": [
            # All basic tools (inherited)
            *BASIC_CORE_TOOLS,
            # Administrative tools
            "metadata_permissions",
            "metadata_workflow",
            "tool_registry_list",
            "tool_registry_toggle",
            "audit_log_view",
            "workflow_action",
        ],
        "restricted_tools": [
            "execute_python_code",
            "query_and_analyze",
        ],
        "description": "Administrative access without code execution capabilities",
    },
    "Assistant User": {
        "allowed_tools": BASIC_CORE_TOOLS,
        "restricted_tools": [
            "execute_python_code",
            "query_and_analyze",
            "metadata_permissions",
            "metadata_workflow",
            "tool_registry_list",
            "tool_registry_toggle",
            "audit_log_view",
            "workflow_action",
        ],
        "description": "Basic business user access with document-level permissions",
    },
    # All other users (any role) get access to basic core tools
    "Default": {
        "allowed_tools": BASIC_CORE_TOOLS,
        "restricted_tools": [
            "execute_python_code",
            "query_and_analyze",
            "metadata_permissions",
            "metadata_workflow",
            "tool_registry_list",
            "tool_registry_toggle",
            "audit_log_view",
            "workflow_action",
        ],
        "description": "Basic tool access for all users - document permissions control actual access",
    },
}

# Sensitive fields that should be filtered based on user roles
SENSITIVE_FIELDS = {
    "all_doctypes": [
        "password",
        "new_password",
        "api_key",
        "api_secret",
        "secret_key",
        "private_key",
        "access_token",
        "refresh_token",
        "reset_password_key",
        "unsubscribe_key",
        "email_signature",
        "bank_account_no",
        "iban",
        "encryption_key",
    ],
    "User": [
        "password",
        "new_password",
        "api_key",
        "api_secret",
        "reset_password_key",
        "unsubscribe_key",
        "email_signature",
        "login_after",
        "user_type",
        "simultaneous_sessions",
        "restrict_ip",
        "last_password_reset_date",
        "last_login",
        "last_active",
        "login_before",
        "bypass_restrict_ip_check_if_2fa_enabled",
    ],
    "System Settings": [
        "password_reset_limit",
        "session_expiry",
        "session_expiry_mobile",
        "email_footer_address",
        "backup_path",
        "backup_path_db",
        "backup_path_files",
        "backup_path_private_files",
        "encryption_key",
    ],
    "Email Account": [
        "password",
        "smtp_password",
        "access_token",
        "refresh_token",
        "auth_method",
        "connected_app",
        "connected_user",
    ],
    "Integration Request": [
        "data",
        "output",
        "error",
        "headers",
    ],
    "OAuth Bearer Token": [
        "access_token",
        "refresh_token",
        "scopes",
        "expires_in",
    ],
    "Connected App": [
        "client_secret",
        "client_id",
        "redirect_uris",
    ],
    "Social Login Key": [
        "client_secret",
        "client_id",
        "base_url",
        "custom_base_url",
    ],
    "Google Settings": [
        "client_secret",
        "client_id",
    ],
    "LDAP Settings": [
        "password",
        "ldap_password",
    ],
    "Dropbox Settings": [
        "app_access_token",
        "access_token",
        "app_secret",
    ],
    "Google Drive": [
        "refresh_token",
        "access_token",
        "indexing_refresh_token",
        "indexing_access_token",
    ],
    "S3 File Attachment": [
        "access_key_id",
        "secret_access_key",
        "region_name",
        "bucket_name",
        "folder_name",
        "file_url",
        "is_private",
    ],
}

# Fields that should be hidden from Assistant Users but visible to admins
ADMIN_ONLY_FIELDS = {
    "all_doctypes": [
        "owner",
        "creation",
        "modified",
        "modified_by",
        "docstatus",
        "idx",
        "_user_tags",
        "_comments",
        "_assign",
        "_liked_by",
    ],
    "User": [
        "enabled",
        "user_type",
        "module_profile",
        "role_profile_name",
        "roles",
        "user_permissions",
        "block_modules",
        "home_settings",
        "defaults",
        "system_user",
        "allowed_in_mentions",
        "banner_image",
        "interest",
        "bio",
        "mute_sounds",
        "desk_theme",
        "simultaneous_sessions",
        "restrict_ip",
        "login_before",
        "login_after",
        "user_image",
        "logout_all_sessions",
        "reset_password_key",
        "last_password_reset_date",
        "last_login",
        "last_active",
        "login_attempts",
        "reCAPTCHA",
    ],
    "System Settings": "*",  # Hide all system settings from Assistant Users
    "Print Settings": "*",
    "Email Domain": "*",
    "Domain Settings": "*",
    "Energy Point Settings": "*",
    "Google Settings": "*",
    "LDAP Settings": "*",
    "OAuth Settings": "*",
    "Social Login Key": "*",
    "Dropbox Settings": "*",
}

# DocTypes that should be completely hidden from Assistant Users
RESTRICTED_DOCTYPES = {
    "Assistant User": [
        # System administration
        "System Settings",
        "Print Settings",
        "Email Domain",
        "LDAP Settings",
        "OAuth Settings",
        "Social Login Key",
        "Dropbox Settings",
        "Connected App",
        "OAuth Bearer Token",
        # Security and permissions
        "Role",
        "User Permission",
        "Role Permission",
        "Custom Role",
        "Module Profile",
        "Role Profile",
        "Custom DocPerm",
        "DocShare",
        # System logs and audit
        "Error Log",
        "Activity Log",
        "Access Log",
        "View Log",
        "Scheduler Log",
        "Integration Request",
        # System customization
        "Server Script",
        "Client Script",
        "Custom Script",
        "Property Setter",
        "Customize Form",
        "Customize Form Field",
        "DocType",
        "DocField",
        "DocPerm",
        "Custom Field",
        # Development tools
        "Package",
        "Package Release",
        "Installed Application",
        "Data Import",
        "Data Export",
        "Bulk Update",
        "Rename Tool",
        "Database Storage Usage By Tables",
        # Workflows (admin level)
        "Workflow",
        "Workflow Action",
        "Workflow State",
        "Workflow Transition",
        # Email system internals
        "Email Queue",
        "Email Queue Recipient",
        "Email Alert",
        "Auto Email Report",
    ]
}


def check_tool_access(user_role: str, tool_name: str) -> bool:
    """
    Check if a user role has access to a specific tool.

    Args:
        user_role: Role name (System Manager, Assistant Admin, Assistant User, or any other role)
        tool_name: Name of the tool to check access for

    Returns:
        bool: True if access is allowed, False otherwise
    """
    # Check if user_role is in our defined access matrix
    if user_role in ROLE_TOOL_ACCESS:
        role_config = ROLE_TOOL_ACCESS[user_role]
    else:
        # Use Default configuration for all other roles
        role_config = ROLE_TOOL_ACCESS["Default"]

    # System Manager has access to all tools
    if role_config["allowed_tools"] == "*":
        return True

    # Check if tool is explicitly restricted first
    if tool_name in role_config["restricted_tools"]:
        return False

    # Check if tool is explicitly allowed
    if tool_name in role_config["allowed_tools"]:
        return True

    return False


def get_allowed_tools(user_role: str) -> List[str]:
    """
    Get list of tools allowed for a specific user role.

    Args:
        user_role: Role name

    Returns:
        List of allowed tool names
    """
    if user_role not in ROLE_TOOL_ACCESS:
        return []

    role_config = ROLE_TOOL_ACCESS[user_role]

    if role_config["allowed_tools"] == "*":
        # Return all available tools for System Manager
        return ["*"]

    return role_config["allowed_tools"]


def filter_sensitive_fields(doc_dict: Dict[str, Any], doctype: str, user_role: str) -> Dict[str, Any]:
    """
    Filter out sensitive fields from document data based on user role.

    Args:
        doc_dict: Document data as dictionary
        doctype: DocType name
        user_role: User role name

    Returns:
        Filtered document dictionary
    """
    if user_role == "System Manager":
        return doc_dict  # System Manager can see all fields

    filtered_doc = doc_dict.copy()

    # Get sensitive fields for this doctype
    sensitive_fields = set()

    # Add global sensitive fields
    sensitive_fields.update(SENSITIVE_FIELDS.get("all_doctypes", []))

    # Add doctype-specific sensitive fields
    sensitive_fields.update(SENSITIVE_FIELDS.get(doctype, []))

    # Add admin-only fields for Assistant Users
    if user_role == "Assistant User":
        admin_fields = ADMIN_ONLY_FIELDS.get("all_doctypes", [])
        sensitive_fields.update(admin_fields)

        doctype_admin_fields = ADMIN_ONLY_FIELDS.get(doctype, [])
        if doctype_admin_fields == "*":
            # Hide all fields for completely restricted doctypes
            return {"error": "Access to this document type is restricted"}
        else:
            sensitive_fields.update(doctype_admin_fields)

    # Filter out sensitive fields
    for field in sensitive_fields:
        if field in filtered_doc:
            filtered_doc[field] = "***RESTRICTED***"

    return filtered_doc


def is_doctype_accessible(doctype: str, user_role: str) -> bool:
    """
    Check if a user role can access a specific DocType.

    Args:
        doctype: DocType name
        user_role: User role name

    Returns:
        bool: True if access is allowed, False otherwise
    """
    if user_role == "System Manager":
        return True  # System Manager can access all doctypes

    # Default users follow the same DocType restrictions as Assistant User for safety
    role_to_check = user_role if user_role in RESTRICTED_DOCTYPES else "Assistant User"

    restricted_doctypes = RESTRICTED_DOCTYPES.get(role_to_check, [])
    return doctype not in restricted_doctypes


def validate_document_access(user: str, doctype: str, name: str, perm_type: str = "read") -> Dict[str, Any]:
    """
    Validate if a user can access a specific document with proper Frappe permission checking.

    Args:
        user: User name
        doctype: DocType name
        name: Document name
        perm_type: Permission type (read, write, create, delete, etc.)

    Returns:
        Dictionary with validation result
    """
    try:
        # Get user's primary role (includes Default for non-assistant users)
        primary_role = get_user_primary_role(user)

        # Check if DocType is accessible for this role
        if not is_doctype_accessible(doctype, primary_role):
            return {"success": False, "error": f"Access to {doctype} is restricted for your role"}

        # Check Frappe DocType-level permissions - this is the primary security control
        if not frappe.has_permission(doctype, perm_type, user=user):
            return {"success": False, "error": f"Insufficient {perm_type} permissions for {doctype}"}

        # Check document-level permissions (if document exists)
        if name:
            if not frappe.has_permission(doctype, perm_type, doc=name, user=user):
                return {
                    "success": False,
                    "error": f"Insufficient {perm_type} permissions for {doctype} {name}",
                }

            # Check if document is submitted and operation is write/delete
            if perm_type in ["write", "delete"]:
                try:
                    doc = frappe.get_doc(doctype, name)
                    if hasattr(doc, "docstatus") and doc.docstatus == 1:
                        if perm_type == "write":
                            meta = frappe.get_meta(doctype)
                            non_allowed_fields = []
                            for field in data.keys():
                                field_meta = meta.get_field(field)
                                if not field_meta or not field_meta.allow_on_submit:
                                    non_allowed_fields.append(field)
                            if non_allowed_fields:
                                return {
                                    "success": False,
                                    "error": f"Cannot modify submitted document {doctype} {name}",
                                }
                        elif perm_type == "delete":
                            return {
                                "success": False,
                                "error": f"Cannot delete submitted document {doctype} {name}",
                            }
                except Exception:
                    pass  # Document might not exist yet for create operations

        return {"success": True, "role": primary_role}

    except Exception as e:
        frappe.log_error(f"Error in validate_document_access: {str(e)}")
        return {"success": False, "error": "Permission validation failed"}


def get_user_primary_role(user: str) -> str:
    """
    Get the primary (highest privilege) role for a user.

    Args:
        user: User name

    Returns:
        Primary role name - specific assistant role or "Default" for all other users
    """
    user_roles = frappe.get_roles(user)

    # Check for specific assistant roles first (highest to lowest privilege)
    if "System Manager" in user_roles:
        return "System Manager"
    elif "Assistant Admin" in user_roles:
        return "Assistant Admin"
    elif "Assistant User" in user_roles:
        return "Assistant User"
    else:
        # All other users get basic tool access via Default role
        return "Default"


# DEPRECATED: audit_log_tool_access function removed
# Audit logging is now handled automatically by BaseTool._safe_execute
