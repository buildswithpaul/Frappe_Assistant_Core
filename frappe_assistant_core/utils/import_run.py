# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Importing a checked session through Frappe's own Data Import (#33993).

The file that passed the dry run is written as a private CSV of the session's sheet, with the
value maps applied and the rows left out blanked: Data Import skips a blank row and keeps the
others' numbers, so its log names the user's own rows. A Data Import is made from that file and
started the way Desk's Start Import does, so it shows in Desk with its file and log like any
other. Data Import commits each record and rolls back only a failed one, so a partial success
is normal; a re-run skips the rows already imported, which is how an interrupted import
continues without duplicates.

Rows that failed are tried again from a new file (#33994): once the user has fixed their causes
and the dry run has checked what is left, a new Data Import is made with the rows already
imported blanked too, so the fixes are in it and no record is imported twice. Every Data
Import stays on the session, which reports them all.
"""

import csv
import io
import os
from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _
from frappe.core.doctype.data_import.importer import INSERT
from frappe.utils import cstr, strip_html
from frappe.utils.background_jobs import enqueue, is_job_enqueued
from frappe.utils.scheduler import is_scheduler_inactive

from frappe_assistant_core.assistant_core.doctype.fac_import_session.fac_import_session import engine_session
from frappe_assistant_core.utils import import_dry_run as dry_run
from frappe_assistant_core.utils import import_failures, import_fixes, import_keys, import_update
from frappe_assistant_core.utils.import_session import (
    import_target_problem,
    read_sheet_rows,
    readable_session_file,
)

READY = "Ready to Import"
IMPORTING = "Importing"
TRY_AGAIN = import_failures.AFTER_IMPORT  # some rows not in: checked again, then imported
FAILED_GROUPS_SHOWN = 5
START_SAVEPOINT = "fac_start_import"

#: The session's status once its Data Import has ended, by the Data Import's status.
FINISHED_STATUS = {"Success": "Completed", "Partial Success": "Partially Completed", "Error": "Failed"}


class ImportProblem(Exception):
    """The import can't start or continue. The message is shown to the user."""


class StartCollided(ImportProblem):
    """The start deadlocked with another import saving at the same moment, and the database undid
    its whole transaction: nothing of it was saved, so it can simply run again (BT-17)."""


#: How many times start_import runs a start that collided before it tells the model.
START_ATTEMPTS = 3


# -- can it run --------------------------------------------------------------------------


def cannot_import(doctype: str, import_type: str = INSERT) -> str:
    """Why the current user can't import into ``doctype`` now, or "" when they can."""
    problem = import_target_problem(doctype, import_type)
    if problem:
        return problem
    if not frappe.has_permission("Data Import", "create"):
        return _(
            "Importing goes through Data Import, which you can't use. A System Manager can import "
            "this file, or give you the Data Import permission."
        )
    if is_scheduler_inactive() and not _runs_now():
        return _("The scheduler is turned off, so imports can't run. A System Manager can turn it on.")
    return ""


def _runs_now() -> bool:
    """As Data Import decides: in tests and developer mode the import runs in the request, so the
    tool call lasts as long as the import, and a large file can hit the request timeout there
    (#34413). Everywhere else it runs in the background."""
    return bool(frappe.flags.in_test or frappe.conf.developer_mode)


def check_card(
    session,
    doctype: str,
    rows: Any,
    import_type: str,
    fingerprint: Any = None,
    file_name: Any = None,
    submit: Any = None,
) -> None:
    """The approval card shows what FACO passed: refuse unless it is what the last check found.

    The check's fingerprint binds the approval to that check (#34402): a remap and a new check of
    the same row count, in another tab or a parallel call, is another check, so it isn't imported
    under this approval. The file's name and whether records are submitted are on the card too."""
    summary = frappe.parse_json(session.validation_summary or "{}") or {}
    checked = (session.target_doctype, summary.get("ready"), session.import_type or INSERT)
    asked = (cstr(doctype).strip(), _int(rows), cstr(import_type).strip())
    if asked != checked:
        raise ImportProblem(
            _(
                "The last check found {1} {0} rows to import as {2}, not what was passed. Pass "
                "those, so the approval card shows them."
            ).format(*checked)
        )
    if not dry_run.names_check(fingerprint, session.validated_fingerprint):
        raise ImportProblem(
            _(
                "The file was checked again since: pass the last check's validated_fingerprint, "
                "so the approval is of what was checked. Show the user that check's result first."
            )
        )
    if submit is None and not session.submit_after_import:
        # Left out, it is the default, false, and the card is right without it: FACO leaves an
        # optional false out (BT-18). A submit the card doesn't show is still refused.
        submit = False
    card = (cstr(file_name).strip(), _bool(submit))
    if card != (cstr(session.file_name), bool(session.submit_after_import)):
        raise ImportProblem(
            _("Pass file_name '{0}' and submit_after_import {1}, so the approval card shows them.").format(
                session.file_name, "true" if session.submit_after_import else "false"
            )
        )


def _bool(value) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if cstr(value).strip().lower() in ("1", "true", "yes"):
        return True
    if cstr(value).strip().lower() in ("0", "false", "no"):
        return False
    return None


def _int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# -- starting and continuing -------------------------------------------------------------------


NOTHING_TO_CHANGE = "Nothing to change: every row already has the file's values in ERPNext."


class NothingToChange(Exception):
    """The update had nothing to send: the session is Completed (#34436)."""


def nothing_to_change(session) -> bool:
    """An update whose last check found no row to send and some already as the file has them."""
    if not (import_update.is_update(session) and import_update.match_fields(session)):
        return False
    statuses = {row.get("status") for row in _checked_rows(session)}
    return "unchanged" in statuses and "ready" not in statuses


def close_unchanged(session) -> bool:
    """Complete an update whose every row already holds the file's values (#34436): it is done
    without a Data Import, and doesn't stay Ready to Import for good. True when it was one."""
    if not nothing_to_change(session):
        return False
    session.status = "Completed"
    session.log_step("Import", "Success", _(NOTHING_TO_CHANGE))
    session.save()
    return True


def start(session) -> str:
    """Import a session that passed the dry run: the cleaned file, a Data Import, started. A
    session imported before gets only its rows not imported yet, in a new Data Import."""
    if dry_run.is_running(session):
        # The check stores its result when it ends, over the status this import would set.
        raise ImportProblem(dry_run.check_running())
    if session.status in TRY_AGAIN:
        raise ImportProblem(
            _(
                "Some rows weren't imported. Once their causes are fixed, check them with "
                "dry_run_import (it checks only the rows not imported yet), then import those."
            )
        )
    if session.status != READY or not import_fixes.checked_as_is(session):
        raise ImportProblem(
            _(
                "The file isn't ready, or it changed since its last check. Check it with "
                "dry_run_import first: only a file that passed is imported."
            )
        )
    if close_unchanged(session):
        raise NothingToChange(_(NOTHING_TO_CHANGE))
    earlier = import_failures.imports_of_this_file(session)
    # A tree's rows whose parent rows aren't in ERPNext yet wait for a later Data Import.
    waiting = _waiting(_checked_rows(session), import_failures.imported_rows(session))
    name = _new_import(session, "Retry" if earlier else "Import", earlier, waiting=waiting)
    # Run in this request (tests, developer mode), the next levels have been imported too.
    return _latest_import(session.name) or name


def _new_import(
    session,
    purpose: str,
    earlier: List[str],
    only: Optional[set] = None,
    waiting: set = frozenset(),
    message: Optional[str] = None,
) -> str:
    """A Data Import of the session's cleaned file (only the rows in ``only`` when given, never
    the ``waiting`` ones), recorded on the session and started."""
    frappe.db.savepoint(START_SAVEPOINT)
    file_doc = None
    try:
        file_doc, column_map = _cleaned_file(session, earlier, only=only, waiting=waiting)
        # Saving it attaches the file to it, as Frappe does for an Attach field.
        data_import = frappe.get_doc(
            {
                "doctype": "Data Import",
                "reference_doctype": session.target_doctype,
                "import_type": session.import_type or INSERT,
                "import_file": file_doc.file_url,
                "template_options": frappe.as_json(data_import_options(session, column_map)),
                "mute_emails": 1,
                "submit_after_import": session.submit_after_import,
            }
        ).insert()
        _record_start(session, data_import.name, purpose, session.source_file, message)
    except Exception as e:
        # Nothing half made stays behind: no Data Import without its session's record of it.
        try:
            frappe.db.rollback(save_point=START_SAVEPOINT)
        except Exception:
            # A deadlock's victim lost its whole transaction, the savepoint with it (BT-17).
            frappe.db.rollback()
        if file_doc:
            _remove_from_disk(file_doc)
        if isinstance(e, frappe.QueryDeadlockError):
            raise StartCollided(
                _(
                    "Another import was saving at the same time, so this one stopped. Nothing was "
                    "saved. Call again with the same values to try again."
                )
            ) from e
        raise
    _launch(session, data_import.name)
    return data_import.name


def job_running(session) -> bool:
    """Whether a background job is importing the session now: its opening engine's, or the job
    of its last Data Import. A session Importing with no such job is stuck (#34542)."""
    from frappe.utils.background_jobs import is_job_enqueued

    from frappe_assistant_core.utils.import_dry_run import special_engine

    engine = special_engine(session)
    if engine and getattr(engine, "JOB", None):
        return is_job_enqueued(engine.JOB.format(session.name))
    return bool(session.data_imports) and is_job_enqueued(_job_id(session.data_imports[-1].data_import))


def resume(session) -> Tuple[str, str]:
    """Continue the session's Data Import: "running" if it still is; "finished" if it had
    ended (its result is recorded); else it is started again ("continued"), skipping the
    records already imported and trying the failed ones again."""
    if not session.data_imports:
        raise ImportProblem(_("This session has no import to continue."))
    name = session.data_imports[-1].data_import
    if not import_failures.own_import(session, name, "write"):
        # A link written over the REST API: never start another user's Data Import.
        raise ImportProblem(_("This session has no import to continue."))
    if is_job_enqueued(_job_id(name)):
        return name, "running"
    di = frappe.get_doc("Data Import", name)
    ended = di.status in FINISHED_STATUS and _log_count(name) >= (di.payload_count or 0)
    if di.status == "Success" or (ended and session.status == IMPORTING):
        # Run to its end from Desk, or its result never recorded: record it, don't run again.
        from frappe_assistant_core.utils import import_plan

        record_result(session.name, name)
        if not _next_level(session.name, name):
            import_plan.child_finished(session.name)
        return name, "finished"
    _record_start(session, name, "Continue", session.data_imports[-1].source_file)
    _launch(session, name)
    return name, "continued"


def _record_start(
    session, data_import: str, purpose: str, source_file: Optional[str], message: Optional[str] = None
) -> None:
    session.append(
        "data_imports",
        {"data_import": data_import, "purpose": purpose, "status": "Pending", "source_file": source_file},
    )
    session.status = IMPORTING
    session.progress = frappe.as_json({"step": "Import", "state": "running", "data_import": data_import})
    message = (
        message
        or {
            "Import": _("Started Data Import {0}."),
            "Retry": _("Started Data Import {0}, for the rows not imported yet."),
            "Continue": _("Continued Data Import {0}."),
        }[purpose]
    ).format(data_import)
    session.log_step("Import", "Success", message)
    session.save()


def _launch(session, data_import: str) -> None:
    """Run the Data Import as Desk's Start Import does: same job, queue and timeout."""
    if _runs_now():
        # The import runs in this request, and the importer undoes a failed record with a full
        # rollback: what this request wrote must be saved first, as Desk's Start Import has it.
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — see the comment above
    enqueue(
        "frappe_assistant_core.utils.import_run.run_job",
        queue="default",
        timeout=10000,
        event="data_import",
        job_id=_job_id(data_import),
        enqueue_after_commit=True,  # the job reads the Data Import this request saved
        now=_runs_now(),
        data_import=data_import,
        session_name=session.name,
    )


def _job_id(data_import: str) -> str:
    return f"data_import::{data_import}"  # Data Import's own, so Desk sees it running


def run_job(data_import: str, session_name: str) -> None:
    """Background job: Data Import's own run, then its result recorded on the session."""
    from frappe.core.doctype.data_import.data_import import start_import

    from frappe_assistant_core.utils import import_plan

    start_import(data_import)
    record_result(session_name, data_import)
    if not _next_level(session_name, data_import):
        import_plan.child_finished(session_name)  # in a migration plan, its next file
    frappe.db.commit()  # nosemgrep: frappe-manual-commit — a background job commits its own work


def _log_count(data_import: str) -> int:
    return frappe.db.count("Data Import Log", {"data_import": data_import})


def _remove_from_disk(file_doc) -> None:
    """A File rolled back with its savepoint leaves its content on disk."""
    path = file_doc.get_full_path()
    if os.path.exists(path) and not frappe.db.exists("File", {"file_url": file_doc.file_url}):
        os.remove(path)


# -- the cleaned file -----------------------------------------------------------------------


# What Data Import reads of template_options besides the mapping: Frappe 16's per-column date
# formats. The dry run parses with the session's own, so the import is given them too (#34413).
PARSE_OPTIONS = ("column_to_date_format_map",)


def data_import_options(session, column_map: Dict[str, str]) -> Dict[str, Any]:
    """The template_options the real Data Import is given: the cleaned file's mapping, and the
    session's parse options as the dry run read them. The cleaned file keeps the columns' places."""
    options = frappe.parse_json(session.template_options or "{}") or {}
    return {"column_to_field_map": column_map, **{k: options[k] for k in PARSE_OPTIONS if options.get(k)}}


def _cleaned_file(session, earlier: List[str], only: Optional[set] = None, waiting: set = frozenset()):
    """The session's sheet as a private CSV: value maps applied, records left out or already
    imported blanked (every row of them, so no child row is left to join another record). It
    is saved unattached, for the Data Import made from it to take. Returns it with the column
    map that Data Import uses: an update's adds the ID column (#34005)."""
    source = readable_session_file(session)
    rows = import_fixes.apply_value_maps(session, read_sheet_rows(source, session.sheet or None))
    column_map = dry_run.column_to_field_map(session)
    if import_update.is_update(session) and import_update.match_fields(session):
        # The records the check matched, not a new match: the user approved these.
        records = import_update.checked_records(session)
        if not records:
            raise ImportProblem(_("Nothing to update: every matched record already has the file's values."))
        width = len(rows[0])
        rows = [rows[0]] + [
            row if number in records else [""] * width for number, row in enumerate(rows[1:], start=2)
        ]
        rows, column_map = import_update.with_ids(session, rows, records)
    column_map = dry_run.only_mapped(column_map, len(rows[0]) if rows else 0)
    excluded = dry_run._excluded_rows(session)
    imported = import_failures.imported_rows(session)
    left_out = set()
    payloads = dry_run._parse(session, source, rows, column_map).get_payloads_for_import()
    for payload in payloads:
        numbers = {row.row_number for row in payload.rows}
        first = payload.rows[0].row_number
        if numbers & (excluded | imported) or first in waiting or (only is not None and first not in only):
            left_out |= numbers
    if all({row.row_number for row in payload.rows} <= left_out for payload in payloads):
        # Every row is in or left out (a Desk retry since the check, say): never import again.
        raise ImportProblem(
            _("Every row of this file is already imported or left out, in Data Import {0}.").format(
                ", ".join(earlier)
            )
            if earlier
            else _("Every row of this file is left out, so there is nothing to import.")
        )
    width = len(rows[0])
    cleaned = [dry_run.unique_headers(rows[0])] + [
        [""] * width if number in left_out else row for number, row in enumerate(rows[1:], start=2)
    ]

    # Data Import refuses the whole file for one value it can't use, so stop here if any row
    # would now fail that way (a master deleted since the check, say).
    warnings = [
        w
        for w in dry_run._parse(session, source, cleaned, column_map).get_warnings()
        if w.get("type") != "info"
    ]
    if warnings:
        raise ImportProblem(
            _(
                "Since the last check, ERPNext would refuse some rows ({0}). Check the file again with dry_run_import."
            ).format(_warning_text(warnings[0]))
        )

    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows([[cstr(value) for value in row] for row in cleaned])
    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": f"{session.name}-import.csv",
            "content": buffer.getvalue().encode("utf-8"),
            "is_private": 1,
        }
    ).insert()
    return file_doc, column_map


