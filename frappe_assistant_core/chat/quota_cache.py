# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""
Redis-backed quota cache for subscription data.

Replaces the former FACO Settings DocType fields (subscription_plan,
subscription_quota, subscription_used, last_sync, billing_enabled,
preferred_model) with a lightweight Redis cache.

Why Redis instead of DocType fields:
- Atomic increment for quota_used (no ORM save contention)
- Sub-millisecond reads for hot paths (stream_complete events)
- Naturally ephemeral — the 6-hour scheduled sync corrects drift
- Cold-start self-healing via seed_from_ar()
"""

from __future__ import annotations

import frappe
from frappe.utils import now

CACHE_KEY = "faco_quota_cache"
CACHE_TTL = 86400  # 24 hours

# After AR fails to answer a seed, quota reads serve the fallback for this long
# instead of each waiting out another get_tenant_info timeout.
SEED_FAILED_KEY = "faco_quota_seed_failed"
SEED_RETRY_AFTER = 45  # seconds


def get_quota_snapshot() -> dict:
    """Read the full quota state from cache.

    On cache miss (cold start / Redis restart), seeds from AR automatically.
    Returns the fallback (``is_fallback: True``) if AR is also unreachable.

    Returns:
            dict: {
                    "plan": str,
                    "quota_total": int,
                    "quota_used": int,
                    "last_sync": str (ISO datetime),
                    "billing_enabled": bool,
                    "preferred_model": str,
                    "features": dict,
                    "is_fallback": bool (present only on the fallback),
            }
    """
    snap = frappe.cache.get_value(CACHE_KEY, expires=True)
    if snap:
        return snap

    return seed_from_ar()


def increment_used(credits: float) -> None:
    """Increment quota_used by the given credit count.

    quota_used and quota_total are both credit-denominated (quota_total is AR's
    credit_quota), so this must be fed the turn's credits_used — never a raw
    token count, which would dwarf the credit quota and peg the meter at 100%.
    Reads current snapshot, adds credits, writes back.
    """
    snap = get_quota_snapshot()
    snap["quota_used"] = (snap.get("quota_used") or 0) + (credits or 0)
    _write(snap)


def update_from_ar(subscription: dict) -> None:
    """Update cache from an AR subscription response.

    Handles both credit-based and token-based field names.
    Called by sync_subscription_status, _fetch_live_quota, etc.
    """
    snap = get_quota_snapshot()
    # The fallback's figures are guesses; AR's answer must not inherit them
    # (a zero credit_quota would otherwise keep the fallback's -1, "unlimited").
    if snap.get("is_fallback"):
        snap = _empty_snapshot()

    snap["plan"] = subscription.get("plan", snap.get("plan", "Free"))
    snap["quota_total"] = subscription.get("credit_quota") or subscription.get(
        "quota", snap.get("quota_total", 0)
    )
    snap["quota_used"] = subscription.get("credits_used") or subscription.get(
        "used", snap.get("quota_used", 0)
    )
    snap["last_sync"] = now()

    # Pass through pricing info if present
    for key in (
        "plan_price_usd",
        "price_per_user_usd",
        "credits_per_user",
        "min_users",
        "credit_balance",
        "features",
    ):
        if key in subscription:
            snap[key] = subscription[key]

    _write(snap)


def set_field(field: str, value) -> None:
    """Set a single field in the cache."""
    snap = get_quota_snapshot()
    snap[field] = value
    _write(snap)


def get_field(field: str, default=None):
    """Get a single field from the cache."""
    snap = get_quota_snapshot()
    return snap.get(field, default)


def seed_from_ar() -> dict:
    """Cold-start handler: fetch subscription data from AR and populate cache.

    Returns the fallback if AR is unreachable so users aren't blocked. A failed
    attempt is remembered for ``SEED_RETRY_AFTER`` seconds, so while AR is down
    every quota read doesn't make its own call and wait out the timeout.
    """
    if frappe.cache.get_value(SEED_FAILED_KEY, expires=True):
        return _safe_defaults()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            # Not registered yet: nothing was asked, so there is nothing to back off from.
            return _safe_defaults()

        info = client.get_tenant_info()
        if info and info.get("subscription"):
            snap = {
                **quota_from_subscription(info["subscription"]),
                "last_sync": now(),
                "billing_enabled": True,
                "preferred_model": info.get("preferred_model", ""),
            }
            _write(snap)
            return snap
    except Exception:
        pass

    frappe.cache.set_value(SEED_FAILED_KEY, True, expires_in_sec=SEED_RETRY_AFTER)
    return _safe_defaults()


def quota_from_subscription(subscription: dict) -> dict:
    """The snapshot quota fields from an AR subscription block."""
    return {
        "plan": subscription.get("plan", "Free"),
        "features": subscription.get("features") or {},
        "quota_total": subscription.get("credit_quota") or subscription.get("quota", 0),
        "quota_used": subscription.get("credits_used") or subscription.get("used", 0),
    }


def summarize(snap: dict) -> dict:
    """The plan and quota figures clients read, derived from one snapshot.

    Shared by the boot payload and get_quota_status so the two cannot drift.
    ``features`` is empty for an AR that predates plan features, which clients
    read as "allowed". ``is_fallback`` marks figures AR never supplied.
    """
    quota_total = snap.get("quota_total", 0)
    quota_used = snap.get("quota_used", 0)
    is_unlimited = quota_total == -1

    if is_unlimited:
        quota_remaining = -1
        percentage_used = 0
    else:
        quota_remaining = max(0, quota_total - quota_used)
        percentage_used = (quota_used / quota_total * 100) if quota_total > 0 else 0

    return {
        "plan": snap.get("plan", "Free"),
        "quota_total": quota_total,
        "quota_used": quota_used,
        "quota_remaining": quota_remaining,
        "percentage_used": round(percentage_used, 1),
        "is_unlimited": is_unlimited,
        "features": snap.get("features") or {},
        "is_fallback": bool(snap.get("is_fallback")),
    }


def clear() -> None:
    """Clear the quota cache and any remembered seed failure."""
    frappe.cache.delete_value(CACHE_KEY)
    frappe.cache.delete_value(SEED_FAILED_KEY)


def _write(snap: dict) -> None:
    """Write snapshot to Redis with TTL.

    The fallback is never written, whichever caller hands it over: set_field
    and increment_used read it on a cold cache, and writing it back kept
    "Unknown plan · Unlimited" on the plan card for the whole TTL.
    """
    if snap.get("is_fallback"):
        return
    frappe.cache.set_value(CACHE_KEY, snap, expires_in_sec=CACHE_TTL)


def _empty_snapshot() -> dict:
    return {
        "plan": "Free",
        "quota_total": 0,
        "quota_used": 0,
        "last_sync": "",
        "billing_enabled": True,
        "preferred_model": "",
    }


def _safe_defaults() -> dict:
    """The fallback served when AR is unreachable on cold start."""
    return {
        **_empty_snapshot(),
        "plan": "Unknown",
        "quota_total": -1,  # Unlimited — don't block users
        "is_fallback": True,
    }
