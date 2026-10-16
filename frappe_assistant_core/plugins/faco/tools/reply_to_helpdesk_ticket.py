from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.plugins.faco.helpdesk.tool import HelpdeskTool, reply_emails_customer


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
        ticket = str(arguments.get("ticket") or "").strip()
        message = arguments.get("message") or ""
        cc = [c.strip() for c in arguments.get("cc") or [] if c and c.strip()]

        if not message.strip():
            return {"success": False, "error": _("The reply is empty")}
        if not ticket or not frappe.db.exists("HD Ticket", ticket):
            return {"success": False, "error": _("Ticket {0} was not found").format(ticket)}
        doc = frappe.get_doc("HD Ticket", ticket)
        if not doc.has_permission("read"):
            return {"success": False, "error": _("Ticket {0} was not found").format(ticket)}

        try:
            # Newer Helpdesk no longer falls back to raised_by, so name the recipient.
            communication = doc.reply_via_agent(message=message, to=doc.raised_by, cc=", ".join(cc) or None)
        except frappe.PermissionError:
            return {"success": False, "error": _("Only Helpdesk agents can send replies.")}
        except frappe.ValidationError as e:
            return {"success": False, "error": str(e)}

        return {
            "success": True,
            "ticket": ticket,
            "communication": communication,
            "email_queued": reply_emails_customer(),
        }
