import frappe
from frappe import _


def send_fac_admin_invite():
    """Welcome every System Manager after installation.

    Unlike every other managed email in the product, this one is sent by the
    customer's own site to its own admins, not by the SaaS server — so it
    must render with plain frappe.sendmail and never depend on
    assistant_runtime being installed here.

    It is deliberately NOT gated on the FAC Chat gate. `enable_fac_chat`
    defaults to 0 and nothing enables it during `after_install` — the only
    writer is the `toggle_chat` admin action — so gating this on the gate would
    suppress the email on every install rather than only on BYO-LLM ones. The
    copy instead describes what is true at install time and points at FAC
    Admin, which is reachable whether or not chat is on; `/copilot/` raises
    PageDoesNotExistError until an administrator enables chat.
    """
    recipients = _get_system_manager_emails()
    if not recipients:
        frappe.log_error("No System Manager users found for FAC invite", "FAC Invite Hook")
        return

    admin_url = frappe.utils.get_url("/app/fac-admin")
    for recipient in recipients:
        try:
            frappe.sendmail(
                recipients=[recipient],
                subject=_("FAC Cloud is installed on your site"),
                template="fac_welcome",
                args={"heading": _("FAC Cloud is installed"), "cta_url": admin_url},
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
