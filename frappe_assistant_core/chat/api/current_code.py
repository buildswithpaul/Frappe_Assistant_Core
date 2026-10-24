# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""
Current code — the stored value of a record's code fields, for the approval card's diff.

When the assistant asks to update a script, condition or template, the card shows the user a
line diff of old against new. Only code fields are returned, and only for a record the caller
may read, so this is no general way to read a document.
"""

import frappe
from frappe import _
from frappe.model import get_permitted_fields

# Mirrored in chat/frontend/src/components/chat/interactions/helpers.js (CODE_KEYS).
CODE_KEYS = (
    "script",
    "condition",
    "query",
    "html",
    "javascript",
    "report_script",
    "css",
    "message",
)

# Not code on every card, but run once an update switches the record on, so the card shows the
# stored value: a Notification's subject is a Jinja template rendered into the email it sends,
# and a FAC Page's style is applied to the page once it is published.
# Mirrored in customisation.js (SWITCHED_CODE).
GO_LIVE_KEYS = ("subject", "style")


def _requested_fields(fields: list | str) -> list[str]:
    if isinstance(fields, str):
        fields = frappe.parse_json(fields)
    return [f for f in fields if isinstance(f, str) and (f in CODE_KEYS or f in GO_LIVE_KEYS)]


@frappe.whitelist(methods=["GET"])
def get_current_code(doctype: str, name: str, fields: list | str) -> dict:
    """Return the stored values of the requested code fields of one record.

    Args:
            fields: Field names, as a list or a JSON-encoded list. Names outside CODE_KEYS and
                    GO_LIVE_KEYS, unknown to the doctype, or above the caller's permission level are ignored.

    Returns:
            {fieldname: stored value or ""}.
    """
    if not frappe.has_permission(doctype, "read", doc=name):
        frappe.throw(
            _("You do not have permission to read {0} {1}").format(doctype, name), frappe.PermissionError
        )

    permitted = get_permitted_fields(doctype)
    wanted = [f for f in _requested_fields(fields) if f in permitted]
    if not wanted:
        return {}
    values = frappe.db.get_value(doctype, name, wanted, as_dict=True) or {}
    return {f: values.get(f) or "" for f in wanted}
