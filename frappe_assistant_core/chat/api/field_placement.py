# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""
Field placement: where a new Custom Field would show on its form, for the approval card.

The card asks before the assistant saves anything, so the answer is predicted from the target
doctype's layout. Nothing is written.
"""

import frappe
from frappe import _

from frappe_assistant_core.utils.customisation import (
    is_hidden,
    placement_is_ambiguous,
    placement_sentence,
    predict_field_location,
)


def _can_read(doctype: str) -> bool:
    """Read permission on the doctype, or for a child table on a parent that embeds it."""
    if frappe.has_permission(doctype, "read"):
        return True
    if not frappe.get_meta(doctype).istable:
        return False
    parents = frappe.get_all(
        "DocField",
        filters={"fieldtype": ["in", ["Table", "Table MultiSelect"]], "options": doctype},
        pluck="parent",
    )
    return any(frappe.has_permission(parent, "read") for parent in parents)


@frappe.whitelist(methods=["GET"])
def get_field_placement(doctype: str, insert_after: str | None = None, fieldtype: str | None = None) -> dict:
    """Say where a Custom Field added to `doctype` after `insert_after` would appear.

    Returns:
            {tab, section, collapsed, first_tab, sentence, warning, ambiguous}; warning is true when
            the field would be collapsed, not on the first tab, or ambiguous (another custom field
            already sits where this one would go, so its place is only known once saved).
    """
    if not _can_read(doctype):
        frappe.throw(_("You do not have permission to read {0}").format(doctype), frappe.PermissionError)

    location = predict_field_location(doctype, insert_after, fieldtype)
    if not location:
        return {}
    if placement_is_ambiguous(doctype, insert_after):
        label = frappe.get_meta(doctype).get_label(insert_after)
        if label:
            sentence = _("Will appear next to {0}. Its tab and section can only be known once it is saved.")
            sentence = sentence.format(_(label))
        else:
            sentence = _("Its tab and section can only be known once it is saved.")
        return {**location, "sentence": sentence, "warning": True, "ambiguous": True}
    return {
        **location,
        "sentence": placement_sentence(location),
        "warning": is_hidden(location),
        "ambiguous": False,
    }
