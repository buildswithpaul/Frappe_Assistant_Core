# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Undo for records the chat created without asking.

The assistant runs low-risk creates without an approval card and lists them in a
``changes_made`` block. ``undo_change`` deletes one of them, and only one the block
lists, not yet undone, on a message of a session the caller owns, and only if the
caller may delete it.
"""

import frappe
from frappe import _

from ._rate_limits import rate_limit, session_user_or_ip
from .block_builder import find_open_change, mark_change_undone
from .chat.messages import _assert_session_owner


@frappe.whitelist(methods=["POST"])
@rate_limit(session_user_or_ip, limit=30, seconds=60)
def undo_change(session_id: str, message_id: str, doctype: str, name: str) -> dict:
    """Delete a record the chat created and mark it undone.

    Returns ``{"success": True}``, or ``{"success": False, "reason": ...}`` when
    something now links to the record (nothing is deleted).
    """
    _assert_session_owner(session_id)

    message = frappe.db.get_value(
        "FAC Chat Message",
        {"session_id": session_id, "message_id": message_id, "role": "assistant"},
        "name",
    )
    if not message or not find_open_change(message, doctype, name):
        frappe.throw(_("This change can't be undone"), frappe.PermissionError)

    if not frappe.has_permission(doctype, "delete", doc=name):
        frappe.throw(
            _("You do not have permission to delete {0} {1}").format(doctype, name),
            frappe.PermissionError,
        )

    try:
        frappe.delete_doc(doctype, name)
    except frappe.LinkExistsError:
        return {"success": False, "reason": _("Something now links to it")}

    mark_change_undone(message, doctype, name)
    return {"success": True}
