# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Migration plans (#33995): several import sessions of one migration, ordered so masters come
before the records that link to them, checked knowing what earlier files will create, and run
after one approval.

The order comes from the target DocTypes' Link fields, not a hand-written list: a file comes
after every other file of the plan whose DocType it links to. The opening imports come last,
stock, then invoices, then the trial balance, as migrate_data.md has always told FACO.

A plan has no DocType of its own (#34351): the session of its first file keeps it. Every file's
session links to that session through migration_plan (the first one to itself) and keeps its own
place in the order (plan_position, plan_reason); plan_settings on the first session holds the
rest: status, failure rule, stop flag, the masters it creates, the run's progress and its log.
"""

import datetime
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import frappe
from frappe import _
from frappe.utils import add_months, cint, cstr, get_datetime, get_last_day, getdate, now_datetime, today

from frappe_assistant_core.utils import import_dry_run as dry_run
from frappe_assistant_core.utils.untrusted_output import unfenced

SESSION_DOCTYPE = dry_run.SESSION_DOCTYPE
ANSWERS_SAVEPOINT = "fac_plan_answers"
#: A session in one of these may join a plan: nothing of it is imported or cancelled.
JOINABLE = ("File Read", "Mapped", "Dry Run Failed", "Ready to Import")
#: A plan in one of these takes new files; once it runs, its files are fixed.
OPEN = ("Planning", "Ready to Run")
#: A session in one of these has been imported, as far as it will go.
IMPORTED = ("Completed", "Partially Completed", "Failed")


class PlanProblem(Exception):
    """The plan can't do what was asked. The message is shown to the user."""


# -- the plan ----------------------------------------------------------------------------------


class Plan:
    """A migration plan, as its first session's plan_settings hold it. save() writes them alone,
    so the plan's saves and its files' own saves never overwrite each other."""

    def __init__(self, name: str, settings: Dict[str, Any]):
        self.name = name
        self._read(settings)

    def _read(self, settings: Dict[str, Any]) -> None:
        self.title = settings.get("title") or ""
        self.status = settings.get("status") or "Planning"
        self.failure_rule = settings.get("failure_rule") or "leave_out"
        self.stop_requested = cint(settings.get("stop_requested"))
        # JSON text, as the plan's code reads and writes them
        self.masters = frappe.as_json(settings["masters"]) if settings.get("masters") else None
        self.progress = frappe.as_json(settings["progress"]) if settings.get("progress") else None
        self.steps = [frappe._dict(step) for step in settings.get("steps") or []]

    def log_step(self, step: str, outcome: str, message: str) -> None:
        """Append a row to the plan's step log. The caller saves the plan."""
        self.steps.append(
            frappe._dict(
                {
                    "timestamp": str(now_datetime()),
                    "step": step,
                    "outcome": outcome,
                    "user": frappe.session.user,
                    "message": message,
                }
            )
        )

    def reload(self) -> None:
        self._read(_settings(self.name))

    def require_open(self) -> None:
        """Raise PlanProblem unless the plan is open in the database now, and hold its row until
        this transaction ends: the run's start waits for it. A plan not saved yet is open."""
        stored = _settings(self.name, for_update=True).get("status")
        if stored and stored not in OPEN:
            raise PlanProblem(
                _("Plan {0} is {1} now, so it can't be changed: its files are fixed.").format(
                    self.name, _(stored)
                )
            )

    def save_open(self) -> None:
        """save() for the paths that open a plan: never over a plan that has started or ended since
        this copy was read (it would take Running, and the run's progress, back)."""
        self.require_open()
        self.save()

    def save(self) -> None:
        settings = {
            "title": self.title,
            "status": self.status,
            "failure_rule": self.failure_rule,
            # The stop flag is request_stop's alone: a run saving a copy read before the stop keeps it.
            "stop_requested": cint(_settings(self.name, for_update=True).get("stop_requested")),
            "masters": frappe.parse_json(self.masters or "[]") or [],
            "progress": frappe.parse_json(self.progress or "{}") or {},
            "steps": [dict(step) for step in self.steps],
        }
        progress = settings["progress"]
        # What Desk shows of the plan, in fields of its own on the first file's session
        shown = {
            "plan_status": self.status,
            "plan_failure_rule": self.failure_rule,
            "plan_cut_off": progress.get("cut_off") or None,
            "plan_importing_now": progress.get("current") or None,
        }
        _write(self.name, settings, shown)


def _settings(name: str, for_update: bool = False) -> Dict[str, Any]:
    raw = frappe.db.get_value(SESSION_DOCTYPE, name, "plan_settings", for_update=for_update)
    return frappe.parse_json(raw or "{}") or {}


def _write(name: str, settings: Dict[str, Any], shown: Optional[Dict[str, Any]] = None) -> None:
    """Write the plan's settings, and the fields that show them in Desk (the stop flag always)."""
    values = {
        "plan_settings": frappe.as_json(settings),
        "plan_stop_requested": cint(settings.get("stop_requested")),
        **(shown or {}),
    }
    # Not the session's modified: the file's own saves would find it changed under them.
    frappe.db.set_value(SESSION_DOCTYPE, name, values, update_modified=False)


def get_plan(name: str) -> Plan:
    """The plan session ``name`` keeps. Raises DoesNotExistError when it keeps none: a file of a
    plan that isn't its first, or a session whose plan ended before it joined another."""
    row = frappe.db.get_value(SESSION_DOCTYPE, name, ["migration_plan", "plan_settings"], as_dict=True)
    if not row or not row.plan_settings or row.migration_plan != name:
        raise frappe.DoesNotExistError(_("Migration plan {0} not found.").format(name))
    return Plan(name, frappe.parse_json(row.plan_settings) or {})


def plan_status(name: str) -> Optional[str]:
    """The plan's status, or None when ``name`` keeps no plan."""
    try:
        return get_plan(name).status
    except frappe.DoesNotExistError:
        return None


def new_plan(sessions: List[Any]) -> Plan:
    """A new plan, kept on the first of ``sessions`` that keeps no other. The caller links the
    sessions to it, then saves it."""
    lead = next((s for s in sessions if not s.get("plan_settings")), None)
    if lead is None:
        raise PlanProblem(_("Each of these files kept an earlier plan. Open one of them again, then plan."))
    return Plan(lead.name, {"title": ", ".join(s.file_name for s in sessions[:3]) or _("Migration")})


def request_stop(plan_name: str, stop: int = 1) -> None:
    """Set the plan's stop flag on its own: the run saves the plan between files, and keeps it."""
    settings = _settings(plan_name, for_update=True)
    settings["stop_requested"] = stop
    _write(plan_name, settings)


def imported_by_its_plan(session) -> Optional[str]:
    """Why ``session``'s file isn't imported on its own, or None: while its plan is open or
    running, the plan imports it, in its order, after the one approval."""
    plan = session.get("migration_plan")
    status = plan_status(plan) if plan else None
    if status in (*OPEN, "Running"):
        return _(
            "{0} is in migration plan {1} ({2}): the plan imports it, in its order. Answer "
            "its questions (dry_run_import with the plan), then run_migration_plan."
        ).format(session.file_name, plan, _(status))
    return None


def load_plan(name: str):
    """The plan, if this user may change it. Raises DoesNotExistError or PermissionError."""
    doc = frappe.get_doc(SESSION_DOCTYPE, name)
    if not frappe.has_permission(SESSION_DOCTYPE, "write", doc=doc):
        raise frappe.PermissionError(_("You can't change migration plan {0}.").format(name))
    return get_plan(name)


def children(plan) -> List[Any]:
    """The plan's sessions in its order; one not ordered yet goes last, oldest first. Only its
    user's: another user's session is never imported under this plan's approval (#34429)."""
    rows = frappe.get_all(
        SESSION_DOCTYPE,
        filters={
            "migration_plan": plan.name,
            "user": frappe.db.get_value(SESSION_DOCTYPE, plan.name, "user"),
        },
        fields=["name", "plan_position"],
        order_by="creation",
    )
    place = {row.name: row.plan_position for row in rows if row.plan_position}
    oldest = {row.name: i for i, row in enumerate(rows)}
    names = sorted(oldest, key=lambda name: place.get(name, len(place) + 1 + oldest[name]))
    return [dry_run.engine_session(name) for name in names]


def _set_order(ordered: List[Dict[str, Any]]) -> None:
    """Keep each session's place in the order, and why, on the session itself."""
    for entry in ordered:
        frappe.db.set_value(
            SESSION_DOCTYPE,
            entry["session"],
            {"plan_position": entry["position"], "plan_reason": entry["reason"]},
            update_modified=False,
        )


def join_problems(plan_name: str, sessions: List[Any]) -> List[str]:
    """Why any of ``sessions`` can't join the plan: in another plan, or past being planned."""
    problems = []
    for session in sessions:
        other = session.migration_plan if session.migration_plan != plan_name else None
        # A plan that stopped or ended lets its files go: the rest can be planned again.
        if other and plan_status(other) in (*OPEN, "Running"):
            problems.append(_("{0} is already in plan {1}.").format(session.file_name, other))
        elif session.status not in JOINABLE:
            problems.append(
                _("{0} is {1}, so it can't join a plan.").format(session.file_name, _(session.status))
            )
    return problems


# -- what the plan's files create ----------------------------------------------------------------


def _created_names(session) -> List[str]:
    """The names the rows of the session's last check create, or mean to: a failing row whose
    name is one of its fields counts too, as its file is fixed or imported without it before any
    later file is."""
    from frappe_assistant_core.utils import import_run

    return [
        row["name"]
        for row in import_run._checked_rows(session)
        if row.get("status") in ("ready", "failed") and row.get("name")
    ]


def _created_old_ids(session) -> List[str]:
    """The old IDs of the records the session's last check creates (#34244): a later file of the plan
    refers to them by those IDs before the records, and so their names, exist."""
    from frappe_assistant_core.utils import import_key_setup, import_run

    keys = import_key_setup.keys_by_row(session)
    if not keys:
        return []
    return [
        keys[row["row"]]
        for row in import_run._checked_rows(session)
        if row.get("status") in ("ready", "failed") and row.get("row") in keys
    ]


#: How many of a link column's values must be an earlier file's old IDs for the plan to translate
#: it: most of them. The rest are what its check then asks about (an ID no file brings).
OLD_ID_SHARE = 0.5


def _translate_earlier_old_ids(session) -> None:
    """Translate the session's link columns that hold the old IDs of an earlier file of its plan
    (#34244), when its mapping didn't say so (DM52: the items' Item Group held the groups' old codes).
    The check counts those IDs as coming, but only a translated column is turned into the records'
    names when its file is imported: every such row would be left out."""
    from frappe_assistant_core.utils import import_key_setup, import_keys
    from frappe_assistant_core.utils.import_session import FileProblem, read_sheet_rows, readable_session_file

    if session.status not in JOINABLE or not session.target_doctype:
        return
    _plan, before, _after = _split(session)
    ids: Dict[str, Dict[str, Set[str]]] = {}  # DocType → source system → old IDs
    for earlier in before:
        kept = import_keys.source_key(earlier)
        if kept and earlier.target_doctype:
            ids.setdefault(earlier.target_doctype, {}).setdefault(kept["system"], set()).update(
                import_key_setup.keys_by_row(earlier).values()
            )
    kept_maps = import_keys.key_maps(session)
    columns = {
        position: doctype
        for position, doctype in import_keys.link_targets(
            session.target_doctype, dry_run.column_to_field_map(session)
        ).items()
        if position not in kept_maps and doctype in ids
    }
    if not columns:
        return
    try:
        rows = read_sheet_rows(readable_session_file(session), session.sheet or None)
    except FileProblem:
        return  # a file that stayed in the chat: its check says what is wrong
    added = {}
    for position, doctype in columns.items():
        values = import_keys.distinct_keys(row[position] for row in rows[1:] if position < len(row))
        for system, known in ids[doctype].items():
            if values and sum(1 for value in values if value in known) / len(values) >= OLD_ID_SHARE:
                added[position] = {"doctype": doctype, "system": system}
                break
    if not added:
        return
    import_keys.set_key_maps(session, {**kept_maps, **added})
    for position, spec in added.items():
        session.log_step(
            "Old IDs",
            "Success",
            _("Column '{0}' holds the old IDs of {1} from an earlier file of the plan: translated.").format(
                rows[0][position], _(spec["doctype"])
            ),
        )
    session.save()


def masters(plan) -> List[Dict[str, Any]]:
    """The records the plan creates before any file is imported."""
    return frappe.parse_json(plan.masters or "[]") or []


def add_masters(session, items: List[Dict[str, Any]]) -> None:
    """Add masters the session's rows need to its plan, once each across the plan."""
    from frappe_assistant_core.utils import import_fixes

    plan = load_plan(session.migration_plan)
    entries = masters(plan)
    known = {(entry["doctype"], entry["name"].casefold()) for entry in entries}
    for item in items:
        name = import_fixes._planned_name(item)
        if (item["doctype"], name.casefold()) not in known:
            known.add((item["doctype"], name.casefold()))
            entries.append(
                {"session": session.name, "doctype": item["doctype"], "name": name, "data": item["data"]}
            )
    plan.masters = frappe.as_json(entries)
    plan.save_open()


def create_planned(plan) -> List[Dict[str, Any]]:
    """Create the plan's masters not in ERPNext yet, each listed on the session whose rows need
    it. Raises PlanProblem if ERPNext refuses one."""
    from frappe_assistant_core.utils import import_fixes

    made: List[Dict[str, Any]] = []
    by_session: Dict[str, List[Dict[str, Any]]] = {}
    for entry in masters(plan):
        if not frappe.db.exists(entry["doctype"], entry["name"]):
            by_session.setdefault(entry["session"], []).append(entry)
    # All or none: a master made before one ERPNext refuses would be listed on no session.
    frappe.db.savepoint(MASTERS_SAVEPOINT)
    try:
        for session_name, entries in by_session.items():
            results = []
            for entry in entries:
                result = import_fixes.create_master(entry)
                if not result.get("success"):
                    raise PlanProblem(
                        _("{0} '{1}' couldn't be created: {2}").format(
                            _(entry["doctype"]), entry["name"], result.get("error")
                        )
                    )
                results.append(result)
            import_fixes.link_created(dry_run.engine_session(session_name), results)
            made += results
    except Exception:
        frappe.db.rollback(save_point=MASTERS_SAVEPOINT)
        raise
    return made


def _names(sessions: List[Any], plan=None) -> Dict[str, Dict[str, str]]:
    names: Dict[str, Dict[str, str]] = {}
    for session in sessions:
        if session.status in IMPORTED:  # its records are in ERPNext now, or genuinely missing
            continue
        for name in _created_names(session) + _created_old_ids(session):
            names.setdefault(session.target_doctype, {}).setdefault(
                name.strip().casefold(), session.file_name
            )
    for entry in masters(plan) if plan else []:
        names.setdefault(entry["doctype"], {}).setdefault(
            entry["name"].strip().casefold(), _("the plan's new records")
        )
    return names


def _split(session) -> Tuple[Any, List[Any], List[Any]]:
    """The session's plan, and its files before and after the session."""
    try:
        plan = get_plan(session.migration_plan) if session.get("migration_plan") else None
    except frappe.DoesNotExistError:  # its plan ended, and its first file went to another
        plan = None
    if not plan:
        return None, [], []
    files = children(plan)
    at = next((i for i, s in enumerate(files) if s.name == session.name), len(files))
    return plan, files[:at], files[at + 1 :]


def planned_names(session) -> Dict[str, Dict[str, str]]:
    """DocType → casefolded name → the file that creates it, for the records the files before the
    session in its plan, and the plan itself, will have created by the time it is imported."""
    plan, before, _after = _split(session)
    return _names(before, plan) if plan else {}


def planned_titles(session, doctype: str) -> List[str]:
    """The names of the ``doctype`` records that the files before the session in its plan, and
    the plan itself, create, as they spell them: what a value of the session can be mapped to."""
    plan, before, _after = _split(session)
    if not plan:
        return []
    names = [
        name
        for earlier in before
        if earlier.status not in IMPORTED and earlier.target_doctype == doctype
        for name in _created_names(earlier)
    ]
    names += [entry["name"] for entry in masters(plan) if entry["doctype"] == doctype]
    return list(dict.fromkeys(cstr(name).strip() for name in names if cstr(name).strip()))


def later_names(session) -> Dict[str, Dict[str, str]]:
    """The same for the files imported after the session: a link to one is an order problem."""
    plan, _before, after = _split(session)
    return _names(after) if plan else {}


def arrange(plan) -> List[str]:
    """Order the plan's sessions and store the order. Returns the order's problems. An order the
    user set (plan_migration's order) is kept: files not in it go after, in their own order."""
    files = children(plan)
    fixed = [name for name in _progress(plan).get("fixed_order") or [] if name in {s.name for s in files}]
    if fixed:
        ordered, _problems = order([s for s in files if s.name not in fixed])
        ordered = [{"session": name, "reason": _("In the order you set.")} for name in fixed] + [
            {"session": entry["session"], "reason": entry["reason"]} for entry in ordered
        ]
        _set_order([{**entry, "position": i} for i, entry in enumerate(ordered, start=1)])
        return []
    ordered, problems = order(files)
    _set_order(ordered)
    return problems


def describe(plan) -> Dict[str, Any]:
    """The plan as FACO shows it: its files in order, each with why it's there and its state."""
    files = []
    for session in children(plan):
        files.append(
            {
                "session": session.name,
                "file_name": session.file_name,
                "doctype": session.target_doctype,
                "position": session.plan_position or None,
                "reason": session.plan_reason,
                "status": session.status,
            }
        )
    return {
        "plan": plan.name,
        "status": plan.status,
        "failure_rule": plan.failure_rule,
        "files": files,
    }


# -- the order ---------------------------------------------------------------------------------


def dependencies(doctype: str) -> Set[str]:
    """The DocTypes ``doctype``'s records link to, its child tables' links included."""
    meta = frappe.get_meta(doctype)
    linked = {df.options for df in meta.fields if df.fieldtype == "Link" and df.options}
    for table_df in meta.get_table_fields():
        child = frappe.get_meta(table_df.options)
        linked |= {df.options for df in child.fields if df.fieldtype == "Link" and df.options}
    linked.discard(doctype)  # a tree's parent is in the same file: import_run takes it a level at a time
    return linked


def _links(session) -> Set[str]:
    """The DocTypes the session's mapped columns link to; all its DocType's links before it is
    mapped. A column mapped to Don't Import doesn't make its file wait for another."""
    from frappe_assistant_core.utils.import_mapping import DONT_IMPORT, session_mapping

    mapping = session_mapping(session)
    if not mapping:
        return dependencies(session.target_doctype)
    meta = frappe.get_meta(session.target_doctype)
    linked = set()
    for field in mapping.values():
        if not field or field == DONT_IMPORT:
            continue
        table, _dot, fieldname = field.rpartition(".")
        on = meta
        if table:
            table_df = meta.get_field(table)
            if not table_df:
                continue
            on = frappe.get_meta(table_df.options)
        df = on.get_field(fieldname)
        if df and df.fieldtype == "Link" and df.options:
            linked.add(df.options)
    linked.discard(session.target_doctype)
    return linked


def _engine_rank(session) -> int:
    """0 for a file imported through Data Import; 1, 2, 3 for opening stock, invoices, balances."""
    from frappe_assistant_core.utils import import_opening_balances as balances
    from frappe_assistant_core.utils import import_opening_invoices as invoices
    from frappe_assistant_core.utils import import_opening_stock as stock

    engine = dry_run.special_engine(session)
    return {None: 0, stock: 1, invoices: 2, balances: 3}.get(engine, 3)


def order(sessions: List[Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """The sessions in the order they are imported, each with its position and the reason, and a
    problem for every pair of files that link to each other. Among files free to go, the one given
    first goes first."""
    plain = [s for s in sessions if not _engine_rank(s)]
    opening = sorted((s for s in sessions if _engine_rank(s)), key=_engine_rank)

    needs = {}
    for session in plain:
        wanted = _links(session) if session.target_doctype else set()
        needs[session.name] = [
            other for other in plain if other.name != session.name and other.target_doctype in wanted
        ]

    ordered, placed, problems = [], set(), []
    waiting = list(plain)
    while waiting:
        free = next((s for s in waiting if all(o.name in placed for o in needs[s.name])), None)
        if free is None:  # every file left waits on another: they link to each other
            first = waiting[0]
            other = next(o for o in needs[first.name] if o.name not in placed)
            problems.append(
                _(
                    "{0} and {1} link to each other: map the linking columns of one to Don't Import "
                    "(and import them later), or set the order with plan_migration's order."
                ).format(first.file_name, other.file_name)
            )
            free = first
        waiting.remove(free)
        placed.add(free.name)
        before = needs[free.name]
        if before:
            reason = _("After {0}: it needs the {1} records from there.").format(
                ", ".join(o.file_name for o in before),
                ", ".join(sorted({_(o.target_doctype) for o in before})),
            )
        else:
            reason = _("No other file is needed before this one.")
        ordered.append((free, reason))

    for session in opening:
        ordered.append((session, _("Opening files go last: they need the records the other files bring.")))
    return [
        {"session": session.name, "position": position, "reason": reason}
        for position, (session, reason) in enumerate(ordered, start=1)
    ], problems


# -- the questions -----------------------------------------------------------------------------
#
# Every question of the plan comes in one list, before anything is imported: the files still to
# map, the files that link to each other, each failure group with the engine's suggested fixes,
# and the failure rule. Answers come back in one call.

FAILURE_RULE_ID = "plan:failure_rule"
CUT_OFF_ID = "plan:cut_off"
CHECKED = ("Dry Run Failed", "Ready to Import")


def _bring_up_to_date(plan, session) -> Optional[Dict[str, Any]]:
    """Check the session again unless its last check is of it as it is now, in a plan whose files
    create what they did then. A question when it can't be checked here: still running, too
    large for this request, or not checkable yet. Keeps what the check depended on in the plan
    (the caller saves it)."""
    from frappe_assistant_core.utils import import_fixes

    if dry_run.is_running(session):
        return {"kind": "checking", "message": _("Still being checked. Ask again in a moment.")}
    if session.status == "File Read":
        return None
    digests = dict(_progress(plan).get("digests") or {})
    digest = plan_digest(session)
    # A file that failed is checked again whatever its fingerprint: an earlier file of the plan may
    # have changed what it will create.
    if (
        session.status == "Ready to Import"
        and import_fixes.checked_as_is(session)
        and digests.get(session.name) == digest
    ):
        return None
    try:
        dry_run.check_can_run(session)
    except dry_run.DryRunProblem as e:
        return {"kind": "blocked", "message": str(e)}
    digests[session.name] = digest
    plan.progress = frappe.as_json({**_progress(plan), "digests": digests})
    if dry_run.check_cost(session) > dry_run.BACKGROUND_ROWS:  # as dry_run_import decides (#34407)
        dry_run.enqueue(session)
        return {"kind": "checking", "message": _("Being checked in the background. Ask again in a moment.")}
    import_fixes.check(session.name)  # never commits: the plan's row stays locked (#34431)
    return None


#: A file with one of these questions isn't checked yet: the files after it wait for it.
UNCHECKED = ("checking", "blocked", "structure")


def _file_questions(plan, session) -> List[Dict[str, Any]]:
    from frappe_assistant_core.utils import import_fixes
    from frappe_assistant_core.utils.import_mapping import session_headers

    about = {"session": session.name, "file_name": session.file_name}
    _translate_earlier_old_ids(session)
    waiting = _bring_up_to_date(plan, session)
    session.reload()
    if waiting:
        return [{"id": f"{session.name}:check", **about, **waiting}]
    if session.status == "File Read" or not session.target_doctype:
        message = _(
            "Map this file (get_import_schema, set_column_mapping), or set it up as opening "
            "stock, invoices or balances."
        )
        return [
            {
                "id": f"{session.name}:structure",
                **about,
                "kind": "structure",
                "message": message,
                "columns": session_headers(session),
            }
        ]
    questions = _columns_question(session, about)
    if session.status != "Dry Run Failed":
        return questions
    for group in import_fixes.last_groups(session).values():
        advice = import_fixes.advise(session, group)
        questions.append(
            {
                "id": f"{session.name}:{group['id']}",
                **about,
                "kind": "fix",
                "cause": group.get("cause"),
                "message": group.get("message"),
                "count": group.get("count"),
                **advice,
            }
        )
    return questions


def _columns_question(session, about: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The file's columns no field was given, asked about in one question of the plan's list
    (#34415): left to the model, each was a card of its own, before and after the plan's list."""
    from frappe_assistant_core.utils.import_mapping import unplaced_columns

    columns = [header for _position, header in unplaced_columns(session)]
    if not columns:
        return []
    # FAC's own words name nothing of the file: its headers reach the model fenced, in columns
    message = _(
        "The file's columns in 'columns' have no field, so they won't be imported. Leave them out, "
        "or map each to a field with set_column_mapping and check the plan again."
    )
    return [
        {
            "id": f"{session.name}:{COLUMNS_QUESTION}",
            **about,
            "kind": "columns",
            "message": message,
            "columns": columns,
            "suggested": {"action": "leave_out"},
        }
    ]


def open_questions(plan) -> Dict[str, Any]:
    """Every open question of the plan, the files checked first in the plan's order (an earlier
    file's records count for the later ones). The plan is Ready to Run once none is left and every
    file is ready."""
    questions: List[Dict[str, Any]] = []
    for problem in arrange(plan):
        questions.append({"id": f"plan:order:{len(questions)}", "kind": "order", "message": problem})
    first_unchecked = None
    for session in children(plan):
        if first_unchecked:
            # What an earlier file creates isn't known until it is checked: checked now, this file
            # would ask about records that file brings.
            questions.append(
                {
                    "id": f"{session.name}:waiting",
                    "session": session.name,
                    "file_name": session.file_name,
                    "kind": "waiting",
                    "message": _("Checked once {0} is.").format(first_unchecked),
                }
            )
            continue
        asked = _file_questions(plan, session)
        if any(q["kind"] in UNCHECKED for q in asked):
            first_unchecked = session.file_name
        questions += asked
    progress = frappe.parse_json(plan.progress or "{}") or {}
    dates = cut_offs(children(plan))
    said = name_dates(children(plan)) if dates else {}
    if dates and not (len(set(dates.values())) == 1 and progress.get("cut_off") in dates.values()):
        # Never a guess (a file's name, today): a wrong date puts invoices after it in the opening.
        message = _(
            "The cut-off date: the day the old system's balances are taken at. Show it on "
            "the card the user approves ('cut-off <date>'): never a date they haven't seen. "
            "Each opening file is set up with the date shown: one that differs from the "
            "user's is set again first (set_opening_stock, set_opening_invoices, "
            "set_opening_balances)."
        )
        questions.append(
            {
                "id": CUT_OFF_ID,
                "kind": "cut_off",
                "message": message,
                "dates": dates,
                # a file whose name gives another date: shown, so the user checks it
                **({"file_names_say": said} if said else {}),
                # a choice card: the date the files are set to, or another the user gives
                "choices": sorted({date for date in dates.values() if date}) + ["another_date"],
            }
        )
    if not progress.get("rule_confirmed"):
        questions.append(
            {
                "id": FAILURE_RULE_ID,
                "kind": "failure_rule",
                "message": _(
                    "If rows still fail when their file comes up (a record changed meanwhile, or the "
                    "row their parent is in failed): leave them out with their reason, or stop the "
                    "plan before that file?"
                ),
                "suggested": plan.failure_rule or "leave_out",
                "choices": ["leave_out", "stop"],
            }
        )
    files = children(plan)
    _add_needed_by(questions, files)
    for question in questions:
        suggested = suggested_fix(question) if question["kind"] == "fix" else None
        if suggested:
            question["suggested"] = suggested
    ready = bool(files) and not questions and all(s.status == "Ready to Import" for s in files)
    plan.status = "Ready to Run" if ready else "Planning"
    plan.save_open()
    result = {**describe(plan), "questions": questions, "ready": ready}
    if questions:
        # The user must see every question before "Apply all suggested answers": left to the
        # model, the table was skipped and the user approved blind.
        result["table"] = questions_table(result["files"], questions)
    if ready:  # what run_migration_plan is given, so its approval card shows it
        result["approval"] = card_figures(plan)
    return result


def suggested_fix(question: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The answer "Apply all suggested answers" gives a fix question: map to the name the value is
    most likely a misspelling of, else create the missing record, else leave the rows out. None
    when no fix fits (an answer the user must give on a card of its own)."""
    from frappe_assistant_core.utils import import_fixes

    fixes = {fix.get("action"): fix for fix in question.get("fixes") or []}
    likely = (fixes.get(import_fixes.MAP) or {}).get("likely")
    if likely:
        return {"action": import_fixes.MAP, "to": likely}
    if import_fixes.CREATE in fixes:
        parent = fixes[import_fixes.CREATE].get("parent")
        return {"action": import_fixes.CREATE, **({"parent": parent} if parent else {})}
    if import_fixes.LEAVE_OUT in fixes:
        return {"action": import_fixes.LEAVE_OUT, "reason": question.get("cause") or _("Left out")}
    return None


def questions_table(files: List[Dict[str, Any]], questions: List[Dict[str, Any]]) -> str:
    """The plan's files in order and every open question with its suggested answer, as markdown:
    what the user reads before choosing "Apply all suggested answers"."""
    lines = [
        "| # | " + _("File") + " | " + _("Records") + " | " + _("Why here") + " |",
        "|---|---|---|---|",
    ]
    for i, file in enumerate(files, 1):
        lines.append(
            f"| {i} | {_cell(file['file_name'])} | {_cell(_(file['doctype'] or ''))} | {_cell(file['reason'])} |"
        )
    lines += [
        "",
        "| # | " + _("File") + " | " + _("Question") + " | " + _("Suggested answer") + " |",
        "|---|---|---|---|",
    ]
    for i, question in enumerate(questions, 1):
        lines.append(
            f"| {i} | {_cell(question.get('file_name') or _('The plan'))} | {_cell(_question_text(question))} "
            f"| {_cell(_answer_text(question))} |"
        )
    return "\n".join(lines)


def _question_text(question: Dict[str, Any]) -> str:
    if question["kind"] == "cut_off":
        return _("The cut-off date of the opening files")
    if question["kind"] == "failure_rule":
        return _("Rows that still fail when their file comes up")
    if question["kind"] == "columns":  # the table is fenced whole: it may name the file's columns
        return _("Columns with no field: {0}").format(", ".join(question.get("columns") or []))
    return question.get("explanation") or question.get("message") or ""


def _answer_text(question: Dict[str, Any]) -> str:
    from frappe_assistant_core.utils import import_fixes

    kind = question["kind"]
    if kind == "cut_off":
        dates = [date for date in question.get("choices") or [] if date != "another_date"]
        return ", ".join(dates) if dates else _("Ask the user")
    if kind == "failure_rule":
        return _("Leave them out") if question.get("suggested") == "leave_out" else _("Stop the plan")
    if kind == "columns":
        return _("Don't import them")
    suggested = question.get("suggested")
    if not suggested:
        return _("Ask the user") if kind == "fix" else ""
    action = suggested["action"]
    if action == import_fixes.MAP:
        return _("Use '{0}'").format(suggested["to"])
    if action == import_fixes.CREATE:
        create = next(fix for fix in question["fixes"] if fix.get("action") == import_fixes.CREATE)
        return _("Create {0} '{1}'").format(_(create.get("doctype") or ""), create.get("name") or "")
    return _("Leave out {0}").format(import_fixes._rows(question.get("count") or 0))


def _cell(text: Any) -> str:
    return " ".join(str(text or "").split()).replace("|", "\\|")


def _add_needed_by(questions: List[Dict[str, Any]], files: List[Any]) -> None:
    """A fix question whose rows create records a later file of the plan needs says which later
    rows need them: leaving those rows out leaves the later ones without their record (an invoice
    without its customer), which the user must know before choosing."""
    from frappe_assistant_core.utils import import_run

    rows = {session.name: import_run._checked_rows(session) for session in files}
    place = {session.name: i for i, session in enumerate(files)}
    for question in questions:
        if question.get("kind") != "fix" or question.get("session") not in place:
            continue
        group = question["id"].rpartition(":")[2]
        names = {
            row["name"].casefold(): row["name"]
            for row in rows[question["session"]]
            if group in (row.get("groups") or []) and row.get("name")
        }
        needed = []
        for later in files[place[question["session"]] + 1 :]:
            for row in rows[later.name]:
                wanted = [name for name in row.get("needs") or [] if name.casefold() in names]
                if wanted:
                    needed.append(
                        _("{0} row {1} ({2})").format(later.file_name, row["row"], ", ".join(wanted))
                    )
        if needed:
            question["needed_by"] = needed


#: What a fix answer takes, as dry_run_import's fixes do; and what describes a suggested fix,
#: which FACO may send back with it and which is let be (#34547).
FIX_KEYS = ("action", "to", "reason", "data", "parent", "value")  # value: a fill's (#34415)
COLUMNS_QUESTION = "columns"  # the id of a file's question about its unplaced columns: <session>:columns
FIX_DESCRIPTION_KEYS = ("doctype", "name", "closest", "likely", "rows", "use", "note", "cause", "label")


def _check_keys(question: str, answer: Dict[str, Any], keys, described=()) -> None:
    """Refuse an answer with a key it doesn't take, naming the ones it does: a wrong key was taken
    for no answer, and asked again (#34547)."""
    unknown = sorted(set(answer) - {"id", *keys, *described})
    if unknown:
        raise PlanProblem(
            _("Answer {0} doesn't take {1}. It takes: {2}.").format(
                question, ", ".join(unknown), ", ".join(keys)
            )
        )


def apply_answers(plan, answers: List[Dict[str, Any]]) -> List[str]:
    """Apply the user's answers, each to the question it names, all or none. Returns what was done.
    Raises PlanProblem, or import_fixes.FixProblem(s) for a fix the session refuses."""
    from frappe_assistant_core.utils import import_fixes

    files = {session.name: session for session in children(plan)}
    fixes: Dict[str, List[Dict[str, Any]]] = {}
    left_columns: List[str] = []
    rule = cut_off = None
    for answer in answers:
        if not isinstance(answer, dict):
            raise PlanProblem(_("Each answer is an object with the id of its question."))
        question = cstr(answer.get("id"))
        if question == CUT_OFF_ID:
            _check_keys(question, answer, ("date",))
            cut_off = as_date(answer.get("date"))
            continue
        if question == FAILURE_RULE_ID:
            # failure_rule is the plan's own name for it, which FACO sends too (#34547)
            _check_keys(question, answer, ("rule", "failure_rule"))
            rule = answer.get("rule") or answer.get("failure_rule")
            if rule not in ("leave_out", "stop"):
                raise PlanProblem(_("The failure rule is leave_out or stop."))
            continue
        session_name, _sep, group = question.rpartition(":")
        if session_name in files and group == COLUMNS_QUESTION:
            _check_keys(question, answer, ("action",))
            if answer.get("action") != "leave_out":
                raise PlanProblem(
                    _("Columns are left out (action leave_out), or mapped with set_column_mapping first.")
                )
            left_columns.append(session_name)
            continue
        if session_name not in files or not group.startswith("G"):
            raise PlanProblem(_("There is no question {0} in this plan.").format(question))
        _check_keys(question, answer, FIX_KEYS, FIX_DESCRIPTION_KEYS)
        fixes.setdefault(session_name, []).append(
            {
                "group": group,
                # a value from a fenced `suggested` or `fixes` may come back still fenced
                **{
                    k: unfenced(v) if isinstance(v, str) else v
                    for k, v in answer.items()
                    if k != "id" and k not in FIX_DESCRIPTION_KEYS
                },
            }
        )

    if cut_off:
        _check_cut_off(list(files.values()), cut_off)

    done: List[str] = []
    frappe.db.savepoint(ANSWERS_SAVEPOINT)
    try:
        for session_name, session_fixes in fixes.items():
            session = files[session_name]
            done += import_fixes.apply_fixes(session, import_fixes.last_groups(session), session_fixes)
            session.save()
        for session_name in left_columns:
            done.append(_leave_columns_out(files[session_name]))
        plan.require_open()  # not after the plan started: its files' fixes roll back with the savepoint
        if rule or cut_off:
            plan.reload()
            progress = _progress(plan)
            if rule:
                plan.failure_rule = rule
                progress["rule_confirmed"] = True
                plan.log_step("Questions", "Success", _("Failure rule: {0}.").format(rule))
                done.append(_("Rows that fail when their file comes up: {0}.").format(rule))
            if cut_off:
                progress["cut_off"] = cut_off
                plan.log_step("Questions", "Success", _("Cut-off date: {0}.").format(cut_off))
                done.append(_("Cut-off date: {0}.").format(cut_off))
            plan.progress = frappe.as_json(progress)
            plan.save_open()
    except Exception:
        frappe.db.rollback(save_point=ANSWERS_SAVEPOINT)
        raise
    return done


def _leave_columns_out(session) -> str:
    """The user's answer to a columns question: Don't Import, as they chose it, so it isn't asked again."""
    from frappe_assistant_core.utils.import_mapping import (
        DONT_IMPORT,
        save_mapping,
        session_mapping,
        unplaced_columns,
    )

    columns = unplaced_columns(session)
    mapping = {**session_mapping(session), **{position: DONT_IMPORT for position, _header in columns}}
    left = ", ".join(header for _position, header in columns)
    save_mapping(
        session, session.target_doctype, mapping, _("Not imported, as the user chose: {0}.").format(left)
    )
    return _("{0}: these columns aren't imported: {1}.").format(session.file_name, left)


def cut_offs(files: List[Any]) -> Dict[str, str]:
    """Each opening file of the plan (stock, invoices, balances) → the cut-off date it is set up
    with."""
    from frappe_assistant_core.utils import import_opening_stock

    dates = {}
    for session in files:
        engine = dry_run.special_engine(session)
        if engine:
            settings = engine.settings(session)
            date = settings.get("posting_date") if engine is import_opening_stock else settings.get("cut_off")
            dates[session.file_name] = as_date(date) if date else ""
    return dates


def as_date(value) -> str:
    # Only YYYY-MM-DD: getdate reads "30 Sept" as this year's, a year nobody gave.
    if isinstance(value, str) and value and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        raise PlanProblem(_("The cut-off date is a date, YYYY-MM-DD: '{0}' isn't.").format(value))
    try:
        return str(getdate(value)) if value else ""
    except Exception:
        raise PlanProblem(_("The cut-off date is a date, YYYY-MM-DD: '{0}' isn't.").format(value))


def _check_cut_off(files: List[Any], cut_off: str) -> None:
    """The user's cut-off date is what every opening file is set up with. Raises PlanProblem."""
    dates = cut_offs(files)
    if not dates:
        raise PlanProblem(_("This plan has no opening stock, invoices or balances: no cut-off date to give."))
    wrong = [
        _("{0} has {1}").format(name, date or _("none")) for name, date in dates.items() if date != cut_off
    ]
    if wrong:
        raise PlanProblem(
            _(
                "Nothing was applied. {0}, not {1}: set the user's date on it first (set_opening_stock, "
                "set_opening_invoices or set_opening_balances), then answer again."
            ).format("; ".join(wrong), cut_off)
        )


# -- the run -------------------------------------------------------------------------------------
#
# One approval, then a chain: the plan's masters, then each file in order, checked again just before
# its import (a file before it may have failed rows) with the failure rule applied, the next file
# starting when the last one ends. A file imported in a background job continues the chain from
# that job's end (child_finished); one imported in the request continues the loop.


PLAN_JOB = "migration_plan::{0}"
STEP_SAVEPOINT = "fac_plan_step"
MASTERS_SAVEPOINT = "fac_plan_masters"


def _progress(plan) -> Dict[str, Any]:
    return frappe.parse_json(plan.progress or "{}") or {}


def _update(plan_name: str, status: Optional[str] = None, step: Optional[Tuple[str, str]] = None, **progress):
    """Change the plan as it is in the database now. The run and stop_migration_plan both write to
    it, so nothing saves a copy read before a long step."""
    plan = get_plan(plan_name)
    if progress:
        plan.progress = frappe.as_json({**_progress(plan), **progress})
    if status:
        plan.status = status
    if step:
        plan.log_step("Run", *step)
    plan.save()
    return plan


def plan_digest(session) -> str:
    """What a ready file's check depends on in its plan, besides the file itself: the records its
    earlier files (and the plan) will create. (What later files create only matters to rows that
    fail, and a file with failing rows is always checked again.)"""
    return hashlib.sha256(json.dumps(planned_names(session), sort_keys=True).encode()).hexdigest()


def card_figures(plan) -> Dict[str, Any]:
    """What the approval card shows, and run_migration_plan is given: files, rows ready to import,
    masters to create, the cut-off date and every decision the answers made, so the user approves
    what they can read rather than what FACO decided out of sight."""
    files = children(plan)
    rows = sum((frappe.parse_json(s.validation_summary or "{}") or {}).get("ready") or 0 for s in files)
    new = [m for m in masters(plan) if not frappe.db.exists(m["doctype"], m["name"])]
    dates = sorted({date for date in cut_offs(files).values() if date})
    return {
        "files": len(files),
        "rows": rows,
        "masters": len(new),
        "cut_off": ", ".join(dates),
        "decisions": decisions(plan, files, new),
    }


def decisions(plan, files: List[Any], new: List[Dict[str, Any]]) -> List[str]:
    """Each decision of the plan, one plain line each: the records it creates, each file's fixes
    and left-out rows, a file name whose date isn't the cut-off, and the failure rule."""
    from frappe_assistant_core.utils import import_fixes

    lines = [_("Create {0} '{1}'.").format(_(entry["doctype"]), entry["name"]) for entry in new]
    for session in files:
        for rule in import_fixes.value_maps(session):
            lines.append(
                _("{0}: {1} '{2}' → '{3}'.").format(
                    session.file_name,
                    _(rule.get("label") or rule.get("field")),
                    rule.get("from"),
                    rule.get("to"),
                )
            )
        for row in import_fixes.left_out(session):
            if row["reason"]:
                lines.append(
                    _("{0}: row {1} left out: {2}").format(session.file_name, row["row"], row["reason"])
                )
            else:
                lines.append(_("{0}: row {1} left out.").format(session.file_name, row["row"]))
        rules = frappe.parse_json(session.transformation_rules or "{}") or {}
        for item in rules.get("zero_rate_items") or []:
            lines.append(_("{0}: {1} is valued at zero.").format(session.file_name, item))
        if rules.get("post_at_cutoff"):
            lines.append(
                _("{0}: invoices dated in no fiscal year are posted at the cut-off.").format(
                    session.file_name
                )
            )
    dates = cut_offs(files)
    for file_name, said in name_dates(files).items():
        lines.append(
            _("Check: {0}'s name says {1}, but its cut-off is {2}.").format(
                file_name, said, dates.get(file_name)
            )
        )
    lines.append(
        _("Rows that still fail when their file comes up: {0}.").format(
            _("left out, with their reason") if plan.failure_rule == "leave_out" else _("the plan stops")
        )
    )
    return lines


MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
# Only a month's own name (Sep, Sept, September), so 30-Sepac isn't read as a date.
NAME_DATE = re.compile(
    r"(?<!\d)(\d{1,2})[-_ .]?(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?![a-z])"
    r"(?:[-_ .](\d{4}))?",
    re.IGNORECASE,
)


def name_dates(files: List[Any]) -> Dict[str, str]:
    """The opening files whose name gives a day and month (Closing Stock 30-Sep) other than their
    cut-off date: file → the date as its name gives it. Not a guess at the cut-off: a check."""
    dates, found = cut_offs(files), {}
    for session in files:
        cut_off = dates.get(session.file_name)
        match = NAME_DATE.search(session.file_name or "")
        if not cut_off or not match:
            continue
        day, month, year = int(match.group(1)), MONTHS.index(match.group(2)[:3].lower()) + 1, match.group(3)
        when = getdate(cut_off)
        if (day, month) != (when.day, when.month) or (year and int(year) != when.year):
            found[session.file_name] = match.group(0)
    return found


def opening_setup(plan) -> Dict[str, Any]:
    """What the plan's opening files (stock, invoices, balances) are set up with, asked once at the
    start rather than file by file: the company (the site's only one: nothing to ask) and the
    cut-off date, the user's once given, else dates to offer on one choice card."""
    if not frappe.db.exists("DocType", "Company"):
        return {}
    companies = frappe.get_all("Company", pluck="name", order_by="name")
    if len(companies) == 1:
        setup: Dict[str, Any] = {"company": companies[0]}
    else:
        setup = {"companies": companies, "suggested_company": frappe.defaults.get_user_default("Company")}
    cut_off = _progress(plan).get("cut_off")
    if cut_off:
        setup["cut_off"] = cut_off
    else:
        setup["cut_off_choices"] = cut_off_choices(children(plan)) + ["another_date"]
    return setup


def cut_off_choices(files: List[Any], on: Optional[str] = None) -> List[str]:
    """Dates to offer for the cut-off, newest first: a day a file's name gives (Closing Stock 30-Sep,
    the last one by then when it has no year), the last month end and the last fiscal year end,
    none after today. Choices the user picks from, never a date taken without asking."""
    on = getdate(on or today())
    dates = {get_last_day(add_months(on, -1))}
    for session in files:
        match = NAME_DATE.search(session.file_name or "")
        if not match:
            continue
        day, month, year = int(match.group(1)), MONTHS.index(match.group(2)[:3].lower()) + 1, match.group(3)
        for candidate in [int(year)] if year else [on.year, on.year - 1]:
            try:
                when = datetime.date(candidate, month, day)
            except ValueError:  # 31-Sep, 29-Feb
                break
            if when <= on:
                dates.add(when)
                break
    if frappe.db.exists("DocType", "Fiscal Year"):
        year_end = frappe.get_all(
            "Fiscal Year",
            filters={"year_end_date": ("<", on), "disabled": 0},
            pluck="year_end_date",
            order_by="year_end_date desc",
            limit=1,
        )
        dates.update(getdate(d) for d in year_end)
    return [str(d) for d in sorted(dates, reverse=True)]


def run_problem(plan) -> Optional[str]:
    """Why the plan can't run now, or None."""
    from frappe_assistant_core.utils import import_fixes, import_run

    if plan.status != "Ready to Run":
        return _("The plan is {0}: check it with dry_run_import (plan) until it is Ready to Run.").format(
            _(plan.status)
        )
    digests = _progress(plan).get("digests") or {}
    for session in children(plan):
        if (
            session.status != "Ready to Import"
            or not import_fixes.checked_as_is(session)
            or digests.get(session.name) != plan_digest(session)
        ):
            return _(
                "{0} changed since it was checked. Check the plan again with dry_run_import: the approval is "
                "for what was checked."
            ).format(session.file_name)
        engine = dry_run.special_engine(session)
        if engine:
            # The opening engines make their documents themselves, not through Data Import: what they
            # need (company, date, account, create and submit) is theirs to say, not Allow Import.
            try:
                engine.check_can_run(session)
                problem = None
            except dry_run.DryRunProblem as e:
                problem = str(e)
        else:
            problem = import_run.cannot_import(
                session.target_doctype, session.import_type or "Insert New Records"
            )
        if problem:
            return _("{0}: {1}").format(session.file_name, problem)
    for entry in masters(plan):
        if frappe.db.exists(entry["doctype"], entry["name"]):
            continue
        reason = import_fixes.cannot_create(entry["doctype"])
        if not reason and not frappe.has_permission(entry["doctype"], "create"):
            reason = _("you can't create {0} records").format(_(entry["doctype"]))
        if reason:
            return _("{0} '{1}' can't be created: {2}.").format(_(entry["doctype"]), entry["name"], reason)
    return None


def start(plan) -> None:
    """Run the approved plan in the background, as the user who approved it. Each file's
    fingerprint is kept: a file that changes after the approval isn't imported."""
    # The status as the database has it, locked: a second approval waits for the first to commit,
    # then finds the plan Running (the copy it was given says Ready to Run).
    stored = _settings(plan.name, for_update=True).get("status")
    if stored == "Running":
        raise PlanProblem(_("Plan {0} is already running.").format(plan.name))
    if stored != "Ready to Run":
        raise PlanProblem(
            _("Plan {0} is {1}: only a plan that is Ready to Run can be started.").format(
                plan.name, _(stored or "Planning")
            )
        )
    approved = {s.name: s.validated_fingerprint for s in children(plan)}
    request_stop(plan.name, 0)
    _update(
        plan.name,
        status="Running",
        step=("Success", _("Approved: {0} files.").format(len(approved))),
        done=[],
        left_out={},
        current=None,
        approved=approved,
        user=frappe.session.user,
    )
    _enqueue(plan.name, "run_job", deduplicate=True, user=frappe.session.user)


def _enqueue(plan_name: str, method: str, deduplicate: bool = False, **kwargs) -> None:
    """Queue a job of the plan. Only the run's start deduplicates: continue_job is queued while the
    job that started the file may still be STARTED (it returns after queueing the file's import),
    and a dropped continue would leave the plan Running with nothing to carry it on."""
    frappe.enqueue(
        f"{__name__}.{method}",
        queue="long",
        timeout=4 * 60 * 60,
        job_id=PLAN_JOB.format(plan_name),
        deduplicate=deduplicate,
        enqueue_after_commit=True,
        # Always a job, also in developer mode (where Data Import runs in the request): a plan imports
        # every file, and in a chat request it would outlast the client's timeout and roll back.
        now=bool(frappe.flags.in_test),
        plan_name=plan_name,
        **kwargs,
    )


def alive(plan) -> bool:
    """Whether a job of the plan, or of the file it is importing, is queued or running."""
    from frappe_assistant_core.utils import import_run

    if import_run.job_alive(PLAN_JOB.format(plan.name)):
        return True
    current = _progress(plan).get("current")
    if not current or frappe.db.get_value(dry_run.SESSION_DOCTYPE, current, "status") != "Importing":
        return False
    return import_run.job_running(frappe.get_doc(dry_run.SESSION_DOCTYPE, current))


#: A plan whose file's job ended less than this ago is between that job and its continue job.
HANDOFF_GRACE_SECONDS = 300
SWEEP_SAVEPOINT = "fac_plan_sweep"


def sweep_dead_plans() -> None:
    """Scheduled: end each Running plan nothing is running for (its worker died, or Redis was
    flushed), so its files can be imported on their own or planned again. What it imported stays."""
    for name in frappe.get_all(SESSION_DOCTYPE, filters={"plan_status": "Running"}, pluck="name"):
        frappe.db.savepoint(SWEEP_SAVEPOINT)
        try:
            if _end_if_dead(name) and not frappe.flags.in_test:
                frappe.db.commit()  # nosemgrep: frappe-manual-commit — a scheduled job commits its own work
        except Exception:
            frappe.db.rollback(save_point=SWEEP_SAVEPOINT)
            frappe.log_error(title=_("FAC migration plan sweep failed"), message=frappe.get_traceback())


def _end_if_dead(name: str) -> bool:
    _settings(name, for_update=True)  # the plan's row, held while it is judged and ended
    try:
        plan = get_plan(name)
    except frappe.DoesNotExistError:
        return False
    if plan.status != "Running" or alive(plan):
        return False
    handoff = _progress(plan).get("handoff_at")
    if handoff and (now_datetime() - get_datetime(handoff)).total_seconds() < HANDOFF_GRACE_SECONDS:
        return False
    _end(name, "Stopped", _("No job was running the plan, so it was stopped. What it imported stays."))
    return True


def _guarded(plan_name: str, work) -> None:
    """Run a step of the plan. Whatever goes wrong in it ends the plan, saying why, instead of
    leaving it Running with nothing to carry it on."""
    frappe.db.savepoint(STEP_SAVEPOINT)
    try:
        work()
    except Exception as e:
        try:
            frappe.db.rollback(save_point=STEP_SAVEPOINT)
        except Exception:
            if frappe.flags.in_test:
                raise
            frappe.db.rollback()  # a commit inside the step released the savepoint
        frappe.log_error(title=_("FAC migration plan stopped"), message=frappe.get_traceback())
        _end(plan_name, "Failed" if isinstance(e, PlanProblem) else "Stopped", str(e) or type(e).__name__)
    finally:
        frappe.local.fac_plan_running = None


def run_job(plan_name: str, user: str) -> None:
    """Background job: the plan's masters, then its files."""
    frappe.set_user(user)  # nosemgrep: frappe-setuser — the job runs as the user who approved the plan

    def masters_then_files():
        create_planned(get_plan(plan_name))
        _next_file(plan_name)

    _guarded(plan_name, masters_then_files)
    if not frappe.flags.in_test:
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — a background job commits its own work


def child_finished(session_name: str) -> None:
    """A session's import ended in a background job: its plan goes on in a job of its own, queued
    once this one has committed, so the plan's next file never runs inside a file's job."""
    if getattr(frappe.local, "fac_plan_running", None):
        return  # the plan's own loop is running and goes on itself
    plan_name = frappe.db.get_value(dry_run.SESSION_DOCTYPE, session_name, "migration_plan")
    if not plan_name:
        return
    try:
        plan = get_plan(plan_name)
    except frappe.DoesNotExistError:
        return
    if plan.status != "Running" or _progress(plan).get("current") != session_name:
        return
    # Committed with this job, before the continue job is in Redis: the sweep leaves the plan alone
    # while the hand-off is this fresh (sweep_dead_plans).
    _update(plan_name, handoff_at=str(now_datetime()))
    _enqueue(
        plan_name,
        "continue_job",
        session_name=session_name,
        user=_progress(plan).get("user") or frappe.session.user,
    )


def continue_job(plan_name: str, session_name: str, user: str) -> None:
    """Background job: record the file that ended, then the plan's next files."""
    frappe.set_user(user)  # nosemgrep: frappe-setuser — the job runs as the user who approved the plan

    def next_files():
        plan = get_plan(plan_name)
        if plan.status != "Running" or _progress(plan).get("current") != session_name:
            return
        if _file_done(plan_name, session_name):
            _next_file(plan_name)

    _guarded(plan_name, next_files)
    if not frappe.flags.in_test:
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — a background job commits its own work


def _next_file(plan_name: str) -> None:
    """Import the plan's files from the first not done, until one waits on a background job, the
    plan stops, or none is left."""
    frappe.local.fac_plan_running = plan_name
    try:
        while True:
            plan = get_plan(plan_name)
            done = set(_progress(plan).get("done") or [])
            child = next((s for s in children(plan) if s.name not in done), None)
            if child is None:
                return _finish(plan_name)
            if plan.stop_requested:
                return _end(plan_name, "Stopped", _("Stopped before {0}, as asked.").format(child.file_name))
            # An error from here on rolls back this file's step only (_guarded): the files before it
            # stay imported, also when one job imports several (in the request, in developer mode).
            frappe.db.savepoint(STEP_SAVEPOINT)
            stop = _prepare(plan, child)
            if stop:
                return _end(plan_name, "Stopped", stop)
            _update(plan_name, current=child.name)
            try:
                waiting = _import(child)
            except Exception as e:
                return _end(
                    plan_name, "Stopped", _("{0} couldn't be imported: {1}").format(child.file_name, str(e))
                )
            if waiting:
                return  # its job calls child_finished when it ends
            if not _file_done(plan_name, child.name):
                return
    finally:
        frappe.local.fac_plan_running = None


def _prepare(plan, child) -> Optional[str]:
    """Check the file again just before its import and apply the failure rule. Returns why the plan
    stops, or None."""
    from frappe_assistant_core.utils import import_fixes

    approved = (_progress(plan).get("approved") or {}).get(child.name)
    # What was checked is compared with what is there now (checked_as_is), not with a stored copy: a
    # changed file, mapping or rule leaves the stored fingerprint alone.
    if (
        child.status != "Ready to Import"
        or child.validated_fingerprint != approved
        or not import_fixes.checked_as_is(child)
    ):
        return _(
            "{0} changed after the plan was approved ({1} now), so it isn't imported. Check the plan "
            "again with dry_run_import."
        ).format(child.file_name, _(child.status))
    # The plan job is a background job: a file over BACKGROUND_ROWS, checked in the background
    # before the approval, is checked here too (#34427).
    import_fixes.check(child.name, in_background=True)
    child.reload()
    if child.status == "Dry Run Failed":
        groups = import_fixes.last_groups(child)
        count = sum(g.get("count") or 0 for g in groups.values())
        if plan.failure_rule == "stop":
            return _("{0}: {1} rows would fail now, and the plan stops when that happens.").format(
                child.file_name, count
            )
        fixes = [
            {
                "group": group_id,
                "action": import_fixes.LEAVE_OUT,
                "reason": _("Not imported: {0}").format(group.get("message") or group.get("cause")),
            }
            for group_id, group in groups.items()
        ]
        import_fixes.apply_fixes(child, groups, fixes)
        child.save()
        left_out = dict(_progress(plan).get("left_out") or {})
        left_out[child.name] = left_out.get(child.name, 0) + count
        _update(
            plan.name,
            step=(
                "Warning",
                _("{0}: {1} rows left out, as they would fail now.").format(child.file_name, count),
            ),
            left_out=left_out,
        )
        import_fixes.check(child.name, in_background=True)
        child.reload()
    if child.status not in ("Ready to Import", "Completed"):
        return _("{0} isn't ready to import ({1}).").format(child.file_name, _(child.status))
    return None


def _import(child) -> bool:
    """Start the file's import. True while it runs in a background job."""
    from frappe_assistant_core.utils import import_run

    summary = frappe.parse_json(child.validation_summary or "{}") or {}
    if child.status == "Completed":
        return False
    if not summary.get("ready"):
        # nothing left to import in it: an update with every row unchanged is done (#34436), and
        # so is a file whose every row is left out, which stayed Ready to Import for good (#34351)
        if not import_run.close_unchanged(child) and child.status == import_run.READY:
            child.status = "Completed"
            child.log_step("Import", "Warning", _("Every row is left out, so nothing was imported."))
            child.save()
        return False
    engine = dry_run.special_engine(child)
    if engine:
        engine.create(child)
    else:
        import_run.start(child)
    child.reload()
    return child.status == "Importing"


def _file_done(plan_name: str, session_name: str) -> bool:
    """Record the file as done. False when its import didn't end, and the plan stops."""
    child = frappe.get_doc(dry_run.SESSION_DOCTYPE, session_name)
    summary = frappe.parse_json(child.validation_summary or "{}") or {}
    if child.status not in IMPORTED and summary.get("ready"):
        last = child.steps[-1].message if child.steps else ""
        _end(plan_name, "Stopped", _("{0} didn't finish importing: {1}").format(child.file_name, last))
        return False
    plan = get_plan(plan_name)
    done = list(_progress(plan).get("done") or [])
    if child.name not in done:
        done.append(child.name)
    _update(
        plan_name,
        step=("Success", _("{0}: {1}.").format(child.file_name, _(child.status))),
        done=done,
        current=None,
    )
    return True


def _finish(plan_name: str) -> None:
    plan = get_plan(plan_name)
    files = children(plan)
    left_out = sum((_progress(plan).get("left_out") or {}).values())
    if all(s.status == "Failed" for s in files):
        status = "Failed"
    elif left_out or any(s.status != "Completed" for s in files):
        status = "Partially Completed"
    else:
        status = "Completed"
    message = _("{0} files imported.").format(len(files))
    if left_out:
        message += " " + _("{0} rows left out, as they would have failed.").format(left_out)
    _end(plan_name, status, message)


def _end(plan_name: str, status: str, message: str) -> None:
    from frappe_assistant_core.utils import import_notify

    outcome = {"Completed": "Success", "Partially Completed": "Warning"}.get(status, "Failed")
    _update(plan_name, status=status, step=(outcome, message), current=None)
    import_notify.plan_ended(get_plan(plan_name), status, message)


def result(plan) -> Dict[str, Any]:
    """The run as FACO reports it: each file's state and counts, and what the plan says."""
    from frappe_assistant_core.utils import import_failures

    left_out = _progress(plan).get("left_out") or {}
    files = []
    for session in children(plan):
        created = sum(run["created"] for run in import_failures.runs(session)) or len(session.created_records)
        files.append(
            {
                "session": session.name,
                "file_name": session.file_name,
                "doctype": session.target_doctype,
                "status": session.status,
                "created": created,
                "left_out": left_out.get(session.name, 0),
            }
        )
    return {
        "plan": plan.name,
        "status": plan.status,
        "files": files,
        "message": plan.steps[-1].message if plan.steps else "",
    }
