# Frappe Assistant Core - Admin dashboard number-card sources.
# Copyright (C) 2026 Paul Clinton
# AGPLv3

"""Whitelisted methods backing Number Cards on the FACO Workspace.

Each method returns the shape Frappe's Custom-type Number Card expects:
    {"value": int | float, "fieldtype": str, "route": list}

`fieldtype` is a display hint; `route` is the list-view the user lands on
when they click the card.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.query_builder.functions import Count
from frappe.utils import get_first_day, now


def _require_system_manager() -> None:
    """Match the access level of the old faco-admin page."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Managers can view FACO admin data."), frappe.PermissionError)


@frappe.whitelist(methods=["GET", "POST"])
def active_users_this_month() -> dict[str, Any]:
    """Distinct message authors since the first of the month."""
    _require_system_manager()

    FACChatMessage = frappe.qb.DocType("FAC Chat Message")
    row = (
        frappe.qb.from_(FACChatMessage)
        .select(Count(FACChatMessage.owner).distinct().as_("count"))
        .where(FACChatMessage.creation >= get_first_day(now()))
        .run(as_dict=True)
    )
    value = (row[0].get("count") if row else 0) or 0

    return {
        "value": value,
        "fieldtype": "Int",
        "route": ["List", "FAC Chat Message"],
    }


@frappe.whitelist(methods=["GET", "POST"])
def token_usage_summary() -> dict[str, Any]:
    """Current-period token usage sourced from the Redis quota cache."""
    _require_system_manager()

    from frappe_assistant_core.chat.quota_cache import get_quota_snapshot

    try:
        snap = get_quota_snapshot() or {}
    except Exception:
        snap = {}

    return {
        "value": snap.get("quota_used") or 0,
        "fieldtype": "Int",
        "route": ["copilot", "billing"],
    }


@frappe.whitelist(methods=["POST"])
def reset_registration() -> dict[str, Any]:
    """Clear this site's tenant credentials.

    Kept as a stable alias — both dotted paths are whitelisted and may already
    be scripted against. It delegates rather than reimplements: the two copies
    drifted once before, leaving the exported one unable to complete.
    """
    from frappe_assistant_core.chat.api.settings.registration import (
        reset_registration as _reset_registration,
    )

    return _reset_registration()
