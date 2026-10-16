from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.plugins.faco.helpdesk.tool import HelpdeskTool
from frappe_assistant_core.utils.message_body import as_html_body
from frappe_assistant_core.utils.savepoint import open_savepoint, release_savepoint, rollback_to_savepoint

# reply_via_agent inserts the Communication (and moves first response and SLA) before it sends,
# so a send that fails must not leave a reply on the ticket that the user was told failed.
_SAVEPOINT = "fac_helpdesk_reply"


class ReplyToHelpdeskTicket(HelpdeskTool):
    def __init__(self):
        super().__init__()
        self.name = "reply_to_helpdesk_ticket"
        self.description = (
            "Send a reply to the customer on a Helpdesk ticket, exactly as an agent replying in "
            "Helpdesk: it is added to the ticket thread and emailed to the person who raised it. "
            "Put the complete reply in `message`. The user sees it in an approval card first and "
            "nothing is sent unless they approve. Only Helpdesk agents can reply."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                "ticket": {"type": "string", "description": "HD Ticket name"},
                "message": {"type": "string", "description": "The complete reply, as HTML"},
                "cc": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional CC email addresses",
                },
            },
            "required": ["ticket", "message"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        from helpdesk.utils import is_agent

        ticket = str(arguments.get("ticket") or "").strip()
        message = arguments.get("message") or ""
        cc = [c.strip() for c in arguments.get("cc") or [] if c and c.strip()]

        if not message.strip():
            return {"success": False, "error": _("The reply is empty")}
        invalid = [c for c in cc if not frappe.utils.validate_email_address(c)]
        if invalid:
            return {"success": False, "error": _("Not a valid email address: {0}").format(", ".join(invalid))}
        if not ticket or not frappe.db.exists("HD Ticket", ticket):
            return {"success": False, "error": _("Ticket {0} was not found").format(ticket)}
        doc = frappe.get_doc("HD Ticket", ticket)
        if not doc.has_permission("read"):
            return {"success": False, "error": _("Ticket {0} was not found").format(ticket)}
        # Helpdesk checks this itself only from 1.23.
        if not is_agent():
            return {"success": False, "error": _("Only Helpdesk agents can send replies.")}

        marks = open_savepoint(_SAVEPOINT)
        try:
            # Newer Helpdesk no longer falls back to raised_by, so name the recipient.
            communication = doc.reply_via_agent(
                message=as_html_body(message), to=doc.raised_by, cc=", ".join(cc) or None
            )
        except Exception as e:
            rollback_to_savepoint(_SAVEPOINT, marks, "HD Ticket", ticket)
            if isinstance(e, frappe.PermissionError):
                return {"success": False, "error": _("Only Helpdesk agents can send replies.")}
            return {"success": False, "error": str(e) or _("The reply could not be sent")}
        release_savepoint(_SAVEPOINT)

        # Helpdesk before 1.30 returns nothing; the reply is the newest Communication on the ticket.
        communication = communication or frappe.db.get_value(
            "Communication",
            {"reference_doctype": "HD Ticket", "reference_name": ticket, "sent_or_received": "Sent"},
            "name",
            order_by="creation desc",
        )
        return {
            "success": True,
            "ticket": ticket,
            "communication": communication,
            "email_queued": bool(frappe.db.exists("Email Queue", {"communication": communication})),
        }
