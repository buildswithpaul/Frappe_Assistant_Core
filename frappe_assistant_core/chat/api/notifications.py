# FACO - Notification Endpoints
# Copyright (C) 2025 Paul Clinton
#
# MIT License

"""
Notification endpoints for the FAC Chat SPA.

Notifications are fetched live from AR (source of truth) with a 60s
per-user cache. AR handles all filtering: is_active, valid date range,
target criteria, and per-user dismissals.

AR failures fall back to the 6-hour cron blob cached on FAC Chat Settings.
That fallback result is cached for the same 60s TTL as a success would be —
so an AR outage costs at most one AR round-trip per user per minute instead
of blocking a worker on every request.
"""

import json

import frappe
from frappe import _

from frappe_assistant_core.chat.api.auth import _ar_user_id
from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client
from frappe_assistant_core.chat.gate import is_chat_enabled

CACHE_TTL_SECONDS = 60


def _cache_key(user: str) -> str:
    return f"fac_notifications:{user}"


@frappe.whitelist(methods=["GET"])
def get_notifications() -> dict:
    """Get pending notifications for the current user — fetched live from AR
    with a 60s per-user cache. AR is the source of truth for active status,
    dismissals, valid date ranges, and target criteria.

    When AR can't be reached, the response falls back to the stale cron blob
    (or an empty list) and carries `degraded: true` so callers know this is
    not AR's authoritative view — in particular, the SPA must not prune its
    locally persisted seen/dismissed sets against a degraded list, or an
    outage silently wipes state that a truncated/empty fallback doesn't
    actually contradict.
    """
    if not is_chat_enabled():
        return {"notifications": [], "user": ""}

    user = _ar_user_id(frappe.session.user)
    cached = frappe.cache.get_value(_cache_key(user), expires=True)
    if cached is not None:
        try:
            payload = json.loads(cached)
            if isinstance(payload, dict) and isinstance(payload.get("notifications"), list):
                return _response(payload["notifications"], user, degraded=bool(payload.get("degraded")))
        except (json.JSONDecodeError, TypeError):
            pass

    notifications = None
    try:
        client = get_fac_cloud_client()
        if client:
            result = client.get_notifications(user_id=user, timeout=5)
            fetched = result.get("notifications") if result else None
            if isinstance(fetched, list):
                notifications = fetched
    except Exception as e:
        frappe.log_error(title="FAC Notifications", message=f"Failed to fetch notifications from AR: {e!s}")

    degraded = notifications is None
    if degraded:
        notifications = _fallback_notifications()

    # Cache success AND failure results — bounds AR round-trips to one
    # per user per TTL even during an AR outage. The degraded flag rides
    # along so a cache hit doesn't lose track of it.
    frappe.cache.set_value(
        _cache_key(user),
        json.dumps({"notifications": notifications, "degraded": degraded}),
        expires_in_sec=CACHE_TTL_SECONDS,
    )
    return _response(notifications, user, degraded=degraded)


def _response(notifications: list, user: str, *, degraded: bool) -> dict:
    response = {"notifications": notifications, "user": user}
    if degraded:
        response["degraded"] = True
    return response


def _fallback_notifications() -> list:
    """Tenant-level blob from the 6-hour cron heartbeat; per-user
    `dismissed` flags are absent there — the SPA's local dismissed set
    still mutes locally."""
    try:
        cached = frappe.db.get_single_value("FAC Chat Settings", "cached_notifications")
        if cached:
            parsed = json.loads(cached)
            if isinstance(parsed, list):
                return [_normalize_fallback_notification(n) for n in parsed if isinstance(n, dict)]
    except Exception as e:
        frappe.log_error(title="FAC Notifications", message=f"Corrupt cached_notifications blob: {e!s}")
    return []


def _normalize_fallback_notification(notification: dict) -> dict:
    """Defend against a stale cron blob — written by a not-yet-upgraded AR
    heartbeat — missing `dismissible`/`dismissed`/`created_at` entirely.
    Missing `dismissible` must fail closed, not be read as permission to
    dismiss."""
    return {
        **notification,
        "dismissible": notification.get("dismissible") is True,
        "dismissed": bool(notification.get("dismissed", False)),
        "created_at": notification.get("created_at") or "",
    }


@frappe.whitelist(methods=["POST"])
def dismiss_notification(notification_id: str | None = None) -> dict:
    """Dismiss a notification for the current user.

    Records the dismissal on AR (persistent, survives restarts) and clears
    the local cache so the next fetch reflects it. Reports "dismissed" only
    when AR actually confirmed it; "local_only" when the AR call failed, so
    callers don't mistake a silently-dropped dismissal for a real one.
    """
    if not notification_id:
        frappe.throw(_("notification_id is required"))
    if not is_chat_enabled():
        frappe.throw(_("Chat is not enabled"))

    user = _ar_user_id(frappe.session.user)
    status = "local_only"
    try:
        client = get_fac_cloud_client()
        if client:
            client.dismiss_notification(notification_id=notification_id, user_id=user, timeout=5)
            status = "dismissed"
    except Exception as e:
        frappe.log_error(title="FAC Notifications", message=f"Failed to dismiss notification on AR: {e!s}")

    frappe.cache.delete_value(_cache_key(user))
    return {"status": status, "notification_id": notification_id}
