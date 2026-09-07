# Frappe Assistant Core - Debug Bundle Export API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""System-Manager-only debug bundle export for zero-retention sessions.

AR keeps no server-side copy of a session, so support needs a way to capture a
session's FAC-side messages, its current signed blob, and component versions
into a single downloadable zip. This is an explicit ADMIN cross-user read path:
the role gate is the FIRST thing the endpoint does, and the generated File is
always private so the conversation content is never world-readable.
"""

from __future__ import annotations

import io
import json
import zipfile

import frappe
from frappe import _

# Real FAC Chat Message fields (verified against the DocType JSON). Ordered by
# the ``idx`` sequencing field. No content is logged anywhere — only the zip
# carries it, and only a System Manager can fetch it.
_MESSAGE_FIELDS = [
    "message_id",
    "role",
    "content",
    "timestamp",
    "model",
    "credits_used",
    "tool_calls",
    "blocks",
    "idx",
    "aborted",
    "is_archived",
]


@frappe.whitelist(methods=["POST"])
def export_debug_bundle(session_id: str) -> dict:
    """Zip a session's FAC messages + current blob + component versions.

    Strictly System-Manager-gated. Returns the URL of a private File holding
    the zip (messages.json, session_state.json, versions.json).
    """
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Manager can export debug bundles"), frappe.PermissionError)

    if not session_id:
        frappe.throw(_("session_id is required"))

    messages = frappe.get_all(
        "FAC Chat Message",
        filters={"session_id": session_id},
        fields=_MESSAGE_FIELDS,
        order_by="idx asc",
    )

    state = frappe.db.get_value(
        "FAC Chat Session State",
        {"session_id": session_id},
        ["state_blob", "state_sig", "format_version", "turn_seq", "updated_at"],
        as_dict=True,
    )

    versions = {
        "frappe": frappe.__version__,
        "frappe_assistant_core": _get_app_version(),
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("messages.json", json.dumps(messages, indent=2, default=str))
        z.writestr("session_state.json", json.dumps(state or {}, indent=2, default=str))
        z.writestr("versions.json", json.dumps(versions, indent=2, default=str))
    content = buf.getvalue()

    fname = f"debug-bundle-{session_id}.zip"
    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": fname,
            "is_private": 1,
            "content": content,
        }
    ).insert(ignore_permissions=True)

    return {"file_url": file_doc.file_url}


def _get_app_version() -> str | None:
    """Best-effort app version. Never crashes the export if unavailable."""
    try:
        from frappe_assistant_core import __version__

        return __version__
    except Exception:
        return None
