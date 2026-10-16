from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.plugins.faco.crm.tool import RECORD_SCHEMA, CrmTool, crm_link, resolve_record

KINDS = ("note", "task", "call")
PRIORITIES = ("Low", "Medium", "High")


def _phone(doc) -> str:
    return doc.get("mobile_no") or doc.get("phone") or ""


class AddCrmActivity(CrmTool):
    def __init__(self):
        super().__init__()
        self.name = "add_crm_activity"
        self.description = (
            "Add a note, a follow-up task or a call log to a Frappe CRM lead or deal, linked so it shows on "
            "the record's Notes, Tasks or Calls tab. A task is assigned to the user unless `assigned_to` "
            "names someone else. Use one call per thing the user asked for."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                **RECORD_SCHEMA,
                "kind": {"type": "string", "enum": list(KINDS)},
                "title": {"type": "string", "description": "Note or task title"},
                "content": {
                    "type": "string",
                    "description": "Note text, task description, or what the call covered",
                },
                "due_date": {"type": "string", "description": "Task due date-time, YYYY-MM-DD HH:MM:SS"},
                "priority": {"type": "string", "enum": list(PRIORITIES)},
                "assigned_to": {
                    "type": "string",
                    "description": "Task assignee (user email); defaults to the user",
                },
                "direction": {"type": "string", "enum": ["Outgoing", "Incoming"], "default": "Outgoing"},
                "duration_seconds": {"type": "integer", "minimum": 0},
                "our_phone": {
                    "type": "string",
                    "description": "Call: the user's number, when their profile has none",
                },
                "their_phone": {
                    "type": "string",
                    "description": "Call: the lead's/deal's number, when the record has none",
                },
            },
            "required": ["doctype", "name", "kind"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        kind = arguments.get("kind")
        if kind not in KINDS:
            return {"success": False, "error": _("kind must be one of: {0}").format(", ".join(KINDS))}
        doc, error = resolve_record(arguments.get("doctype"), arguments.get("name"), ptype="write")
        if error:
            return error
        link = {"reference_doctype": doc.doctype, "reference_docname": doc.name}
        title = str(arguments.get("title") or "").strip()
        content = arguments.get("content") or ""

        if kind == "note":
            if not title:
                return {"success": False, "error": _("A note needs a title")}
            created = frappe.get_doc(
                {"doctype": "FCRM Note", "title": title, "content": content, **link}
            ).insert()
        elif kind == "task":
            if not title:
                return {"success": False, "error": _("A task needs a title")}
            priority = arguments.get("priority")
            created = frappe.get_doc(
                {
                    "doctype": "CRM Task",
                    "title": title,
                    "description": content,
                    "due_date": arguments.get("due_date") or None,
                    "priority": priority if priority in PRIORITIES else "Medium",
                    "status": "Todo",
                    # CRM assigns the task (a ToDo) to this user when it is saved.
                    "assigned_to": arguments.get("assigned_to") or frappe.session.user,
                    **link,
                }
            ).insert()
        else:
            direction = "Incoming" if arguments.get("direction") == "Incoming" else "Outgoing"
            ours = arguments.get("our_phone") or _phone(frappe.get_doc("User", frappe.session.user))
            theirs = arguments.get("their_phone") or _phone(doc)
            missing = [
                label
                for label, value in ((_("your phone number"), ours), (_("their phone number"), theirs))
                if not value
            ]
            if missing:
                return {
                    "success": False,
                    "error": _("A call log needs both phone numbers; ask the user for {0}").format(
                        ", ".join(missing)
                    ),
                }
            note = None
            if content:
                note = frappe.get_doc(
                    {"doctype": "FCRM Note", "title": title or _("Call notes"), "content": content, **link}
                ).insert()
            created = frappe.get_doc(
                {
                    "doctype": "CRM Call Log",
                    "type": direction,
                    "status": "Completed",
                    "from": ours if direction == "Outgoing" else theirs,
                    "to": theirs if direction == "Outgoing" else ours,
                    "duration": int(arguments.get("duration_seconds") or 0),
                    "telephony_medium": "Manual",
                    "caller": frappe.session.user if direction == "Outgoing" else None,
                    "receiver": frappe.session.user if direction == "Incoming" else None,
                    "note": note.name if note else None,
                    **link,
                }
            ).insert()

        return {
            "success": True,
            "kind": kind,
            "created": created.name,
            "record": doc.name,
            "link": f"{crm_link(doc.doctype, doc.name)}#{kind}s",
        }