def _warning_text(warning: Dict[str, Any]) -> str:
    text = " ".join(strip_html(cstr(warning.get("message"))).split())
    row = warning.get("row")
    return _("row {0}: {1}").format(row, text) if row else text


# -- a tree, a level at a time ----------------------------------------------------------------
#
# Data Import refuses a whole file when a row links to a record not in ERPNext yet, as a tree's
# child row does to its parent row higher up the file. The dry run marks such a row with the rows
# it needs ("after"). Those go in first, and each Data Import that ends starts the next one with
# the rows whose parent rows it brought in.


def _checked_rows(session) -> List[Dict[str, Any]]:
    """The rows of the session's last check, as its result file has them."""
    file_doc = dry_run._results_file(session)
    content = (frappe.parse_json(file_doc.get_content()) or {}) if file_doc else {}
    return content.get("rows") or []


def _waiting(rows: List[Dict[str, Any]], imported: set) -> set:
    """Rows not imported yet whose parent rows aren't all in ERPNext."""
    return {
        row["row"]
        for row in rows
        if row.get("after") and row["row"] not in imported and not set(row["after"]) <= imported
    }


def _latest_import(session_name: str) -> Optional[str]:
    names = frappe.get_all(
        "FAC Import Session Data Import",
        filters={"parent": session_name, "parenttype": dry_run.SESSION_DOCTYPE},
        order_by="idx desc",
        limit=1,
        pluck="data_import",
    )
    return names[0] if names else None


