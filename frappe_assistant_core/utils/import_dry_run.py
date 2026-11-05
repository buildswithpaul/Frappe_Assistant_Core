# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
The dry run (#33990): every row of an import session's file checked exactly the way
Data Import would import it, with nothing written.

Rows are parsed by Data Import's own ImportFile and tried by its own Importer.process_doc
(an insert or an update, or the DocType's import provider on Frappe 16), each inside a
savepoint that is rolled back. That runs mandatory, link, duplicate and controller checks,
which Data Import's preview does not. Emails, background jobs, realtime events, commits and
commit callbacks are held back while a row is tried.

The full per-row list is attached to the session as a file; the model gets only the
grouped summary.
"""

import copy
import hashlib
import importlib
import json
import re
import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional, Tuple

import frappe
import frappe.realtime
import frappe.utils.background_jobs
from frappe import _
from frappe.core.doctype.data_import.importer import (
    INSERT,
    INVALID_VALUES,
    Importer,
    ImportFile,
    df_as_json,
    get_autoname_field,
)
from frappe.query_builder import DocType
from frappe.utils import cint, cstr, now_datetime, strip_html
from rq import Queue

from frappe_assistant_core.assistant_core.doctype.fac_import_session.fac_import_session import engine_session
from frappe_assistant_core.utils import import_keys
from frappe_assistant_core.utils.import_session import (
    FileProblem,
    attach_session_copy,
    discard_session_copy,
    import_target_problem,
    is_session_copy,
    read_sheet_rows,
    read_spreadsheet,
    readable_session_file,
    row_limit_problem,
    save_session_copy,
    shown_cell,
)

SESSION_DOCTYPE = "FAC Import Session"
BACKGROUND_ROWS = 500  # larger files are checked in a background job
PROGRESS_EVERY = 100
EXAMPLES_PER_GROUP = 3
VALUES_KEPT = 20  # a group of refusals keeps this many of the values its message quoted
QUOTED = "…"  # what a row's own value in a refusal's message reads as, so rows share a group
STALE_AFTER_SECONDS = 2 * 60 * 60  # a run this old without finishing is taken as dead
SAVEPOINT = "fac_dry_run_row"
STAND_IN_SAVEPOINT = "fac_dry_run_stand_in"
SAMPLES_KEPT = 5  # records whose old and new values an update's check shows
# After an import, what it didn't get in is checked again on its own (#33994): rows that failed,
# or a corrected file of them, or of the rows left out of a completed one.
RUNNABLE_STATUSES = (
    "Mapped",
    "Dry Run Failed",
    "Ready to Import",
    "Partially Completed",
    "Failed",
    "Completed",
)

_UNSET = object()

#: DocTypes whose insert can't be held back or rolled back. Sites add more with the
#: ``fac_dry_run_unsafe_doctypes`` site config key (a list of DocType names).
UNSAFE_DOCTYPES = {
    "DocType": "creating it changes the database schema, which can't be rolled back",
    "Custom Field": "creating it changes the database schema, which can't be rolled back",
    "Payment Request": "it can contact the payment gateway as it is created",
    "File": "saving it can move or write the file on disk, which can't be rolled back",
    "Website Theme": "saving it deletes and writes the theme's CSS files, which can't be rolled back",
}

#: Records named for a row that matches more than one: the rest are counted (a match field
#: shared by thousands, a Customer Group say, would put every name in each reply).
MAX_MATCHES_NAMED = 10

CAUSE_MISSING_LINK = "Missing link"
CAUSE_LATER_FILE = "Comes from a later file"  # a migration plan's file imported after this one
CAUSE_BAD_OPTION = "Not an allowed option"
CAUSE_BAD_DATE = "Wrong date format"
CAUSE_BAD_VALUE = "Invalid value"
CAUSE_DUPLICATE_IN_FILE = "Duplicate in the file"
CAUSE_ALREADY_EXISTS = "Already in ERPNext"
CAUSE_SHARED_VALUE = "Shared value"  # a warning, never a group: the rows stay ready
CAUSE_REJECTED = "Rejected by ERPNext"
CAUSE_REQUIRED_MISSING = "Required value missing"  # a new record's required or naming field blank
#: What a row refused with an internal error rather than a message is told (#34537): never Python's
#: class or text. The full error goes to the Error Log (#34417); the group's rows are the example.
UNEXPLAINED = "ERPNext refused these rows for a reason I couldn't read. The full error is in the Error Log."
INTERNAL_ERROR_TITLE = "FAC import check: internal error"
# An update (#34005): the row's record isn't found, is found more than once, or another row has it.
CAUSE_NO_MATCH = "No match"
CAUSE_MANY_MATCHES = "More than one match"
CAUSE_SAME_RECORD = "Same record twice"
CAUSE_FETCHED = "Comes from a linked record"  # a fetch_from field: saving copies it back


class DryRunProblem(Exception):
    """The dry run can't start. The message is shown to the user."""


# -- can it run ------------------------------------------------------------------------


def check_status(session) -> None:
    """Raise DryRunProblem when ``session``'s status lets nothing be checked, or a file linked."""
    if session.status == "File Read":
        raise DryRunProblem(_("Map the columns first, with set_column_mapping."))
    if session.status not in RUNNABLE_STATUSES:
        raise DryRunProblem(_("This session is {0}, so it can't be checked again.").format(_(session.status)))
    if nothing_left(session):
        raise DryRunProblem(_(NOTHING_LEFT))


NOTHING_LEFT = (
    "Every row of this file is imported, so there is nothing to check or import again. To import "
    "it again or as something else, start a new import session."
)


def nothing_left(session) -> bool:
    """A Completed session whose every row is in ERPNext (#34402): rows left out of it, or that
    failed, are still checked again on their own (#33994), but with none there is nothing to do."""
    if session.status != "Completed":
        return False
    from frappe_assistant_core.utils import import_failures

    file_doc = _results_file(session)
    rows = ((frappe.parse_json(file_doc.get_content()) or {}) if file_doc else {}).get("rows") or []
    if not rows:
        return False
    imported = import_failures.imported_rows(session)
    return all(row.get("status") in ("imported", "unchanged") or row.get("row") in imported for row in rows)


def special_engine(session):
    """The engine of a session that isn't imported through Data Import (opening stock, opening
    invoices, opening balances), or None. Each keeps its settings under its own key in
    template_options."""
    from frappe_assistant_core.utils import import_opening_balances as opening_balances
    from frappe_assistant_core.utils import import_opening_invoices as opening_invoices
    from frappe_assistant_core.utils import import_opening_stock as opening_stock

    for engine in (opening_stock, opening_invoices, opening_balances):
        if engine.settings(session):
            return engine
    return None


def check_can_run(session) -> None:
    """Raise DryRunProblem when ``session`` can't be checked yet, saying what to do."""
    problem = row_limit_problem(row_count(session))  # a corrected file can be larger
    if problem:
        raise DryRunProblem(problem)
    engine = special_engine(session)
    if engine:
        return engine.check_can_run(session)
    check_status(session)
    if not column_to_field_map(session):
        raise DryRunProblem(_("Map the columns first, with set_column_mapping."))
    problem = import_target_problem(session.target_doctype, session.import_type or INSERT)
    if problem:
        raise DryRunProblem(problem)
    reason = unsafe_reason(session.target_doctype)
    if reason:
        raise DryRunProblem(
            _("A dry run can't be done for {0}: {1}. Import it with care.").format(
                session.target_doctype, reason
            )
        )
    if not session.source_file:
        raise DryRunProblem(
            _(
                "The file {0} is only in the chat, so its rows can't be checked here. Upload it "
                "in File Manager (or attach it in FAC Chat) and call dry_run_import again with "
                "its file_id. The mapping is kept."
            ).format(session.file_name)
        )


def unsafe_reason(doctype: str) -> Optional[str]:
    if doctype in UNSAFE_DOCTYPES:
        return _(UNSAFE_DOCTYPES[doctype])
    if doctype in (frappe.conf.get("fac_dry_run_unsafe_doctypes") or []):
        return _("this site marks its side effects as ones that can't be held back")
    return None


def link_site_file(session, file_doc, sheet_url: Optional[str] = None) -> None:
    """Give a session whose file stayed in the chat the same file, uploaded to the site; or a
    corrected one, as the failed-rows file came back (#33994), or a fresh copy of its Google
    Sheet (#34006): the same columns, perhaps with the ones that file added after them, which
    are not imported. ``file_doc`` is a File the user may read (find_site_file), or the copy
    ``sheet_url`` was read into. Like a new session, the session reads its own copy of it (#34405)."""
    from frappe_assistant_core.utils.import_failures import own_columns

    def read_with(header_row=None):
        try:
            return read_spreadsheet(file_doc, session.sheet or None, header_row=header_row, keep_rows=True)
        except FileProblem:
            # A corrected file saved from the CSV FACO gave has its own sheet name: its columns decide.
            return read_spreadsheet(file_doc, header_row=header_row, keep_rows=True)

    read = read_with()
    # Older sessions stored their headings as written; the copy's are unique (#34405).
    expected = unique_headers(_session_columns(session))
    stored = next(
        (s for s in frappe.parse_json(session.sheets or "[]") or [] if s.get("name") == session.sheet), {}
    )
    if (
        expected
        and own_columns(read.chosen.columns) != own_columns(expected)
        and stored.get("header_row", 1) > 1
    ):
        # The guess missed the headings: the corrected file has the title rows the first one had (#34541)
        try:
            read = read_with(stored["header_row"])
        except FileProblem:
            pass
    columns = read.chosen.columns
    if expected and own_columns(columns) != own_columns(expected):
        raise FileProblem(
            _("This file's columns don't match the session's. Expected: {0}. Found: {1}.").format(
                ", ".join(own_columns(expected)), ", ".join(columns)
            )
        )
    # Refused before the session changes: it keeps its file, and the rows it leaves out (#34003).
    problem = row_limit_problem(read.chosen.row_count)
    if problem:
        raise FileProblem(problem)
    if expected:
        options = frappe.parse_json(session.template_options or "{}") or {}
        mapping = {
            k: v for k, v in (options.get("column_to_field_map") or {}).items() if int(k) < len(columns)
        }
        for position in range(len(own_columns(columns)), len(columns)):
            mapping[str(position)] = "Don't Import"
        options["column_to_field_map"] = mapping
        session.template_options = frappe.as_json(options)
    for link in session.data_imports:
        # A Data Import recorded before source_file was kept is of the file the session had.
        link.source_file = link.source_file or session.source_file
    copy = save_session_copy(file_doc.file_name, read.chosen)
    replaced = session.source_file
    session.source_file = copy.name
    session.original_file = None if sheet_url else file_doc.name
    session.file_source = "Google Sheet" if sheet_url else "Site File"
    session.source_url = sheet_url
    session.sheet = read.chosen.name  # a workbook saved as CSV, say, has no sheet names
    session.sheets = frappe.as_json([s.as_dict() for s in read.sheets])
    if sheet_url:
        linked = _("Copied the Google Sheet again for checking.")
    else:
        linked = _("Linked {0} from this site for checking.").format(file_doc.file_name)
    session.log_step("Link File", "Success", linked)
    try:
        session.save()
    except Exception:
        discard_session_copy(copy)  # the session kept its file
        raise
    attach_session_copy(copy, session.name)
    # The copy it replaced, unless a Data Import still names it, doesn't stay on disk (#34539).
    # Only the session's own copy: an older session's source_file was the user's own file.
    old = (
        frappe.db.get_value("File", replaced, ["file_name", "attached_to_name"], as_dict=True)
        if replaced
        else None
    )
    if (
        old
        and old.attached_to_name == session.name
        and is_session_copy(old)
        and not any(link.source_file == replaced for link in session.data_imports)
    ):
        discard_session_copy(frappe._dict(name=replaced))


def check_cost(session) -> int:
    """What checking the session costs, counted in rows (#34407): a row of a submittable DocType
    counts twice (its controller works out totals, taxes and stock), three times when it is
    submitted too, as an opening import's always is. Above BACKGROUND_ROWS, it is checked in the
    background, so a slow file can't run past the request's time limit."""
    weight = 1
    if special_engine(session):
        weight = 3
    elif session.target_doctype and frappe.get_meta(session.target_doctype).is_submittable:
        weight = 3 if session.submit_after_import else 2
    return row_count(session) * weight


def row_count(session) -> int:
    for sheet in frappe.parse_json(session.sheets or "[]") or []:
        if sheet.get("name") == session.sheet:
            return int(sheet.get("row_count") or 0)
    return 0


def is_running(session) -> bool:
    progress = frappe.parse_json(session.progress or "{}") or {}
    if progress.get("step") != "Dry Run" or progress.get("state") not in ("queued", "running"):
        return False
    started = progress.get("started_on")
    if not started:
        return True
    age = (now_datetime() - frappe.utils.get_datetime(started)).total_seconds()
    return age < STALE_AFTER_SECONDS


def check_running() -> str:
    return _(
        "This file is being checked in the background. Wait for the check to finish (call "
        "dry_run_import to see where it is), then try again."
    )


def column_to_field_map(session) -> Dict[str, str]:
    options = frappe.parse_json(session.template_options or "{}") or {}
    return dict(options.get("column_to_field_map") or {})


def _session_columns(session) -> List[str]:
    for sheet in frappe.parse_json(session.sheets or "[]") or []:
        if sheet.get("name") == session.sheet:
            return [str(c) for c in sheet.get("columns") or []]
    return []


# -- background ------------------------------------------------------------------------


def enqueue(session) -> None:
    session.db_set("progress", _progress("queued", 0, row_count(session)), update_modified=False)
    frappe.enqueue(
        "frappe_assistant_core.utils.import_dry_run.run_job",
        queue="long",
        timeout=4 * 60 * 60,
        job_id=f"fac_dry_run::{session.name}",
        deduplicate=True,
        enqueue_after_commit=True,
        session_name=session.name,
        user=frappe.session.user,
    )


def run_job(session_name: str, user: str) -> None:
    """Background job: the dry run as the user who asked for it."""
    from frappe_assistant_core.utils.import_fixes import check

    frappe.set_user(user)  # nosemgrep: frappe-setuser — the job runs as the user who asked for the check
    try:
        check(session_name, commit_progress=True)  # the run, explained for the model to read later
        frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        session = engine_session(session_name)
        session.progress = _progress("failed", 0, row_count(session))
        session.log_step("Dry Run", "Failed", _("The check stopped: {0}").format(_message_of(e)))
        session.save()
        frappe.db.commit()
        frappe.log_error(title=_("FAC Import dry run failed"), message=frappe.get_traceback())


def _progress(state: str, done: int, total: int) -> str:
    return frappe.as_json(
        {"step": "Dry Run", "state": state, "done": done, "total": total, "started_on": str(now_datetime())}
    )


# -- the dry run -----------------------------------------------------------------------


def run(session_name: str, commit_progress: bool = False, in_background: bool = False) -> Dict[str, Any]:
    """Check every row of the session's file. Stores the result on the session and
    returns the summary, with up to three example rows per group for the model.
    ``in_background``: the caller is already a background job (a plan's), so a file of more than
    BACKGROUND_ROWS rows is checked here. Separate from ``commit_progress``: that one also
    commits, which would release the plan step's savepoint."""
    from frappe_assistant_core.utils.import_failures import imported_rows
    from frappe_assistant_core.utils.import_fixes import apply_value_maps

    session = engine_session(session_name)
    file_doc = readable_session_file(session)
    sheet_rows = read_sheet_rows(file_doc, session.sheet or None)
    _real_size(len(sheet_rows) - 1, in_background=commit_progress or in_background)
    # What is checked is the session as it is now: a change saved while the check runs (a remap
    # in another request) must not be stamped as checked when the result is stored.
    _checking()[session_name] = fingerprint(session, file_doc)
    engine = special_engine(session)
    if engine:
        return engine.run(session_name, commit_progress=commit_progress)
    from frappe_assistant_core.utils import import_update

    rows = apply_value_maps(session, sheet_rows)
    matches, column_map = None, None
    if import_update.is_update(session) and import_update.match_fields(session):
        matches = import_update.match_records(session, rows)
        single = {n: names[0] for n, names in matches.items() if len(names) == 1}
        rows, column_map = import_update.with_ids(session, rows, single)
    import_file = _parse(session, file_doc, rows, column_map)
    payloads = import_file.get_payloads_for_import()

    from frappe_assistant_core.utils import import_plan

    checker = _Checker(
        session,
        import_file,
        matches,
        coming=import_plan.planned_names(session),
        later=import_plan.later_names(session),
    )
    excluded = _excluded_rows(session)
    imported = imported_rows(session)
    total = len(payloads)
    for done, payload in enumerate(payloads, start=1):
        checker.check(payload, excluded, imported)
        if commit_progress and done % PROGRESS_EVERY == 0:
            frappe.db.set_value(
                SESSION_DOCTYPE,
                session_name,
                "progress",
                _progress("running", done, total),
                update_modified=False,
            )
            commit_progress_now()

    return _store(session_name, file_doc, checker, total)


def commit_progress_now() -> None:
    """The check job's progress, committed so the session shows it (run_job: the job's transaction
    holds nothing else). A check inside a request or a migration plan never commits: the caller's
    transaction, a plan step's savepoint included, stays whole. No commit is needed to free a
    naming series either: a row being tried never locks one (_held_series, #34401)."""
    frappe.db.commit()  # nosemgrep: frappe-manual-commit — the check job's own transaction


def only_mapped(column_map: Dict[str, str], width: int) -> Dict[str, str]:
    """``column_map`` with every one of ``width`` columns it doesn't map set to Don't Import.
    Data Import maps a column it isn't told about by its header, so a column the user left
    unmapped would otherwise be checked and imported anyway."""
    out = dict(column_map)
    for position in range(width):
        if not out.get(str(position)):
            out[str(position)] = "Don't Import"
    return out


def unique_headers(header: List[Any]) -> List[str]:
    """The heading row with a repeated heading made unique ("Name", "Name (2)"): Data Import
    skips a column whose heading it has seen, even one mapped by its position. Positions, and
    so the mapping, are unchanged."""
    seen, out = set(), []
    for title in header:
        text = cstr(title).strip()
        unique, n = text, 1
        while unique in seen:
            n += 1
            unique = f"{text} ({n})"
        seen.add(unique)
        out.append(unique if unique != text else title)
    return out


def _parse(session, file_doc, rows, column_map=None) -> ImportFile:
    if rows:
        rows = [unique_headers(rows[0]), *rows[1:]]
    options = frappe._dict(frappe.parse_json(session.template_options or "{}") or {})
    if column_map is not None:
        options.column_to_field_map = column_map
    options.column_to_field_map = frappe._dict(
        only_mapped(options.get("column_to_field_map") or {}, len(rows[0]) if rows else 0)
    )
    try:
        return _SessionRows(session.target_doctype, file_doc.file_url, rows, options, session.import_type)
    except frappe.ValidationError as e:
        raise FileProblem(_message_of(e)) from e


class _SessionRows(ImportFile):
    """Data Import's own parser, given the rows of the session's chosen sheet."""

    def __init__(self, doctype, file_url, rows, template_options, import_type):
        self._rows = rows
        super().__init__(doctype, file_url, template_options, import_type)

    def get_data_from_template_file(self):
        return self._rows


class _SessionImporter(Importer):
    """Data Import's own Importer, for the session's rows as _SessionRows parsed them, with a Data
    Import that is never saved: its import type and submit-after-import are the session's."""

    def __init__(self, session, import_file: ImportFile):
        data_import = frappe.new_doc("Data Import")
        data_import.update(
            {
                "reference_doctype": session.target_doctype,
                "import_type": session.import_type or INSERT,
                "submit_after_import": session.submit_after_import,
                "mute_emails": 1,
            }
        )
        # What Importer.__init__ sets, but with the rows already parsed: it would read the file
        # again from disk, without the session's value maps.
        self.doctype = session.target_doctype
        self.console = False
        self.use_sniffer = False
        self.blocked_by_warnings = False
        self.data_import = data_import
        self.template_options = import_file.template_options
        self.import_type = data_import.import_type
        self.import_file = import_file
        # Frappe's own setup for an import. On Frappe 16 it finds the DocType's import provider
        # and a tree's parents named by their title, which process_doc reads. It also sets the
        # import flags, which held_back() sets while a row is tried: they are put back here.
        flags = {name: frappe.flags.get(name) for name in ("in_import", "mute_emails")}
        try:
            self.before_import()  # the Data Import is unsaved, so its db_set writes nothing
        finally:
            frappe.flags.update(flags)

    def try_row(self, doc) -> Any:
        """The record ``doc`` makes or changes, through Data Import's own process_doc: Frappe 15
        returns it, Frappe 16 returns it with the action taken."""
        result = self.process_doc(doc)
        return result[0] if isinstance(result, tuple) else result


def _value_warnings(header, doctype: str) -> Dict[int, List[Dict[str, Any]]]:
    """Row number → the warnings Frappe 15 gives a row for a Link or Select value it can't use.
    Frappe 16 gives them once per column instead, with its rows (Column.invalid_value_items), and
    keeps the value in the parsed record. Empty on Frappe 15, whose rows carry their own."""
    out: Dict[int, List[Dict[str, Any]]] = {}

    def warn(row_number, column):
        out.setdefault(row_number, []).append(
            {"row": row_number, "field": df_as_json(column.df), "message": _("Value missing")}
        )

    # The names and titles of the file's own records (Frappe 16)
    in_file = set()
    for refs in (getattr(header, "import_ids", None), getattr(header, "import_aliases", None)):
        in_file |= set(refs or ())
    alias_field = getattr(header, "tree_alias_field", None)
    for column in header.columns:
        items = getattr(column, "invalid_value_items", None)
        if not column.df or column.skip_import or items is None:
            continue
        for item in items:
            for row_number in item["rows"]:
                warn(row_number, column)
        if column.df.options != doctype or not getattr(column, "import_refs", None):
            continue
        # A tree's parent named by a row of the same file isn't reported, as that row is imported
        # first. Frappe 15 reports it, and the check passes it only once that row is ready: so here.
        missing = {}
        for value, row_number in zip(column.column_values, column.value_row_numbers):
            value = cstr(value).strip()
            if value in in_file:
                missing.setdefault(value, []).append(row_number)
        for value, row_numbers in missing.items():
            if frappe.db.exists(doctype, value) or (
                alias_field and frappe.db.exists(doctype, {alias_field: value})
            ):
                continue
            for row_number in row_numbers:
                warn(row_number, column)
    return out


def _field_key(warning: Dict[str, Any]) -> Tuple[Any, Any]:
    field = warning["field"]
    return field.get("fieldname"), field.get("parent")


def _provider_warnings(importer, import_file) -> Dict[Optional[int], List[Dict[str, Any]]]:
    """Row number (None for the whole file) → what the DocType's import provider (Frappe 16)
    finds wrong with the file. Data Import refuses to start while any is not "info"."""
    provider = getattr(importer, "provider", None)
    out: Dict[Optional[int], List[Dict[str, Any]]] = {}
    for warning in (provider.validate(import_file) or []) if provider else []:
        if warning.get("type") != "info":
            row = warning.get("row")
            out.setdefault(int(row) if row else None, []).append(warning)
    return out


def _excluded_rows(session) -> set:
    value = frappe.parse_json(session.excluded_rows or "[]") or []
    return {int(row) for row in value if isinstance(row, (int, str)) and str(row).isdigit()}


class _Checker:
    """Checks payloads one by one and collects the groups and the per-row list."""

    def __init__(self, session, import_file, matches=None, coming=None, later=None):
        self.doctype = session.target_doctype
        self.import_type = session.import_type or INSERT
        header = self.header = import_file.header
        self.importer = _SessionImporter(session, import_file)
        self.value_warnings = _value_warnings(header, self.doctype)
        self.provider_warnings = _provider_warnings(self.importer, import_file)
        # Frappe 16 lets a tree's row name its parent by the parent's title (an Account's name
        # without the company's abbreviation): None where Data Import doesn't.
        self.alias_field = getattr(header, "tree_alias_field", None)
        self.key_df = _key_field(session, header)
        self.seen_keys: Dict[str, int] = {}
        # The field ERPNext names the record after, by a setting (#34398): a repeat in the file fails
        self.named_df = None if self.key_df else _named_field(session, header)
        self.seen_named: Dict[str, int] = {}
        # The title field, when it isn't the key: rows sharing its value are a warning, not a failure
        self.title_df = _title_field(session, header, self.key_df or self.named_df)
        # A new record's mapped fields it can't be saved without: blank, the row is its own group
        self.required = _required_fields(session, header) if self.import_type == INSERT else []
        self.seen_titles: Dict[str, int] = {}
        self.shared_rows: List[int] = []
        self.groups: Dict[Tuple, Dict[str, Any]] = {}
        self.rows: List[Dict[str, Any]] = []
        self.matches = matches  # None unless updating on match fields: row → matching records
        self.seen_records: Dict[str, int] = {}
        # A row may link to a record a row higher up the file creates (a tree's parent): Data
        # Import is run a level at a time for such a file (import_run), so that link is no problem.
        self.self_links = _self_links(self.doctype) if self.import_type == INSERT and matches is None else []
        # Casefolded name (and title, where Data Import takes one) → the ready row that creates it
        self.planned: Dict[str, Dict[str, Any]] = {}
        # In a migration plan: DocType → casefolded name → the earlier file (or the plan) that creates
        # it, and the same for the files imported after this one (import_plan).
        self.coming: Dict[str, Dict[str, str]] = coming or {}
        self.later: Dict[str, Dict[str, str]] = later or {}
        # Fields an old ID column is mapped to (#34244): a value left in them is an ID not imported yet
        self.translated = import_keys.translated_fields(session)
        self.preview = {"records_changing": 0, "fields_changing": 0, "by_field": {}, "samples": []}
        if matches is not None:
            from frappe_assistant_core.utils import import_update

            self.key_label = import_update.key_label(session)

    def check(self, payload, excluded: set, imported: set = frozenset()) -> None:
        row_numbers = [row.row_number for row in payload.rows]
        if imported.intersection(row_numbers):  # already in ERPNext, from an earlier import
            self.rows += [{"row": n, "status": "imported"} for n in row_numbers]
            return
        if excluded.intersection(row_numbers):
            self.rows += [{"row": n, "status": "excluded"} for n in row_numbers]
            return

        needs = self._needs(payload)
        from_files = self._from_earlier_files(payload)
        problems = self._match_problems(payload) if self.matches is not None else []
        if not problems:
            problems = self._parse_problems(payload, needs, from_files)
            # Checked beside the row's other problems too: a duplicate under a row with a typo would
            # otherwise show only once the typo is fixed, a second round of questions.
            problems += self._duplicate_problems(payload)
            problems += self._fetched_problems(payload)
            problems += self._required_problems(payload, {info.get("field") for _key, info in problems})
        record, changed = self._record(payload), []
        if not problems and record:
            from frappe_assistant_core.utils import import_update

            changed = import_update.changes(self.doctype, record, payload.doc)
            if not changed:  # Data Import would fail it: "No changes to update"
                self.rows += [{"row": n, "status": "unchanged", "record": record} for n in row_numbers]
                return
        created = None
        if not problems:
            problems, created = self._insert_problems(payload, needs, from_files)
        if record and _no_changes(problems):  # Frappe saw no change the plan did: nothing to do
            self.rows += [{"row": n, "status": "unchanged", "record": record} for n in row_numbers]
            return

        if not problems:
            extra = {"record": record} if record else {}
            if needs:  # imported once the rows it needs are (import_run)
                extra["after"] = sorted(entry["row"] for entry in needs)
            if from_files:  # imported once those files are (import_plan)
                extra["after_files"] = sorted({link["file"] for link in from_files.values()})
                extra["needs"] = sorted({link["value"] for link in from_files.values()})
            if created:  # what a later file of a migration plan may link to
                extra["name"] = created
            self.rows += [{"row": n, "status": "ready", **extra} for n in row_numbers]
            if created and self.self_links:
                entry = {
                    "row": row_numbers[0],
                    "name": created,
                    "alias": self._alias(payload),
                    "doc": _with_links(payload.doc, needs),
                    "needs": needs,
                }
                self.planned[created.casefold()] = entry
                if entry["alias"]:
                    self.planned.setdefault(entry["alias"].casefold(), entry)
            if record:
                self._add_to_preview(payload.rows[0].row_number, record, changed)
            return
        ids = [self._group(key, info, payload) for key, info in problems]
        # A failing row still names the record it means to create, when its name comes from one of
        # its fields: a later file of the plan counts it as coming. Whether it comes is settled when
        # its file is imported (the fix the user picks, else the plan's failure rule).
        named = self._intended_name(payload)
        extra = {"name": named} if named else {}
        self.rows += [{"row": n, "status": "failed", "groups": ids, **extra} for n in row_numbers]

    # An update: the row's record, found on the match fields.
    def _record(self, payload) -> Optional[str]:
        if self.matches is None:
            return None
        names = self.matches.get(payload.rows[0].row_number) or []
        return names[0] if len(names) == 1 else None

    def _match_problems(self, payload) -> List[Tuple[Tuple, Dict]]:
        names = self.matches.get(payload.rows[0].row_number) or []
        if len(names) == 1:
            return []
        info = {"label": self.key_label}
        if not names:
            message = _("No {0} has this {1}.").format(_(self.doctype), self.key_label)
            return [((CAUSE_NO_MATCH,), {**info, "cause": CAUSE_NO_MATCH, "message": message})]
        key = tuple(sorted(names))
        shown = ", ".join(key[:MAX_MATCHES_NAMED])
        if len(key) > MAX_MATCHES_NAMED:
            shown = _("{0} and {1} more").format(shown, len(key) - MAX_MATCHES_NAMED)
        message = _("{0} {1} records have this {2}: {3}.").format(
            len(names), _(self.doctype), self.key_label, shown
        )
        return [
            (
                (CAUSE_MANY_MATCHES, *key),
                {
                    **info,
                    "cause": CAUSE_MANY_MATCHES,
                    "records": list(key[:MAX_MATCHES_NAMED]),
                    "record_count": len(key),
                    "message": message,
                },
            )
        ]

    def _add_to_preview(self, row: int, record: str, changed: List[Dict]) -> None:
        self.preview["records_changing"] += 1
        self.preview["fields_changing"] += len(changed)
        for change in changed:
            self.preview["by_field"][change["label"]] = self.preview["by_field"].get(change["label"], 0) + 1
        if len(self.preview["samples"]) < SAMPLES_KEPT:
            self.preview["samples"].append({"row": row, "record": record, "changes": changed})

    # Data Import's own value checks, made while it parsed the rows.
    def _required_problems(self, payload, flagged=frozenset()) -> List[Tuple[Tuple, Dict]]:
        """A required field, or the one the record is named by, that the row leaves blank (#34537).
        ERPNext can fail on it before Frappe says it is required: naming a Customer strips its
        Customer Name, so a blank one failed as "'NoneType' object has no attribute 'strip'"."""
        problems = []
        cells = payload.rows[0].data
        for df, index in self.required:
            # The file's own cell: the parse leaves out a link it can't find yet (a missing record,
            # or one an earlier file of the plan creates), which isn't an empty value
            if df.fieldname in flagged or (index < len(cells) and cstr(cells[index]).strip()):
                continue
            label = _(df.label)
            info = {
                "cause": CAUSE_REQUIRED_MISSING,
                "field": df.fieldname,
                "label": label,
                "message": _("{0} is empty.").format(label),
            }
            problems.append(((CAUSE_REQUIRED_MISSING, df.fieldname), info))
        return problems

    def _parse_problems(self, payload, needs=(), from_files=None) -> List[Tuple[Tuple, Dict]]:
        problems = []
        planned = {entry[key].casefold() for entry in needs for key in ("name", "alias") if entry.get(key)}
        # The import provider's warnings about the whole file, on the record's first row
        warnings_of = {payload.rows[0].row_number: list(self.provider_warnings.get(None, []))}
        for row in payload.rows:
            warned = {_field_key(w) for w in row.warnings if w.get("field")}
            warnings = list(row.warnings) + [
                w for w in self.value_warnings.get(row.row_number, []) if _field_key(w) not in warned
            ]
            warnings += self.provider_warnings.get(row.row_number, [])
            warnings += warnings_of.get(row.row_number, [])
            for warning in warnings:
                if (
                    warning.get("type") == "info"
                    or self._from_the_file(row, warning, planned)
                    or self._link_key(row, warning) in (from_files or {})
                ):
                    continue
                problems.append(self._from_warning(row, warning))
        return problems

    def _from_warning(self, row, warning) -> Tuple[Tuple, Dict]:
        field = frappe._dict(warning.get("field") or {})
        if not field.fieldname:
            message = strip_html(cstr(warning.get("message")))
            return (CAUSE_BAD_VALUE, message), {"cause": CAUSE_BAD_VALUE, "message": message}

        value = self._value_of(row, field)
        later = self.later.get(field.options, {}).get(value.casefold()) if field.fieldtype == "Link" else None
        if later:
            cause = CAUSE_LATER_FILE
            message = _(
                "{0} '{1}' comes from {2}, which is imported after this file. Move that file first "
                "(plan_migration's order)."
            ).format(_(field.options), value, later)
        elif field.fieldtype == "Link" and (field.parent, field.fieldname) in self.translated:
            cause = CAUSE_MISSING_LINK
            message = _(
                "{0} '{1}' isn't imported yet. Import the file that creates it first, map it to an "
                "existing record, or leave these rows out."
            ).format(_(field.options), value)
        elif field.fieldtype == "Link":
            cause = CAUSE_MISSING_LINK
            message = _("{0} '{1}' doesn't exist.").format(_(field.options), value)
        elif field.fieldtype == "Select":
            cause = CAUSE_BAD_OPTION
            message = _("'{0}' isn't one of the options for {1}.").format(value, _(field.label))
        elif field.fieldtype in ("Date", "Datetime"):
            cause = CAUSE_BAD_DATE
            message = strip_html(cstr(warning.get("message")))
        else:
            cause = CAUSE_BAD_VALUE
            message = strip_html(cstr(warning.get("message")))
        info = {
            "cause": cause,
            "parent": field.parent,  # the DocType the field is on: a child table's, for its columns
            "field": field.fieldname,
            "label": _(field.label),
            "value": value,
            "message": message,
        }
        return (cause, field.parent, field.fieldname, value), info

    def _from_the_file(self, row, warning, planned: set) -> bool:
        """Whether ``warning`` is Data Import's "missing" for a record a row higher up the file
        creates, which is in ERPNext by the time this row is imported."""
        field = frappe._dict(warning.get("field") or {})
        return bool(
            planned
            and field.fieldtype == "Link"
            and field.options == self.doctype
            and field.parent == self.doctype
            and self._value_of(row, field).casefold() in planned
        )

    def _alias(self, payload) -> Optional[str]:
        """The title a row of a tree may be named by in place of its name (Frappe 16), else None."""
        if not self.alias_field:
            return None
        return cstr(payload.doc.get(self.alias_field)).strip() or None

    def _intended_name(self, payload) -> Optional[str]:
        """The name an insert of this row would give its record, when it is a field of the row."""
        if self.import_type != INSERT or self.matches is not None:
            return None
        fieldname = _name_field(self.doctype)
        if not fieldname:
            return None
        for column in self.header.columns:
            df = column.df
            if df and not column.skip_import and df.parent == self.doctype and df.fieldname == fieldname:
                return cstr(payload.rows[0].data[column.index]).strip() or None
        return None

    # Links to records the earlier files of a migration plan create.
    def _from_earlier_files(self, payload) -> Dict[Tuple[str, str], Dict[str, str]]:
        """(DocType, casefolded value) → the earlier file of the plan that creates that record and
        the field that links to it, for each of this record's links to one. Read from the rows
        themselves: Data Import leaves a link it found missing out of the record it parsed."""
        found: Dict[Tuple[str, str], Dict[str, str]] = {}
        if not self.coming:
            return found
        for row in payload.rows:
            for column in self.header.columns:
                df = column.df
                if not df or column.skip_import or df.fieldtype != "Link" or df.options not in self.coming:
                    continue
                value = cstr(row.data[column.index]).strip()
                source = self.coming[df.options].get(value.casefold()) if value else None
                if source:
                    found[(df.options, value.casefold())] = {
                        "doctype": df.options,
                        "file": source,
                        "field": df.fieldname,
                        "parent": df.parent,
                        "value": value,
                    }
        return found

    def _put_back(self, payload, doc, from_files) -> None:
        """Put back in ``doc`` the links to records earlier files of the plan create, which Data
        Import's parse left out: on the record, and on each child row they are in."""
        counters: Dict[str, int] = {}
        for row in payload.rows:
            for doctype, table_df in self.header.doctypes:
                indexes = self.header.get_column_indexes(doctype, table_df)
                if all(value in INVALID_VALUES for value in row.get_values(indexes)):
                    continue  # no record of this table on this row
                target = doc
                if table_df:
                    at = counters.get(table_df.fieldname, 0)
                    counters[table_df.fieldname] = at + 1
                    rows = doc.get(table_df.fieldname) or []
                    target = rows[at] if at < len(rows) else None
                if target is None:
                    continue
                for column in self.header.get_columns(indexes):
                    df = column.df
                    if df.fieldtype != "Link":
                        continue
                    value = cstr(row.data[column.index]).strip()
                    if (df.options, value.casefold()) in from_files:
                        target[df.fieldname] = value

    def _link_key(self, row, warning) -> Optional[Tuple[str, str]]:
        field = frappe._dict(warning.get("field") or {})
        if field.fieldtype != "Link":
            return None
        return (field.options, self._value_of(row, field).casefold())

    # Links to records rows higher up the file create.
    def _needs(self, payload) -> List[Dict[str, Any]]:
        """The ready rows higher up the file whose records this row links to, each with the field
        that links. Read from the row itself: Data Import leaves a link it found missing out of
        the record it parsed."""
        if not self.planned:
            return []
        needs, rows = [], set()
        for fieldname in self.self_links:
            field = frappe._dict(fieldname=fieldname, parent=self.doctype)
            value = self._value_of(payload.rows[0], field)
            entry = self.planned.get(value.casefold()) if value else None
            if entry and (fieldname, entry["row"]) not in rows:
                rows.add((fieldname, entry["row"]))
                needs.append({**entry, "field": fieldname})
        return needs

    @staticmethod
    def _higher_up(needs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """The records of ``needs`` and of the rows they need in turn, the topmost first."""
        ordered, seen = [], set()

        def visit(entry):
            if entry["row"] in seen:
                return
            seen.add(entry["row"])
            for parent in entry["needs"]:
                visit(parent)
            ordered.append(entry["doc"])

        for entry in needs:
            visit(entry)
        return ordered

    def _value_of(self, row, field) -> str:
        for column in self.header.columns:
            df = column.df
            if (
                df
                and not column.skip_import
                and df.fieldname == field.fieldname
                and df.parent == field.parent
            ):
                return cstr(row.data[column.index]).strip()
        return ""

    def _duplicate_problems(self, payload) -> List[Tuple[Tuple, Dict]]:
        if self.matches is not None:  # an update: two rows for one record
            record = self._record(payload)
            if not record:
                return []
            first = self.seen_records.setdefault(record, payload.rows[0].row_number)
            if first == payload.rows[0].row_number:
                return []
            message = _("Row {0} updates the same {1}, {2}.").format(first, _(self.doctype), record)
            return [
                (
                    (CAUSE_SAME_RECORD,),
                    {"cause": CAUSE_SAME_RECORD, "label": self.key_label, "message": message},
                )
            ]
        named = self._named_duplicate(payload)
        if named:
            return named
        self._note_shared_title(payload)
        if not self.key_df:
            return []
        value = cstr(payload.doc.get(self.key_df.fieldname)).strip()
        if not value:
            return []
        label = _(self.key_df.label)
        first = self.seen_keys.setdefault(value.casefold(), payload.rows[0].row_number)
        if first != payload.rows[0].row_number:
            message = _("{0} '{1}' is also in row {2}.").format(label, value, first)
            info = {"cause": CAUSE_DUPLICATE_IN_FILE, "field": self.key_df.fieldname, "label": label}
            return [((CAUSE_DUPLICATE_IN_FILE, self.key_df.fieldname), {**info, "message": message})]
        if self.import_type == INSERT and frappe.db.exists(self.doctype, {self.key_df.fieldname: value}):
            info = {"cause": CAUSE_ALREADY_EXISTS, "field": self.key_df.fieldname, "label": label}
            message = _("A {0} with {1} '{2}' already exists.").format(_(self.doctype), label, value)
            return [((CAUSE_ALREADY_EXISTS, self.key_df.fieldname), {**info, "message": message})]
        return []

    def _fetched_problems(self, payload) -> List[Tuple[Tuple, Dict]]:
        """An update can't change a field Frappe fetches from a linked record (``fetch_from``, not
        ``fetch_if_empty``) while the record has that link set: every save copies the linked
        record's value back, and Data Import would still report the row a success."""
        record = self._record(payload) if self.matches is not None else None
        if not record:
            return []
        from frappe_assistant_core.utils import import_update

        meta = frappe.get_meta(self.doctype)
        problems = []
        for field, value in payload.doc.items():
            df = meta.get_field(field)
            if not df or not df.fetch_from or df.fetch_if_empty or "." not in df.fetch_from:
                continue
            if not cstr(value).strip():  # a blank cell is no change
                continue
            link_field = df.fetch_from.split(".")[0]
            link_df = meta.get_field(link_field)
            linked = frappe.db.get_value(self.doctype, record, link_field)
            if not link_df or not linked:
                continue
            if import_update._same(df, frappe.db.get_value(self.doctype, record, field), value):
                continue
            message = _(
                "{0} on {1} {2} comes from its {3} {4}, so an import can't change it here. Change it on the {5}."
            ).format(
                _(df.label),
                _(self.doctype),
                record,
                _(link_df.label),
                linked,
                _(link_df.options or link_df.label),
            )
            problems.append(
                (
                    (CAUSE_FETCHED, field),
                    {"cause": CAUSE_FETCHED, "field": field, "label": _(df.label), "message": message},
                )
            )
        return problems

    def _named_duplicate(self, payload) -> List[Tuple[Tuple, Dict]]:
        """A row repeating an earlier row's value of the field ERPNext names the record after
        (named_df). The import would refuse the second record of that name, but the check rolls
        each row back, so its insert can't see the first (#34398). One already in ERPNext is
        refused by the check's own insert."""
        if not self.named_df:
            return []
        value = cstr(payload.doc.get(self.named_df.fieldname)).strip()
        if not value:
            return []
        row = payload.rows[0].row_number
        first = self.seen_named.setdefault(value.casefold(), row)
        if first == row:
            return []
        label = _(self.named_df.label)
        message = _("{0} '{1}' is also in row {2}.").format(label, value, first)
        info = {"cause": CAUSE_DUPLICATE_IN_FILE, "field": self.named_df.fieldname, "label": label}
        return [((CAUSE_DUPLICATE_IN_FILE, self.named_df.fieldname), {**info, "message": message})]

    def _note_shared_title(self, payload) -> None:
        """Remember a row whose title repeats an earlier row's or a record in ERPNext. Two records
        may share a title when a naming series names them, so the row is never failed for it."""
        if not self.title_df:
            return
        value = cstr(payload.doc.get(self.title_df.fieldname)).strip()
        if not value:
            return
        row = payload.rows[0].row_number
        first = self.seen_titles.setdefault(value.casefold(), row)
        if first != row or (
            self.import_type == INSERT and frappe.db.exists(self.doctype, {self.title_df.fieldname: value})
        ):
            self.shared_rows.append(row)

    def shared_warnings(self) -> List[Dict[str, Any]]:
        """The warning for the rows that share their title with another record, if any."""
        if not self.shared_rows:
            return []
        label = _(self.title_df.label)
        count = len(self.shared_rows)
        return [
            {
                "cause": CAUSE_SHARED_VALUE,
                "field": self.title_df.fieldname,
                "label": label,
                "count": count,
                "example_rows": self.shared_rows[:EXAMPLES_PER_GROUP],
                "message": _(
                    "{0} rows share their {1} with another {2}, in the file or in ERPNext. This is "
                    "allowed here, so they are still ready."
                ).format(count, label, _(self.doctype)),
            }
        ]

    # The real insert (or update), rolled back. Returns the problems and the name it created.
    def _insert_problems(
        self, payload, needs=(), from_files=None
    ) -> Tuple[List[Tuple[Tuple, Dict]], Optional[str]]:
        doc = frappe._dict(copy.deepcopy(_with_links(payload.doc, needs)))
        with own_messages(), held_back():
            frappe.db.savepoint(SAVEPOINT)
            try:
                if self.import_type != INSERT:
                    self.importer.try_row(doc)
                    return [], None
                # The records rows higher up the file create are in ERPNext when this row is
                # imported: put them in first, inside the same savepoint.
                for earlier in self._higher_up(list(needs)):
                    self.importer.insert_record(frappe._dict(copy.deepcopy(earlier)))
                if from_files:
                    # Records an earlier file of the plan creates aren't in ERPNext yet: stand-ins
                    # take their place inside the savepoint, and the links Data Import's parse left
                    # out are put back.
                    for link in from_files.values():
                        _stand_in(link["doctype"], link["value"])
                    self._put_back(payload, doc, from_files)
                    # The parse cached them as missing; the rollback clears this cache too.
                    frappe.db.value_cache.clear()
                return [], self.importer.try_row(doc).name
            except Exception as e:
                # ERPNext's refusals quote the row's value: one group per message, not per value
                kind, text = refusal(e)
                message, values = message_pattern(text, _values_of([row.data for row in payload.rows]))
                return [
                    (
                        (CAUSE_REJECTED, kind, message),
                        {"cause": CAUSE_REJECTED, "error": kind, "message": message, "values": values},
                    )
                ], None
            finally:
                frappe.db.rollback(save_point=SAVEPOINT)

    def _group(self, key: Tuple, info: Dict, payload) -> str:
        group = self.groups.get(key)
        if not group:
            group = {"id": self._group_id(key), **info, "count": 0, "rows": []}
            if info["cause"] in (CAUSE_DUPLICATE_IN_FILE, CAUSE_ALREADY_EXISTS):
                group["message"] = {
                    CAUSE_DUPLICATE_IN_FILE: _("{0} appears more than once in the file."),
                    CAUSE_ALREADY_EXISTS: _("A {1} with this {0} already exists."),
                }[info["cause"]].format(info["label"], _(self.doctype))
            self.groups[key] = group
            if "values" in info:
                group["values"] = []
        for value in info.get("values") or []:
            if value not in group["values"] and len(group["values"]) < VALUES_KEPT:
                group["values"].append(value)
        for row in payload.rows:
            group["count"] += 1
            group["rows"].append(row.row_number)
        return group["id"]

    def _group_id(self, key: Tuple) -> str:
        """The same failure gets the same id in every check, so a fix picked from an earlier
        reply still finds its rows, and is refused once they no longer fail."""
        digest = hashlib.sha256(json.dumps(key, default=str).encode()).hexdigest()
        taken = {group["id"] for group in self.groups.values()}
        size = 6
        while f"G{digest[:size]}" in taken:
            size += 2
        return f"G{digest[:size]}"


def _stand_in(doctype: str, name: str) -> None:
    """A bare ``doctype`` record called ``name``, for a row's check to link to while an earlier file
    of its migration plan, which creates the real one, isn't imported yet. Only ever made inside the
    row's savepoint, which is rolled back."""
    if frappe.db.exists(doctype, name):
        return
    frappe.db.savepoint(STAND_IN_SAVEPOINT)
    messages = len(frappe.local.message_log or [])
    try:
        _bare(doctype, name).insert(
            ignore_permissions=True, ignore_links=True, ignore_mandatory=True, set_name=name
        )
    except Exception:
        # An app's validate hook refuses a bare record, mandatory fields ignored or not (India
        # Compliance wants an Item's HSN code). The DocType's own controller still fills in what
        # its records have (an Item's UOM row, which an Item Price checks): only the hooks are left out.
        frappe.db.rollback(save_point=STAND_IN_SAVEPOINT)
        if frappe.local.message_log:
            del frappe.local.message_log[messages:]
        doc = _bare(doctype, name)

        def own_rules_only():
            for method in ("before_validate", "validate", "before_save"):
                getattr(doc, method, lambda: None)()

        doc.run_before_save_methods = own_rules_only
        doc.insert(ignore_permissions=True, ignore_links=True, ignore_mandatory=True, set_name=name)


def _bare(doctype: str, name: str):
    """A new ``doctype`` record with only its name, and its tree's default parent."""
    from frappe_assistant_core.utils import import_fixes

    meta = frappe.get_meta(doctype)
    doc = frappe.new_doc(doctype)
    name_field = import_fixes._name_field(meta)
    if name_field:
        doc.set(name_field, name)
    parent_field = import_fixes._parent_field(meta)
    if parent_field and not doc.get(parent_field):
        doc.set(parent_field, import_fixes.default_parent(doctype))
    return doc


#: ERPNext names these in code, from a field, when its settings say so: not in the DocType's autoname.
NAMED_BY_SETTING = {
    "Customer": ("Selling Settings", "cust_master_name", "Customer Name", "customer_name"),
    "Supplier": ("Buying Settings", "supp_master_name", "Supplier Name", "supplier_name"),
}


def _name_field(doctype: str) -> Optional[str]:
    """The field whose value a new ``doctype`` record is named by, if it is named by one. The
    setting is read as the controller reads it, from the global default, as _named_field does."""
    autoname = get_autoname_field(doctype)
    if autoname:
        return autoname.fieldname
    rule = NAMED_BY_SETTING.get(doctype)
    if rule and frappe.defaults.get_global_default(rule[1]) == rule[2]:
        return rule[3]
    return None


def _required_fields(session, header) -> List[Tuple[Any, int]]:
    """The mapped fields a new record can't be saved without, each with its column: required with
    no default, and the one it is named by (#34537)."""
    named = _name_field(session.target_doctype)
    return [
        (column.df, column.index)
        for column in header.columns
        if column.df
        and not column.skip_import
        and column.df.parent == session.target_doctype
        and (column.df.fieldname == named or (column.df.reqd and not column.df.default))
    ]


def refusal(e: Exception) -> Tuple[str, str]:
    """(kind, message) of a row ERPNext refused: its message, or for an internal error (a Python
    exception, not a message for the user) a plain sentence (#34537). The full error goes to the server log now, and to the Error Log once the check has
    stored its result (log_internal_errors): the row's savepoint is rolled back after, with
    anything written inside it."""
    if message_texts(frappe.local.message_log) or isinstance(e, frappe.ValidationError):
        return type(e).__name__, _message_of(e)
    logged = getattr(frappe.local, "fac_logged_errors", None)
    if logged is None:
        logged = frappe.local.fac_logged_errors = {}
    key = (type(e).__name__, str(e))
    if key not in logged:
        logged[key] = frappe.get_traceback()
        frappe.logger("frappe_assistant_core.import", allow_site=True).error(
            "A row of an import check failed with an internal error:\n" + logged[key]
        )
    return "InternalError", _(UNEXPLAINED)


def log_internal_errors() -> None:
    """Each internal error the check met, once, in the Error Log: outside the rows' savepoints, so
    it stays. The same error is logged again only in a later request."""
    logged = getattr(frappe.local, "fac_logged_errors", None) or {}
    for key, traceback in list(logged.items()):
        if traceback:
            frappe.log_error(title=INTERNAL_ERROR_TITLE, message=traceback)
            logged[key] = None


def _with_links(doc, needs) -> Dict[str, Any]:
    """``doc`` with the links to records rows higher up the file create put back in."""
    return {**doc, **{entry["field"]: entry["name"] for entry in needs}}


def _self_links(doctype: str) -> List[str]:
    """The fields of ``doctype`` that link to ``doctype`` itself, as a tree's parent does."""
    meta = frappe.get_meta(doctype)
    return [df.fieldname for df in meta.fields if df.fieldtype == "Link" and df.options == doctype]


def _mapped_fields(session, header) -> Dict[str, Any]:
    return {
        column.df.fieldname: column.df
        for column in header.columns
        if column.df and not column.skip_import and column.df.parent == session.target_doctype
    }


def _named_field(session, header):
    """The mapped field a setting names the record after on this site (NAMED_BY_SETTING: a
    Customer by its customer name, as Selling Settings has it unless changed), or None. Read as
    the controller reads it, from the global default (#34398)."""
    rule = NAMED_BY_SETTING.get(session.target_doctype)
    if not rule or frappe.defaults.get_global_default(rule[1]) != rule[2]:
        return None
    return _mapped_fields(session, header).get(rule[3])


def _key_field(session, header):
    """The mapped field that is the record's name, else the first mapped field marked unique: a
    repeated value of it is a real duplicate. Any other field, the title field included, may repeat
    (a naming series names a record whatever its title says)."""
    autoname = get_autoname_field(session.target_doctype)
    mapped = _mapped_fields(session, header)
    for fieldname in (session.match_key, autoname.fieldname if autoname else None):
        if fieldname and fieldname in mapped:
            return mapped[fieldname]
    return next((df for df in mapped.values() if df.unique), None)


def _title_field(session, header, key_df):
    """The mapped title field when it isn't the key: its repeated values are only a warning."""
    title = frappe.get_meta(session.target_doctype).title_field
    df = _mapped_fields(session, header).get(title) if title else None
    return df if df and not (key_df and key_df.fieldname == df.fieldname) else None


_TEMPORARY_NAME = re.compile(r"\bnew-[a-z0-9-]+-[a-z0-9]{6,}\b")


def message_texts(entries) -> List[str]:
    """The messages of a message log, Frappe's or a Data Import Log's, as plain text: each entry a
    dict, its JSON, or the text itself. The dry run and the import's failures read them alike."""
    texts = []
    for entry in entries or []:
        if isinstance(entry, str):
            try:
                entry = json.loads(entry)
            except ValueError:
                entry = {"message": entry}
        if isinstance(entry, dict) and entry.get("message"):
            texts.append(" ".join(strip_html(cstr(entry["message"])).split()))
    return texts


def _message_of(e: Exception) -> str:
    """The message ERPNext showed for ``e``, as plain text, without per-row temporary names."""
    texts = message_texts(frappe.local.message_log)
    text = texts[-1] if texts else " ".join(strip_html(cstr(e) or type(e).__name__).split())
    return _TEMPORARY_NAME.sub("", text).strip()


@contextmanager
def own_messages():
    """Messages a row's check makes stay its own: the request's earlier messages are put back
    after (#34413), rather than cleared with the row's."""
    before = list(frappe.local.message_log or [])
    frappe.clear_messages()
    try:
        yield
    finally:
        frappe.local.message_log = before


#: What a row's insert could send out at once: held back by held_back(), in its request only.
_HELD_FUNCTIONS = (
    (frappe, "enqueue"),
    (frappe.utils.background_jobs, "enqueue"),
    # A Server Script's frappe.enqueue: safe_exec took its own copy of enqueue on import
    ("frappe.utils.safe_exec", "enqueue"),
    # Where every enqueue ends up, whoever holds the function: a module that did `from
    # frappe.utils.background_jobs import enqueue` keeps the real one, which still ends here.
    (Queue, "enqueue_job"),
    # Past enqueue_job: enqueue_many puts its jobs in with _enqueue_job, and enqueue_at and
    # enqueue_in with schedule_job (#34401)
    (Queue, "_enqueue_job"),
    (Queue, "schedule_job"),
    (frappe, "publish_realtime"),
    (frappe.realtime, "publish_realtime"),
    # A naming series: its SELECT ... FOR UPDATE outlives the row's savepoint (#34401)
    ("frappe.model.naming", "getseries"),
)
#: Doc-event handlers that reach an outside service while the row is tried, held back with it:
#: the Google Calendar and Google Contacts sync call Google at once, not at commit, and would change
#: the user's real events and contacts, and email attendees.
SENT_AT_ONCE = {
    "frappe.integrations.doctype.google_calendar.google_calendar": (
        "insert_event_in_google_calendar",
        "update_event_in_google_calendar",
        "delete_event_from_google_calendar",
    ),
    "frappe.integrations.doctype.google_contacts.google_contacts": (
        "insert_contacts_to_google_contacts",
        "update_contacts_to_google_contacts",
    ),
}
_HOLD_LOCK = threading.Lock()


def _held_functions() -> List[Tuple[Any, str]]:
    """(owner, name) of every function held_back() holds back, of the modules this site has."""
    held = []
    for owner, name in _HELD_FUNCTIONS:
        held.append((importlib.import_module(owner) if isinstance(owner, str) else owner, name))
    for module, functions in SENT_AT_ONCE.items():
        try:
            owner = importlib.import_module(module)
        except ImportError:
            continue
        held += [(owner, name) for name in functions if hasattr(owner, name)]
    return held


class HeldJob:
    """What enqueue gives back while a job is held back: a controller may read its ``id``."""

    def __init__(self, job_id: Optional[str] = None):
        self.id = cstr(job_id) if job_id else f"fac_dry_run_held::{frappe.generate_hash(length=12)}"

    def get_id(self) -> str:
        return self.id


def _held_enqueue(*args, **kwargs) -> HeldJob:
    return HeldJob(kwargs.get("job_id"))


def _held_queue_job(queue, job, *args, **kwargs):
    """RQ's Queue.enqueue_job, held: the job rq made (and has not saved) is what is given back."""
    return job


#: What a held function gives back instead of None, by name
def _held_series(key: str, digits: int) -> str:
    """getseries while a row is tried: the next number, read without a lock and never written.
    getseries locks the series row until the transaction ends, which a savepoint's rollback
    doesn't do, so real users numbering documents in that series would wait for the whole check
    (#34401). The row is rolled back, so the series mustn't move anyway. The numbers this row
    takes count, so a row that names two documents in a series gets two names."""
    taken = frappe.local.fac_held_series
    series = DocType("Series")
    current = frappe.qb.from_(series).select(series.current).where(series.name == key).run()
    taken[key] = taken.get(key, cint(current[0][0]) if current and current[0][0] is not None else 0) + 1
    return ("%0" + str(digits) + "d") % taken[key]


_HELD_RESULTS = {
    "enqueue": _held_enqueue,
    "enqueue_job": _held_queue_job,
    "_enqueue_job": _held_queue_job,
    "schedule_job": _held_queue_job,
    "getseries": _held_series,
}


def _hold_aware(original, held=None):
    """``original``, doing nothing while this request holds back (held_back): ``held(*args,
    **kwargs)`` is what the caller gets then, None unless said."""

    def hold_aware(*args, **kwargs):
        if getattr(frappe.local, "fac_holding_back", 0):
            return held(*args, **kwargs) if held else None
        return original(*args, **kwargs)

    hold_aware.__wrapped__ = original
    hold_aware.fac_hold_aware = True
    return hold_aware


def _install_hold_aware() -> None:
    """Put the hold-aware stand-ins in place, once: any other request still gets the real thing."""
    with _HOLD_LOCK:
        for owner, name in _held_functions():
            current = getattr(owner, name)
            if getattr(current, "fac_hold_aware", False) is not True:  # a Mock answers any attribute
                setattr(owner, name, _hold_aware(current, _HELD_RESULTS.get(name)))


@contextmanager
def held_back():
    """Hold back what a row's insert would send out or commit while it is tried. The caller rolls
    back to a savepoint inside it; the work the row registered for a rollback (a File moved back,
    a cache cleared) runs on the way out, as a full rollback would run it."""
    flags = frappe.local.flags
    saved_flags = {name: flags.get(name) for name in ("in_import", "mute_emails")}
    # Data Import sets in_import (which also stops webhooks); emails are always muted.
    flags.in_import = True
    flags.mute_emails = True
    # A saved document queues its search entry in Redis, which no rollback reaches.
    conf = frappe.local.conf
    search_setting = conf.get("disable_global_search", _UNSET)
    conf["disable_global_search"] = True

    callbacks = {
        name: list(getattr(frappe.db, name)._functions)
        for name in ("before_commit", "after_commit", "before_rollback", "after_rollback")
    }

    def swallow(*args, **kwargs):
        return None

    # Jobs and realtime events are module functions, shared by every request a worker serves at
    # once: they are held back for this request only, never swapped out for the whole process.
    _install_hold_aware()
    frappe.local.fac_holding_back = getattr(frappe.local, "fac_holding_back", 0) + 1
    if frappe.local.fac_holding_back == 1:
        frappe.local.fac_held_series = {}  # the series numbers this row has taken
    # A controller that commits must not keep the row (frappe.db is this request's own). What was
    # in place before goes back after: the class's commit, or a stand-in set around this check.
    before = frappe.db.__dict__.get("commit")
    frappe.db.commit = swallow
    # Nor may it roll the whole transaction back: that ends the row's savepoint, and the run
    # with it ("SAVEPOINT does not exist"). A rollback to a savepoint goes through. What the row
    # wrote is undone by its own savepoint's rollback, as with document_batch's guard.
    rollback = frappe.db.rollback
    before_rollback = frappe.db.__dict__.get("rollback")

    def hold_full_rollback(*args, save_point=None, **kwargs):
        if save_point:
            return rollback(*args, save_point=save_point, **kwargs)

    frappe.db.rollback = hold_full_rollback
    try:
        yield
    finally:
        if before is None:
            del frappe.db.commit
        else:
            frappe.db.commit = before
        if before_rollback is None:
            del frappe.db.rollback
        else:
            frappe.db.rollback = before_rollback
        frappe.local.fac_holding_back -= 1
        if not frappe.local.fac_holding_back:
            frappe.local.fac_held_series = None
        rolled_back = list(frappe.db.after_rollback._functions)[len(callbacks["after_rollback"]) :]
        for name, functions in callbacks.items():
            manager = getattr(frappe.db, name)
            manager._functions.clear()
            manager._functions.extend(functions)
        for callback in rolled_back:
            try:
                callback()
            except Exception:
                frappe.log_error(title=_("Dry Run Rollback Error"), message=frappe.get_traceback())
        if search_setting is _UNSET:
            conf.pop("disable_global_search", None)
        else:
            conf["disable_global_search"] = search_setting
        for name, value in saved_flags.items():
            flags[name] = value


# -- storing the result ----------------------------------------------------------------


def _real_size(rows: int, in_background: bool) -> None:
    """The Max Rows refusal and the choice of a background check read the row count the session
    recorded, whose fields can be written over the REST API: the file's own count is held to them
    too, so a file swapped in is neither checked past the limit nor inside the web request."""
    problem = row_limit_problem(rows)
    if problem:
        raise DryRunProblem(problem)
    if not in_background and rows > BACKGROUND_ROWS:
        raise DryRunProblem(
            _(
                "This file has {0} rows, not the number this session recorded, so it isn't checked "
                "here. Start a new import session for it."
            ).format(rows)
        )


def _checking() -> Dict[str, str]:
    """Session -> the fingerprint of what this request's check started from."""
    if not hasattr(frappe.local, "fac_dry_run_checking"):
        frappe.local.fac_dry_run_checking = {}
    return frappe.local.fac_dry_run_checking


def _store(session_name: str, file_doc, checker: _Checker, total_payloads: int) -> Dict[str, Any]:
    session = engine_session(session_name)
    counts = {"ready": 0, "failed": 0, "excluded": 0, "imported": 0, "unchanged": 0}
    for row in checker.rows:
        counts[row["status"]] += 1
    failed_rows = {row["row"] for row in checker.rows if row["status"] == "failed"}

    previous = _previous_failed_rows(session)
    groups = list(checker.groups.values())
    summary = {
        "checked_on": str(now_datetime()),
        "doctype": session.target_doctype,
        "import_type": session.import_type,
        "total_rows": len(checker.rows),
        "records": total_payloads,
        **counts,
        "duplicate_key": checker.key_df.fieldname if checker.key_df else None,
        "groups": [_summary_group(g) for g in groups],
        "warnings": checker.shared_warnings() if hasattr(checker, "shared_warnings") else [],
    }
    if getattr(checker, "matches", None) is not None:  # the opening engines' checkers have none
        summary["update"] = checker.preview
    if previous is not None:
        summary["previous"] = {"failed": len(previous), "fixed": len(previous - failed_rows)}

    _replace_results_file(
        session,
        {"session": session.name, "summary": summary, "groups": groups, "rows": checker.rows},
    )
    log_internal_errors()
    session.validation_summary = frappe.as_json(summary)
    session.validated_fingerprint = _checking().pop(session_name, None) or fingerprint(session, file_doc)
    session.status = "Dry Run Failed" if counts["failed"] else "Ready to Import"
    if counts["imported"] and not counts["ready"] and not counts["failed"]:
        session.status = "Completed"  # the rest is left out or already so: nothing left to do
    session.progress = frappe.as_json(
        {"step": "Dry Run", "state": "done", "done": total_payloads, "total": total_payloads}
    )
    session.log_step(
        "Dry Run",
        "Warning" if counts["failed"] else "Success",
        headline(summary),
        rows_ok=counts["ready"],
        rows_failed=counts["failed"],
    )
    session.save()
    return summary


def _no_changes(problems) -> bool:
    """Whether ``problems`` is Data Import's refusal of an update that changes nothing."""
    return len(problems) == 1 and problems[0][1].get("message") == _("No changes to update")


def message_pattern(message: str, values: Iterable[Any]) -> Tuple[str, List[str]]:
    """``message`` as every row gets it, and the values it quoted (#34407). ERPNext's refusals
    quote the value they refused ("x@ is not a valid Email Address", "Row #3: ..."), so 400 rows
    with 400 bad values would be 400 groups. The row's own values of three characters or more,
    and row numbers, read as QUOTED instead."""
    text, found = cstr(message), []
    for value in sorted({cstr(v).strip() for v in values if cstr(v).strip()}, key=len, reverse=True):
        if frappe.db.exists("DocType", value):
            continue  # "Customer" in a row is also ERPNext's own word in its message (#34541)
        if len(value) >= 3:
            pattern = re.compile(rf"(?<!\w){re.escape(value)}(?!\w)")
        else:  # a short value only where the message quotes it, or it matches inside words
            pattern = re.compile(rf"(?<=['\"‘“]){re.escape(value)}(?=['\"’”])")
        if pattern.search(text):
            text = pattern.sub(QUOTED, text)
            found.append(value)
    return re.sub(r"(Row\s*#?\s*)\d+", rf"\g<1>{QUOTED}", text), found


def _values_of(doc: Any) -> List[str]:
    """Every value in ``doc`` as text: given the file's rows, what the user wrote, never a default
    Frappe filled in (#34407)."""
    if isinstance(doc, dict):
        return [v for value in doc.values() for v in _values_of(value)]
    if isinstance(doc, (list, tuple)):
        return [v for value in doc for v in _values_of(value)]
    return [cstr(doc)] if doc not in (None, "") else []


def _summary_group(group: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in group.items() if k != "rows"}
    out["example_rows"] = group["rows"][:EXAMPLES_PER_GROUP]
    return out


def headline(summary: Dict[str, Any]) -> str:
    text = _("{0} rows ready, {1} would fail").format(summary["ready"], summary["failed"])
    if summary.get("excluded"):
        text += _(", {0} left out").format(summary["excluded"])
    if summary.get("imported"):
        text += _(", {0} already imported").format(summary["imported"])
    if summary.get("unchanged"):
        text += _(", {0} unchanged").format(summary["unchanged"])
    return text + "."


def _previous_failed_rows(session) -> Optional[set]:
    file_doc = _results_file(session)
    if not file_doc:
        return None
    try:
        rows = json.loads(file_doc.get_content()).get("rows") or []
    except Exception:
        return None
    return {row["row"] for row in rows if row.get("status") == "failed"}


def _results_file(session):
    if not session.validation_results:
        return None
    name = frappe.db.get_value(
        "File",
        {
            "file_url": session.validation_results,
            "attached_to_doctype": SESSION_DOCTYPE,
            "attached_to_name": session.name,
        },
    )
    return frappe.get_doc("File", name) if name else None


def _replace_results_file(session, content: Dict[str, Any]) -> None:
    old = _results_file(session)
    if old:
        frappe.delete_doc("File", old.name, force=True, ignore_permissions=True)
    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": f"{session.name}-dry-run.json",
            "content": json.dumps(content, default=str, indent=1),
            "is_private": 1,
            "attached_to_doctype": SESSION_DOCTYPE,
            "attached_to_name": session.name,
            "attached_to_field": "validation_results",
        }
    ).insert(ignore_permissions=True)
    session.validation_results = file_doc.file_url


#: How much of a check's fingerprint names it to FACO and on the approval card (#34545): it
#: copied 64 characters and dropped one, twice, so an import took three approvals.
CHECK_ID_LENGTH = 12


def check_id(fingerprint: Optional[str]) -> Optional[str]:
    """The check's name as FACO passes it to start_import: its fingerprint's first characters."""
    return fingerprint[:CHECK_ID_LENGTH] if fingerprint else fingerprint


def names_check(given: Any, fingerprint: Optional[str]) -> bool:
    """Whether ``given`` (a check id, or the whole fingerprint) names the check ``fingerprint``."""
    given = cstr(given).strip().lower()
    return bool(fingerprint) and len(given) >= CHECK_ID_LENGTH and fingerprint.startswith(given)


def fingerprint(session, file_doc) -> str:
    """Changes when anything the check depended on changes, so an import can tell
    whether it is importing what was checked."""
    content_hash = file_doc.content_hash or hashlib.sha256(_bytes(file_doc.get_content())).hexdigest()
    parts = [
        content_hash,
        session.sheet or "",
        session.target_doctype,
        session.import_type or "",
        session.match_key or "",
        str(session.submit_after_import or 0),
        json.dumps(_checked_options(session), sort_keys=True),
        json.dumps(frappe.parse_json(session.transformation_rules or "null"), sort_keys=True),
        json.dumps(sorted(_excluded_rows(session))),
    ]
    from frappe_assistant_core.utils.import_failures import imported_rows

    imported = imported_rows(session)
    if imported:  # an import since the check makes it stale: other rows are left to import
        parts.append(json.dumps(sorted(imported)))
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


#: What other steps keep in template_options that no check reads: the plan and result a removed
#: undo feature left on older sessions (key "undo"), and the failures of the last opening invoices import (reset as an
#: import starts). The records an import made stay in: the check leaves those rows out. And the
#: fingerprint the session's last fixes left it at (UNCHECKED_FIXES, import_fixes.fixed_unchecked).
UNCHECKED_FIXES = "unchecked_fixes"
_NOT_CHECKED = {"undo": None, "opening_invoices": ("failed",), UNCHECKED_FIXES: None}


def _checked_options(session) -> Dict[str, Any]:
    """The session's template_options as far as the check depends on them."""
    options = dict(frappe.parse_json(session.template_options or "{}") or {})
    for key, inner in _NOT_CHECKED.items():
        if inner is None:
            options.pop(key, None)
        elif isinstance(options.get(key), dict):
            options[key] = {k: v for k, v in options[key].items() if k not in inner}
    return options


def _bytes(content) -> bytes:
    return content.encode("utf-8") if isinstance(content, str) else content


def examples(session, groups: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Up to three example rows per group, read from the file for the reply only."""
    wanted = {row for group in groups for row in group["example_rows"]}
    if not wanted:
        return {}
    file_doc = readable_session_file(session)
    rows = read_sheet_rows(file_doc, session.sheet or None)
    header, mapped = rows[0], column_to_field_map(session)
    shown = [i for i in range(len(header)) if mapped.get(str(i)) not in (None, "Don't Import")]
    by_row = {}
    for number in wanted:
        if 1 <= number - 1 < len(rows):
            by_row[number] = {header[i]: shown_cell(rows[number - 1][i]) for i in shown}
    return {
        group["id"]: [{"row": n, "values": by_row[n]} for n in group["example_rows"] if n in by_row]
        for group in groups
    }
