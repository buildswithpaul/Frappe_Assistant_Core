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


def get_quota_snapshot() -> dict:
    """Read the full quota state from cache.

    On cache miss (cold start / Redis restart), seeds from AR automatically.
    Returns safe defaults if AR is also unreachable.

    Returns:
            dict: {
                    "plan": str,
                    "quota_total": int,
                    "quota_used": int,
                    "last_sync": str (ISO datetime),
                    "billing_enabled": bool,
                    "preferred_model": str,
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

    snap["plan"] = subscription.get("plan", snap.get("plan", "Free"))
    snap["quota_total"] = subscription.get("credit_quota") or subscription.get(
        "quota", snap.get("quota_total", 0)
    )
    snap["quota_used"] = subscription.get("credits_used") or subscription.get(
        "used", snap.get("quota_used", 0)
    )
    snap["last_sync"] = now()

    # Pass through pricing info if present
    for key in ("plan_price_usd", "price_per_user_usd", "credits_per_user", "min_users", "credit_balance"):
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

    Returns safe defaults if AR is unreachable so users aren't blocked.
    """
    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if client:
            info = client.get_tenant_info()
            if info and info.get("subscription"):
                sub = info["subscription"]
                snap = {
                    "plan": sub.get("plan", "Free"),
                    "quota_total": sub.get("credit_quota") or sub.get("quota", 0),
                    "quota_used": sub.get("credits_used") or sub.get("used", 0),
                    "last_sync": now(),
                    "billing_enabled": True,
                    "preferred_model": info.get("preferred_model", ""),
                }
                _write(snap)
                return snap
    except Exception:
        pass

    # AR unreachable — return safe defaults (unlimited so users aren't blocked)
    defaults = _safe_defaults()
    _write(defaults)
    return defaults


def clear() -> None:
    """Clear the quota cache. Used in tests."""
    frappe.cache.delete_value(CACHE_KEY)


def _write(snap: dict) -> None:
    """Write snapshot to Redis with TTL."""
    frappe.cache.set_value(CACHE_KEY, snap, expires_in_sec=CACHE_TTL)


def _safe_defaults() -> dict:
    """Safe defaults when AR is unreachable on cold start."""
    return {
        "plan": "Unknown",
        "quota_total": -1,  # Unlimited — don't block users
        "quota_used": 0,
        "last_sync": "",
        "billing_enabled": True,
        "preferred_model": "",
    }
