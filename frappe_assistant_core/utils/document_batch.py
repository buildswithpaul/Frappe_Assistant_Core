# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Many documents in one tool call: the list mode of create_document and update_document.

One call is one approval card, so a list lets the user approve many records at once. The
records are checked first, then written all or none: they share a savepoint that is rolled
back on the first failure, and what a write leaves for the commit (its global search entry,
the commit callbacks and the realtime and webhook events it queues) is held until all have
succeeded. Each record goes through the tool's own single-record code, so with the same
permission and field checks.

Nothing inside the list may end its transaction. A controller's commit is ignored (Frappe's
own ``_disable_transaction_control`` where Frappe has it, v16; a stand-in for commit on v15).
A controller's full rollback, and any change to the database schema (which commits), fail the
list instead, before they run. Customisations and the doctypes known to change the schema are
refused before anything is written: they are made one at a time, where the customisation
approval applies to them.

What a save sends out at once, rather than at the commit, can't be held: a Notification's
Slack or SMS message, or a job a controller enqueues straight away. A record undone with a
failed batch may already have sent those, as a single record that fails after saving would.
"""

from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional

import frappe
from frappe import _
from frappe.utils import cstr
from frappe.utils.global_search import update_global_search

from frappe_assistant_core.utils.customisation import CUSTOMISATION_DOCTYPES, SCHEMA_CHANGING_DOCTYPES

MAX_DOCUMENTS = 100
SAVEPOINT = "fac_document_batch"
_UNSET = object()

# Realtime events and webhooks wait in these lists for the commit, which flushes them through
# a callback added with the list. A list that outlives its callback would never be sent again.
_QUEUES = ("_realtime_log", "_webhook_queue")

# Statements that change the schema, which MariaDB commits implicitly (Frappe's own list, less
# START and BEGIN, which Frappe's check_implicit_commit still refuses after a write).
_SCHEMA_STATEMENTS = frozenset(("alter", "create", "drop", "truncate"))


class BatchProblem(Exception):
    """The list can't be written. Nothing was. ``problems`` says which records and why."""

    def __init__(
        self,
        message: str,
        problems: Optional[List[Dict[str, Any]]] = None,
        written: bool = False,
        error_type: Optional[str] = None,
    ):
        super().__init__(message)
        self.problems = problems or []
        self.written = written  # True when a write failed (and was undone), not a check
        self.error_type = error_type

    def as_result(self) -> Dict[str, Any]:
        """The tool's reply for it."""
        result = {"success": False, "error": str(self), "problems": self.problems}
        if self.error_type:
            result["error_type"] = self.error_type
        return result


class SchemaChangeStopped(Exception):
    """Raised in place of a statement that would change the schema while a list is written."""


def given(value) -> bool:
    """An input counts only when it holds something: clients fill optional inputs with
    empty values ("" or [] or {}), which must read as not given."""
    return value not in (None, "", [], {})


def read_documents(arguments: Dict[str, Any], single_inputs: tuple, with_name: bool) -> List[Dict[str, Any]]:
    """``arguments["documents"]`` checked: a list of up to MAX_DOCUMENTS entries, each with a
    doctype and a data object (and a name, for updates), and not mixed with the single-record
    inputs, with no customisation and no internal key. Raises BatchProblem."""
    documents = arguments.get("documents")
    clashing = [key for key in single_inputs if given(arguments.get(key))]
    if clashing:
        raise BatchProblem(_("Pass either documents or {0}, not both.").format(" + ".join(single_inputs)))
    if not isinstance(documents, list):
        raise BatchProblem(_("documents must be a list."))
    if len(documents) > MAX_DOCUMENTS:
        raise BatchProblem(
            _("At most {0} documents in one call; this has {1}. Split them into several calls.").format(
                MAX_DOCUMENTS, len(documents)
            )
        )
    keys = ("doctype", "name", "data") if with_name else ("doctype", "data")
    problems = []
    for number, entry in enumerate(documents, start=1):
        if not isinstance(entry, dict):
            problems.append({"document": number, "error": _("Each document must be an object.")})
            continue
        missing = [key for key in keys if key != "data" and not cstr(entry.get(key)).strip()]
        if not isinstance(entry.get("data"), dict):
            missing.append("data")
        if missing:
            problems.append({"document": number, "error": _("Missing {0}.").format(", ".join(missing))})
    if problems:
        raise BatchProblem(_("Nothing was written. Correct these and call again."), problems)
    _refuse_one_at_a_time(documents, with_name)
    _refuse_internal_keys(documents)
    return documents


def internal_keys_refusal(doctype: Any, data: Any) -> Optional[Dict[str, Any]]:
    """The reply refusing one record (create_document or update_document without documents)
    whose data sets Frappe's own keys, as a list's records are refused; else None (#34541)."""
    if not isinstance(data, dict):
        return None
    try:
        _refuse_internal_keys([{"doctype": doctype, "data": data}])
    except BatchProblem as e:
        return e.as_result()
    return None