def _next_level(session_name: str, data_import: str) -> bool:
    """Once a Data Import of the session ended: the rows whose parent rows it imported, in a new
    Data Import. When none is left, a ready row still not imported makes the import partial.
    Returns whether a next level started."""
    session = engine_session(session_name)
    rows = _checked_rows(session)
    if session.status not in FINISHED_STATUS.values() or not any(row.get("after") for row in rows):
        return False
    imported = import_failures.imported_rows(session)
    brought = import_failures._success_rows([data_import])
    level = {
        row["row"]
        for row in rows
        if row.get("after")
        and row["row"] not in imported
        and set(row["after"]) <= imported
        and set(row["after"]) & brought
    }
    if level:
        try:
            _new_import(
                session,
                "Import",
                import_failures.imports_of_this_file(session),
                only=level,
                message=_("Started Data Import {0}, for the rows whose parent rows are now imported."),
            )
            return True
        except ImportProblem as e:
            session.reload()
            session.log_step("Import", "Failed", str(e))
    left = sorted({row["row"] for row in rows if row.get("status") == "ready"} - imported)
    # The latest level's Data Import alone sets the status: one whose every row failed says Failed,
    # though the levels before it brought rows in.
    if left and imported and session.status in ("Completed", "Failed"):
        session.status = "Partially Completed"
        waiting = sorted(_waiting(rows, imported))
        message = (
            _("{0} not imported: the parent rows they need weren't.").format(_rows_text(waiting))
            if waiting
            else _("{0} not imported.").format(_rows_text(left))
        )
        session.log_step("Import", "Warning", message)
    session.save()
    return False


