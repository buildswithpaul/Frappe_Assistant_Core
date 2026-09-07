# Frappe Assistant Core - Powered by FAC Cloud
# Copyright (C) 2026 Paul Clinton
# AGPLv3

"""Retry sweep for trigger fires lost to a transient AR failure.

``frappe.enqueue`` has no retry policy — a job that raises is simply dead and
the fire is gone, so an AR outage silently drops every trigger that fired
during it. This hourly sweep re-enqueues the ``enqueue_failed`` rows the fire
job leaves behind, capped so a permanently broken workflow cannot retry
forever.

The payload is rebuilt from the document's CURRENT state: this is a delivery
retry for an event that already happened, and the original payload is not
stored. ``changed_fields`` is therefore empty on a retry, and the trigger block
carries ``retry: <attempt>`` so the workflow can tell.
"""

import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime

from frappe_assistant_core.chat.workflows.triggers.filters import build_payload
from frappe_assistant_core.chat.workflows.triggers.log import (
    STATUS_ENQUEUE_FAILED,
    STATUS_RETRY_SCHEDULED,
)
from frappe_assistant_core.chat.workflows.triggers.remote import enqueue_remote_fire

MAX_RETRY_ATTEMPTS = 3
RETRY_WINDOW_HOURS = 24
SWEEP_BATCH_SIZE = 50


def sweep_failed_trigger_fires() -> dict:
    """Scheduled hourly job — re-enqueue recent fires that never reached AR."""
    from frappe_assistant_core.chat.gate import is_chat_enabled

    if not is_chat_enabled():
        return {"candidates": 0, "retried": 0}

    cutoff = add_to_date(now_datetime(), hours=-RETRY_WINDOW_HOURS)
    rows = frappe.get_all(
        "FAC Workflow Trigger Log",
        filters={
            "status": STATUS_ENQUEUE_FAILED,
            "retry_attempts": ["<", MAX_RETRY_ATTEMPTS],
            "fired_at": [">=", cutoff],
        },
        fields=[
            "name",
            "trigger",
            "reference_doctype",
            "reference_docname",
            "event",
            "user",
            "retry_attempts",
            "error_message",
        ],
        order_by="fired_at asc",
        limit=SWEEP_BATCH_SIZE,
    )

    retried = 0
    for row in rows:
        try:
            if _retry(row):
                retried += 1
        except Exception:
            frappe.log_error(
                title=f"FAC Workflow Trigger retry failed: {row.name}",
                message=frappe.get_traceback(),
            )

    # Scheduled job, not a request: nothing else will flush these rows, and a
    # retry that is re-enqueued but never recorded gets swept again next tick.
    frappe.db.commit()  # nosemgrep
    return {"candidates": len(rows), "retried": retried}


def _retry(row) -> bool:
    """Re-enqueue one failed fire, or abandon it with a stated reason."""
    if not frappe.db.exists("FAC Workflow Trigger", row.trigger):
        _abandon(row, _("Retry abandoned: the trigger no longer exists."))
        return False

    trigger = frappe.get_doc("FAC Workflow Trigger", row.trigger)
    if not trigger.enabled:
        _abandon(row, _("Retry abandoned: the trigger is disabled."))
        return False

    if not row.reference_doctype or not frappe.db.exists("DocType", row.reference_doctype):
        _abandon(row, _("Retry abandoned: DocType {0} no longer exists.").format(row.reference_doctype))
        return False

    if not frappe.db.exists(row.reference_doctype, row.reference_docname):
        _abandon(row, _("Retry abandoned: the document no longer exists."))
        return False

    attempt = int(row.retry_attempts or 0) + 1
    doc = frappe.get_doc(row.reference_doctype, row.reference_docname)
    payload = build_payload(trigger, doc, row.event, {})
    payload["trigger"]["retry"] = attempt

    enqueue_remote_fire(
        trigger_name=trigger.name,
        workflow_name=trigger.workflow_name,
        workflow_docname=trigger.get("workflow_docname") or "",
        payload=payload,
        user_id=row.user or trigger.created_by_user or "Administrator",
        reference_doctype=row.reference_doctype,
        reference_docname=row.reference_docname,
        event=row.event,
        attempt=attempt,
    )

    # Retiring the row from `enqueue_failed` is what stops it being swept
    # again; the retry's own outcome writes a fresh row carrying `attempt`.
    frappe.db.set_value(
        "FAC Workflow Trigger Log",
        row.name,
        {"status": STATUS_RETRY_SCHEDULED, "retry_attempts": attempt},
    )
    return True


def _abandon(row, reason: str) -> None:
    """Take a row out of the sweep permanently, saying why on the row itself."""
    message = f"{row.error_message or ''} {reason}".strip()
    frappe.db.set_value(
        "FAC Workflow Trigger Log",
        row.name,
        {"retry_attempts": MAX_RETRY_ATTEMPTS, "error_message": message[:500]},
    )
