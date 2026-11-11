# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
The rows an import didn't get in (#33994): explained, tried again on their own, or handed
to the user as a file to correct.

A session's rows already imported are the ones in a success log of a Data Import made from
its current file. The dry run skips them and the next Data Import blanks them, so trying
again imports only the rest, from a new file with the fixes made since, and never touches a
record already in. A corrected file the user uploads (or a Google Sheet fetched again) is the
session's file from then on: a row of it that is the same as one an earlier file imported
counts as imported too, since a record with no key column (an Address) can't be stopped by
the dry run's duplicate check.

Every Data Import stays linked to the session, so the report covers every run.
"""

import io
import json
from collections import Counter
from typing import Any, Dict, List, Optional

import frappe
from frappe import _
from frappe.utils import cstr, get_url

from frappe_assistant_core.utils import import_dry_run as dry_run
from frappe_assistant_core.utils import import_fixes
from frappe_assistant_core.utils.import_session import (
    FORMULA_START,
    FileProblem,
    read_sheet_rows,
    readable_session_file,
)

#: The columns the failed-rows file adds after the user's own. A file sent back with them is
#: the same file: they are not imported.
ROW_COLUMN = "FACO Original Row"
REASON_COLUMN = "FACO Error"
#: FACO's suggestion for the row, when it has one (#34417)
FIX_COLUMN = "FACO Fix"
#: The reason's column in the CSV files FACO gave before #34417: such a file can still come back
OLD_REASON_COLUMN = "FACO Failure Reason"
ADDED_COLUMNS = (ROW_COLUMN, REASON_COLUMN, FIX_COLUMN, OLD_REASON_COLUMN)

#: Statuses whose failures come from the last Data Import, and from the last check.
AFTER_IMPORT = ("Partially Completed", "Failed")
AFTER_CHECK = ("Dry Run Failed", "Ready to Import")


class FailuresProblem(Exception):
    """There is no failed-rows file to give. The message is shown to the user."""


# -- what is already in -------------------------------------------------------------------


def own_import(session, data_import: str, ptype: str = "read") -> bool:
    """Whether a Data Import linked on the session is the session's to use: made by its user, or
    one the current user has ``ptype`` on anyway ("write" to start it again). A session's child
    rows can be written over the REST API, so a link to another user's import must not bring in
    its rows, its file or its failure messages, nor be started. The session's user is the one
    field that can't be set to someone else: it gives access to the session (its has_permission)."""
    owner = frappe.db.get_value("Data Import", data_import, "owner")
    if not owner:
        return False
    if owner == session.user:
        return True
    return frappe.has_permission("Data Import", ptype, doc=frappe.get_doc("Data Import", data_import))


def own_links(session) -> list:
    """The session's Data Import rows that own_import allows, in order."""
    return [link for link in session.data_imports if own_import(session, link.data_import)]


def imports_of_this_file(session) -> List[str]:
    """The session's Data Imports made from its current file, each once, oldest first."""
    names = []
    for link in own_links(session):
        # A link from before source_file was kept is from the file the session had then.
        if (link.source_file or session.source_file) == session.source_file and link.data_import not in names:
            names.append(link.data_import)
    return names


def _success_rows(names: List[str]) -> set:
    lost = {log for name in names for log in lost_logs(name)}
    rows = set()
    for log in frappe.get_all(
        "Data Import Log",
        filters={"data_import": ["in", names], "success": 1},
        fields=["name", "row_indexes"],
    ):
        if log.name not in lost:
            rows.update(json.loads(log.row_indexes or "[]"))
    return rows


def lost_logs(data_import: str) -> List[str]:
    """Success logs of an import cut short whose record isn't in ERPNext (QA 2026-11-04 #2).

    Frappe's Data Import Log is a MyISAM table: a row's log is on disk as soon as it is written,
    while its record waits in the transaction committed right after. A worker killed between the
    two leaves a log saying "created" for a record that never was, and a continued import skips
    that row as imported, losing it for good. Only an import that didn't end can have one: a
    record deleted after an import ended was imported, and isn't brought in again. Its status
    can't tell (v15 sets "Partial Success" at its first record); as for Frappe's importer, an
    import ended once it has a log for each of its rows."""
    di = frappe.db.get_value(
        "Data Import",
        data_import,
        ["status", "import_type", "reference_doctype", "payload_count"],
        as_dict=True,
    )
    if not di or di.status == "Success" or di.import_type != "Insert New Records":
        return []
    if frappe.db.count("Data Import Log", {"data_import": data_import}) >= (di.payload_count or 0):
        return []
    logs = frappe.get_all(
        "Data Import Log",
        filters={"data_import": data_import, "success": 1},
        fields=["name", "docname"],
    )
    names = list({log.docname for log in logs if log.docname})
    there = (
        set(frappe.get_all(di.reference_doctype, filters={"name": ["in", names]}, pluck="name"))
        if names
        else set()
    )
    return [log.name for log in logs if log.docname and log.docname not in there]