# -- the result ------------------------------------------------------------------------------


def record_result(session_name: str, data_import: str) -> Dict[str, Any]:
    """Where the Data Import ended, recorded on the session: its status, the counts on its
    Data Import row, and the step log. Returns the result, as FACO reports it."""
    session = engine_session(session_name)
    result = result_of(session, data_import)
    kept = import_keys.record(session, data_import)  # the old IDs of the records it created
    if kept.get("conflicts"):
        result["message"] += " " + _(
            "{0} old ID(s) already belong to another record, so they were not kept for these: {1}."
        ).format(len(kept["conflicts"]), ", ".join(kept["conflicts"][:5]))
    if kept:
        result["old_ids"] = kept
    link = next((d for d in reversed(session.data_imports) if d.data_import == data_import), None)
    if link:
        link.status, link.success_count, link.failed_count = (
            result["data_import_status"],
            result["created"],
            result["failed"],
        )
    session.status = result["session_status"]
    session.progress = frappe.as_json(
        {"step": "Import", "state": result["state"], "data_import": data_import}
    )
    outcome = {"finished": "Success" if not result["failed"] else "Warning"}.get(result["state"], "Failed")
    session.log_step(
        "Import", outcome, result["message"], rows_ok=result["created"], rows_failed=result["failed"]
    )
    session.save()
    return result


