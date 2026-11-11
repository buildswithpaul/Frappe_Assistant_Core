# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Import session housekeeping for administrators (#34542).

A session whose import job died stays Importing, holding its file, and the engine guard refuses
every hand edit, so nobody could release it. A System Manager releases it here: through the engine's
own copy of the session, never by switching the guard off, and the step log says who and why. A
plan with no job running it is stopped the way the scheduled sweep stops one. The files outlive no
retention window either way: import_retention deletes them (#34539).
"""

from typing import Any, Dict, List, Optional

import frappe
from frappe import _
from frappe.utils import cstr, date_diff, now_datetime

from frappe_assistant_core.assistant_core.doctype.fac_import_session.fac_import_session import engine_session
from frappe_assistant_core.utils.import_session import HOLDING_STATUSES

SESSION_DOCTYPE = "FAC Import Session"
#: A session stuck in one of these can be released: it is importing, with no job doing it
STUCK = ("Importing",)


def _only_system_manager() -> None:
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only a System Manager can release an import session."), frappe.PermissionError)


def _imported_any(session) -> bool:
    from frappe_assistant_core.utils import import_failures

    return bool(session.created_records) or any(run["created"] for run in import_failures.runs(session))


def _holds_plan(session) -> bool:
    """Whether ``session`` keeps a running plan: the plan lives on its first file's session."""
    return (
        session.plan_status == "Running"
        and session.migration_plan == session.name
        and bool(session.plan_settings)
    )


def why_not_releasable(session) -> Optional[str]:
    """Why ``session`` can't be released, or None when it can: a running job is left alone."""
    from frappe_assistant_core.utils import import_plan, import_run

    if _holds_plan(session):
        if import_plan.alive(import_plan.get_plan(session.name)):
            return _("The plan is still running. Stop it with stop_migration_plan, or wait for it to end.")
        return None
    if session.status not in STUCK:
        return _(
            "Session {0} is {1}: only a session stuck importing, or a plan nothing runs, is released."
        ).format(session.name, _(session.status))
    if (
        session.migration_plan
        and frappe.db.get_value(SESSION_DOCTYPE, session.migration_plan, "plan_status") == "Running"
    ):
        return _("It is a file of plan {0}, which is still running: release the plan.").format(
            session.migration_plan
        )
    if import_run.job_running(session):
        return _("Its import is still running. Wait for it to end, or for it to time out.")
    return None


def release(name: str, reason: str) -> Dict[str, Any]:
    """Release a stuck session or a dead plan, saying who and why. What was imported stays."""
    _only_system_manager()
    reason = cstr(reason).strip()
    if not reason:
        frappe.throw(_("Say why the session is released: it goes in its step log."))
    session = engine_session(name)
    problem = why_not_releasable(session)
    if problem:
        frappe.throw(problem)
    said = _("Released by {0}: {1}").format(frappe.session.user, reason)
    if _holds_plan(session):
        from frappe_assistant_core.utils import import_plan

        import_plan._end(name, "Stopped", said + " " + _("What it imported stays."))
        return {"session": name, "plan_status": "Stopped"}
    session.status = "Partially Completed" if _imported_any(session) else "Failed"
    session.log_step("Release", "Warning", said)
    session.save()
    return {"session": name, "status": session.status}


def sessions(filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Every session, for the Import Sessions report: whose, which file, where it stands, its last
    step, its age, whether it holds its file and whether it can be released."""
    filters = frappe._dict(filters or {})
    where: Dict[str, Any] = {}
    if filters.get("status"):
        where["status"] = filters.status
    if filters.get("user"):
        where["user"] = filters.user
    rows = frappe.get_list(
        SESSION_DOCTYPE,
        filters=where,
        fields=[
            "name",
            "user",
            "file_name",
            "target_doctype",
            "status",
            "plan_status",
            "modified",
            "source_file",
        ],
        order_by="modified desc",
        limit_page_length=0,
    )
    last_steps = {}
    if rows:
        for step in frappe.get_all(
            "FAC Import Session Step",
            filters={"parent": ["in", [r.name for r in rows]], "parenttype": SESSION_DOCTYPE},
            fields=["parent", "step", "outcome", "idx"],
            order_by="idx asc",
        ):
            last_steps[step.parent] = f"{_(step.step)}: {_(step.outcome)}"
    today = now_datetime()
    out = []
    for row in rows:
        stuck = row.status in STUCK or row.plan_status == "Running"
        if filters.get("stuck_only") and not stuck:
            continue
        out.append(
            {
                "session": row.name,
                "user": row.user,
                "file_name": row.file_name,
                "target_doctype": row.target_doctype,
                "status": row.status,
                "plan_status": row.plan_status,
                "last_step": last_steps.get(row.name, ""),
                "age_days": date_diff(today, row.modified),
                "holds_file": 1
                if row.source_file and (row.status in HOLDING_STATUSES or row.status in STUCK)
                else 0,
                "may_release": 1 if stuck else 0,
            }
        )
    return out
