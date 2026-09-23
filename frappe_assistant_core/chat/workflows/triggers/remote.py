# Frappe Assistant Core - Powered by FAC Cloud
# Copyright (C) 2026 Paul Clinton
# AGPLv3

"""Remote fire: enqueue a Frappe job that POSTs to AR via the SDK.

Decouples the HTTP call from the doc save so a slow/unavailable AR server
never blocks user actions on the customer bench.
"""

import inspect
from typing import Any

import frappe
from assistant_runtime_sdk import (
    ARAPIError,
    ARAuthenticationError,
    ARConfigurationError,
    ARRateLimitError,
)
from frappe.utils import now

from frappe_assistant_core.chat.workflows.triggers.log import (
    STATUS_AR_ERROR,
    STATUS_DISPATCHED,
    STATUS_ENQUEUE_FAILED,
    STATUS_QUOTA_SKIPPED,
    write_trigger_log,
)


def enqueue_remote_fire(
    trigger_name: str,
    workflow_name: str,
    payload: dict[str, Any],
    user_id: str,
    reference_doctype: str,
    reference_docname: str,
    event: str,
    workflow_docname: str = "",
    attempt: int = 0,
) -> None:
    """Queue a local Frappe job to POST the trigger fire to AR after commit.

    NOTE: kwargs to ``fire_to_ar`` are passed through ``frappe.enqueue`` as
    **kwargs. ``frappe.enqueue`` has a built-in ``event`` parameter (used for
    queue clearing) that consumes any ``event=...`` we pass — it never
    reaches the worker. So we forward the doc-event under the renamed key
    ``doc_event`` and the worker translates it back.
    """
    frappe.enqueue(
        "frappe_assistant_core.chat.workflows.triggers.remote.fire_to_ar",
        queue="default",
        job_id=f"ar-trigger:{trigger_name}:{reference_docname}:{frappe.generate_hash(length=8)}",
        enqueue_after_commit=True,
        trigger_name=trigger_name,
        workflow_name=workflow_name,
        workflow_docname=workflow_docname,
        payload=payload,
        user_id=user_id,
        reference_doctype=reference_doctype,
        reference_docname=reference_docname,
        doc_event=event,
        attempt=attempt,
    )


def fire_to_ar(
    trigger_name: str,
    workflow_name: str,
    payload: dict[str, Any],
    user_id: str,
    reference_doctype: str,
    reference_docname: str,
    doc_event: str,
    workflow_docname: str = "",
    attempt: int = 0,
) -> None:
    """Background job: call AR's execute_from_event and log the outcome.

    The doc-event name (after_insert / on_update / etc.) arrives here under
    ``doc_event`` because ``frappe.enqueue`` reserves the ``event`` kwarg for
    its own queue-clearing feature. See enqueue_remote_fire's docstring.

    A retryable failure is recorded as ``enqueue_failed`` and left for
    ``sweeper.sweep_failed_trigger_fires``; raising here would only kill the
    RQ job, because ``frappe.enqueue`` has no retry policy of its own.
    """
    # Local alias keeps the rest of this function readable.
    event = doc_event
    from frappe_assistant_core.chat.api.auth import _ar_user_id
    from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

    client = get_fac_cloud_client()
    if client is None:
        _write_log(
            trigger_name,
            STATUS_ENQUEUE_FAILED,
            reference_doctype,
            reference_docname,
            event,
            user_id,
            error_message="FACO not registered with AR (no client available)",
            attempt=attempt,
        )
        return

    try:
        response = _execute_from_event(
            client,
            workflow_name=workflow_name,
            workflow_docname=workflow_docname,
            payload=payload,
            user_id=_ar_user_id(user_id) if user_id else "Administrator",
            trigger_id=trigger_name,
        )
    except Exception as exc:
        status, message = _classify_exception(exc)
        _write_log(
            trigger_name,
            status,
            reference_doctype,
            reference_docname,
            event,
            user_id,
            error_message=message,
            attempt=attempt,
        )
        _record_trigger_error(trigger_name, message)
        return

    ar_run_id = (response or {}).get("run_name") or (response or {}).get("run_id") or ""
    _write_log(
        trigger_name,
        STATUS_DISPATCHED,
        reference_doctype,
        reference_docname,
        event,
        user_id,
        ar_run_id=ar_run_id,
        attempt=attempt,
    )
    _record_trigger_success(trigger_name)