def forget_lost_rows(data_import: str) -> int:
    """Delete the success logs lost_logs finds, so continuing the import brings their rows in
    (Frappe's importer skips every row with a success log). Returns how many it deleted."""
    lost = lost_logs(data_import)
    for name in lost:
        frappe.db.delete("Data Import Log", {"name": name})
    return len(lost)


def imported_rows(session) -> set:
    """Rows of the session's current file already imported: in a success log of a Data
    Import made from it (every row of a record spread over several), or brought back from an
    earlier file of the session (see came_back)."""
    names = imports_of_this_file(session)
    return (_success_rows(names) if names else set()) | came_back(session)


def _row_key(header: List[str], row: List[str]) -> tuple:
    """A row as the user's own columns hold it: header and text, whatever their order."""
    return tuple(
        sorted(
            (cstr(name).strip(), cstr(row[i]).strip() if i < len(row) else "")
            for i, name in enumerate(own_columns(dry_run.unique_headers(header)))
        )
    )


def came_back(session) -> set:
    """Rows of the session's current file that a Data Import from an earlier file of the
    session already brought in: the same text in each of the user's columns, read from that
    import's own file (value maps applied, as here). A record with no key column, an Address
    say, can't be stopped as "Already in ERPNext", so without this a whole file sent again
    would import it twice. Each row imported counts once: two equal rows of the new file aren't
    both taken for one imported earlier."""
    earlier = [
        link.data_import
        for link in own_links(session)
        if link.source_file and link.source_file != session.source_file
    ]
    seen: Counter = Counter()
    for name in dict.fromkeys(earlier):
        success = _success_rows([name])
        rows = _import_file_rows(name) if success else []
        for number in success:
            if 2 <= number <= len(rows):
                seen[_row_key(rows[0], rows[number - 1])] += 1
    if not seen:
        return set()
    current = import_fixes.apply_value_maps(
        session, read_sheet_rows(readable_session_file(session), session.sheet or None)
    )
    rows = set()
    for number, row in enumerate(current[1:], start=2):
        key = _row_key(current[0], row)
        if seen[key] > 0 and any(text for _name, text in key):
            seen[key] -= 1
            rows.add(number)
    return rows


def _import_file_rows(data_import: str) -> List[List[str]]:
    """The rows of the file a Data Import imported: the session's sheet as FAC cleaned it, with
    the rows it didn't import blanked, so its row numbers are the success logs'."""
    file_url = frappe.db.get_value("Data Import", data_import, "import_file")
    files = frappe.get_all(
        "File",
        filters={"file_url": file_url, "attached_to_doctype": "Data Import", "attached_to_name": data_import},
        pluck="name",
        limit=1,
    )
    if not file_url or not files:
        return []
    file_doc = frappe.get_doc("File", files[0])
    if not frappe.has_permission("File", "read", doc=file_doc):
        return []
    try:
        return read_sheet_rows(file_doc, None)
    except FileProblem:
        # Gone from disk, say: the Data Import Log still has the counts, so the result is
        # recorded with them, and the session doesn't stay Importing for good (#34538).
        return []


# -- explaining what failed -----------------------------------------------------------------


def failure_groups(
    session, logs, file_rows: Optional[List[List[str]]] = None, explained: Optional[int] = None
) -> List[Dict[str, Any]]:
    """An import's failed records grouped by what ERPNext said, each explained as the dry run
    explains its groups: ``reason``, ``error``, ``count`` records, ``rows`` and ``explanation``.

    As in the dry run, a message is grouped with its rows' own values read as "…", which the group
    lists as ``values`` (#34407): ``file_rows`` are the Data Import's file, whose line numbers the
    logs give. Only the first ``explained`` groups, the largest, are explained."""
    by_key: Dict[tuple, Dict[str, Any]] = {}
    for log in logs:
        rows = json.loads(log.row_indexes or "[]")
        values = [v for n in rows if file_rows and 1 <= n - 1 < len(file_rows) for v in file_rows[n - 1]]
        reason, quoted = dry_run.message_pattern(log_reason(log.messages), values)
        error = _error_of(log.get("exception"))
        group = by_key.setdefault(
            (error, reason),
            {
                "cause": dry_run.CAUSE_REJECTED,
                "error": error,
                "message": reason,
                "count": 0,
                "rows": [],
                "values": [],
            },
        )
        group["count"] += 1
        group["rows"].extend(rows)
        for value in quoted:
            if value not in group["values"] and len(group["values"]) < dry_run.VALUES_KEPT:
                group["values"].append(value)
    groups = []
    for index, group in enumerate(sorted(by_key.values(), key=lambda g: -g["count"])):
        rows = sorted(set(group["rows"]))
        out = {"reason": group["message"], "error": group["error"], "count": group["count"], "rows": rows}
        if group["values"]:
            out["values"] = group["values"]
        if explained is None or index < explained:
            # Said in rows, as the dry run says it: the rows are what the user sees.
            out["explanation"] = import_fixes.advise(session, {**group, "count": len(rows)})["explanation"]
        groups.append(out)
    return groups


