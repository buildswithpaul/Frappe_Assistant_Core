# Frappe Assistant Core - Subscription Sync API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Subscription sync, scheduled-sync, AR heartbeat, notification cache."""

from __future__ import annotations

import frappe

from .._helpers import (
    _log,
    _not_registered_error,
    _require_system_manager,
    _safe_error,
)


@frappe.whitelist(methods=["POST"])
def sync_subscription_status():
    """
    Sync subscription info from AR.

    Fetches current tenant info including quota usage and updates
    the Redis quota cache.

    Returns:
            dict: Updated subscription info or error
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client
        from frappe_assistant_core.chat.quota_cache import (
            get_field,
            set_field,
            update_from_ar,
        )

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        info = client.get_tenant_info()

        # Probe billing availability only if not recently checked
        last_sync = get_field("last_sync", "")
        skip_probe = False
        if last_sync:
            from frappe.utils import now, time_diff_in_hours

            skip_probe = time_diff_in_hours(now(), last_sync) < 6

        if skip_probe:
            billing_available = None
        else:
            try:
                billing_available = client.check_billing_available()
            except Exception:
                billing_available = None

        if info:
            subscription = info.get("subscription", {})
            update_from_ar(subscription)

            if info.get("preferred_model"):
                set_field("preferred_model", info["preferred_model"])

            if billing_available is not None:
                set_field("billing_enabled", billing_available)

            return {
                "success": True,
                "subscription": subscription,
                "preferred_model": info.get("preferred_model"),
            }

        return {"error": "Failed to fetch tenant info"}

    except Exception as e:
        _log(title="FACO Sync Error", message=f"Error syncing subscription: {e!s}")
        return {"error": _safe_error(e, "FACO Sync Error")}


def scheduled_sync_subscription():
    """Scheduled task to sync subscription status from AR."""
    # Master gate: nothing to sync if FAC Chat is disabled.
    from frappe_assistant_core.chat.gate import is_chat_enabled

    if not is_chat_enabled():
        return
    try:
        settings = frappe.get_single("FAC Chat Settings")
        if settings.registration_status != "Registered":
            return
        sync_subscription_status()
        _send_heartbeat()
    except Exception as e:
        _log(title="FACO Scheduled Sync", message=f"Scheduled sync failed: {e!s}")


def _send_heartbeat():
    """Send version/health info to AR and process any notifications received."""
    try:
        import sys

        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return

        # Gather version info
        versions = {}
        try:
            from frappe.utils.change_log import get_versions

            versions = get_versions() or {}
        except Exception:
            # Best-effort — heartbeat still proceeds without version metadata.
            frappe.logger("faco.billing").exception("FACO heartbeat: get_versions failed")

        result = client.heartbeat(
            copilot_version=versions.get("frappe_assistant_core", {}).get("version"),
            fac_version=versions.get("frappe_assistant_core", {}).get("version"),
            frappe_version=versions.get("frappe", {}).get("version"),
            erpnext_version=versions.get("erpnext", {}).get("version"),
            python_version=sys.version.split()[0],
            timeout=10,
        )

        # Store any notifications received
        if result and result.get("notifications"):
            _store_notifications(result["notifications"])

    except Exception as e:
        # Heartbeat failure should never break the sync
        _log(title="FACO Heartbeat", message=f"Heartbeat failed: {e!s}")


def _store_notifications(notifications):
    """Cache notifications from AR in FACO Settings for the frontend to read."""
    import json as _json

    try:
        frappe.db.set_single_value(
            "FAC Chat Settings",
            "cached_notifications",
            _json.dumps(notifications),
        )
    except Exception:
        # Field may not exist yet on older sites — non-fatal, but trace it
        # so we know the heartbeat notifications channel is silently dropping.
        frappe.logger("faco.billing").exception(
            "FACO heartbeat: failed to cache notifications " "(cached_notifications field may be missing)"
        )