def result_of(session, data_import: str) -> Dict[str, Any]:
    """The Data Import's result in the session's terms: created, failed and skipped counts, the
    failed rows by reason, the rows left out, and what FACO says."""
    if not import_failures.own_import(session, data_import):
        # Never another user's Data Import: its counts and failure messages aren't this user's.
        raise frappe.PermissionError(_("Data Import {0} isn't this session's.").format(data_import))
    di = frappe.get_doc("Data Import", data_import)
    logs = frappe.get_all(
        "Data Import Log",
        filters={"data_import": data_import},
        fields=["success", "row_indexes", "messages", "exception"],
        order_by="log_index",
    )
    created = sum(1 for log in logs if log.success)
    failed = import_failures.failure_groups(
        session,
        [log for log in logs if not log.success],
        import_failures._import_file_rows(data_import),
        explained=import_fixes.GROUPS_SHOWN,
    )
    failed_count = sum(group["count"] for group in failed)
    left_out = import_fixes.left_out_report(session)
    skipped = sum(group["count"] for group in left_out)
    ended = di.status in FINISHED_STATUS and len(logs) >= (di.payload_count or 0)

    doctype = _(di.reference_doctype)
    done = _("Imported") if (di.import_type or INSERT) == INSERT else _("Updated")
    # Data Import's last run refused the whole file before importing a record (it clears these
    # at the start of every run).
    warnings = [w for w in (frappe.parse_json(di.template_warnings or "[]") or []) if w.get("type") != "info"]
    if warnings and not created:
        state, session_status = "refused", "Mapped"
        message = _(
            "ERPNext refused the file before importing anything ({0}). Check it again with dry_run_import."
        ).format(_warning_text(warnings[0]))
    elif warnings:
        state, session_status = "refused", IMPORTING
        message = _(
            "ERPNext now refuses some rows ({0}), so the import can't continue. Fix that (restore "
            "a deleted record, say), then ask to continue: the {1} {2} records imported stay."
        ).format(_warning_text(warnings[0]), created, doctype)
    elif ended:
        state, session_status = "finished", FINISHED_STATUS[di.status]
        message = _("{0} {1} {2} records into ERPNext.").format(done, created, doctype)
    else:
        state, session_status = "interrupted", IMPORTING
        message = _(
            "The import stopped after {0} of {1} {2} records ({3}). Ask to continue: records already imported are skipped."
        ).format(len(logs), di.payload_count or 0, doctype, _(di.status))
    if failed:
        reasons = "; ".join(
            _("{0}: {1}").format(_rows_text(group["rows"]), group["reason"])
            for group in failed[:FAILED_GROUPS_SHOWN]
        )
        if len(failed) > FAILED_GROUPS_SHOWN:
            reasons += "; " + _("{0} other causes").format(len(failed) - FAILED_GROUPS_SHOWN)
        message += " " + _("{0} failed ({1}).").format(failed_count, reasons)
    if skipped:
        message += " " + _("{0} left out ({1}).").format(
            _("1 row") if skipped == 1 else _("{0} rows").format(skipped),
            "; ".join(
                "{}: {}".format(
                    group["reason"],
                    (_("row {0}") if group["count"] == 1 else _("rows {0}")).format(group["rows"]),
                )
                for group in left_out
            ),
        )
    message += " " + _("Data Import {0}.").format(data_import)
    all_runs = import_failures.runs(session)
    if len(all_runs) > 1:
        message += " " + _("In all, {0} records imported over {1} Data Imports.").format(
            sum(run["created"] for run in all_runs), len(all_runs)
        )

    result = {
        "state": state,
        "session_status": session_status,
        "data_import": data_import,
        "data_import_status": di.status,
        "desk_url": f"/app/data-import/{data_import}",
        "total": di.payload_count or 0,
        "created": created,
        "failed": failed_count,
        "skipped": skipped,
        # As many causes as the dry run shows; the failed-rows file has every row (#34407)
        "failed_rows": failed[: import_fixes.GROUPS_SHOWN],
        "left_out": left_out,
        "message": message,
    }
    if len(failed) > import_fixes.GROUPS_SHOWN:
        result["failed_groups_total"] = len(failed)
        result["failed_groups_not_shown"] = len(failed) - import_fixes.GROUPS_SHOWN
    if len(all_runs) > 1:
        result["runs"] = all_runs
        result["created_in_all"] = sum(run["created"] for run in all_runs)
    if failed and state == "finished":
        result["next"] = import_failures.next_steps()
    return result


def _rows_text(rows: List[int]) -> str:
    return (_("row {0}") if len(rows) == 1 else _("rows {0}")).format(import_fixes.row_ranges(rows))
