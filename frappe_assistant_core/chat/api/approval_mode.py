# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The composer's auto-approve switch: read it, flip it, and note the notice was seen."""

import frappe
from frappe import _
from frappe.utils import sbool

from frappe_assistant_core.chat.doctype.fac_chat_user_preferences.fac_chat_user_preferences import (
    FACChatUserPreferences,
)

from ..approval_mode import NOTICE_FIELD, OFF_FIELD, PREFERENCES_DOCTYPE, state


def _save(field: str, value: int) -> dict:
    # Before migrate adds the column, save() would drop the value without a word.
    if not frappe.db.has_column(PREFERENCES_DOCTYPE, field):
        frappe.throw(_("This setting needs a site update. Ask your administrator to run bench migrate."))
    prefs = FACChatUserPreferences.get_or_create_preferences()
    prefs.set(field, value)
    prefs.save(ignore_permissions=True)
    return state(frappe.session.user)


@frappe.whitelist(methods=["GET"])
def get_approval_mode() -> dict:
    """The session user's auto-approve mode: ``{"available", "on", "notice_seen"}``."""
    return state(frappe.session.user)


@frappe.whitelist(methods=["POST"])
def set_approval_mode(on: bool) -> dict:
    """Switch auto-approve mode on or off for the session user. Flipping the switch is seeing it,
    so the notice is not shown again."""
    _save(NOTICE_FIELD, 1)
    return _save(OFF_FIELD, 0 if sbool(on) else 1)


@frappe.whitelist(methods=["POST"])
def acknowledge_approval_mode() -> dict:
    """Record that the session user has seen the notice explaining the mode. Until then the mode
    is not sent to the runtime, so nobody loses approval cards without having been told."""
    return _save(NOTICE_FIELD, 1)
