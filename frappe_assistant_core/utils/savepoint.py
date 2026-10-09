# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Savepoints that also undo the commit work queued inside them.

A tool that wants a refused action to leave nothing behind cannot rely on
``frappe.db.rollback(save_point=...)`` alone. It undoes the SQL, but work queued
for the commit stays queued and runs when the request commits, after the action
it belonged to was undone: ERPNext's Period Closing Voucher, for one, enqueues
the cancellation of its GL entries after commit. Desk raises instead, and its
full rollback resets those queues; ``rollback_to_savepoint`` puts back what the
refused action added to them.

Used by document_action (submit, cancel, amend) and create_document (submit).
"""

import copy
from typing import Any, Dict

import frappe
from frappe import _

_COMMIT_CALLBACKS = ("before_commit", "after_commit")
# Frappe parks some commit work on frappe.local and registers its flush only when it first
# creates the queue, so dropping the flush while keeping the queue would stop every later
# event in the request from flushing. These are put back exactly as they were.
_LOCAL_COMMIT_QUEUES = ("_realtime_log", "_webhook_queue", "_link_count")
_ABSENT = object()


def _callback_queue(name: str):
    return getattr(getattr(frappe.db, name, None), "_functions", None)


def _snapshot_local(name: str):
    value = getattr(frappe.local, name, _ABSENT)
    return value if value is _ABSENT else copy.copy(value)


def open_savepoint(savepoint: str) -> Dict[str, Any]:
    """Open ``savepoint`` and note the commit work already queued, to unwind back to."""
    frappe.db.savepoint(savepoint)
    return {
        "callbacks": {
            name: len(queue)
            for name in (*_COMMIT_CALLBACKS, "after_rollback")
            if (queue := _callback_queue(name)) is not None
        },
        "locals": {name: _snapshot_local(name) for name in _LOCAL_COMMIT_QUEUES},
    }


def _unwind_commit_work(marks: Dict[str, Any]) -> None:
    """Undo what the refused action queued for the commit, as a full rollback would."""
    # A full rollback runs its after_rollback work (file cleanup, cache and realtime resets);
    # run what the refused action registered, in order.
    queue = _callback_queue("after_rollback")
    if queue is not None:
        added = [queue.pop() for _ in range(len(queue) - marks["callbacks"].get("after_rollback", 0))]
        for callback in reversed(added):
            try:
                callback()
            except Exception:
                frappe.log_error(title=_("Document Rollback Error"), message=frappe.get_traceback())

    for name, value in marks["locals"].items():
        if value is _ABSENT:
            if hasattr(frappe.local, name):
                delattr(frappe.local, name)
        else:
            setattr(frappe.local, name, value)

    for name in _COMMIT_CALLBACKS:
        queue = _callback_queue(name)
        if queue is not None:
            while len(queue) > marks["callbacks"].get(name, 0):
                queue.pop()


def rollback_to_savepoint(savepoint: str, marks: Dict[str, Any], doctype: str, name: str) -> None:
    """Undo everything since ``open_savepoint``: the SQL and the commit work it queued."""
    try:
        frappe.db.rollback(save_point=savepoint)
    except Exception:
        # The savepoint only disappears if something inside the call committed, in which
        # case its partial changes are already persisted and need a human to look at them.
        # That commit also ran its queued work, so there is nothing left to unwind.
        frappe.log_error(
            title=_("Document Rollback Error"),
            message=f"Could not roll back {doctype} '{name}':\n{frappe.get_traceback()}",
        )
    else:
        _unwind_commit_work(marks)
    # A doc cached while the rolled-back changes were visible would otherwise outlive them.
    frappe.clear_document_cache(doctype, name)


def release_savepoint(savepoint: str) -> None:
    try:
        frappe.db.release_savepoint(savepoint)
    except Exception:
        pass  # Already gone because something inside the call committed; the work succeeded.
