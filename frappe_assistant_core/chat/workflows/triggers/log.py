# Frappe Assistant Core - Powered by FAC Cloud
# Copyright (C) 2026 Paul Clinton
# AGPLv3

"""Single writer for FAC Workflow Trigger Log rows.

Two callers with opposite transaction needs share it. The background fire job
(``remote.fire_to_ar``) owns its transaction and must commit; the dispatcher
runs inside the customer's own doc-save transaction and must not — a commit
there would flush their half-saved document.
"""

import frappe
from frappe.utils import now

STATUS_DISPATCHED = "dispatched"
STATUS_FILTERED_OUT = "filtered_out"
STATUS_QUOTA_SKIPPED = "quota_skipped"
STATUS_AR_ERROR = "ar_error"
STATUS_ENQUEUE_FAILED = "enqueue_failed"
STATUS_LOOP_BLOCKED = "loop_blocked"
STATUS_RETRY_SCHEDULED = "retry_scheduled"

ERROR_MESSAGE_LIMIT = 500


def write_trigger_log(
    trigger_name: str,
    status: str,
    *,
    reference_doctype: str,
    reference_docname: str,
    event: str,
    user: str | None = None,
    ar_run_id: str | None = None,
    error_message: str | None = None,
    retry_attempts: int = 0,
    commit: bool = False,
) -> str | None:
    """Insert one log row, returning its name. Never raises."""
    try:
        log = frappe.get_doc(
            {
                "doctype": "FAC Workflow Trigger Log",
                "trigger": trigger_name,
                "status": status,
                "fired_at": now(),
                "reference_doctype": reference_doctype,
                "reference_docname": reference_docname,
                "event": event,
                "user": user if user and frappe.db.exists("User", user) else None,
                "fac_cloud_run_id": ar_run_id or "",
                "error_message": (error_message or "")[:ERROR_MESSAGE_LIMIT],
                "retry_attempts": int(retry_attempts or 0),
            }
        )
        log.insert(ignore_permissions=True)
        if commit:
            frappe.db.commit()
        return log.name
    except Exception:
        frappe.log_error(
            title=f"FAC Workflow Trigger Log write failed: {trigger_name}",
            message=frappe.get_traceback(),
        )
        return None
