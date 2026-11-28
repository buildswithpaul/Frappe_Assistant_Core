# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Per-user auto-approve mode, sent to the runtime with each chat turn.

In the mode the runtime runs an ordinary create or update without an approval card and lists
it in the reply. It still asks before a submit, a cancel, a delete, an edit of a submitted
record, a message going out, a publish, and any change to users, roles, system settings or
customisations.

The mode is on for a user who has not switched it off, but it reaches the runtime only once
the user has seen the notice that explains it, and only from the clients that show the switch:
FAC Chat and the Desk widget.
"""

import frappe

PREFERENCES_DOCTYPE = "FAC Chat User Preferences"
OFF_FIELD = "auto_approve_off"
NOTICE_FIELD = "auto_approve_notice_seen"
AUTO = "auto"
#: The clients that show the switch: FAC Chat and the Desk widget, which is built from the same
#: composer. Any other sends no mode, so its writes ask as before.
SWITCH_CLIENTS = frozenset({"spa", "widget"})


def available() -> bool:
    """Whether the runtime this site talks to offers the mode."""
    # Imported here: chat.api imports the relay, and the relay imports this module.
    from frappe_assistant_core.chat.api._helpers import _cached_capability

    return _cached_capability("features", "auto_approve")


def state(user: str) -> dict:
    """What the composer shows for ``user``: ``{"available", "on", "notice_seen"}``."""
    migrated = frappe.db.has_column(PREFERENCES_DOCTYPE, OFF_FIELD)
    row = (
        frappe.db.get_value(PREFERENCES_DOCTYPE, user, [OFF_FIELD, NOTICE_FIELD], as_dict=True)
        if migrated
        else None
    ) or {}
    return {
        # Before migrate adds the columns the choice could not be saved, so there is no switch.
        "available": migrated and available(),
        "on": not row.get(OFF_FIELD),
        "notice_seen": bool(row.get(NOTICE_FIELD)),
    }


def turn_approval_mode(user: str, client_type: str | None) -> str | None:
    """The ``approval_mode`` to send with a turn: ``"auto"`` or None for none."""
    if client_type not in SWITCH_CLIENTS:
        return None
    current = state(user)
    return AUTO if current["available"] and current["on"] and current["notice_seen"] else None
