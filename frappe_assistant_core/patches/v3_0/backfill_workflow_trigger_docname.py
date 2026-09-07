# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Backfill FAC Workflow Trigger.workflow_docname from FAC Cloud.

Existing triggers store only the workflow's MUTABLE display name, which AR
resolves by {workflow_name, tenant, status: "Active"} — so renaming an agent in
the builder silently killed every trigger bound to it. This resolves each row's
display name to the AR docname once, and the dispatcher prefers that from then
on.

Best-effort by design: a site that is not registered, or whose FAC Cloud is
unreachable during migrate, keeps the empty field and keeps using the legacy
human-name lookup. Re-running the patch fills in what it missed.
"""

import frappe


def execute():
    frappe.reload_doc("chat", "doctype", "fac_workflow_trigger")
    frappe.reload_doc("chat", "doctype", "fac_workflow_trigger_log")

    if not frappe.db.table_exists("FAC Workflow Trigger"):
        return

    rows = frappe.get_all(
        "FAC Workflow Trigger",
        fields=["name", "workflow_name", "workflow_docname"],
    )
    pending = [row for row in rows if not row.workflow_docname]
    if not pending:
        return

    from frappe_assistant_core.chat.api.workflow_triggers import _resolve_workflow_docname

    for row in pending:
        docname = _resolve_workflow_docname(row.workflow_name)
        if docname:
            frappe.db.set_value(
                "FAC Workflow Trigger",
                row.name,
                "workflow_docname",
                docname,
                update_modified=False,
            )
