from typing import Any, Dict

import frappe
from frappe import _
from frappe.utils import strip_html

from frappe_assistant_core.plugins.faco.crm.tool import RECORD_SCHEMA, CrmTool, crm_link, resolve_record

_TEXT_LIMIT = 1000


def _text(html) -> str:
    text = strip_html(str(html or "")).strip()
    return text if len(text) <= _TEXT_LIMIT else text[:_TEXT_LIMIT] + "…"


def newest(rows: list) -> list:
    return sorted(rows, key=lambda r: str(r.get("creation") or r.get("modified") or ""), reverse=True)


def _pick(row: dict, keys: tuple) -> dict:
    return {k: row.get(k) for k in keys if row.get(k) not in (None, "")}


class GetCrmActivity(CrmTool):
    def __init__(self):
        super().__init__()
        self.name = "get_crm_activity"
        self.description = (
            "Read a Frappe CRM lead's or deal's whole history — emails, notes, calls, tasks, comments and "
            "field changes, newest first — through CRM's own timeline. Use it before summarising a lead or "
            "deal, or deciding a next step; the lead or deal record alone does not contain its history."
        )
        self.requires_permission = None
        self.inputSchema = {
            "type": "object",
            "properties": {
                **RECORD_SCHEMA,
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 30},
            },
            "required": ["doctype", "name"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        from crm.api.activities import get_activities

        doc, error = resolve_record(arguments.get("doctype"), arguments.get("name"))
        if error:
            return error
        limit = min(max(int(arguments.get("limit") or 30), 1), 100)
        try:
            activities, calls, notes, tasks, _attachments = get_activities(doc.name)
        except frappe.PermissionError:
            return {"success": False, "error": _("{0} {1} was not found").format(_(doc.doctype), doc.name)}
        finally:
            # CRM builds the timeline from Desk's docinfo, which it leaves on the HTTP response.
            frappe.response.pop("docinfo", None)

        emails, comments, changes = [], [], []
        for a in activities:
            kind, data = a.get("activity_type"), a.get("data") or {}
            if kind == "communication":
                emails.append(
                    {
                        "date": str(a.get("creation")),
                        "subject": data.get("subject"),
                        "from": data.get("sender"),
                        "to": data.get("recipients"),
                        "body": _text(data.get("content")),
                    }
                )
            elif kind == "comment":
                comments.append(
                    {"date": str(a.get("creation")), "by": a.get("owner"), "text": _text(a.get("content"))}
                )
            elif kind in ("added", "changed", "removed") and isinstance(data, dict):
                changes.append(
                    {
                        "date": str(a.get("creation")),
                        "by": a.get("owner"),
                        "change": kind,
                        **_pick(data, ("field_label", "old_value", "value")),
                    }
                )

        return {
            "success": True,
            "record": {
                "doctype": doc.doctype,
                "name": doc.name,
                "title": doc.get("lead_name") or doc.get("organization") or doc.name,
                "status": doc.get("status"),
                "owner": doc.get("lead_owner") or doc.get("deal_owner"),
                "link": crm_link(doc.doctype, doc.name),
            },
            "emails": emails[:limit],
            "notes": [
                {**_pick(n, ("title", "owner", "modified")), "content": _text(n.get("content"))}
                for n in newest(notes)[:limit]
            ],
            "calls": [
                _pick(c, ("type", "status", "duration", "creation", "caller", "receiver", "note"))
                for c in newest(calls)[:limit]
            ],
            "tasks": [
                {
                    **_pick(t, ("title", "status", "priority", "assigned_to", "due_date")),
                    "description": _text(t.get("description")),
                }
                for t in newest(tasks)[:limit]
            ],
            "comments": comments[:limit],
            "changes": changes[:limit],
        }
