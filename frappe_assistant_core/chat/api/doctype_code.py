# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Code on a dormant DocType, for the approval card of a write that opens it to other people.

A custom DocType nobody else can reach yet takes Custom Fields and Property Setters without a card,
since their code runs for nobody. The write that opens it (a permission for another role, or making
it a child table) puts all of that code live at once, so the card lists it.
"""

import frappe
from frappe import _

from frappe_assistant_core.utils.customisation import code_going_live


@frappe.whitelist(methods=["GET"])
def get_code_going_live(target: str | None = None, custom_docperm: str | None = None) -> list[dict]:
    """The code on a DocType that is dormant now, which a write opening it would put live.

    Args:
            target: The DocType's name.
            custom_docperm: Instead of ``target``, a Custom DocPerm whose DocType it is, for an update
                    that does not restate its parent.

    Returns:
            ``code_going_live`` entries (``code_on_doctype``), leaving out those of a record kind
            the caller may not read, or [] when the DocType is not dormant: its code already
            reaches people.
    """
    if custom_docperm:
        if not frappe.has_permission("Custom DocPerm", "read", doc=custom_docperm):
            frappe.throw(_("You do not have permission to read this permission rule"), frappe.PermissionError)
        target = frappe.db.get_value("Custom DocPerm", custom_docperm, "parent")
    if not isinstance(target, str) or not target:
        return []
    if not frappe.has_permission("DocType", "read", doc=target):
        frappe.throw(
            _("You do not have permission to read DocType {0}").format(target), frappe.PermissionError
        )
    entries = code_going_live(target)
    for source in ("Custom Field", "Property Setter"):
        if not frappe.has_permission(source, "read"):
            entries = [entry for entry in entries if entry["source"] != source]
    return entries
