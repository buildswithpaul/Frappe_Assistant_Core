# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
MCP tasks (spec §7.4): a tools/call whose work is queued answers with a task the client polls.

A tool that has queued work, and sees ``tasks_requested()``, returns its normal dict plus a
``TASK_MARKER`` naming the reference document. ``finish_call`` turns that into a FAC MCP Task row
once the tool has returned for good (after any deadlock retry). An adapter, registered per tool,
reads the reference document on each ``tasks/get`` and rebuilds the result the synchronous path
would have returned; no result is ever stored.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timezone
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, get_system_timezone, now_datetime
from zoneinfo import ZoneInfo

from frappe_assistant_core.mcp.protocol import ERR_INVALID_PARAMS, ProtocolError
from frappe_assistant_core.mcp.tool_result import finish_unwrapped, unwrap_tool_result

TASK_TTL_MS = 86_400_000
POLL_INTERVAL_MS = 5000
TASK_MARKER = "_fac_task"

DOCTYPE = "FAC MCP Task"
TERMINAL = ("completed", "failed", "cancelled")
# A JSON-RPC internal error: the task's work failed, not the tasks/get request.
ERR_TASK_FAILED = -32603


@dataclass
class Progress:
    """What an adapter reads from the reference document."""

    status: str
    status_message: str | None = None
    raw_result: Any = None
    error: dict | None = None


_ADAPTERS: dict[str, Callable[[str, str, dict], Progress]] = {}


def register_adapter(tool_name: str, poll: Callable[[str, str, dict], Progress]) -> None:
    """``poll(reference_doctype, reference_name, arguments)`` answers the task's progress.

    For a completed task, ``raw_result`` is the tool's inner result dict, as ``execute`` returns
    it, not the ``_safe_execute`` envelope. ``{"success": False, ...}`` in it marks an error
    result, as on the synchronous path; ``own_message`` is not available here, so an error's
    text is fenced like any other untrusted field.
    """
    _ADAPTERS[tool_name] = poll


def tasks_requested() -> bool:
    """True when this request is modern era and the client declared the tasks extension."""
    caps = getattr(frappe.local, "mcp_client_caps", None)
    return getattr(frappe.local, "mcp_era", None) == "modern" and bool(caps and caps.tasks)


def finish_call(tool_name: str, tool: dict, arguments: dict, raw: Any) -> dict:
    """Finish a tools/call return value: a task when the tool queued work and the client takes
    tasks, otherwise the normal result. The marker never reaches the client."""
    result, is_error, own_message = unwrap_tool_result(tool, raw)
    marker = result.pop(TASK_MARKER, None) if isinstance(result, dict) else None
    if marker is not None and not is_error and tasks_requested():
        if _valid_marker(marker):
            return create(tool_name, arguments, marker)
        # The work is already queued: answer with the tool's own result, never an error.
        frappe.log_error(
            title=f"FAC MCP task: {tool_name} returned an invalid task marker", message=repr(marker)
        )
    return finish_unwrapped(tool, result, is_error, own_message)


def _valid_marker(marker: Any) -> bool:
    if not isinstance(marker, dict):
        return False
    doctype, name = marker.get("reference_doctype"), marker.get("reference_name")
    return (
        isinstance(doctype, str)
        and bool(doctype)
        and isinstance(name, str)
        and bool(name)
        and bool(frappe.db.exists("DocType", doctype))
    )


