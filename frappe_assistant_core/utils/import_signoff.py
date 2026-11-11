# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
The migration's sign-off report (#33999): what every import session brought in, proved row by
row, and the opening balances in ERPNext against the files' totals, so the business can sign
off on go-live. It is the ERPNext report "Migration Sign-off", so FACO runs it with
generate_report and makes its PDF with generate_document, and it opens in Desk too.

Every number here is counted or summed by this module from the files and from ERPNext, never by
the model: each row of each file is either imported, left out (with the user's reason), failed
(with why) or not imported yet, so the four always add up to the file's rows. Nothing is written.
"""

from typing import Any, Dict, List, Optional

import frappe
from frappe import _
from frappe.utils import add_days, cint, cstr, escape_html, flt, fmt_money, getdate, now_datetime

from frappe_assistant_core.utils import import_dry_run as dry_run
from frappe_assistant_core.utils import import_failures, import_fixes
from frappe_assistant_core.utils.import_session import (
    FileProblem,
    get_readable_file_by_id,
    read_sheet_rows,
    read_spreadsheet,
    readable_session_file,
)

STATUSES = ("imported", "unchanged", "excluded", "failed", "not_imported")
FINISHED = ("Completed", "Partially Completed", "Failed")
MAX_SESSIONS = 200
NOT_IMPORTED = "Checked, not imported yet"


# -- counting rows ---------------------------------------------------------------------------


def tally(outcomes: List[Dict[str, Any]], measures=(), precision: int = 2) -> Dict[str, Any]:
    """Rows per status, the reasons rows were left out or failed (grouped, with their row
    numbers), and each measure (amount, value) summed per status over the rows that are not a
    file's own totals row. ``source`` is every row, so source = imported + unchanged + excluded +
    failed + not_imported. An unchanged row (an update's, already as the file has it) is done."""
    rows = {"source": len(outcomes), **{status: 0 for status in STATUSES}}
    reasons: Dict[str, Dict[str, List[int]]] = {"excluded": {}, "failed": {}, "not_imported": {}}
    sums = {m: {"source": 0.0, **{status: 0.0 for status in STATUSES}} for m in measures}
    unreadable, totals_rows = [], []
    for outcome in outcomes:
        status = outcome["status"]
        rows[status] += 1
        if status in reasons:
            reasons[status].setdefault(outcome.get("reason") or "", []).append(outcome["row"])
        if outcome.get("totals_row"):
            totals_rows.append(outcome)
            continue
        for measure in measures:
            value = outcome.get(measure)
            if value is None:
                if measure == measures[0] and outcome.get("unreadable"):
                    unreadable.append(outcome["row"])
                continue
            sums[measure]["source"] += value
            sums[measure][status] += value
    out = {
        "rows": rows,
        **{
            status: [
                {"reason": reason, "count": len(found), "rows": import_fixes.row_ranges(found)}
                for reason, found in sorted(by_reason.items(), key=lambda item: -len(item[1]))
            ]
            for status, by_reason in reasons.items()
        },
    }
    for measure in measures:
        out[measure] = {key: flt(value, precision) for key, value in sums[measure].items()}
    if unreadable:
        out["unreadable_rows"] = import_fixes.row_ranges(unreadable)
    if totals_rows and measures:
        # The file's own total, when it has one: a check on the sum of its rows.
        out["file_says"] = flt(sum(flt(o.get("file_says")) for o in totals_rows), precision)
    return out


def adds_up(rows: Dict[str, int]) -> bool:
    return rows["source"] == sum(rows[status] for status in STATUSES)


# -- a Data Import session ------------------------------------------------------------------


def data_import_outcomes(session) -> List[Dict[str, Any]]:
    """Every non-blank row of a Data Import session's files and where it stands, numbered as in
    its first file: in a success log of a Data Import, left out, refused by the last Data Import
    or the last check (with why), or not imported yet.

    A session imports from more than one file when the user sends rows back corrected (#33994):
    a failed-rows file holds some rows, each with its row number in the file before it
    (import_failures.ROW_COLUMN); a whole file sent again, or a Google Sheet fetched again, keeps
    its rows in their places. Each later file's rows are laid over the row they stand for, and a
    row imported from any file stays imported; a row a later file leaves out keeps where it stood.
    Reading only the current file, the report forgot every row the earlier files brought in."""
    files = _session_files(session)
    merged: Dict[Any, Dict[str, Any]] = {}
    to_first: Optional[Dict[int, Any]] = None  # row of the file before -> row of the first file
    for file_name, names in files:
        if file_name == session.source_file:
            rows, outcomes = _current_file_outcomes(session)
        else:
            rows, outcomes = _earlier_file_outcomes(file_name, names)
        if not rows:
            continue
        back = _row_column(rows[0])
        place: Dict[int, Any] = {}
        for outcome in outcomes:
            number = outcome["row"]
            if to_first is None:
                first = number
            else:
                before = (
                    _int(rows[number - 1][back])
                    if back is not None and back < len(rows[number - 1])
                    else number
                )
                first = to_first.get(before, ("later", file_name, number))
            place[number] = first
            if merged.get(first, {}).get("status") != "imported":
                merged[first] = {**outcome, "row": first}
        to_first = place  # the next file's row numbers are this file's
    numbered = sorted(key for key in merged if isinstance(key, int))
    extra = [key for key in merged if not isinstance(key, int)]
    last = numbered[-1] if numbered else 1
    for offset, key in enumerate(extra, start=1):  # a row no earlier file had
        merged[key]["row"] = last + offset
    return [merged[key] for key in numbered + extra]


def _session_files(session) -> List[tuple]:
    """(file, its Data Imports) for each file the session imported from, oldest first, then its
    current file. A Data Import with no file noted is of the current one."""
    files: Dict[str, List[str]] = {}
    for link in import_failures.own_links(session):
        if link.source_file and link.source_file != session.source_file:
            files.setdefault(link.source_file, [])
            if link.data_import not in files[link.source_file]:
                files[link.source_file].append(link.data_import)
    return [*files.items(), (session.source_file, import_failures.imports_of_this_file(session))]


def _row_column(header: List[Any]) -> Optional[int]:
    for i, name in enumerate(header):
        if cstr(name).strip() == import_failures.ROW_COLUMN:
            return i
    return None


def _int(value) -> Optional[int]:
    try:
        return int(cstr(value).strip())
    except ValueError:
        return None


def _refused_by(data_import: Optional[str]) -> Dict[int, str]:
    refused: Dict[int, str] = {}
    if data_import:
        for log in frappe.get_all(
            "Data Import Log",
            filters={"data_import": data_import, "success": 0},
            fields=["row_indexes", "messages"],
            order_by="log_index",
        ):
            for row in frappe.parse_json(log.row_indexes or "[]") or []:
                refused[int(row)] = import_failures.log_reason(log.messages)
    return refused


def _current_file_outcomes(session):
    """The session's current file: its rows, and where each non-blank one stands."""
    rows = read_sheet_rows(readable_session_file(session), session.sheet or None)
    imported = import_failures.imported_rows(session)
    left = {entry["row"]: entry["reason"] for entry in import_fixes.left_out(session)}
    names = import_failures.imports_of_this_file(session)
    refused = _refused_by(names[-1] if names else None)
    for row, reason in _check_failures(session).items():
        refused.setdefault(row, reason)
    unchanged = _check_unchanged(session)

    out = []
    for number, values in enumerate(rows[1:], start=2):
        if not any(cstr(v).strip() for v in values):
            continue
        if number in imported:
            out.append({"row": number, "status": "imported"})
        elif number in unchanged:
            # an update's row whose record already holds its values: nothing to import (#34436)
            out.append({"row": number, "status": "unchanged"})
        elif number in left:
            out.append(
                {"row": number, "status": "excluded", "reason": left[number] or _("Left out by the user")}
            )
        elif number in refused:
            out.append({"row": number, "status": "failed", "reason": refused[number]})
        else:
            out.append({"row": number, "status": "not_imported", "reason": _(NOT_IMPORTED)})
    return rows, out


def _earlier_file_outcomes(file_name: str, names: List[str]):
    """A file the session imported from before its current one: its rows, and where each
    non-blank one stood when the next file came. Its Data Import's own file blanks the rows left
    out (and those imported before), so a row blank there that no import brought in was left
    out. The file is read again for its rows; when it is gone, that imported file stands in."""
    imported_file = import_failures._import_file_rows(names[-1]) if names else []
    rows = _earlier_rows(file_name, imported_file) or imported_file
    success = import_failures._success_rows(names) if names else set()
    refused = _refused_by(names[-1] if names else None)
    out = []
    for number, values in enumerate(rows[1:], start=2):
        if not any(cstr(v).strip() for v in values):
            continue
        sent = imported_file[number - 1] if number - 1 < len(imported_file) else []
        if number in success:
            out.append({"row": number, "status": "imported"})
        elif number in refused:
            out.append({"row": number, "status": "failed", "reason": refused[number]})
        elif not any(cstr(v).strip() for v in sent):
            out.append({"row": number, "status": "excluded", "reason": _("Left out by the user")})
        else:
            out.append({"row": number, "status": "not_imported", "reason": _(NOT_IMPORTED)})
    return rows, out


def _earlier_rows(file_name: str, imported_file: List[List[str]]) -> List[List[str]]:
    """The rows of an earlier file of the session: the sheet whose headings are the ones its
    Data Import took. [] when the file is gone, isn't the user's to read, or has no such sheet."""
    if not imported_file:
        return []
    want = import_failures.own_columns(dry_run.unique_headers(imported_file[0]))
    try:
        file_doc = get_readable_file_by_id(file_name)
        sheets = [sheet.name for sheet in read_spreadsheet(file_doc).sheets]
        for sheet in sheets:
            rows = read_sheet_rows(file_doc, sheet)
            if rows and import_failures.own_columns(dry_run.unique_headers(rows[0])) == want:
                return rows
    except FileProblem:
        pass
    return []


def _check_unchanged(session) -> set:
    """The rows the session's last check found already as the file has them (an update's)."""
    results = dry_run._results_file(session)
    if not results:
        return set()
    try:
        content = frappe.parse_json(results.get_content()) or {}
    except Exception:
        return set()
    return {int(row["row"]) for row in content.get("rows") or [] if row.get("status") == "unchanged"}


def _check_failures(session) -> Dict[int, str]:
    """The rows the session's last check found failing, with why."""
    results = dry_run._results_file(session)
    if not results:
        return {}
    try:
        content = frappe.parse_json(results.get_content()) or {}
    except Exception:
        return {}
    messages = {g["id"]: g.get("message") or _(g.get("cause") or "") for g in content.get("groups") or []}
    return {
        int(row["row"]): "; ".join(messages.get(g, "") for g in row.get("groups") or [])
        for row in content.get("rows") or []
        if row.get("status") == "failed"
    }


def _data_import_summary(session) -> Dict[str, Any]:
    out = tally(data_import_outcomes(session))
    out.update({"kind": "data_import", "doctype": session.target_doctype, "label": _(session.target_doctype)})
    return out


# -- who may see ERPNext's side ----------------------------------------------------------------

#: The ledger each opening import is compared with; opening invoices are compared with the
#: invoices themselves.
LEDGERS = {"opening_stock": "Stock Ledger Entry", "opening_balances": "GL Entry"}


def can_read_ledger(doctype: str, company: str) -> bool:
    """Whether the user may read ``doctype``'s records of ``company``: a role lets them read it,
    and no User Permission keeps them from that company. The report sums ERPNext's records
    without going through get_list, so it asks first, as ERPNext's own reports do."""
    if not frappe.has_permission(doctype, "read"):
        return False
    probe = frappe.new_doc(doctype)
    if probe.meta.has_field("company"):
        probe.company = company
    return bool(frappe.has_permission(doctype, "read", doc=probe))


def _cannot_read(doctype: str, company: str) -> str:
    return _("You can't read {0} of {1}, so ERPNext's side isn't shown.").format(_(doctype), company)


# -- one session ------------------------------------------------------------------------------


def session_summary(session) -> Dict[str, Any]:
    """What ``session`` brought in, proved row by row. A file that can't be read is said so."""
    engine = dry_run.special_engine(session)
    head = {
        "session": session.name,
        "file_name": session.file_name,
        "status": session.status,
        "finished": session.status in FINISHED,
        "started_on": str(session.started_on or session.creation),
    }
    try:
        body = engine.summary(session) if engine else _data_import_summary(session)
    except FileProblem as e:
        from frappe_assistant_core.utils.import_retention import was_purged

        problem = (
            _("Its files were deleted after it ended (retention), so its rows can't be counted again.")
            if was_purged(session)
            else _("The file can't be read, so its rows can't be counted: {0}").format(str(e))
        )
        return {
            **head,
            "kind": "unreadable",
            "doctype": session.target_doctype,
            "label": _(session.target_doctype or "") or _("Unknown"),
            "problem": problem,
        }
    if body.get("erpnext") is not None:
        ledger = LEDGERS.get(body["kind"]) or body["doctype"]
        if not can_read_ledger(ledger, body["company"]):
            # the rows are the user's own file; ERPNext's totals are only for who may read them
            body["erpnext"] = {"problem": _cannot_read(ledger, body["company"])}
    return {**head, **body}


# -- the migration ----------------------------------------------------------------------------


def plan_sessions(plan: str) -> List[str]:
    """A migration plan's sessions, the plan's own first (#34549): a migration reported on its own,
    whatever its dates, without earlier runs of the same files."""
    names = frappe.get_list(
        dry_run.SESSION_DOCTYPE, filters={"migration_plan": plan}, pluck="name", order_by="creation asc"
    )
    if not names:
        raise frappe.DoesNotExistError(_("Migration plan {0} not found, or you can't read it.").format(plan))
    return names


def sessions_of(
    names: Optional[List[str]] = None,
    user: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> List[Any]:
    """The sessions to report on, oldest first, that the user may read: the ones named, else
    ``user``'s (the current user's by default) started between the dates when given. Cancelled
    ones are left out. Named sessions count whenever they started: generate_report fills in a
    fiscal year's dates by itself, and those must not hide a session the user asked for."""
    filters: List[Any] = [["status", "!=", "Cancelled"]]
    if names:
        filters.append(["name", "in", list(names)])
    else:
        filters.append(["user", "=", user or frappe.session.user])
        if from_date:
            filters.append(["creation", ">=", str(getdate(from_date))])
        if to_date:
            filters.append(["creation", "<", str(add_days(getdate(to_date), 1))])
    found = frappe.get_list(
        dry_run.SESSION_DOCTYPE,
        filters=filters,
        pluck="name",
        order_by="creation asc",
        limit_page_length=MAX_SESSIONS,
    )
    if names:
        missing = [name for name in names if name not in found]
        if missing:
            raise frappe.DoesNotExistError(
                _("Import session {0} not found, or you can't read it.").format(", ".join(missing))
            )
    return [frappe.get_doc(dry_run.SESSION_DOCTYPE, name) for name in found]


def build(sessions: List[Any]) -> Dict[str, Any]:
    """The sign-off report of ``sessions``: per DocType, the rows of the files and where each
    ended; the opening balances per company against the files' totals; and what stands in the
    way of signing off."""
    summaries = [session_summary(session) for session in sessions]
    report = {
        "generated_on": str(now_datetime()),
        "generated_by": frappe.session.user,
        "sessions": summaries,
        "doctypes": _per_doctype(summaries),
        "opening_balances": _opening_balances(summaries),
    }
    report["open_points"] = open_points(report)
    report["ready_to_sign"] = bool(summaries) and not report["open_points"]
    report["message"] = _message(report)
    return report


def _per_doctype(summaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_label: Dict[str, Dict[str, Any]] = {}
    for summary in summaries:
        if "rows" not in summary:
            continue
        entry = by_label.setdefault(
            summary["label"],
            {
                "label": summary["label"],
                "doctype": summary["doctype"],
                "sessions": [],
                "rows": {"source": 0, **{status: 0 for status in STATUSES}},
            },
        )
        entry["sessions"].append(summary["session"])
        for key, value in summary["rows"].items():
            entry["rows"][key] += value
    return list(by_label.values())


def _precision() -> int:
    return frappe.get_precision("GL Entry", "debit") or 2


def _opening_balances(summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Per company: stock value, receivables and payables against the files', and the trial
    balance at the latest cut-off, against the opening balances file when one was imported."""
    precision = _precision()
    companies: Dict[str, Dict[str, Any]] = {}
    for summary in summaries:
        balance = summary.get("balance")
        if not balance:
            continue
        company = companies.setdefault(summary["company"], {"cut_off": summary["cut_off"]})
        company["cut_off"] = max(company["cut_off"], summary["cut_off"])
        if balance == "trial_balance":
            company.setdefault("trial_balance_files", []).append(summary)
            continue
        measure = "value" if balance == "stock" else "amount"
        entry = company.setdefault(
            balance,
            {"sessions": [], "file": 0.0, "imported": 0.0, "erpnext": 0.0, "not_in": 0.0, "difference": 0.0},
        )
        entry["sessions"].append(summary["session"])
        entry["file"] += summary[measure]["source"]
        entry["imported"] += summary[measure]["imported"]
        entry["not_in"] += summary[measure]["source"] - summary[measure]["imported"]
        if summary["erpnext"].get("problem"):
            entry["problem"] = summary["erpnext"]["problem"]
            continue
        entry["erpnext"] += summary["erpnext"]["total"]
        # ERPNext against the file's rows that are in; what isn't in is shown apart.
        entry["difference"] += summary["erpnext"]["difference"]
    for name, company in companies.items():
        for balance in ("stock", "receivables", "payables"):
            entry = company.get(balance)
            if entry:
                for key in ("file", "imported", "erpnext", "not_in", "difference"):
                    entry[key] = flt(entry[key], precision)
                if entry.get("problem"):
                    entry["erpnext"] = entry["difference"] = None
        trial = trial_balance(name, company["cut_off"])
        files = company.pop("trial_balance_files", [])
        if files:
            trial["source"] = {
                "sessions": [f["session"] for f in files],
                "debit": flt(sum(f["debit"]["source"] for f in files), precision),
                "credit": flt(sum(f["credit"]["source"] for f in files), precision),
                "imported_debit": flt(sum(f["debit"]["imported"] for f in files), precision),
                "imported_credit": flt(sum(f["credit"]["imported"] for f in files), precision),
                "accounts_differing": sum(f["erpnext"].get("accounts_differing") or 0 for f in files),
                "differing": [row for f in files for row in f["erpnext"].get("differing") or []],
                "covered_differing": [
                    row for f in files for row in f["erpnext"].get("covered_differing") or []
                ],
            }
        company["trial_balance"] = trial
    return companies


def trial_balance(company: str, as_of: str) -> Dict[str, Any]:
    """ERPNext's trial balance of ``company`` at ``as_of``: total debits and credits, and what is
    left on the Temporary Opening account, which every opening entry goes through and which is
    zero once all of them are in. ``source`` is the opening balances file, when one was imported.
    Summed with frappe.qb: Frappe v16 refuses SQL functions in get_all's fields."""
    from frappe.query_builder.functions import Sum

    if not can_read_ledger("GL Entry", company):
        return {"as_of": as_of, "problem": _cannot_read("GL Entry", company)}
    precision = _precision()
    gle = frappe.qb.DocType("GL Entry")
    up_to = (gle.company == company) & (gle.is_cancelled == 0) & (gle.posting_date <= as_of)

    def sums(condition):
        row = (
            frappe.qb.from_(gle)
            .select(Sum(gle.debit).as_("debit"), Sum(gle.credit).as_("credit"))
            .where(condition)
        ).run(as_dict=True)[0]
        return flt(row.debit, precision), flt(row.credit, precision)

    debit, credit = sums(up_to)
    out = {
        "as_of": as_of,
        "debit": debit,
        "credit": credit,
        "difference": flt(debit - credit, precision),
        "source": None,
    }
    temporary = frappe.get_all(
        "Account", filters={"company": company, "account_type": "Temporary", "is_group": 0}, pluck="name"
    )
    if temporary:
        temp_debit, temp_credit = sums(up_to & gle.account.isin(temporary))
        out["temporary_opening"] = {
            "accounts": temporary,
            "balance": flt(temp_debit - temp_credit, precision),
        }
    return out


def _amount(value) -> str:
    """An amount in a sentence, written the site's way: 1,96,850.00 rather than 196850.0."""
    return fmt_money(flt(value), precision=_precision())


def open_points(report: Dict[str, Any]) -> List[str]:
    """What stands in the way of signing off, each a sentence."""
    points = []
    for summary in report["sessions"]:
        name = f"{summary['label']} ({summary['session']}, {summary.get('file_name') or ''})"
        if summary.get("problem"):
            points.append(_("{0}: {1}").format(name, summary["problem"]))
            continue
        if not summary["finished"]:
            points.append(_("{0} is {1}, not imported to the end.").format(name, _(summary["status"])))
        rows = summary["rows"]
        if rows["failed"]:
            points.append(_("{0}: {1} rows failed.").format(name, rows["failed"]))
        if rows["not_imported"]:
            points.append(_("{0}: {1} rows aren't imported yet.").format(name, rows["not_imported"]))
        erpnext = summary.get("erpnext") or {}
        if erpnext.get("problem"):
            points.append(_("{0}: {1}").format(name, erpnext["problem"]))
        if erpnext.get("difference"):
            points.append(
                _("{0}: ERPNext differs from the file's rows by {1}.").format(
                    name, _amount(erpnext["difference"])
                )
            )
        if erpnext.get("no_longer_submitted"):
            points.append(
                _("{0}: {1} documents made by the import were cancelled or deleted since.").format(
                    name, erpnext["no_longer_submitted"]
                )
            )
    for company, balances in report["opening_balances"].items():
        trial = balances.get("trial_balance") or {}
        if trial.get("problem"):
            points.append(_("{0}: the trial balance isn't checked. {1}").format(company, trial["problem"]))
        if trial.get("difference"):
            points.append(
                _("{0}: the trial balance at {1} doesn't balance (debit {2}, credit {3}).").format(
                    company, trial["as_of"], _amount(trial["debit"]), _amount(trial["credit"])
                )
            )
        source = trial.get("source") or {}
        if source.get("accounts_differing"):
            points.append(
                _("{0}: {1} accounts in ERPNext differ from the opening balances file.").format(
                    company, source["accounts_differing"]
                )
            )
        for row in source.get("covered_differing") or []:
            points.append(
                _(
                    "{0}: {1} is {2} in ERPNext but {3} in the opening balances file; the opening "
                    "invoices or opening stock don't add up to it."
                ).format(company, row["account"], _amount(row["erpnext_net"]), _amount(row["file_net"]))
            )
        temporary = (trial.get("temporary_opening") or {}).get("balance")
        if temporary:
            points.append(
                _(
                    "{0}: {1} is left on the Temporary Opening account at {2}; it is zero once every "
                    "opening balance is in."
                ).format(company, _amount(temporary), trial["as_of"])
            )
    return points


def _message(report: Dict[str, Any]) -> str:
    if not report["sessions"]:
        return _("No import sessions to report on.")
    rows = _row_totals(report)
    text = _(
        "{0} sessions: {1} rows in the files, {2} imported, {3} left out, {4} failed, {5} not imported yet."
    ).format(
        len(report["sessions"]),
        rows["source"],
        rows["imported"],
        rows["excluded"],
        rows["failed"],
        rows["not_imported"],
    )
    if rows["unchanged"]:
        text += " " + _("{0} rows were already as the file has them.").format(rows["unchanged"])
    if report["ready_to_sign"]:
        return text + " " + _("Everything is in and matches: ready to sign off.")
    return text + " " + _("{0} open points before sign-off.").format(len(report["open_points"]))


def _row_totals(report: Dict[str, Any]) -> Dict[str, int]:
    return {status: sum(d["rows"][status] for d in report["doctypes"]) for status in ("source", *STATUSES)}


# -- as an ERPNext report ---------------------------------------------------------------------

STATUS_TITLES = {"excluded": "Left out", "failed": "Failed", "not_imported": "Not imported"}


def columns() -> List[Dict[str, Any]]:
    money = {"fieldtype": "Float", "precision": 2, "width": 130}
    count = {"fieldtype": "Int", "width": 100}
    return [
        {"fieldname": "section", "label": _("Section"), "fieldtype": "Data", "width": 140},
        {"fieldname": "item", "label": _("Item"), "fieldtype": "Data", "width": 220},
        {
            "fieldname": "company",
            "label": _("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "width": 140,
        },
        {"fieldname": "source_rows", "label": _("Rows in the Files"), **count},
        {"fieldname": "imported_rows", "label": _("Imported"), **count},
        {"fieldname": "unchanged_rows", "label": _("Unchanged"), **count},
        {"fieldname": "left_out_rows", "label": _("Left Out"), **count},
        {"fieldname": "failed_rows", "label": _("Failed"), **count},
        {"fieldname": "not_imported_rows", "label": _("Not Imported"), **count},
        {"fieldname": "in_files", "label": _("In the Files"), **money},
        {"fieldname": "not_imported_amount", "label": _("Not Imported Amount"), **money},
        {"fieldname": "imported_amount", "label": _("Imported Rows Amount"), **money},
        {"fieldname": "in_erpnext", "label": _("In ERPNext"), **money},
        {"fieldname": "difference", "label": _("Difference"), **money},
        {"fieldname": "details", "label": _("Details"), "fieldtype": "Data", "width": 420},
    ]


def rows(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The report as one table, a section after another: records per DocType, why rows aren't
    in, opening balances, the trial balance, the open points and the sessions. The text comes
    from users' files, their reasons and ERPNext's messages, and Desk shows a report's cells and
    message as HTML: so every text is escaped here."""
    out = _rows(report)
    for row in out:
        for key in ("item", "details"):
            if row.get(key) not in (None, ""):
                row[key] = escape_html(cstr(row[key]))
    return out


def _rows(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The report as one table, a section after another: records per DocType, why rows aren't
    in, opening balances, the trial balance, the open points and the sessions."""
    out: List[Dict[str, Any]] = []
    for entry in report["doctypes"]:
        counts = entry["rows"]
        out.append(
            {
                "section": _("Records"),
                "item": entry["label"],
                "source_rows": counts["source"],
                "imported_rows": counts["imported"],
                "unchanged_rows": counts["unchanged"],
                "left_out_rows": counts["excluded"],
                "failed_rows": counts["failed"],
                "not_imported_rows": counts["not_imported"],
            }
        )
    column_of = {"excluded": "left_out_rows", "failed": "failed_rows", "not_imported": "not_imported_rows"}
    for summary in report["sessions"]:
        if summary.get("problem"):
            out.append(
                {"section": _("Why Not Imported"), "item": summary["label"], "details": summary["problem"]}
            )
            continue
        for status, title in STATUS_TITLES.items():
            for group in summary.get(status) or []:
                out.append(
                    {
                        "section": _("Why Not Imported"),
                        "item": "{}: {}".format(summary["label"], _(title)),
                        column_of[status]: group["count"],
                        "details": rows_of(group, summary.get("file_name") or summary["session"]),
                    }
                )
    titles = {"stock": _("Stock Value"), "receivables": _("Receivables"), "payables": _("Payables")}
    for company, balances in report["opening_balances"].items():
        for key, title in titles.items():
            entry = balances.get(key)
            if entry:
                out.append(
                    {
                        "section": _("Opening Balances"),
                        "item": title,
                        "company": company,
                        "in_files": entry["file"],
                        "not_imported_amount": entry["not_in"],
                        "imported_amount": entry["imported"],
                        "in_erpnext": entry["erpnext"],
                        "difference": entry["difference"],
                        "details": entry.get("problem"),
                    }
                )
        out += _trial_balance_rows(company, balances.get("trial_balance") or {})
    for number, point in enumerate(report["open_points"], start=1):
        out.append({"section": _("Open Points"), "item": str(number), "details": point})
    for summary in report["sessions"]:
        out.append(
            {
                "section": _("Sessions"),
                "item": summary["session"],
                "details": "{} | {} | {} | {}".format(
                    summary.get("file_name") or "",
                    summary["label"],
                    _(summary["status"]),
                    summary["started_on"][:16],
                ),
            }
        )
    return out


def _trial_balance_rows(company: str, trial: Dict[str, Any]) -> List[Dict[str, Any]]:
    section = _("Trial Balance")
    if trial.get("problem"):
        return [{"section": section, "item": trial["as_of"], "company": company, "details": trial["problem"]}]
    out = []
    source = trial.get("source")
    if source:
        for side in ("debit", "credit"):
            out.append(
                {
                    "section": section,
                    "item": _("Total {0} in the file").format(_(side)),
                    "company": company,
                    "in_files": source[side],
                    "imported_amount": source[f"imported_{side}"],
                    "not_imported_amount": flt(source[side] - source[f"imported_{side}"], _precision()),
                    "details": _(
                        "Rows not in the opening entry are left out, failed, or brought in by "
                        "the opening invoices and stock."
                    ),
                }
            )
        differing = source["differing"] + source["covered_differing"]
        out.append(
            {
                "section": section,
                "item": _("Accounts that differ from the file: {0}").format(len(differing)),
                "company": company,
                "details": "; ".join(
                    _("{0}: file {1}, ERPNext {2}").format(
                        row["account"], _amount(row["file_net"]), _amount(row["erpnext_net"])
                    )
                    for row in differing[:20]
                )
                or _("Every account matches the file at {0}.").format(trial["as_of"]),
            }
        )
    else:
        out.append(
            {
                "section": section,
                "item": _("Opening balances file"),
                "company": company,
                "details": _("No opening balances were imported, so there is no file to compare with."),
            }
        )
    out.append(
        {
            "section": section,
            "item": _("ERPNext debit and credit at {0}").format(trial["as_of"]),
            "company": company,
            "in_erpnext": trial["debit"],
            "difference": trial["difference"],
            "details": _("Debit {0}, credit {1}.").format(_amount(trial["debit"]), _amount(trial["credit"])),
        }
    )
    if "temporary_opening" in trial:
        out.append(
            {
                "section": section,
                "item": _("Left on Temporary Opening"),
                "company": company,
                "in_erpnext": trial["temporary_opening"]["balance"],
                "difference": trial["temporary_opening"]["balance"],
                "details": _("Zero once every opening balance is in."),
            }
        )
    return out


def summary_cards(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    totals = _row_totals(report)
    return [
        {"value": totals["source"], "label": _("Rows in the Files"), "datatype": "Int"},
        {"value": totals["imported"], "label": _("Imported"), "datatype": "Int", "indicator": "Green"},
        {"value": totals["excluded"], "label": _("Left Out"), "datatype": "Int", "indicator": "Blue"},
        {
            "value": totals["failed"],
            "label": _("Failed"),
            "datatype": "Int",
            "indicator": "Red" if totals["failed"] else "Green",
        },
        {
            "value": totals["not_imported"],
            "label": _("Not Imported"),
            "datatype": "Int",
            "indicator": "Orange" if totals["not_imported"] else "Green",
        },
        {
            "value": _("Yes") if report["ready_to_sign"] else _("No"),
            "label": _("Ready to Sign Off"),
            "datatype": "Data",
            "indicator": "Green" if report["ready_to_sign"] else "Red",
        },
    ]


SECTIONS = ("Records", "Why Not Imported", "Opening Balances", "Trial Balance", "Open Points", "Sessions")


def _value(column: Dict[str, Any], value) -> str:
    if value is None or value == "":
        return ""
    if column["fieldtype"] == "Float":
        return fmt_money(flt(value), precision=column.get("precision", 2))
    return cstr(value).replace("|", "\\|").replace("\n", " ")


def document(report: Dict[str, Any]) -> str:
    """The whole report as a markdown document, for generate_document to make the PDF: the same
    rows and numbers as the report, so nothing is typed out again."""
    cols, table = columns(), rows(report)
    cards = summary_cards(report)
    out = [
        "**"
        + _("Generated on {0} by {1}.").format(
            report["generated_on"][:16], escape_html(report["generated_by"])
        )
        + "**",
        "",
        report["message"],
        "",
        " · ".join(f"{card['label']}: {card['value']}" for card in cards),
    ]
    for title in SECTIONS:
        section_rows = [row for row in table if row.get("section") == _(title)]
        if not section_rows:
            continue
        shown = [
            c
            for c in cols
            if c["fieldname"] != "section"
            and any(r.get(c["fieldname"]) not in (None, "") for r in section_rows)
        ]
        out += ["", f"## {_(title)}", ""]
        out.append("| " + " | ".join(c["label"] for c in shown) + " |")
        out.append(
            "|" + "|".join("---:" if c["fieldtype"] in ("Int", "Float") else "---" for c in shown) + "|"
        )
        for row in section_rows:
            out.append("| " + " | ".join(_value(c, row.get(c["fieldname"])) for c in shown) + " |")
    out += [
        "",
        "## " + _("Sign-off"),
        "",
        _("Name:") + " ______________________",
        "",
        _("Date:") + " ______________________",
    ]
    return "\n".join(out) + "\n"


def scope(filters, plan: str, names: List[str], count: int) -> str:
    """The sentence that says what the report covers."""
    files = _("1 file") if count == 1 else _("{0} files").format(count)
    if plan:
        return _("Scope: migration plan {0}, {1}.").format(plan, files)
    if names:
        return _("Scope: the sessions {0}.").format(", ".join(names))
    return _("Scope: {0}'s sessions started from {1} to {2}, {3}.").format(
        filters.get("user") or frappe.session.user,
        filters.get("from_date") or _("the first"),
        filters.get("to_date") or _("today"),
        files,
    )


def execute(filters: Optional[Dict[str, Any]] = None):
    """The Migration Sign-off report: columns, rows, the headline and the summary cards. With the
    ``document`` filter, the message is the whole report as a document, for the PDF."""
    filters = frappe._dict(filters or {})
    names = [name.strip() for name in cstr(filters.get("import_session")).split(",") if name.strip()]
    plan = cstr(filters.get("migration_plan")).strip() if not names else ""
    if plan:
        names = plan_sessions(plan)
    sessions = sessions_of(
        names or None, filters.get("user"), filters.get("from_date"), filters.get("to_date")
    )
    report = build(sessions)
    # What the report covers, first: a date range takes in earlier test runs, a plan doesn't (#34549)
    report["message"] = scope(filters, plan, names, len(sessions)) + " " + report["message"]
    message = document(report) if cint(filters.get("document")) else report["message"]
    return columns(), rows(report), message, None, summary_cards(report)


def rows_of(group: Dict[str, Any], file_name: str) -> str:
    """'Closed shop (row 3 of customers.csv)': a group of rows left out, failed or not imported."""
    text = _("{0} (row {1} of {2})") if group["count"] == 1 else _("{0} (rows {1} of {2})")
    return text.format(group["reason"], group["rows"], file_name)
