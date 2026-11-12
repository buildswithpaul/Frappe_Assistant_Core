# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Import progress in FAC Chat (#34416): where each import session of a conversation stands, for the
progress block under start_import and the Import card in the side panel. The chat asks it once on
load (so a reopened conversation shows the session's state now) and again when Frappe's
data_import_progress events say the import moved: no model call, and no polling by the model.
"""

import json
from typing import Any, Dict, List, Optional, Union

import frappe
from frappe import _
from frappe.utils import cint, cstr

SESSION = "FAC Import Session"
#: At most this many sessions in one call: a conversation's imports, not a site's
MAX_SESSIONS = 20
#: The card's steps, in order
STEPS = ("read", "mapped", "checked", "imported")
STEP_OF_STATUS = {
    "File Read": "read",
    "Mapped": "mapped",
    "Dry Run Failed": "checked",
    "Ready to Import": "checked",
    "Importing": "imported",
    "Completed": "imported",
    "Partially Completed": "imported",
}
ENDED = ("Completed", "Partially Completed", "Failed", "Cancelled", "Undone")


def _names(sessions: Any) -> List[str]:
    if isinstance(sessions, str):
        try:
            sessions = json.loads(sessions)
        except ValueError:
            sessions = [s.strip() for s in sessions.split(",")]
    if not isinstance(sessions, list):
        return []
    return [s for s in dict.fromkeys(str(s) for s in sessions if s)][:MAX_SESSIONS]


def _ready(doc) -> Optional[int]:
    try:
        return (json.loads(doc.validation_summary or "{}") or {}).get("ready")
    except (TypeError, ValueError):
        return None


def progress(doc) -> Dict[str, Any]:
    """One session as the chat shows it: its step, the counts so far and the Data Import running it."""
    from frappe_assistant_core.utils import import_failures

    runs = import_failures.runs(doc)
    created = sum(run["created"] for run in runs) or len(doc.created_records)
    # a retry imports the rows that failed before: the last run's failures are the ones left
    failed = runs[-1]["failed"] if runs else 0
    step = STEP_OF_STATUS.get(doc.status)
    if doc.status == "Failed":
        step = "imported" if runs else "checked"
    return {
        "session": doc.name,
        "file_name": doc.file_name,
        "doctype": doc.target_doctype,
        "status": doc.status,
        "step": step,
        "importing": doc.status == "Importing",
        "ended": doc.status in ENDED,
        "data_import": doc.data_imports[-1].data_import if doc.data_imports else None,
        "total": _ready(doc),
        "created": created,
        "failed": failed,
        # Frappe's own form URL: /app on v15, /desk on v16
        "url": frappe.utils.get_url_to_form(SESSION, doc.name),
    }


@frappe.whitelist(methods=["GET"])
def import_progress(sessions: Union[str, List[str], None] = None) -> Dict[str, Any]:
    """The sessions the user may read, each as ``progress`` says it; others are left out."""
    out = []
    for name in _names(sessions):
        if not frappe.db.exists(SESSION, name) or not frappe.has_permission(SESSION, "read", doc=name):
            continue
        out.append(progress(frappe.get_doc(SESSION, name)))
    labels = {"read": _("Read"), "mapped": _("Mapped"), "checked": _("Checked"), "imported": _("Imported")}
    return {"sessions": out, "steps": [{"key": key, "label": labels[key]} for key in STEPS]}


@frappe.whitelist(methods=["GET"])
def plan_progress(plan: str) -> Dict[str, Any]:
    """A migration plan as the chat shows it while it runs (#34351): its status and each file's
    progress, in the plan's order. A plan the user may not read is not found."""
    from frappe_assistant_core.utils import import_plan

    if not frappe.db.exists(SESSION, plan) or not frappe.has_permission(SESSION, "read", doc=plan):
        raise frappe.DoesNotExistError(_("Migration plan {0} not found.").format(plan))
    found = import_plan.get_plan(plan)
    files = [progress(child) for child in import_plan.children(found)]
    return {
        "plan": found.name,
        "status": found.status,
        "running": found.status == "Running",
        "ended": found.status in PLAN_ENDED,
        "files": files,
        "url": frappe.utils.get_url_to_form(SESSION, found.name),
    }


PLAN_ENDED = ("Completed", "Partially Completed", "Failed", "Stopped")


# -- the mapping review card and the import approval card (#34415) -----------------------------

#: How many of a column's first values the review card shows
SAMPLES_SHOWN = 3


def _review(doc) -> Dict[str, Any]:
    """The session's mapping as the review card shows it: each column with its first values, its
    field and a status, the fields it can choose from and the required fields with no column."""
    from frappe_assistant_core.plugins.migration.tools.set_column_mapping import _mapping_refused, _samples
    from frappe_assistant_core.utils.import_mapping import (
        DONT_IMPORT,
        _mapping_targets,
        _table_title,
        build_import_schema,
        describe_mapping,
        session_headers,
        session_mapping,
    )

    if not doc.target_doctype:
        return {"session": doc.name, "ready": False, "message": _("The file has no ERPNext type yet.")}
    headers = session_headers(doc)
    schema = build_import_schema(doc.target_doctype)
    targets = _mapping_targets(schema)
    mapping = session_mapping(doc)
    samples = _samples(doc)
    described = describe_mapping(
        schema, headers, mapping, update=doc.import_type == "Update Existing Records", samples=samples
    )
    columns = []
    for position, header in enumerate(headers):
        field = mapping.get(str(position))
        if field == DONT_IMPORT:
            status = "not_imported"
        elif field and field in targets:
            status = "mapped"
        else:
            status, field = "unmapped", None
        values = [row[position] for row in samples if position < len(row) and str(row[position]).strip()]
        columns.append(
            {
                "position": position,
                "column": header,
                "samples": values[:SAMPLES_SHOWN],
                "field": field,
                "label": targets[field]["label"] if field in targets else None,
                "status": status,
            }
        )
    options = [{"value": DONT_IMPORT, "label": _("Don't import")}]
    for field, target in targets.items():
        table = target.get("table")
        label = f"{_table_title(table)}: {target['label']}" if table else target["label"]
        options.append({"value": field, "label": label, "required": bool(target.get("required"))})
    refused = _mapping_refused(doc)
    return {
        "session": doc.name,
        "ready": True,
        "file_name": doc.file_name,
        "doctype": doc.target_doctype,
        "status": doc.status,
        "editable": not refused,
        "refused": refused,
        "columns": columns,
        "options": options,
        "missing_required": described["missing_required"],
        "summary": described["summary"],
    }


def _load(session: str):
    from frappe_assistant_core.utils.import_mapping import load_session

    return load_session(session)  # the session's own permission: its user, or a System Manager


@frappe.whitelist(methods=["GET"])
def mapping_review(session: str) -> Dict[str, Any]:
    """The mapping review card's data for a session the user may read."""
    return _review(_load(session))


@frappe.whitelist(methods=["POST"])
def set_mapping_column(session: str, position: int, field: str) -> Dict[str, Any]:
    """A dropdown changed on the review card: that one column remapped through set_column_mapping
    itself, so its checks, permission and audit are the model's, and the card refreshed. No chat
    message: the user changed it by hand."""
    from frappe_assistant_core.core.tool_registry import get_tool_registry

    doc = _load(session)
    reply = (
        get_tool_registry()
        .get_tool("set_column_mapping")
        ._safe_execute({"session": doc.name, "mapping": {str(int(position)): field}})
    )
    result = reply.get("result") if isinstance(reply, dict) and "result" in reply else reply
    ok = bool(reply.get("success")) and bool((result or {}).get("success", True))
    out = {"success": ok, "review": _review(_load(session))}
    if not ok:
        out["error"] = (result or {}).get("error") or reply.get("error")
        out["problems"] = (result or {}).get("problems") or []
    return out


@frappe.whitelist(methods=["GET"])
def import_card(session: str) -> Dict[str, Any]:
    """What the import approval card says besides the tool's own figures: the file, new records or
    updates, the rows left out, whether they are submitted and the mapping in one line."""
    from frappe_assistant_core.utils import import_fixes
    from frappe_assistant_core.utils.import_mapping import (
        _mapping_targets,
        build_import_schema,
        session_headers,
        session_mapping,
    )

    doc = _load(session)
    try:
        summary = json.loads(doc.validation_summary or "{}") or {}
    except (TypeError, ValueError):
        summary = {}
    headers = session_headers(doc) if doc.target_doctype else []
    targets = _mapping_targets(build_import_schema(doc.target_doctype)) if doc.target_doctype else {}
    pairs = []
    for position, field in session_mapping(doc).items():
        if field in targets and int(position) < len(headers):
            pairs.append(f"{headers[int(position)]} → {targets[field]['label']}")
    shown = ", ".join(pairs[:4])
    if len(pairs) > 4:
        shown += " " + _("and {0} more").format(len(pairs) - 4)
    update = doc.import_type == "Update Existing Records"
    return {
        "session": doc.name,
        "file_name": doc.file_name,
        "doctype": doc.target_doctype,
        "update": update,
        "rows": summary.get("ready"),
        "left_out": len(import_fixes.left_out(doc)),
        "submit": bool(doc.get("submit_after_import")),
        "mapping": shown,
        "changes": _changes(summary.get("update")) if update else None,
    }


#: A value on the approval card is cut to this many characters
CARD_VALUE_LENGTH = 80


def _changes(preview: Any) -> Optional[Dict[str, Any]]:
    """An update's old and new values, from its last check, for the approval card (PR #392, F6):
    the card said "Update 1 Customer records" with counts only, and the values were shown only if
    the model chose to. The user approves what changes, so the card shows it."""
    if not isinstance(preview, dict):
        return None

    def shown(value: Any) -> str:
        text = cstr(value)
        return text if len(text) <= CARD_VALUE_LENGTH else text[: CARD_VALUE_LENGTH - 1] + "…"

    samples = []
    for sample in preview.get("samples") or []:
        changes = [
            {"label": cstr(c.get("label")), "old": shown(c.get("old")), "new": shown(c.get("new"))}
            for c in sample.get("changes") or []
        ]
        samples.append({"record": cstr(sample.get("record")), "changes": changes})
    return {
        "records": cint(preview.get("records_changing")),
        "fields": cint(preview.get("fields_changing")),
        "by_field": preview.get("by_field") or {},
        "samples": samples,
    }