def create(tool_name: str, arguments: dict, marker: dict) -> dict:
    """Insert the task row and return the ``resultType: "task"`` result."""
    doc = frappe.get_doc(
        {
            "doctype": DOCTYPE,
            "owner_user": frappe.session.user,
            "tool": tool_name,
            "status": "working",
            "status_message": marker.get("status_message"),
            "reference_doctype": marker.get("reference_doctype"),
            "reference_name": marker.get("reference_name"),
            "arguments": json.dumps(arguments or {}, default=str),
            "expires_at": add_to_date(now_datetime(), seconds=TASK_TTL_MS // 1000),
        }
    ).insert(ignore_permissions=True)
    return {"resultType": "task", **_wire(doc)}


def get(params: dict, tool_registry: dict) -> dict:
    """tasks/get: the task's state, with the finished result once it has completed."""
    doc = _load(params)
    if doc.status in ("failed", "cancelled"):
        return _answer(doc)
    tool = tool_registry.get(doc.tool)
    if tool is None:
        # Not saved: the user may be given the tool back.
        return _answer(doc, failed=_error(_("This tool is no longer available to you.")))
    progress = _poll(doc)
    if doc.status == "working":
        _apply(doc, progress)
    elif progress.status != "completed":
        # A completed task stays completed; only this answer lacks the result.
        unavailable = _error(_("The result of this task is no longer available."))
        return _answer(doc, failed=progress.error or unavailable)
    return _answer(doc, tool, progress)


def _answer(
    doc, tool: dict | None = None, progress: Progress | None = None, failed: dict | None = None
) -> dict:
    """The tasks/get result for the row, or ``failed`` for this answer only."""
    out = {"resultType": "complete", **_wire(doc)}
    if failed is not None:
        out.update(status="failed", error=failed)
    elif doc.status == "completed":
        raw = progress.raw_result
        is_error = isinstance(raw, dict) and raw.get("success") is False
        out["result"] = finish_unwrapped(tool, raw, is_error)
    elif doc.status == "failed":
        out["error"] = _json_field(doc.error) or _error(_("The task failed."))
    return out


def cancel(params: dict) -> dict:
    """tasks/cancel: mark the task cancelled. The queued job itself keeps running."""
    doc = _load(params)
    if doc.status not in TERMINAL:
        doc.status = "cancelled"
        doc.save(ignore_permissions=True)
    return {}


# tasks/update is not served (no tool needs input mid-task), so it answers method-not-found.
METHODS = ("tasks/get", "tasks/cancel")


def handle(method: str, params: dict, tool_registry: dict) -> dict:
    """Route a modern-era tasks/* method; see ``METHODS``."""
    if method == "tasks/get":
        return get(params, tool_registry)
    return cancel(params)


def delete_expired() -> None:
    """Daily: delete task rows past their TTL."""
    frappe.db.delete(DOCTYPE, {"expires_at": ("<", now_datetime())})
    frappe.db.commit()  # nosemgrep: frappe-manual-commit — a scheduler job: nothing else commits


def _load(params: dict):
    """The caller's own, unexpired task, or -32602 exactly as for an unknown id."""
    task_id = params.get("taskId") if isinstance(params, dict) else None
    doc = (
        frappe.get_doc(DOCTYPE, task_id)
        if isinstance(task_id, str) and frappe.db.exists(DOCTYPE, task_id)
        else None
    )
    if doc is None or doc.owner_user != frappe.session.user or get_datetime(doc.expires_at) <= now_datetime():
        raise ProtocolError(400, ERR_INVALID_PARAMS, _("Task not found"), {"taskId": task_id})
    return doc


def _poll(doc) -> Progress:
    """Ask the tool's adapter; a reference gone or an adapter crash ends the task as failed."""
    adapter = _adapter(doc.tool)
    if adapter is None:
        return Progress("failed", error=_error(_("This task can no longer be checked.")))
    try:
        return adapter(doc.reference_doctype, doc.reference_name, _json_field(doc.arguments) or {})
    except frappe.DoesNotExistError:
        frappe.clear_messages()
        message = _("The {0} this task was following no longer exists.").format(_(doc.reference_doctype))
        return Progress("failed", error=_error(message))
    except Exception:
        frappe.log_error(title=f"FAC MCP task {doc.name}: checking {doc.tool} failed")
        return Progress("failed", error=_error(_("Checking this task failed. The error has been logged.")))


def _adapter(tool_name: str) -> Callable[[str, str, dict], Progress] | None:
    """The tool's adapter, registering the built-in ones first if this worker has not yet."""
    if tool_name not in _ADAPTERS:
        from frappe_assistant_core.mcp import task_adapters

        task_adapters.register()
    return _ADAPTERS.get(tool_name)


def _apply(doc, progress: Progress) -> None:
    """Save what the adapter reported; an unchanged row keeps its lastUpdatedAt."""
    status = progress.status if progress.status in ("working",) + TERMINAL else "failed"
    error = (progress.error or _error(_("The task failed."))) if status == "failed" else None
    message = progress.status_message if progress.status_message is not None else doc.status_message
    if (doc.status, doc.status_message, _json_field(doc.error)) == (status, message, error):
        return
    doc.update({"status": status, "status_message": message, "error": json.dumps(error) if error else None})
    doc.save(ignore_permissions=True)


def _json_field(value) -> Any:
    """A JSON field's value, whether Frappe handed back the stored text or the parsed value."""
    return json.loads(value) if isinstance(value, str) and value else value or None


def _error(message: str) -> dict:
    return {"code": ERR_TASK_FAILED, "message": message}


def _wire(doc) -> dict:
    out = {
        "taskId": doc.name,
        "status": doc.status,
        "createdAt": _utc_iso(doc.creation),
        "lastUpdatedAt": _utc_iso(doc.modified),
        "ttlMs": TASK_TTL_MS,
        "pollIntervalMs": POLL_INTERVAL_MS,
    }
    if doc.status_message:
        out["statusMessage"] = doc.status_message
    return out


def _utc_iso(value) -> str:
    """A Frappe datetime (naive, system timezone) as UTC ISO 8601 with "Z"."""
    local = get_datetime(value).replace(tzinfo=ZoneInfo(get_system_timezone()))
    return local.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
