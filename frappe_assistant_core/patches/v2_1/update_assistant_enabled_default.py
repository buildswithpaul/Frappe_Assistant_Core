import frappe


def execute():
    """
    Update assistant_enabled custom field to be enabled by default.

    This improves the onboarding experience - users can start using
    the assistant immediately after installation without manual configuration.
    """
    # Update the Custom Field to have default = 1
    if frappe.db.exists("Custom Field", {"dt": "User", "fieldname": "assistant_enabled"}):
        custom_field = frappe.get_doc("Custom Field", {"dt": "User", "fieldname": "assistant_enabled"})
        custom_field.default = "1"
        custom_field.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.logger().info("Updated assistant_enabled custom field default to 1")

    # Enable assistant access for all existing enabled users
    # This ensures existing users don't need manual enabling
    frappe.db.sql("""
        UPDATE `tabUser`
        SET assistant_enabled = 1
        WHERE enabled = 1
        AND user_type = 'System User'
        AND name NOT IN ('Guest', 'Administrator')
    """)

    frappe.db.commit()
    frappe.logger().info("Enabled assistant access for all existing enabled users")
