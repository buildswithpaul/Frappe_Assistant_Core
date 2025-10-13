import frappe


def execute():
    """
    Rename assistant-admin page to fac-admin.

    This updates the page name to the new convention while preserving
    all functionality and user bookmarks will be redirected automatically.
    """
    try:
        # Check if the old page exists
        if frappe.db.exists("Page", "assistant-admin"):
            # Check if new page already exists (shouldn't happen, but safety check)
            if frappe.db.exists("Page", "fac-admin"):
                frappe.logger().info("fac-admin page already exists, deleting old assistant-admin page")
                frappe.delete_doc("Page", "assistant-admin", force=True, ignore_permissions=True)
                print("✓ Removed old assistant-admin page (fac-admin already exists)")
            else:
                # Rename the page using Frappe's rename_doc function
                frappe.rename_doc("Page", "assistant-admin", "fac-admin", force=True)
                frappe.logger().info("Renamed assistant-admin page to fac-admin")
                print("✓ Renamed assistant-admin to fac-admin")
        else:
            frappe.logger().info("Old assistant-admin page does not exist, skipping")
            print("✓ assistant-admin page does not exist (already renamed or doesn't exist)")

        frappe.db.commit()

    except Exception as e:
        frappe.logger().error(f"Failed to rename assistant-admin page: {str(e)}")
        print(f"✗ Failed to rename assistant-admin page: {str(e)}")
