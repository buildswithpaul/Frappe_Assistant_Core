# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""FAC Chat discovery banner endpoints.

The banner is shown once per eligible admin user immediately after the
upgrade to FAC 3.0. Once dismissed it never reappears, even if chat is
later toggled off and back on.

Eligibility (all must hold):
  - user has write permission on Assistant Core Settings (admin)
  - Assistant Core Settings.enable_fac_chat is currently False
  - user has not previously dismissed the banner

Server-side enforces all three rules; the client-side JS just renders
when `should_show_banner` returns True.
"""

import frappe
from frappe import _

from frappe_assistant_core.chat.gate import clear_chat_gate_cache, is_chat_enabled


def _has_chat_admin_perm() -> bool:
    """Return True when the current user can manage FAC Chat settings."""
    return bool(frappe.has_permission("Assistant Core Settings", "write"))


@frappe.whitelist(methods=["GET"])
def should_show_banner() -> bool:
    """Return True if the FAC Chat discovery banner should display now."""
    if is_chat_enabled():
        return False
    if not _has_chat_admin_perm():
        return False
    user = frappe.session.user
    dismissed = frappe.db.exists("FAC Chat Banner Dismissal", {"user": user})
    return not dismissed


@frappe.whitelist(methods=["POST"])
def dismiss_banner() -> dict:
    """Record that the current user has dismissed the FAC Chat banner.

    Idempotent: calling twice returns ``{"already_dismissed": True}`` instead
    of raising a uniqueness error.
    """
    if not _has_chat_admin_perm():
        frappe.throw(_("You do not have permission to manage FAC Chat."), frappe.PermissionError)
    user = frappe.session.user
    if frappe.db.exists("FAC Chat Banner Dismissal", {"user": user}):
        return {"already_dismissed": True}
    frappe.get_doc({"doctype": "FAC Chat Banner Dismissal", "user": user}).insert(ignore_permissions=True)
    return {"dismissed": True}


@frappe.whitelist(methods=["GET"])
def get_chat_status() -> dict:
    """Return current FAC Chat enablement state for the FAC Admin card."""
    if not _has_chat_admin_perm():
        frappe.throw(_("You do not have permission to manage FAC Chat."), frappe.PermissionError)
    return {
        "enabled": is_chat_enabled(),
        "can_toggle": True,
    }


@frappe.whitelist(methods=["GET"])
def get_chat_analytics() -> dict:
    """Return chat-usage analytics for the FAC Admin right-column card.

    Single round-trip replacement for the old FACO workspace number cards
    (Monthly Conversations, Total Messages, Active Users, Credit Usage)
    plus a 30-day daily-message series for the sparkline. Returns
    ``{"enabled": False}`` when chat is off so the caller can hide the
    card entirely without a second call.
    """
    if not _has_chat_admin_perm():
        frappe.throw(_("You do not have permission to manage FAC Chat."), frappe.PermissionError)

    if not is_chat_enabled():
        return {"enabled": False}

    from datetime import timedelta

    from frappe.query_builder.functions import Count, Date
    from frappe.utils import get_first_day, now, today

    Message = frappe.qb.DocType("FAC Chat Message")

    month_start = get_first_day(now())
    monthly_row = (
        frappe.qb.from_(Message)
        .select(Count(Message.name).as_("count"))
        .where(Message.creation >= month_start)
        .run(as_dict=True)
    )
    monthly_messages = (monthly_row[0].get("count") if monthly_row else 0) or 0

    total_row = frappe.qb.from_(Message).select(Count(Message.name).as_("count")).run(as_dict=True)
    total_messages = (total_row[0].get("count") if total_row else 0) or 0

    active_row = (
        frappe.qb.from_(Message)
        .select(Count(Message.owner).distinct().as_("count"))
        .where(Message.creation >= month_start)
        .run(as_dict=True)
    )
    active_users = (active_row[0].get("count") if active_row else 0) or 0

    # Credit usage — best-effort from Redis quota snapshot
    quota_used = 0
    quota_limit = 0
    try:
        from frappe_assistant_core.chat.quota_cache import get_quota_snapshot

        snap = get_quota_snapshot() or {}
        quota_used = snap.get("quota_used") or 0
        quota_limit = snap.get("quota_limit") or 0
    except Exception:
        pass

    # 30-day daily series for the sparkline
    today_date = frappe.utils.getdate(today())
    series_start = today_date - timedelta(days=29)
    series_rows = (
        frappe.qb.from_(Message)
        .select(
            Date(Message.creation).as_("day"),
            Count(Message.name).as_("count"),
        )
        .where(Message.creation >= series_start)
        .groupby(Date(Message.creation))
        .run(as_dict=True)
    )
    series_map = {str(r["day"]): int(r["count"] or 0) for r in series_rows}
    series = [
        {
            "day": str(series_start + timedelta(days=i)),
            "count": series_map.get(str(series_start + timedelta(days=i)), 0),
        }
        for i in range(30)
    ]

    return {
        "enabled": True,
        "monthly_messages": monthly_messages,
        "total_messages": total_messages,
        "active_users": active_users,
        "quota_used": quota_used,
        "quota_limit": quota_limit,
        "series": series,
    }


@frappe.whitelist(methods=["POST"])
def toggle_chat(enabled: int | bool) -> dict:
    """Toggle the FAC Chat module on or off.

    Updates ``Assistant Core Settings.enable_fac_chat`` and clears the
    per-request gate cache so the next page load on this Desk session
    reflects the change. All other workers pick up the new state on
    their next request via the per-request cache lookup — no restart
    needed since the chat hooks are registered unconditionally and each
    consumer checks the gate at runtime.

    The FACO Tools plugin is kept in lockstep with the chat toggle —
    enabling chat auto-enables the plugin (chat is unusable without
    its tools: email, document generation, rich blocks, browser
    bridge); disabling chat auto-disables it. Plugin failures are
    swallowed so they cannot block the chat toggle itself.
    """
    if not _has_chat_admin_perm():
        frappe.throw(_("You do not have permission to manage FAC Chat."), frappe.PermissionError)

    new_state = 1 if int(enabled) else 0
    settings = frappe.get_single("Assistant Core Settings")
    settings.enable_fac_chat = new_state
    settings.save(ignore_permissions=True)

    clear_chat_gate_cache()
    # Drop the Single DocType value cache so subsequent reads on this worker
    # pick up the new value within the same request.
    frappe.clear_document_cache("Assistant Core Settings", "Assistant Core Settings")

    faco_plugin_state = _sync_faco_plugin_state(bool(new_state))

    return {
        "enabled": bool(new_state),
        "faco_plugin": faco_plugin_state,
    }


def _sync_faco_plugin_state(should_be_enabled: bool) -> str:
    """Keep the FACO Tools plugin in lockstep with the chat toggle.

    Returns a short status string: ``"enabled"``, ``"disabled"``,
    ``"unchanged"`` (already in the desired state), or ``"error"``
    (plugin operation failed — logged but swallowed so it cannot
    block the chat toggle). Idempotent.
    """
    from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

    try:
        manager = get_plugin_manager()
        currently_enabled = "faco" in manager.get_enabled_plugins()
        if should_be_enabled and not currently_enabled:
            manager.enable_plugin("faco")
            return "enabled"
        if not should_be_enabled and currently_enabled:
            manager.disable_plugin("faco")
            return "disabled"
        return "unchanged"
    except Exception:
        frappe.log_error(
            title="FAC Chat: failed to sync FACO plugin state",
            message=frappe.get_traceback(),
        )
        return "error"
