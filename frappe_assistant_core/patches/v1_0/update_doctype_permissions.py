# -*- coding: utf-8 -*-

import frappe
import json

def execute():
    """Update DocType permissions to include Assistant roles appropriately"""
    
    try:
        # Update Assistant Core Settings - add Assistant Admin role
        add_doctype_permission("Assistant Core Settings", "Assistant Admin", {
            "read": 1,
            "write": 1,
            "create": 1,
            "delete": 0,  # Only System Manager can delete settings
            "email": 0,
            "print": 0,
            "share": 0
        })
        
        # Update Assistant Audit Log - replace Auditor with Assistant Admin and add Assistant User
        update_audit_log_permissions()
        
        # Assistant Connection Log removed - no longer needed for HTTP-based MCP
        # add_doctype_permission("Assistant Connection Log", "Assistant Admin", {...})
        
        frappe.logger().info("Updated DocType permissions for Assistant roles")
        
    except Exception as e:
        frappe.logger().warning(f"Permission update had issues: {str(e)}")


def add_doctype_permission(doctype, role, permissions):
    """Add a permission entry to a DocType"""
    try:
        # Check if permission already exists
        existing = frappe.db.sql("""
            SELECT name FROM `tabDocPerm` 
            WHERE parent = %s AND role = %s
        """, (doctype, role))
        
        if not existing:
            doc = frappe.get_doc("DocType", doctype)
            doc.append("permissions", dict(
                role=role,
                **permissions
            ))
            doc.save(ignore_permissions=True)
            frappe.logger().info(f"Added {role} permission to {doctype}")
    
    except Exception as e:
        frappe.logger().warning(f"Could not add {role} permission to {doctype}: {str(e)}")


def update_audit_log_permissions():
    """Update Assistant Audit Log permissions"""
    try:
        # Remove Auditor role and add Assistant roles
        doc = frappe.get_doc("DocType", "Assistant Audit Log")
        
        # Remove existing Auditor permission if it exists
        permissions_to_remove = []
        for i, perm in enumerate(doc.permissions):
            if perm.role == "Auditor":
                permissions_to_remove.append(i)
        
        # Remove in reverse order to maintain indices
        for i in reversed(permissions_to_remove):
            del doc.permissions[i]
        
        # Add Assistant Admin permission (full access)
        admin_exists = any(p.role == "Assistant Admin" for p in doc.permissions)
        if not admin_exists:
            doc.append("permissions", dict(
                role="Assistant Admin",
                read=1,
                write=1,
                create=1,
                delete=1,
                email=1,
                export=1,
                print=1,
                report=1,
                share=1
            ))
        
        # Add Assistant User permission (read only)
        user_exists = any(p.role == "Assistant User" for p in doc.permissions)
        if not user_exists:
            doc.append("permissions", dict(
                role="Assistant User",
                read=1,
                write=0,
                create=0,
                delete=0,
                email=0,
                export=0,
                print=0,
                report=0,
                share=0
            ))
        
        doc.save(ignore_permissions=True)
        frappe.logger().info("Updated Assistant Audit Log permissions")
        
    except Exception as e:
        frappe.logger().warning(f"Could not update audit log permissions: {str(e)}")