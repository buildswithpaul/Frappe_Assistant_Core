# Frappe Assistant Core - Powered by FAC Cloud
# Copyright (C) 2026 Paul Clinton
# AGPLv3

"""API endpoints for the FAC Workflow Trigger DocType (CRUD + helpers).

All endpoints require System Manager role (authoring triggers is an admin
action — equivalent power to Server Script).
"""

import json
from typing import Any

import frappe
from frappe import _

from frappe_assistant_core.chat.doctype.fac_workflow_trigger.fac_workflow_trigger import (
    DOCTYPE_BLOCKLIST,
    VALID_EVENTS,
)


def _require_admin() -> None:
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Managers can manage workflow triggers."), frappe.PermissionError)


@frappe.whitelist(methods=["GET"])
def list_triggers(
    workflow_name: str | None = None,
    workflow_docname: str | None = None,
) -> dict[str, Any]:
    """List triggers, optionally filtered to one workflow.

    ``workflow_docname`` (the AR Workflow WF-##### id) is the authoritative
    binding — it is what the write and dispatch paths use, and it survives a
    rename. ``workflow_name`` is the legacy display-name column, matched only
    for rows saved before the docname binding existed. Filtering on the display
    name alone made a renamed workflow show zero triggers while its triggers
    kept firing, so the user recreated them as duplicates.
    """
    _require_admin()

    filters: dict[str, Any] = {}
    or_filters: dict[str, Any] = {}
    if workflow_docname and workflow_name:
        or_filters = {"workflow_docname": workflow_docname, "workflow_name": workflow_name}
    elif workflow_docname:
        filters["workflow_docname"] = workflow_docname
    elif workflow_name:
        filters["workflow_name"] = workflow_name

    rows = frappe.get_all(
        "FAC Workflow Trigger",
        filters=filters,
        or_filters=or_filters,
        fields=[
            "name",
            "title",
            "enabled",
            "workflow_name",
            "workflow_docname",
            "workflow_display_name",
            "reference_doctype",
            "doctype_event",
            "changed_fields",
            "last_fired_at",
            "fire_count",
            "last_error_at",
            "last_error",
            "modified",
        ],
        order_by="modified desc",
    )
    if or_filters:
        rows = [r for r in rows if _binds_to_workflow(r, workflow_name, workflow_docname)]
    return {"triggers": rows, "total": len(rows)}


def _binds_to_workflow(row: dict, workflow_name: str, workflow_docname: str) -> bool:
    """Narrow the OR query back to a single workflow.

    The OR is only there so legacy rows (no docname yet) stay visible; a row
    that *has* a docname is judged by it alone, otherwise a stale cached
    display name would pull in a different workflow's triggers.
    """
    bound = row.get("workflow_docname")
    if bound:
        return bound == workflow_docname
    return row.get("workflow_name") == workflow_name


@frappe.whitelist(methods=["POST"])
def create_trigger(
    title: str,
    workflow_name: str,
    reference_doctype: str,
    doctype_event: str,
    filters: str | None = None,
    changed_fields: str | None = None,
    enabled: int = 1,
    workflow_display_name: str | None = None,
    workflow_docname: str | None = None,
) -> dict[str, Any]:
    """Create a FAC Workflow Trigger."""
    _require_admin()

    if doctype_event not in VALID_EVENTS:
        frappe.throw(_("Invalid doctype_event: {0}").format(doctype_event))

    doc = frappe.new_doc("FAC Workflow Trigger")
    doc.title = title
    doc.workflow_name = workflow_name
    doc.workflow_docname = workflow_docname or _resolve_workflow_docname(workflow_name)
    doc.workflow_display_name = workflow_display_name or workflow_name
    doc.reference_doctype = reference_doctype
    doc.doctype_event = doctype_event
    doc.changed_fields = changed_fields or ""
    doc.enabled = 1 if int(enabled) else 0

    _apply_filter_rows(doc, filters)
    doc.insert()

    return {
        "name": doc.name,
        "title": doc.title,
        "enabled": doc.enabled,
        "workflow_docname": doc.workflow_docname,
    }


@frappe.whitelist(methods=["POST"])
def update_trigger(
    name: str,
    title: str | None = None,
    workflow_name: str | None = None,
    workflow_display_name: str | None = None,
    reference_doctype: str | None = None,
    doctype_event: str | None = None,
    filters: str | None = None,
    changed_fields: str | None = None,
    enabled: int | None = None,
    workflow_docname: str | None = None,
) -> dict[str, Any]:
    _require_admin()

    doc = frappe.get_doc("FAC Workflow Trigger", name)

    if title is not None:
        doc.title = title
    if workflow_docname is not None:
        doc.workflow_docname = workflow_docname
    if workflow_name is not None:
        doc.workflow_name = workflow_name
        if workflow_docname is None:
            # The caller re-pointed the trigger by display name; re-resolve so the
            # authoritative binding does not keep pointing at the old workflow.
            doc.workflow_docname = _resolve_workflow_docname(workflow_name) or doc.workflow_docname
    if workflow_display_name is not None:
        doc.workflow_display_name = workflow_display_name
    if reference_doctype is not None:
        doc.reference_doctype = reference_doctype
    if doctype_event is not None:
        doc.doctype_event = doctype_event
    if changed_fields is not None:
        doc.changed_fields = changed_fields
    if enabled is not None:
        doc.enabled = 1 if int(enabled) else 0
    if filters is not None:
        _apply_filter_rows(doc, filters)

    doc.save()
    return {"name": doc.name, "enabled": doc.enabled, "workflow_docname": doc.workflow_docname}


