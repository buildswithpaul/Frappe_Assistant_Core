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
# and a FAC Page's style is applied to the page once it is published. A FAC Page's or a Report's
# roles say who it reaches. Keyed by the doctype each belongs to, since another doctype's field of
# the same name may be no code at all (a Workflow State's style is a colour); utils/customisation.py
# reads the same map. Mirrored in customisation.js (SWITCHED_CODE) for the doctypes with a switch.
GO_LIVE_KEYS_BY_DOCTYPE = {
    "Notification": ("subject",),
    "FAC Page": ("style", "roles"),
    "Report": ("roles",),
}
GO_LIVE_KEYS = tuple(dict.fromkeys(key for keys in GO_LIVE_KEYS_BY_DOCTYPE.values() for key in keys))

# Every field each doctype runs as code or renders as a template, which utils/customisation.py
# reads to judge whether a write runs code the user has not seen. Wider than CODE_KEYS, the fields
# the card shows as code: a raw print's commands and a print designer layout (which can hold
# Jinja in custom HTML) render too.
CODE_KEYS_BY_DOCTYPE = {
    "Server Script": ("script",),
    "Client Script": ("script",),
    "Notification": ("condition", "message"),
    "FAC Page": ("html", "script"),
    "Report": ("report_script", "query", "javascript"),
    "Print Format": ("html", "css", "raw_commands", "format_data"),
}

# Child tables among GO_LIVE_KEYS, and the column each returns, one value per row.
TABLE_COLUMNS = {"roles": "role"}


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
            {fieldname: stored value or ""}; a child table in TABLE_COLUMNS gives a list of values.
    """
    if not frappe.has_permission(doctype, "read", doc=name):
        frappe.throw(
            _("You do not have permission to read {0} {1}").format(doctype, name), frappe.PermissionError
        )

    requested = _requested_fields(fields)
    permitted = get_permitted_fields(doctype)
    columns = [f for f in requested if f in permitted]
    # get_permitted_fields leaves child tables out, so their permission level is checked here.
    meta = frappe.get_meta(doctype)
    levels = meta.get_permlevel_access("read")
    tables = [
        df.fieldname
        for df in meta.get_table_fields()
        if df.fieldname in requested and df.fieldname in TABLE_COLUMNS and df.permlevel in levels
    ]
    out = {}
    if columns:
        values = frappe.db.get_value(doctype, name, columns, as_dict=True) or {}
        out = {f: values.get(f) or "" for f in columns}
    if tables:
        # Read was checked above; child rows come from the record itself.
        doc = frappe.get_doc(doctype, name)
        out.update({f: [row.get(TABLE_COLUMNS[f]) for row in doc.get(f)] for f in tables})
    return out
