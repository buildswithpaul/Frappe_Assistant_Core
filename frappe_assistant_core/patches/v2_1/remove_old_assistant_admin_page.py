import frappe


def execute():
    """
    Remove old assistant-admin page after renaming to fac-admin.

    This cleanup ensures no orphaned pages remain after the rename.
    """
    try:
        # Check if the old page exists
        if frappe.db.exists("Page", "assistant-admin"):
            frappe.delete_doc("Page", "assistant-admin", force=True, ignore_permissions=True)
            frappe.logger().info("Deleted old assistant-admin page")
            print("✓ Removed old assistant-admin page")
        else:
            frappe.logger().info("Old assistant-admin page does not exist, skipping")
            print("✓ Old assistant-admin page already removed")

        frappe.db.commit()

    except Exception as e:
        frappe.logger().error(f"Failed to remove old assistant-admin page: {str(e)}")
        print(f"✗ Failed to remove old assistant-admin page: {str(e)}")
