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
from frappe.model.delete_doc import check_if_doc_is_dynamically_linked, check_if_doc_is_linked

from ._rate_limits import rate_limit, session_user_or_ip
from .block_builder import find_open_change, mark_change_undone
from .chat.messages import _assert_session_owner

SAVEPOINT = "undo_change"


@frappe.whitelist(methods=["POST"])
@rate_limit(session_user_or_ip, limit=30, seconds=60)
def undo_change(session_id: str, message_id: str, doctype: str, name: str) -> dict:
    """Delete a record the chat created and mark it undone.

    Returns ``{"success": True}``, or ``{"success": False, "reason": ...}`` when
    something now links to the record (nothing is deleted).
    """
    _assert_session_owner(session_id)

    row = frappe.db.get_value(
        "FAC Chat Message",
        {"session_id": session_id, "message_id": message_id, "role": "assistant"},
        ["name", "user", "creation"],
        as_dict=True,
    )
    if not row or row.user != frappe.session.user or not find_open_change(row.name, doctype, name):
        frappe.throw(_("This change can't be undone"), frappe.PermissionError)

    if not frappe.db.exists(doctype, name):
        mark_change_undone(row.name, doctype, name)
        return {"success": True}

    if not frappe.has_permission(doctype, "delete", doc=name):
        frappe.throw(
            _("You do not have permission to delete {0} {1}").format(doctype, name),
            frappe.PermissionError,
        )

    owner, creation = frappe.db.get_value(doctype, name, ["owner", "creation"])
    turn_start = frappe.db.get_value(
        "FAC Chat Message",
        {"session_id": session_id, "role": "user", "creation": ["<=", row.creation]},
        "creation",
        order_by="creation desc",
    )
    # No turn row (retention off, or it was pruned): fall back to the conversation's start, and
    # with neither on record there is nothing to prove the chat created the record.
    bound = turn_start or frappe.db.get_value("FAC Chat Conversation", session_id, "creation")
    if owner != frappe.session.user or not bound or creation < bound:
        return {"success": False, "reason": _("This record has changed since the chat created it")}

    # delete_doc runs on_trash hooks before it checks links, and Frappe's own hook deletes a
    # Contact or Address linked only to this record, so check links first: Undo never cascades.
    if _is_linked(frappe.get_doc(doctype, name)):
        return {"success": False, "reason": _("Something now links to it")}

    # A link made after that check still refuses the delete; undo what on_trash did then.
    frappe.db.savepoint(SAVEPOINT)
    try:
        frappe.delete_doc(doctype, name)
    except frappe.LinkExistsError:
        frappe.db.rollback(save_point=SAVEPOINT)
        return {"success": False, "reason": _("Something now links to it")}

    frappe.db.release_savepoint(SAVEPOINT)
    mark_change_undone(row.name, doctype, name)
    return {"success": True}


def _is_linked(doc) -> bool:
    try:
        check_if_doc_is_linked(doc)
        check_if_doc_is_dynamically_linked(doc)
    except frappe.LinkExistsError:
        # The refusal is returned as a reason, not shown again as Frappe's own message.
        frappe.clear_last_message()
        return True
    return False
