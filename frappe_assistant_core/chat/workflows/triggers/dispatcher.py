# Frappe Assistant Core - Powered by FAC Cloud
# Copyright (C) 2026 Paul Clinton
# AGPLv3

"""Doc-event dispatcher.

Wired into Frappe via `doc_events = {"*": {"<event>": "...dispatcher.dispatch"}}`
in hooks.py. Hot path: runs for every doc save on the site, so must early-return
fast when no trigger matches the (doctype, event) pair.

Pattern mirrors Frappe's Server Script
(frappe/core/doctype/server_script/server_script_utils.py:run_server_script_for_doc_event).
"""

import frappe
from frappe import _

# Single source of truth — imported from the controller so the UI picker,
# controller validate(), and this dispatcher stay consistent.
from frappe_assistant_core.chat.doctype.fac_workflow_trigger.fac_workflow_trigger import (
    DOCTYPE_BLOCKLIST,
)
from frappe_assistant_core.chat.gate import is_chat_enabled
from frappe_assistant_core.chat.workflows.triggers.breaker import (
    check_dispatch,
    claim_once,
)
from frappe_assistant_core.chat.workflows.triggers.filters import (
    build_payload,
    first_failing_filter,
    get_changed_fields,
    parse_changed_fields_config,
)
from frappe_assistant_core.chat.workflows.triggers.log import (
    STATUS_FILTERED_OUT,
    STATUS_LOOP_BLOCKED,
    write_trigger_log,
)
from frappe_assistant_core.chat.workflows.triggers.map import (
    get_workflow_trigger_map,
)

EVENT_METHODS = frozenset(
    {
        "after_insert",
        "on_update",
        "on_submit",
        "on_cancel",
        "on_trash",
    }
)

#: A `filtered_out` row is only useful as a diagnosis aid, and the filter gate
#: runs on every save of a watched DocType — so at most one row per trigger and
#: DocType per this many seconds.
FILTERED_OUT_SAMPLE_SECONDS = 300


def dispatch(doc, method):
    """Entry point for all registered doc_events.

    Must never raise — doc saves on the customer bench cannot be blocked by
    workflow trigger failures.
    """
    try:
        _dispatch_inner(doc, method)
    except Exception:
        frappe.log_error(
            title="FAC Workflow Trigger dispatch failed",
            message=frappe.get_traceback(),
        )


def _dispatch_inner(doc, method):
    # Skip during bulk/schema operations FIRST — before any DB read. Frappe
    # saves DocTypes during migrate/install, which fires this wildcard event
    # while the schema (incl. the gate's own `enable_fac_chat` field) may not
    # exist yet. Reading the gate here would raise mid-migration. Bail early.
    flags = getattr(frappe, "flags", None)
    if flags and (
        getattr(flags, "in_import", False)
        or getattr(flags, "in_migrate", False)
        or getattr(flags, "in_patch", False)
        or getattr(flags, "in_install", False)
    ):
        return

    # Master gate: FAC Chat off → workflow triggers don't fire. Cheap (per-
    # request `frappe.local` cache), and the dominant hot-path case on
    # MCP-only sites is "chat is off forever," so this avoids loading the
    # trigger map at all.
    if not is_chat_enabled():
        return

    if method not in EVENT_METHODS:
        return
    if not doc or not getattr(doc, "doctype", None):
        return

    doctype = doc.doctype
    if doctype in DOCTYPE_BLOCKLIST:
        return

    trigger_map = get_workflow_trigger_map()
    matches = trigger_map.get(doctype, {}).get(method, [])
    if not matches:
        return

    for trigger_id in matches:
        try:
            _process_trigger(trigger_id, doc, method)
        except Exception:
            frappe.log_error(
                title=f"FAC Workflow Trigger process failed: {trigger_id}",
                message=frappe.get_traceback(),
            )


def _process_trigger(trigger_id: str, doc, method: str) -> None:
    trigger = frappe.get_cached_doc("FAC Workflow Trigger", trigger_id)
    if not trigger.enabled:
        return

    # changed_fields gate (on_update only)
    changed = {}
    if method == "on_update":
        watch_list = parse_changed_fields_config(trigger.changed_fields)
        if watch_list:
            changed = get_changed_fields(doc, watch_list)
            if not changed:
                return  # no watched field changed — skip silently

    # Filter gate
    doc_dict = doc.as_dict()
    failing = first_failing_filter(doc_dict, trigger.filters or [])
    if failing is not None:
        _log_filtered_out(trigger, doc, method, failing)
        return

    # Loop gate. Runs after the filter gate so a save that was never going to
    # fire does not consume the budget of one that would.
    decision = check_dispatch(trigger.name, doc.doctype, doc.name)
    if not decision.allowed:
        if decision.reason:
            _log_row(trigger, doc, method, STATUS_LOOP_BLOCKED, decision.reason)
        return

    # Build structured payload
    payload = build_payload(trigger, doc, method, changed)

    # Enqueue remote dispatch after the DB transaction commits — so we don't
    # fire for rolled-back saves.
    from frappe_assistant_core.chat.workflows.triggers.remote import (
        enqueue_remote_fire,
    )

    enqueue_remote_fire(
        trigger_name=trigger.name,
        workflow_name=trigger.workflow_name,
        workflow_docname=trigger.get("workflow_docname") or "",
        payload=payload,
        user_id=frappe.session.user,
        reference_doctype=doc.doctype,
        reference_docname=doc.name,
        event=method,
    )


def _log_filtered_out(trigger, doc, method: str, row) -> None:
    """Name the filter that stopped this fire — sampled, and only once."""
    if not claim_once(f"fac_trigger_filtered:{trigger.name}:{doc.doctype}", FILTERED_OUT_SAMPLE_SECONDS):
        return

    _log_row(
        trigger,
        doc,
        method,
        STATUS_FILTERED_OUT,
        _("Filter did not match: {0} {1} {2}").format(
            row.fieldname, row.operator, str(row.value or "")[:100]
        ),
    )


def _log_row(trigger, doc, method: str, status: str, message: str) -> None:
    """Write a log row inside the caller's doc-save transaction (never commits)."""
    write_trigger_log(
        trigger.name,
        status,
        reference_doctype=doc.doctype,
        reference_docname=doc.name,
        event=method,
        user=frappe.session.user,
        error_message=message,
    )
