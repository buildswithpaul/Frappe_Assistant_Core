import frappe


def execute():
    """Add assistant_enabled field to User DocType"""

    # Check if custom field already exists
    if frappe.db.exists("Custom Field", {"dt": "User", "fieldname": "assistant_enabled"}):
        return

    # Create the custom field
    custom_field = frappe.get_doc(
        {
            "doctype": "Custom Field",
            "dt": "User",
            "fieldname": "assistant_enabled",
            "label": "Enable Assistant Access",
            "fieldtype": "Check",
            "insert_after": "enabled",
            "description": "Allow this user to access assistant tools",
            "default": "1",
            "reqd": 0,
            "read_only": 0,
            "print_hide": 1,
            "report_hide": 0,
            "in_global_search": 0,
            "permlevel": 0,
        }
    )

    custom_field.insert(ignore_permissions=True)
    frappe.logger().info("Added assistant_enabled field to User DocType")