def _refuse_internal_keys(documents: List[Dict[str, Any]]) -> None:
    """A key that starts with "_" is Frappe's own (_assign, _comments, _liked_by, _user_tags)
    and is set on the document like any field: refused for every role, before anything is
    written. Only two are inputs: ``__newname`` names a Prompt-named record (the masters plan
    sends it), and a child row's ``_delete`` removes it in an update. Raises BatchProblem
    listing every such record and key."""
    problems = []
    for number, entry in enumerate(documents, start=1):
        keys = [key for key in entry["data"] if _internal(key) and key != "__newname"]
        for field, rows in entry["data"].items():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if isinstance(row, dict):
                    keys += [
                        f"{field}.{key}"
                        for key in row
                        if _internal(key) and key != "_delete" and f"{field}.{key}" not in keys
                    ]
        if keys:
            problems.append(_problem(number, entry, _("Can't set {0}.").format(", ".join(keys))))
    if problems:
        raise BatchProblem(
            _(
                "Nothing was written. Keys that start with an underscore are Frappe's own and can't "
                "be set: take them out of these records and call again. Only __newname (the name of "
                "a record named by prompt) and a child row's _delete may be sent."
            ),
            problems,
            error_type="internal_key",
        )


def _internal(key: Any) -> bool:
    return cstr(key).startswith("_")


def _refuse_one_at_a_time(documents: List[Dict[str, Any]], with_name: bool) -> None:
    """Customisations and doctypes whose save changes the schema are made one at a time: as one
    record the customisation approval applies to them, and a schema change commits, which would
    keep half a list. Raises BatchProblem listing every such record."""
    problems = []
    for number, entry in enumerate(documents, start=1):
        doctype = cstr(entry["doctype"]).strip()
        if doctype in CUSTOMISATION_DOCTYPES:
            problems.append(_problem(number, entry, _("A customisation: make it on its own.")))
        elif doctype in SCHEMA_CHANGING_DOCTYPES:
            problems.append(_problem(number, entry, _("Changes the database schema: make it on its own.")))
    if problems:
        inputs = _("doctype, name and data") if with_name else _("doctype and data")
        raise BatchProblem(
            _(
                "Nothing was written. Customisations and records that change the database schema "
                "can't be in documents: make each of these on its own, with {0}, one call each. "
                "The other records may still go as a list."
            ).format(inputs),
            problems,
            error_type="one_at_a_time",
        )


def check_access(documents: List[Dict[str, Any]], perm_type: str) -> None:
    """Before anything is written: may the user ``perm_type`` each record, without setting a
    field kept from them? The same checks the tools make for one record. Raises BatchProblem
    listing every record that fails."""
    from frappe_assistant_core.core.security_config import get_restricted_fields, validate_document_access

    problems = []
    for number, entry in enumerate(documents, start=1):
        doctype, name = entry["doctype"], entry.get("name")
        access = validate_document_access(
            user=frappe.session.user, doctype=doctype, name=name, perm_type=perm_type
        )
        if not access.get("success"):
            problems.append(_problem(number, entry, access.get("error")))
            continue
        restricted = get_restricted_fields(doctype, access.get("role"))
        kept = [field for field in entry["data"] if field in restricted]
        if kept:
            problems.append(
                _problem(number, entry, _("Cannot set restricted fields: {0}.").format(", ".join(kept)))
            )
    if problems:
        raise BatchProblem(_("Nothing was written. Correct these and call again."), problems)


def write_all(
    documents: List[Dict[str, Any]],
    write: Callable[[Dict[str, Any]], Dict[str, Any]],
    done: str,
    after: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
) -> List[Dict[str, Any]]:
    """``write`` every document, or, if one fails, none.

    ``write`` is the tool's own single-record call and returns its result. ``after`` runs with
    the results inside the same savepoint, so what it saves is undone with a failure too.
    ``done`` is the past tense for messages ("created"). Raises BatchProblem.
    """
    callbacks = _commit_callbacks()
    queues = _commit_queues()
    conf = frappe.local.conf
    search_setting = conf.get("disable_global_search", _UNSET)
    conf["disable_global_search"] = True
    guard = _TransactionGuard()
    frappe.db.savepoint(SAVEPOINT)
    results = []
    try:
        with guard.held():
            for number, entry in enumerate(documents, start=1):
                result = write(entry)
                guard.check(number, entry, result, done)
                results.append(result)
            if after:
                after(results)
    except Exception:
        frappe.db.rollback(save_point=SAVEPOINT)
        _run_rollback_work(callbacks)
        _restore_commit_callbacks(callbacks)
        _restore_commit_queues(queues)
        raise
    finally:
        if search_setting is _UNSET:
            conf.pop("disable_global_search", None)
        else:
            conf["disable_global_search"] = search_setting

    for result in results:
        # The records are written: a search entry that can't be made mustn't report otherwise.
        try:
            update_global_search(frappe.get_doc(result["doctype"], result["name"]))
        except Exception:
            frappe.log_error(title=_("Global search entry not made"), message=frappe.get_traceback())
    return results