@frappe.whitelist(methods=["POST"])
def delete_trigger(name: str) -> dict[str, Any]:
    """Delete a trigger and the fire log that belongs to it.

    The log rows link back to the trigger, so Frappe's link check refused the
    delete outright — "You can disable this instead" — and the only trigger a
    user could remove was one that had never fired. The log is a record of that
    trigger's own firings and has no meaning without it, so it goes too.
    """
    _require_admin()

    logs = frappe.get_all("FAC Workflow Trigger Log", filters={"trigger": name}, pluck="name")
    for log in logs:
        frappe.delete_doc("FAC Workflow Trigger Log", log, ignore_permissions=True)

    frappe.delete_doc("FAC Workflow Trigger", name)

    from frappe_assistant_core.chat.workflows.triggers.map import invalidate

    invalidate()
    return {"name": name, "deleted": True, "logs_deleted": len(logs)}


@frappe.whitelist(methods=["POST"])
def toggle_trigger(name: str, enabled: int) -> dict[str, Any]:
    _require_admin()
    frappe.db.set_value("FAC Workflow Trigger", name, "enabled", 1 if int(enabled) else 0)
    # Ensure the cached map picks up the change immediately
    from frappe_assistant_core.chat.workflows.triggers.map import invalidate

    invalidate()
    return {"name": name, "enabled": 1 if int(enabled) else 0}


@frappe.whitelist(methods=["GET"])
def get_doctype_fields(doctype: str) -> dict[str, Any]:
    """Return filterable fields for a DocType (used by the filter-row editor).

    Lookup-style endpoint — returns an empty list for any DocType that is not
    a valid trigger target (blocklisted, AR/FACO namespace, unknown, child
    table, Single) rather than throwing. The authoritative rejection of
    invalid targets happens in the trigger controller's `validate()` at save
    time. Throwing here would flood the browser console during typing.
    """
    _require_admin()

    doctype = (doctype or "").strip()
    if not doctype:
        return {"doctype": doctype, "fields": []}

    if doctype in DOCTYPE_BLOCKLIST:
        return {"doctype": doctype, "fields": []}
    if not frappe.db.exists("DocType", doctype):
        return {"doctype": doctype, "fields": []}

    meta = frappe.get_meta(doctype)
    if meta.istable or meta.issingle:
        return {"doctype": doctype, "fields": []}

    fields: list[dict[str, Any]] = []
    for f in meta.fields:
        if f.fieldtype in ("Section Break", "Column Break", "Tab Break", "HTML", "Table", "Button"):
            continue
        if f.fieldtype == "Password":
            continue
        fields.append(
            {
                "fieldname": f.fieldname,
                "label": f.label or f.fieldname,
                "fieldtype": f.fieldtype,
                "options": f.options or "",
            }
        )

    # Add standard metadata fields useful for filtering
    fields.append({"fieldname": "docstatus", "label": "Doc Status", "fieldtype": "Int", "options": ""})
    fields.append({"fieldname": "owner", "label": "Owner", "fieldtype": "Link", "options": "User"})

    return {"doctype": doctype, "fields": fields}


