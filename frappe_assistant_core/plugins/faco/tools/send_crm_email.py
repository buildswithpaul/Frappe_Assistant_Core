from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.plugins.faco.crm.email import crm_sender
from frappe_assistant_core.plugins.faco.crm.tool import RECORD_SCHEMA, CrmTool, resolve_record
from frappe_assistant_core.utils.message_body import as_html_body
from frappe_assistant_core.utils.savepoint import open_savepoint, release_savepoint, rollback_to_savepoint

# make() inserts the Communication before it sends; a send that fails must not leave an
# email on the record that the user was told failed.
_SAVEPOINT = "fac_crm_email"


def _addresses(values) -> list[str]:
    return [v.strip() for v in values or [] if v and str(v).strip()]


class SendCrmEmail(CrmTool):
    def __init__(self):
        super().__init__()
        self.name = "send_crm_email"
        self.description = (
            "Email a Frappe CRM lead or deal from the record, exactly as CRM's own email composer does: it "
            "lands on the record's Emails tab and goes out from the user's email account. Put the complete "
            "email in `message`; the user approves it in a card before anything is sent. `recipients` "
            "defaults to the record's email."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                **RECORD_SCHEMA,
                "recipients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Defaults to the record's email",
                },
                "cc": {"type": "array", "items": {"type": "string"}},
                "subject": {"type": "string"},
                "message": {"type": "string", "description": "The complete email, HTML or plain text"},
            },
            "required": ["doctype", "name", "subject", "message"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doc, error = resolve_record(arguments.get("doctype"), arguments.get("name"))
        if error:
            return error
        if not frappe.has_permission(doc.doctype, "email", doc.name):
            return {"success": False, "error": _("You are not permitted to email from {0}").format(doc.name)}

        subject = str(arguments.get("subject") or "").strip()
        message = arguments.get("message") or ""
        if not subject or not message.strip():
            return {"success": False, "error": _("The email needs a subject and a message")}
        recipients = _addresses(arguments.get("recipients")) or _addresses([doc.get("email")])
        if not recipients:
            return {
                "success": False,
                "error": _("{0} has no email address; pass recipients").format(doc.name),
            }
        cc = _addresses(arguments.get("cc"))
        invalid = [a for a in recipients + cc if not frappe.utils.validate_email_address(a)]
        if invalid:
            return {"success": False, "error": _("Not a valid email address: {0}").format(", ".join(invalid))}
        account = crm_sender()
        if not account:
            return {
                "success": False,
                "error": _("No outgoing email account is set up, so this email cannot be sent."),
            }

        from frappe.core.doctype.communication.email import make

        marks = open_savepoint(_SAVEPOINT)
        try:
            result = make(
                doctype=doc.doctype,
                name=doc.name,
                subject=subject,
                content=as_html_body(message),
                recipients=", ".join(recipients),
                cc=", ".join(cc) or None,
                sender=account.email_id,
                send_email=1,
            )
        except Exception as e:
            rollback_to_savepoint(_SAVEPOINT, marks, doc.doctype, doc.name)
            return {"success": False, "error": str(e) or _("The email could not be sent")}
        release_savepoint(_SAVEPOINT)

        communication = result.get("name")
        return {
            "success": True,
            "communication": communication,
            "recipients": recipients,
            "email_queued": bool(frappe.db.exists("Email Queue", {"communication": communication})),
        }
