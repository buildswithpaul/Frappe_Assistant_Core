# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
An import session's files don't outlive retention (#34539).

A session keeps its own copy of the user's file, and its check's results, so it can carry on once
chat retention has deleted the chat's attachment. Those files hold the user's customers and
accounts. An ended session's files are deleted after the chat retention window, and a user's
when their personal data is deleted; the session itself stays, with its step log.
"""

from typing import List

import frappe
from frappe import _
from frappe.utils import add_days, now_datetime

from frappe_assistant_core.assistant_core.doctype.fac_import_session.fac_import_session import engine_session
from frappe_assistant_core.utils.import_session import HOLDING_STATUSES

SESSION_DOCTYPE = "FAC Import Session"
#: A session in one of these is done with its files: a Failed or Partially Completed one that
#: nobody carried on with for the whole window is abandoned, and is Cancelled with them (#34541).
ENDED = ("Completed", "Failed", "Partially Completed", "Cancelled", "Undone")
ABANDONED = ("Failed", "Partially Completed")
PURGED_STEP = "Retention"


def purge_old_sessions() -> int:
    """Daily: delete the files of every session that ended before the chat retention window
    (FAC Chat Settings, as cleanup_old_messages reads it). Returns how many sessions."""
    from frappe_assistant_core.chat.scheduler.retention import DEFAULT_RETENTION_DAYS, MIN_RETENTION_DAYS

    settings = frappe.get_cached_doc("FAC Chat Settings")
    if not getattr(settings, "enable_retention_cleanup", 1):
        return 0
    days = int(getattr(settings, "message_retention_days", 0) or 0)
    if days < MIN_RETENTION_DAYS:
        days = DEFAULT_RETENTION_DAYS
    names = frappe.get_all(
        SESSION_DOCTYPE,
        filters={"status": ["in", ENDED], "modified": ["<", add_days(now_datetime(), -days)]},
        pluck="name",
    )
    message = _("Its files were deleted {0} days after it ended, as chat retention keeps them.").format(days)
    return purge(names, message)


def purge_user_sessions(doc, method=None) -> None:
    """When a Personal Data Deletion Request ends: delete the user's session files. Frappe only
    redacts text in the user's records, which would leave their files' rows on disk."""
    if doc.status != "Deleted":
        return
    # The user may already be renamed to the request's name, which their sessions then carry
    names = frappe.get_all(SESSION_DOCTYPE, filters={"user": ["in", [doc.email, doc.name]]}, pluck="name")
    # an open session can't carry on without its files either
    purge(names, _("Its files were deleted with the user's personal data."), cancel=HOLDING_STATUSES)


def purge(names: List[str], message: str, cancel=ABANDONED) -> int:
    """Delete the files attached to each session, through the ORM so their bytes go too, and
    note it on the session; one in a ``cancel`` status is Cancelled, as it can't carry on
    without them. A session with no file left is left alone."""
    purged = 0
    for name in names:
        files = frappe.get_all(
            "File", filters={"attached_to_doctype": SESSION_DOCTYPE, "attached_to_name": name}, pluck="name"
        )
        if not files:
            continue
        for file_name in files:
            frappe.delete_doc("File", file_name, force=True, ignore_permissions=True)
        session = engine_session(name)
        if session.status in cancel:
            session.status = "Cancelled"  # it can't carry on without its files, nor hold the user's
        session.log_step(PURGED_STEP, "Success", message)
        session.save(ignore_permissions=True)
        purged += 1
    return purged


def was_purged(session) -> bool:
    """Whether retention or a personal data deletion took the session's files."""
    return any(step.step == PURGED_STEP for step in session.steps)
