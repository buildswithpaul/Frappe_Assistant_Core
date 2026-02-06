import frappe


def send_fac_admin_invite():
    """Send a welcome email to all System Manager users after FAC installation."""
    recipients = _get_system_manager_emails()

    if not recipients:
        frappe.log_error("No System Manager users found for FAC invite", "FAC Invite Hook")
        return

    email_account = frappe.db.get_value(
        "Email Account", {"default_outgoing": 1, "enable_outgoing": 1}, "email_id"
    )

    if not email_account:
        frappe.log_error("No default outgoing Email Account found", "FAC Invite Hook")
        return

    site_url = frappe.utils.get_url()

    try:
        frappe.sendmail(
            recipients=recipients,
            subject="Welcome to Frappe Assistant Core",
            template="fac_welcome_invite",
            args={"site_url": site_url},
            sender=email_account,
            delayed=True,
        )
    except Exception:
        frappe.log_error("Failed to send FAC welcome email", "FAC Invite Hook")


def _get_system_manager_emails():
    """Batch-fetch emails for all enabled System Manager users."""
    system_managers = frappe.get_all(
        "Has Role",
        filters={"role": "System Manager", "parenttype": "User"},
        fields=["parent"],
    )

    if not system_managers:
        return []

    user_names = [sm.parent for sm in system_managers]

    users = frappe.get_all(
        "User",
        filters={"name": ("in", user_names), "enabled": 1},
        fields=["email"],
    )

    return [
        user.email
        for user in users
        if user.email and "@" in user.email and not user.email.endswith("@example.com")
    ]