def _execute_from_event(
    client,
    *,
    workflow_name: str,
    workflow_docname: str,
    payload: dict[str, Any],
    user_id: str,
    trigger_id: str,
) -> dict[str, Any] | None:
    """POST the fire, binding on the docname rather than the display name.

    The docname is authoritative: renaming an agent in the SPA toolbar used to
    silently orphan every trigger bound to it. The installed SDK may predate
    the argument, so when it does we post the prepared payload ourselves with
    the docname added — AR falls back to the human-name lookup when the key is
    absent, and Frappe drops kwargs an older AR does not declare.
    """
    if not workflow_docname:
        return client.execute_workflow_from_event(
            workflow_name=workflow_name,
            input_data=payload,
            user_id=user_id,
            trigger_id=trigger_id,
        )

    if _sdk_forwards_docname(client):
        return client.execute_workflow_from_event(
            workflow_name=workflow_name,
            workflow_docname=workflow_docname,
            input_data=payload,
            user_id=user_id,
            trigger_id=trigger_id,
        )

    endpoint, body = client._prepare_execute_workflow_from_event(workflow_name, payload, user_id, trigger_id)
    body["workflow_docname"] = workflow_docname
    return client._request_post_json(endpoint, body, api_base=client.workflows_api_base)


def _sdk_forwards_docname(client) -> bool:
    try:
        params = inspect.signature(client.execute_workflow_from_event).parameters
    except (TypeError, ValueError):
        return False
    return "workflow_docname" in params


def _classify_exception(exc: Exception) -> tuple[str, str]:
    """Map an SDK exception to a log status.

    Classifies on the HTTP status code and the exception type, never on
    ``str(exc)``: substring matching put a 403 plan gate and a 401 auth failure
    in the retryable bucket, where no number of retries could ever clear them.
    """
    message = str(exc)[:500]

    if isinstance(exc, ARRateLimitError):
        return STATUS_QUOTA_SKIPPED, message
    if isinstance(exc, ARAuthenticationError | ARConfigurationError):
        return STATUS_AR_ERROR, message

    status_code = getattr(exc, "status_code", None) if isinstance(exc, ARAPIError) else None
    if status_code is not None:
        if status_code in (402, 429):
            return STATUS_QUOTA_SKIPPED, message
        if 400 <= status_code < 500:
            # Entitlement or configuration (401/403/404/422). Retrying cannot fix it.
            return STATUS_AR_ERROR, message

    # 5xx, timeouts, connection errors, and anything unrecognised: retryable.
    return STATUS_ENQUEUE_FAILED, message


def _write_log(
    trigger_name: str,
    status: str,
    reference_doctype: str,
    reference_docname: str,
    event: str,
    user_id: str,
    ar_run_id: str | None = None,
    error_message: str | None = None,
    attempt: int = 0,
) -> None:
    write_trigger_log(
        trigger_name,
        status,
        reference_doctype=reference_doctype,
        reference_docname=reference_docname,
        event=event,
        user=user_id,
        ar_run_id=ar_run_id,
        error_message=error_message,
        retry_attempts=attempt,
        commit=True,
    )


def _record_trigger_success(trigger_name: str) -> None:
    try:
        existing = frappe.db.get_value("FAC Workflow Trigger", trigger_name, "fire_count")
        frappe.db.set_value(
            "FAC Workflow Trigger",
            trigger_name,
            {
                "last_fired_at": now(),
                "fire_count": (existing or 0) + 1,
            },
        )
        frappe.db.commit()
    except Exception:
        pass


def _record_trigger_error(trigger_name: str, message: str) -> None:
    try:
        frappe.db.set_value(
            "FAC Workflow Trigger",
            trigger_name,
            {
                "last_error_at": now(),
                "last_error": (message or "")[:500],
            },
        )
        frappe.db.commit()
    except Exception:
        pass
