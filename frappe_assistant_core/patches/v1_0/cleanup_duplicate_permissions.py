# -*- coding: utf-8 -*-

import frappe

def execute():
    """Clean up duplicate Custom DocPerm entries created by install.py"""
    
    try:
        # DocTypes that have permissions defined in their JSON files
        doctypes_with_builtin_permissions = [
            "Assistant Core Settings",
            "Assistant Audit Log"  # Assistant Connection Log removed
        ]
        
        for doctype in doctypes_with_builtin_permissions:
            # Remove any Custom DocPerm entries that duplicate built-in permissions
            duplicate_perms = frappe.db.sql("""
                SELECT name FROM `tabCustom DocPerm` 
                WHERE parent = %s AND role = 'System Manager'
            """, (doctype,), as_dict=True)
            
            for perm in duplicate_perms:
                frappe.delete_doc("Custom DocPerm", perm.name, ignore_permissions=True)
                frappe.logger().info(f"Removed duplicate permission for {doctype}")
        
        frappe.logger().info("Cleaned up duplicate permissions successfully")
        
    except Exception as e:
        frappe.logger().warning(f"Permission cleanup had issues: {str(e)}")