@frappe.whitelist(methods=["GET"])
def list_filterable_doctypes(search: str | None = None, limit: int = 50) -> dict[str, Any]:
    """Return non-system, non-table, non-single DocTypes a user can target.

    Server-side search + limit so the UI doesn't need to ship thousands of
    DocType names upfront. The user's DocType read permissions are enforced
    (intentional — don't surface what they can't access).

    Includes:
      - Standard DocTypes shipped by Frappe / ERPNext (custom=0)
      - DocTypes shipped by any custom installed app (custom=0, different module)
      - Desk-created "Custom DocTypes" (custom=1, stored only in DB)

    Args:
            search: Optional substring; matches `name` case-insensitively.
            limit: Max rows to return. Capped server-side at 200 to keep payload bounded.
    """
    _require_admin()

    try:
        limit = max(1, min(int(limit), 200))
    except (ValueError, TypeError):
        limit = 50

    filters: dict[str, Any] = {"istable": 0, "issingle": 0}
    if search and search.strip():
        filters["name"] = ["like", f"%{search.strip()}%"]

    # Fetch `limit + 1` so we can detect "has more" without a separate count
    # query. Over-fetch to absorb post-filter drops (blocklist / namespace).
    fetch_cap = limit + 50
    rows = frappe.get_all(
        "DocType",
        filters=filters,
        fields=["name", "module", "app", "custom"],
        order_by="name asc",
        limit_page_length=fetch_cap,
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        if row.name in DOCTYPE_BLOCKLIST:
            continue
        out.append(
            {
                "name": row.name,
                "module": row.module,
                "app": row.get("app") or "",
                "custom": bool(row.get("custom")),
            }
        )
        if len(out) >= limit:
            break

    # `has_more` is true ONLY if:
    #   - we returned the full `limit`, AND
    #   - the raw query hit the fetch cap (meaning more rows existed to paginate)
    # This avoids the buggy "and N more" hint when all overflow rows were
    # blocklisted out (returned=0, raw_count=2 shouldn't say "2 more").
    has_more = len(out) >= limit and len(rows) >= fetch_cap
    return {
        "doctypes": out,
        "returned": len(out),
        "has_more": has_more,
    }


@frappe.whitelist(methods=["GET"])
def get_trigger_log(trigger_name: str, limit: int = 20) -> dict[str, Any]:
    _require_admin()

    try:
        limit = max(1, min(int(limit), 200))
    except (ValueError, TypeError):
        limit = 20

    rows = frappe.get_all(
        "FAC Workflow Trigger Log",
        filters={"trigger": trigger_name},
        fields=[
            "name",
            "status",
            "fired_at",
            "reference_doctype",
            "reference_docname",
            "event",
            "fac_cloud_run_id",
            "error_message",
            "user",
        ],
        order_by="fired_at desc",
        limit=limit,
    )
    return {"logs": rows, "total": len(rows)}


@frappe.whitelist(methods=["POST"])
def test_trigger(trigger_name: str) -> dict[str, Any]:
    """Build a preview payload using the most recent matching doc. No send."""
    _require_admin()

    trigger = frappe.get_doc("FAC Workflow Trigger", trigger_name)

    if not frappe.db.exists("DocType", trigger.reference_doctype):
        frappe.throw(
            _("DocType '{0}' no longer exists on this site.").format(trigger.reference_doctype),
            frappe.DoesNotExistError,
        )

    latest = frappe.get_all(
        trigger.reference_doctype,
        fields=["name"],
        order_by="modified desc",
        limit=1,
    )
    if not latest:
        return {
            "payload": None,
            "message": _("No documents of type {0} found.").format(trigger.reference_doctype),
        }

    doc = frappe.get_doc(trigger.reference_doctype, latest[0].name)

    from frappe_assistant_core.chat.workflows.triggers.filters import (
        build_payload,
        evaluate_filters,
    )

    doc_dict = doc.as_dict()
    passes = evaluate_filters(doc_dict, trigger.filters or [])
    payload = build_payload(trigger, doc, trigger.doctype_event, {})

    return {
        "payload": payload,
        "would_fire": bool(passes),
        "sample_doc": latest[0].name,
    }


def _resolve_workflow_docname(workflow_name: str | None) -> str:
    """Resolve whatever the SPA sent to the AR docname that survives a rename.

    The builder toolbar sends the workflow's mutable display name. AR then
    resolves it by ``{workflow_name, tenant, status: "Active"}``, so renaming
    an agent silently orphaned every trigger bound to it. Storing the docname
    breaks that coupling.

    Best-effort: an unreachable FAC Cloud leaves the field empty and the
    dispatcher falls back to the legacy human-name lookup.
    """
    if not workflow_name:
        return ""

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return ""

        # The caller may have sent either identifier; try the human name first
        # because that is what the builder sends today.
        for lookup in ({"workflow_name": workflow_name}, {"name": workflow_name}):
            try:
                result = client.get_workflow(**lookup) or {}
            except Exception:
                continue
            if result.get("name"):
                return result["name"]
    except Exception:
        frappe.log_error(
            title="FAC Workflow Trigger docname resolution failed",
            message=frappe.get_traceback(),
        )

    return ""


def _apply_filter_rows(doc, filters_json: str | None) -> None:
    """Replace child table rows from a JSON string."""
    doc.set("filters", [])
    if not filters_json:
        return
    try:
        rows = json.loads(filters_json) if isinstance(filters_json, str) else filters_json
    except (ValueError, TypeError):
        frappe.throw(_("filters must be a JSON array of {fieldname, operator, value} objects."))
    if not isinstance(rows, list):
        frappe.throw(_("filters must be a JSON array."))
    for row in rows:
        if not isinstance(row, dict):
            continue
        doc.append(
            "filters",
            {
                "fieldname": row.get("fieldname", ""),
                "operator": row.get("operator", "="),
                "value": row.get("value", ""),
            },
        )