class _TransactionGuard:
    """Keeps a list's transaction whole while it is written.

    - A commit is ignored: Frappe's own ``_disable_transaction_control`` where it exists (v16),
      raised and given back exactly as it was, so a caller's own raise is kept; on v15, which has
      no such flag, a stand-in for ``frappe.db.commit``.
    - A full rollback is not run (it would undo what the request wrote before the list, and the
      list's savepoint), but noted, and fails the list.
    - A schema change is refused before it runs (it commits, even on v16, whose sql_ddl lifts
      the flag to commit), and fails the list.

    The stand-ins are set on this request's own ``frappe.db``; whatever was there before,
    such as the dry run's own commit stand-in, is put back.
    """

    def __init__(self):
        self.rolled_back = False
        self.schema_change: Optional[str] = None

    @contextmanager
    def held(self):
        db = frappe.db
        replaced = ("commit", "rollback", "sql_ddl", "check_implicit_commit")
        before = {name: vars(db).get(name, _UNSET) for name in replaced}
        rollback, check_implicit_commit = db.rollback, db.check_implicit_commit
        flag = getattr(db, "_disable_transaction_control", None)

        def no_rollback(*args, save_point=None, **kwargs):
            if save_point:
                return rollback(*args, save_point=save_point, **kwargs)
            self.rolled_back = True

        def no_ddl(query, *args, **kwargs):
            self._stop(query)

        def no_schema_change(query, *args, **kwargs):
            if _statement(query) in _SCHEMA_STATEMENTS:
                self._stop(query)
            return check_implicit_commit(query, *args, **kwargs)

        if flag is None:
            db.commit = _no_commit
        else:
            db._disable_transaction_control = flag + 1
        db.rollback = no_rollback
        db.sql_ddl = no_ddl
        db.check_implicit_commit = no_schema_change
        try:
            yield
        finally:
            for name, value in before.items():
                if value is _UNSET:
                    vars(db).pop(name, None)
                else:
                    setattr(db, name, value)
            if flag is not None:
                db._disable_transaction_control = flag

    def _stop(self, query: str) -> None:
        self.schema_change = self.schema_change or cstr(query)
        raise SchemaChangeStopped(
            _("A change to the database schema can't be made inside a list of documents.")
        )

    def check(self, number: int, entry: Dict[str, Any], result: Dict[str, Any], done: str) -> None:
        """After a record is written: raise BatchProblem if it failed, changed the schema or
        rolled back, even when it reports success (a controller may catch the refusal)."""
        if self.schema_change:
            error = _(
                "It would change the database schema, which commits, so it can't be in a list. "
                "Make it on its own, then send the others as a list"
            )
            error_type = "schema_change_in_list"
        elif not result.get("success"):
            error, error_type = cstr(result.get("error")).rstrip("."), None
        elif self.rolled_back:
            error = _(
                "It tried to roll back the whole transaction, which would undo more than this "
                "list. Make it on its own"
            )
            error_type = "rollback_in_list"
        else:
            return
        raise BatchProblem(
            _("Document {0} ({1}) couldn't be {2}: {3}. Nothing was {2}.").format(
                number, _label(entry), done, error
            ),
            [_problem(number, entry, error)],
            written=True,
            error_type=error_type,
        )


def _statement(query: Any) -> str:
    """The statement's first word, lower case: "alter", "insert"."""
    words = cstr(query).split(None, 1)
    return words[0].lower() if words else ""


def _label(entry: Dict[str, Any]) -> str:
    """ "Note", or "Customer 'CUST-0001'" when the record has a name."""
    label = _(entry["doctype"])
    return f"{label} '{entry['name']}'" if entry.get("name") else label


def _problem(number: int, entry: Dict[str, Any], error: Any) -> Dict[str, Any]:
    problem = {"document": number, "doctype": entry.get("doctype"), "error": cstr(error)}
    if entry.get("name"):
        problem["name"] = entry["name"]
    return problem


def _commit_callbacks() -> Dict[str, list]:
    return {
        name: list(getattr(frappe.db, name)._functions)
        for name in ("before_commit", "after_commit", "before_rollback", "after_rollback")
    }


def _run_rollback_work(callbacks: Dict[str, list]) -> None:
    """Run the after_rollback work the batch queued, as a full rollback would: a File made
    public is moved back to private, a cached document is cleared."""
    queue = frappe.db.after_rollback._functions
    for callback in list(queue)[len(callbacks["after_rollback"]) :]:
        try:
            callback()
        except Exception:
            frappe.log_error(title=_("Document Rollback Error"), message=frappe.get_traceback())


def _restore_commit_callbacks(callbacks: Dict[str, list]) -> None:
    for name, functions in callbacks.items():
        manager = getattr(frappe.db, name)
        manager._functions.clear()
        manager._functions.extend(functions)


def _commit_queues() -> Dict[str, Any]:
    return {
        name: list(getattr(frappe.local, name)) if hasattr(frappe.local, name) else _UNSET for name in _QUEUES
    }


def _restore_commit_queues(queues: Dict[str, Any]) -> None:
    for name, items in queues.items():
        if items is _UNSET:
            if hasattr(frappe.local, name):
                delattr(frappe.local, name)
        else:
            setattr(frappe.local, name, items)


def _no_commit(*args, **kwargs):
    """Stands in for frappe.db.commit while the batch is written."""
    return None
