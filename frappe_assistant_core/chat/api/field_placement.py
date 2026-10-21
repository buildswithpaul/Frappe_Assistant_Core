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
    placement_sentence,
    placement_warning,
    predict_field_location,
)


@frappe.whitelist(methods=["GET"])
def get_field_placement(doctype: str, insert_after: str | None = None, fieldtype: str | None = None) -> dict:
    """Say where a Custom Field added to `doctype` after `insert_after` would appear.

    Returns:
            {tab, section, collapsed, first_tab, sentence, warning}; warning is true when the
            field would be collapsed or not on the first tab.
    """
    if not frappe.has_permission(doctype, "read"):
        frappe.throw(_("You do not have permission to read {0}").format(doctype), frappe.PermissionError)

    location = predict_field_location(doctype, insert_after, fieldtype)
    if not location:
        return {}
    return {
        **location,
        "sentence": placement_sentence(location),
        "warning": bool(placement_warning(location)),
    }
