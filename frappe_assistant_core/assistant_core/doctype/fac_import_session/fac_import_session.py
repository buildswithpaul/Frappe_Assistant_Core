# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
FAC Import Session: one uploaded file moving through a data migration — read,
map, dry run, import.

The assistant is rebuilt on every turn, so this record is what keeps the file,
the mapping, the fixes and the validation results between messages. Its step
log records what was done, by whom, and what failed.
"""

import copy
from typing import Any, List, Optional

import frappe
from frappe import _
from frappe.model import no_value_fields, table_fields
from frappe.model.document import Document
from frappe.utils import cint, flt, get_datetime, getdate, now_datetime

from frappe_assistant_core.chat.utils.permissions import _doc_owner_or_admin, _user_or_admin

SESSION_DOCTYPE = "FAC Import Session"

#: The migration plan's fields (#34351): written only by import_plan, with db.set_value.
PLAN_FIELDS = (
    "migration_plan",
    "plan_position",
    "plan_reason",
    "plan_settings",
    "plan_status",
    "plan_failure_rule",
    "plan_cut_off",
    "plan_stop_requested",
    "plan_importing_now",
)

#: What a new session may be given by anyone: whose it is, and when it was made (its default).
#: Every other field is the import engine's.
NEW_SESSION_FIELDS = ("user", "started_on")


def engine_write(doc):
    """Mark ``doc`` as the import engine's own copy: its saves may change the session's fields.
    The mark is a document flag, which no request body, frappe.client call or document tool
    can set (Frappe drops a "flags" key from the values it is given).

    Its links aren't checked: created_records lists what the import made, and an undo, or a user,
    may delete those records since. Frappe 16 checks a child table's Dynamic Links on save, so a
    session naming one that is gone could no longer be saved, not even by the undo itself."""
    doc.flags.fac_import_engine = True
    doc.flags.ignore_links = True
    return doc


def engine_session(name: str):
    """The session ``name``, loaded by the import engine for its own writes."""
    return engine_write(frappe.get_doc(SESSION_DOCTYPE, name))


class SessionRow(Document):
    """A row of an import session's tables: its audit steps, created records and Data Imports. The
    engine writes rows only with their session, whose save writes them without their own
    validate, so a row saved, added or deleted on its own (PUT or POST on its DocType,
    frappe.client, bulk_update, a delete) is never the engine's (#34400)."""

    def validate(self):
        self._refuse()

    def on_trash(self):
        self._refuse()

    def _refuse(self):
        frappe.throw(
            _(
                "Only the import tools can change an import session: its {0} rows aren't changed one by one."
            ).format(_(self.doctype)),
            frappe.PermissionError,
        )


