import frappe


def send_fac_admin_invite():
    users = frappe.get_all(
        "User", filters={"enabled": 1}, fields=["name", "email", "first_name", "full_name"]
    )
    recipients = []

    for user in users:
        roles = frappe.get_roles(user.name)

        if "System Manager" in roles:
            if user.email and "@" in user.email and not user.email.endswith("@example.com"):
                recipients.append(user.email)

    if not recipients:
        frappe.log_error("No System Manager users found for FAC invite", "FAC Invite Hook")
        return

    email_account = frappe.db.get_value(
        "Email Account", {"default_outgoing": 1, "enable_outgoing": 1}, "email_id"
    )

    if not email_account:
        frappe.log_error("No default outgoing Email Account found", "FAC Invite Hook")
        return

    frappe.sendmail(
        recipients=[email_account],
        bcc=recipients,
        subject="Welcome to Frappe Assistant Core",
        template="fac_welcome_invite",
        sender=email_account,
        delayed=False,
    )
