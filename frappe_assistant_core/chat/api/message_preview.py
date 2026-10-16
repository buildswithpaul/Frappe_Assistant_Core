# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""
Message preview — what a message tool will really send, for its approval card.

The card shows the model's draft (body, Cc) from the tool input. Who it goes to and which
account sends it come from here, resolved the way the tool itself will resolve them, so the
user approves what actually happens rather than what the model claims.
"""

import frappe
from frappe import _
from frappe.email.doctype.email_account.email_account import EmailAccount


def _preview(**fields) -> dict:
    return {
        "can_send": True,
        "reason": None,
        "title": "",
        "context": None,
        "to": None,
        "subject": None,
        "sender": None,
        "will_email": True,
        **fields,
    }


def _helpdesk_reply(ticket: str | None) -> dict:
    from frappe_assistant_core.plugins.faco.helpdesk.tool import helpdesk_installed, reply_emails_customer

    title = _("Send reply on {0}").format(ticket or "")
    if not helpdesk_installed():
        return _preview(title=title, can_send=False, reason=_("Helpdesk is not installed"))
    if not ticket or not frappe.db.exists("HD Ticket", ticket):
        return _preview(title=title, can_send=False, reason=_("Ticket {0} was not found").format(ticket))
    doc = frappe.get_doc("HD Ticket", ticket)
    if not doc.has_permission("read"):
        return _preview(title=title, can_send=False, reason=_("Ticket {0} was not found").format(ticket))

    from helpdesk.utils import is_agent

    preview = _preview(title=title, context=doc.subject, to=[doc.raised_by], subject=f"Re: {doc.subject}")
    if not is_agent():
        preview.update(can_send=False, reason=_("Only Helpdesk agents can send replies."))
    if not reply_emails_customer():
        preview["will_email"] = False
        return preview
    account = doc.sender_email()
    if account:
        preview["sender"] = account.email_id
    elif preview["can_send"]:
        preview.update(
            can_send=False,
            reason=_("No outgoing email account is set up, so Helpdesk cannot send the reply."),
        )
    return preview


def _send_email(ticket: str | None) -> dict:
    # send_email passes no sender, so frappe.sendmail falls back to the default outgoing account.
    account = EmailAccount.find_default_outgoing()
    if not account:
        return _preview(
            title=_("Send email"),
            can_send=False,
            reason=_("No outgoing email account is set up, so this email cannot be sent."),
        )
    return _preview(title=_("Send email"), sender=account.email_id)


_BUILDERS = {
    "reply_to_helpdesk_ticket": _helpdesk_reply,
    "send_email": _send_email,
}


@frappe.whitelist(methods=["GET"])
def get_message_preview(tool_name: str, ticket: str | None = None) -> dict:
    """Resolve what a message tool's approval card should show.

    Returns:
            {"can_send", "reason", "title", "context", "to", "subject", "sender", "will_email"}.
            ``to``/``subject`` are None when the card should read them from the tool input.
    """
    builder = _BUILDERS.get(tool_name)
    if not builder:
        frappe.throw(_("No preview for {0}").format(tool_name), frappe.ValidationError)
    return builder(ticket)
