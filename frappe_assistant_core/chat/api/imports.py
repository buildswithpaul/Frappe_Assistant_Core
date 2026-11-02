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