def log_reason(messages: Optional[str]) -> str:
    """The last message ERPNext showed for a failed record, as plain text."""
    texts = dry_run.message_texts(json.loads(messages or "[]"))
    return texts[-1] if texts else _("ERPNext refused it")


def _error_of(traceback: Optional[str]) -> str:
    """The exception's class from a traceback's last line, as the dry run names it."""
    for line in reversed(cstr(traceback).strip().splitlines()):
        head = line.split(":", 1)[0].strip()
        if head and " " not in head:
            return head.rsplit(".", 1)[-1]
    return "Exception"


def next_steps() -> str:
    """What FACO offers once rows failed."""
    return _(
        "Explain each reason and fix what can be fixed in chat (create a missing record with "
        "create_document, or correct one with update_document). Then call dry_run_import: it "
        "checks only the rows not imported yet, and start_import imports just those. For rows "
        "the user would rather correct in the file, call dry_run_import with failed_rows_file."
    )


def runs(session) -> List[Dict[str, Any]]:
    """Every Data Import of the session once, oldest first, with its counts from its log."""
    names, purposes = [], {}
    for link in own_links(session):
        if link.data_import not in purposes:
            names.append(link.data_import)
            purposes[link.data_import] = link.purpose
    if not names:
        return []
    out = {
        name: {"data_import": name, "purpose": purposes[name], "created": 0, "failed": 0} for name in names
    }
    # Counted here, not with "count(*)" in the query: Frappe v16 refuses SQL functions in fields.
    for row in frappe.get_all(
        "Data Import Log", filters={"data_import": ["in", names]}, fields=["data_import", "success"]
    ):
        out[row.data_import]["created" if row.success else "failed"] += 1
    return [out[name] for name in names]


# -- the failed-rows file -------------------------------------------------------------------


def csv_cell(value) -> str:
    """``value`` as a CSV cell a spreadsheet won't run: a cell that starts like a formula gets a
    leading ' (#34413). A plain number, -5 or +3.5, is left as it is."""
    text = cstr(value)
    if text.startswith(FORMULA_START):
        try:
            float(text)
        except ValueError:
            return "'" + text
    return text


def _xlsx(rows: List[List[str]]) -> bytes:
    """``rows`` as an Excel sheet where every cell is text (#34417): a code keeps its leading zeros
    (00123), and a cell that starts like a formula (=, +, -, @) is shown, never run."""
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.title = "Rows not imported"
    for r, row in enumerate(rows, start=1):
        for c, value in enumerate(row, start=1):
            cell = sheet.cell(row=r, column=c)
            cell.value = cstr(value)
            cell.data_type = "s"  # openpyxl would take "=..." for a formula
            cell.number_format = "@"
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def failed_rows_file(session) -> Dict[str, Any]:
    """The rows still not imported, failed or left out, with the user's columns (the value
    maps applied), their row number, the error and FACO's fix when it has one, as a private
    Excel file on the session: every cell text."""
    if session.status == "Importing":
        raise FailuresProblem(_("The import is still running. Ask for the rows once it has ended."))
    problems = _problems(session)
    if not problems:
        raise FailuresProblem(
            _("No row of this file is failing or left out, so there is nothing to download.")
        )

    source = readable_session_file(session)
    rows = import_fixes.apply_value_maps(session, read_sheet_rows(source, session.sheet or None))
    width = len(own_columns(rows[0]))
    with_fix = any(problem["fix"] for problem in problems.values())
    added = [ROW_COLUMN, REASON_COLUMN] + ([FIX_COLUMN] if with_fix else [])
    out = [rows[0][:width] + added]
    for number in sorted(problems):
        if 1 <= number - 1 < len(rows):
            problem = problems[number]
            extra = [str(number), problem["reason"]] + ([problem["fix"] or ""] if with_fix else [])
            out.append((rows[number - 1] + [""] * width)[:width] + extra)

    file_name = f"{session.name}-failed-rows.xlsx"
    for old in frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": dry_run.SESSION_DOCTYPE,
            "attached_to_name": session.name,
            # the CSV FACO gave before #34417 goes too: one file of failed rows per session
            "file_name": ["in", [file_name, f"{session.name}-failed-rows.csv"]],
        },
        pluck="name",
    ):
        frappe.delete_doc("File", old, force=True, ignore_permissions=True)
    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": file_name,
            "content": _xlsx(out),
            "is_private": 1,
            "attached_to_doctype": dry_run.SESSION_DOCTYPE,
            "attached_to_name": session.name,
        }
    ).insert(ignore_permissions=True)  # the session's own file, made for its user

    count = len(out) - 1
    session.log_step(
        "Failed Rows File",
        "Success",
        _("Gave {0} not imported as a file to correct: {1}.").format(
            _("1 row") if count == 1 else _("{0} rows").format(count), file_doc.file_name
        ),
    )
    session.save()
    message = _(
        "{0} rows in an Excel file, with the user's columns, then '{1}' (the row's number in the file) "
        "and '{2}'"
    ).format(count, ROW_COLUMN, REASON_COLUMN)
    if with_fix:
        message += _(", and '{0}' where FACO has a fix").format(FIX_COLUMN)
    message += ". " + _(
        "Every cell is text, so codes keep their leading zeros. Once corrected, the file can come back "
        "as it is: once uploaded, pass it to dry_run_import as file_id, and only these rows are checked "
        "and imported, into this session."
    )
    return {
        "session": session.name,
        "rows": count,
        "file_url": file_doc.file_url,
        "download_url": get_url(file_doc.file_url),
        "message": message,
    }


