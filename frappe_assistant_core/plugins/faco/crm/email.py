"""Which account a CRM email goes out from — shared by send_crm_email and its approval card."""

import frappe
from frappe.email.doctype.email_account.email_account import EmailAccount


def crm_sender(user: str | None = None):
    """The user's own outgoing Email Account, as CRM's composer offers first; else the site default.

    None when the site has no outgoing account at all.
    """
    user = user or frappe.session.user
    for account in frappe.get_all(
        "User Email", filters={"parent": user, "parenttype": "User"}, pluck="email_account"
    ):
        if account and frappe.db.get_value("Email Account", account, "enable_outgoing"):
            return frappe.get_doc("Email Account", account)
    return EmailAccount.find_default_outgoing()