class FACImportSession(Document):
    @frappe.whitelist(methods=["POST"])
    def release(self, reason: str):
        """Release a session stuck importing, or a plan nothing runs (#34542): System Manager only,
        through the engine's own copy, with who and why in the step log. Frappe checks only read
        before a document method; the role is checked in release."""
        from frappe_assistant_core.utils import import_housekeeping

        return import_housekeeping.release(self.name, reason)

    def validate(self):
        # Every field is the engine's state: the dry run's verdict, the mapping, the file, the
        # Data Imports and the created-records list (#34400). Only the engine writes them, for everyone
        # (System Managers too): a session changed by hand would import what was never checked.
        if self.flags.fac_import_engine:
            return
        changed = self._changed_by_hand()
        if changed:
            frappe.throw(
                _("Only the import tools can change an import session: {0} can't be set by hand.").format(
                    ", ".join(changed)
                ),
                frappe.PermissionError,
            )

    def _changed_by_hand(self) -> List[str]:
        """The engine-owned fields this save would change. A new session may set only its user,
        so it joins no plan and carries no verdict (#34429); the plan's fields of a saved one are
        put back by before_save, so they are left to it."""
        if self.is_new():
            before, skip = frappe.new_doc(self.doctype), NEW_SESSION_FIELDS
        else:
            before, skip = self.get_doc_before_save() or frappe.get_doc(self.doctype, self.name), PLAN_FIELDS
        changed = []
        for df in self.meta.fields:
            if df.fieldname in skip:
                continue
            if df.fieldtype in table_fields:  # a Table is in no_value_fields too
                same = _rows(self, df) == _rows(before, df)
            elif df.fieldtype in no_value_fields:
                continue
            else:
                same = _comparable(df, self.get(df.fieldname)) == _comparable(df, before.get(df.fieldname))
            if not same:
                changed.append(df.fieldname)
        return changed

    def save_version(self):
        """Desk's history of the session, without its JSON fields (#34413): the check's summary,
        the file's sheets and the rules are large, and every save would copy them into a Version.
        The steps table says what happened."""
        before = self._doc_before_save
        if before is not None:
            # the same JSON on both sides: Version records no change to it
            self._doc_before_save = copy.copy(before)
            for df in self.meta.get("fields", {"fieldtype": "JSON"}):
                self._doc_before_save.set(df.fieldname, self.get(df.fieldname))
        try:
            super().save_version()
        finally:
            self._doc_before_save = before

    def before_save(self):
        # A plan's run saves a file's session it read before it moved the plan on: that copy must
        # not write the plan's old values back.
        if not self.is_new():
            self.update(frappe.db.get_value(self.doctype, self.name, PLAN_FIELDS, as_dict=True) or {})

    def log_step(
        self,
        step: str,
        outcome: str,
        message: str,
        rows_ok: Optional[int] = None,
        rows_failed: Optional[int] = None,
    ) -> None:
        """Append a row to the step log. The caller saves the session."""
        self.append(
            "steps",
            {
                "timestamp": now_datetime(),
                "step": step,
                "outcome": outcome,
                "user": frappe.session.user,
                # which file the step worked on: a corrected file later replaces source_file. The
                # one the user gave, not the session's copy of it (#34405)
                "file": self.original_file or self.source_file or self.file_name,
                "rows_ok": rows_ok,
                "rows_failed": rows_failed,
                "message": message,
            },
        )


def _comparable(df, value) -> Any:
    """A field's value as the database keeps it: Desk sends dates and JSON as text, and blank
    for nothing, so an untouched form compares equal."""
    if df.fieldtype in ("Int", "Check"):
        return cint(value)
    if df.fieldtype in ("Float", "Currency", "Percent"):
        return flt(value)
    if value in (None, ""):
        return None
    if df.fieldtype == "Datetime":
        return get_datetime(value)
    if df.fieldtype == "Date":
        return getdate(value)
    if df.fieldtype == "JSON" and isinstance(value, str):
        try:
            return frappe.parse_json(value)
        except ValueError:
            return value
    return value


def _rows(doc, table_df) -> List[tuple]:
    """A child table's rows, in order, by their own fields' values."""
    fields = [df for df in frappe.get_meta(table_df.options).fields if df.fieldtype not in no_value_fields]
    return [
        tuple(_comparable(df, row.get(df.fieldname)) for df in fields)
        for row in doc.get(table_df.fieldname) or []
    ]


# Same rule as FAC Chat Message: a session is visible to its user and to System Managers.
def get_permission_query_conditions(user=None):
    return _user_or_admin(user, "FAC Import Session")


def has_permission(doc, user=None, permission_type=None):
    return _doc_owner_or_admin(doc, user)


#: A session in one of these has ended: there is nothing to release.
ENDED = ("Completed", "Cancelled", "Undone")


@frappe.whitelist(methods=["POST"])
def release(session: str) -> None:
    """End a session no tool moves on any more, for a System Manager (#34538): an import whose
    worker died, say. It is Cancelled, so it stops holding the user's file; nothing it imported is
    undone. The engine writes it, as only it may (validate refuses a hand edit)."""
    # Not frappe.only_for, which lets anyone through while tests run (Frappe 15)
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only a System Manager can release an import session."), frappe.PermissionError)
    doc = engine_session(session)
    if doc.status in ENDED:
        frappe.throw(_("Import session {0} has ended already ({1}).").format(session, _(doc.status)))
    doc.status = "Cancelled"
    doc.log_step(
        "Release",
        "Warning",
        _("Released by {0}: the session is cancelled. Records it imported stay.").format(frappe.session.user),
    )
    doc.save(ignore_permissions=True)
