# Frappe Assistant Core - Billing Package Internal Helpers
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Shared helpers used by every billing submodule.

Not whitelisted; not part of the public API path
``frappe_assistant_core.chat.api.billing.<func>``.
"""

from __future__ import annotations


def _infer_gateway_from_plans(plans_data):
    """Infer gateway from plan pricing keys when get_recommended_gateway fails."""
    # Pricing is now USD-only — gateway selection is done server-side
    return {"gateway": "stripe", "currency": "USD"}


def _build_dashboard_response(usage_data, settings, tenant_info=None):
    """Build the dashboard response dict from AR usage data and quota cache.

    When `tenant_info` is supplied (from `client.get_tenant_info()`), the
    `referral` block is merged into the subscription object so the UI can
    render partner attribution.
    """
    from frappe_assistant_core.chat.quota_cache import get_quota_snapshot

    usage_data = usage_data or {}
    snap = get_quota_snapshot()
    quota_total = snap.get("quota_total", 0)
    quota_used = snap.get("quota_used", 0)
    is_unlimited = quota_total == -1

    subscription = {
        "plan": snap.get("plan", "Free"),
        "status": "active" if settings.registration_status == "Registered" else "inactive",
        "quota_total": quota_total,
        "quota_used": quota_used,
        "quota_remaining": -1 if is_unlimited else max(0, quota_total - quota_used),
        "is_unlimited": is_unlimited,
    }

    # AR's usage dashboard nests money-state under `billing`. Surface the
    # fields the SPA needs for cancel-at-period-end / next-billing UX onto
    # `subscription` so a refresh doesn't look like a normal active plan.
    # Without this, `_build_dashboard_response` only mirrored the quota
    # cache and the cancel banner vanished on reload.
    billing = usage_data.get("billing") or {}
    if billing:
        if billing.get("current_period_end"):
            subscription["current_period_end"] = billing["current_period_end"]
        if billing.get("billing_cycle_start"):
            subscription["billing_cycle_start"] = billing["billing_cycle_start"]
        if "cancel_at_period_end" in billing:
            subscription["cancel_at_period_end"] = bool(billing.get("cancel_at_period_end"))
        if billing.get("payment_status"):
            subscription["payment_status"] = billing["payment_status"]
        if billing.get("currency"):
            subscription["currency"] = billing["currency"]
        if billing.get("payment_gateway"):
            subscription["payment_gateway"] = billing["payment_gateway"]

    # Merge referral attribution. The SDK's get_tenant_info response is
    # {tenant_id, site_url, ..., subscription: {..., referral: {...}}} —
    # referral lives nested under `.subscription.referral`.
    if tenant_info:
        referral = (tenant_info.get("subscription") or {}).get("referral")
        if referral:
            subscription["referral"] = referral

    return {
        "success": True,
        "subscription": subscription,
        "usage": usage_data,
        "billing": billing,
        "last_sync": snap.get("last_sync", ""),
    }


def _fetch_live_quota():
    """
    Fetch live subscription data from AR and update the quota cache.

    Returns the subscription dict on success, None on failure.
    Side effect: updates Redis quota cache so other endpoints stay fresh.
    """
    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client
        from frappe_assistant_core.chat.quota_cache import update_from_ar

        client = get_fac_cloud_client()
        if not client:
            return None

        info = client.get_tenant_info()
        if not info or not info.get("subscription"):
            return None

        sub = info["subscription"]
        update_from_ar(sub)
        return sub
    except Exception:
        return None


def _refresh_subscription_cache():
    """
    Immediately sync subscription data from AR after a plan change.

    Called after verify_payment to ensure the quota cache reflects
    the new plan, quota, and usage without waiting for the 6-hour scheduler.
    """
    import frappe

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client
        from frappe_assistant_core.chat.quota_cache import update_from_ar

        client = get_fac_cloud_client()
        if not client:
            return

        info = client.get_tenant_info()
        if not info or not info.get("subscription"):
            return

        update_from_ar(info["subscription"])
    except Exception as e:
        frappe.logger().warning(f"Post-verify cache refresh failed: {e}")