def _fix_of(session, group: Dict[str, Any]) -> Optional[str]:
    """FACO's fix for a failed group, in a few words: the likely name it meant, or what a known
    refusal needs. None when FACO has none."""
    if group.get("cause") == dry_run.CAUSE_MISSING_LINK:
        # advise works out the linked DocType from the group's field, as the check stored it
        advice = import_fixes.advise(session, {**group, "count": 1})
        likely = next((f.get("likely") for f in advice["fixes"] if f.get("likely")), None)
        return _("Use '{0}'").format(likely) if likely else None
    return import_fixes.known_refusal(group.get("message"), _("This row"))


def _problems(session) -> Dict[int, Dict[str, Optional[str]]]:
    """Each row still not imported, failed or left out: {"reason", "fix"}. From the last Data
    Import once the import ended, from the last check before (or after a check of what is left)."""
    problems: Dict[int, Dict[str, Optional[str]]] = {}

    def add(row: int, reason: str, fix: Optional[str] = None) -> None:
        problems[row] = {"reason": reason, "fix": fix}

    engine = dry_run.special_engine(session)
    if engine:
        # Opening stock and opening invoices keep no Data Import Logs: they say themselves
        # where each row of the file stands.
        for outcome in engine.outcomes(session):
            if outcome["status"] == "excluded":
                add(outcome["row"], _("Left out: {0}").format(outcome["reason"]))
            elif outcome["status"] == "failed":
                add(
                    outcome["row"],
                    outcome["reason"],
                    import_fixes.known_refusal(outcome["reason"], _("This row")),
                )
        return problems
    if session.status in AFTER_IMPORT:
        names = imports_of_this_file(session)
        if names:
            for log in frappe.get_all(
                "Data Import Log",
                filters={"data_import": names[-1], "success": 0},
                fields=["row_indexes", "messages"],
                order_by="log_index",
            ):
                reason = log_reason(log.messages)
                for row in json.loads(log.row_indexes or "[]"):
                    add(row, reason, import_fixes.known_refusal(reason, _("This row")))
    elif session.status in AFTER_CHECK:
        results = dry_run._results_file(session)
        content = frappe.parse_json(results.get_content()) if results else {}
        groups = {group["id"]: group for group in content.get("groups") or []}
        fixes: Dict[Any, Optional[str]] = {}
        for row in content.get("rows") or []:
            if row.get("status") != "failed":
                continue
            ids = [g for g in row.get("groups") or [] if g in groups]
            for g in ids:
                if g not in fixes:
                    fixes[g] = _fix_of(session, groups[g])
            reason = "; ".join(groups[g].get("message") or groups[g]["cause"] for g in ids)
            add(row["row"], reason, "; ".join(fixes[g] for g in ids if fixes[g]) or None)
    for entry in import_fixes.left_out(session):
        if entry["row"] not in problems:
            add(entry["row"], _("Left out: {0}").format(entry["reason"] or _("by the user")))
    for row in imported_rows(session):
        problems.pop(row, None)
    return problems


def own_columns(columns: List[str]) -> List[str]:
    """The user's columns: a file this module gave ends with its added ones."""
    columns = list(columns)
    while columns and cstr(columns[-1]).strip() in ADDED_COLUMNS:
        columns.pop()
    return columns
