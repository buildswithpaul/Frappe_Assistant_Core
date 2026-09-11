# Frappe Assistant Core - Quota Status API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""User-facing quota status endpoint (NOT admin-only)."""

from __future__ import annotations

import frappe

from .._helpers import (
    _log,
    _safe_error,
)


def _fetch_live_quota_dispatch():
    """Resolve _fetch_live_quota via the package namespace at call time.

    Tests patch ``...api.billing._fetch_live_quota`` directly; resolving
    the symbol at call time (rather than binding it at import) lets that
    patch take effect on the call inside ``get_quota_status`` below.
    """
    from frappe_assistant_core.chat.api import billing as _billing

    return _billing._fetch_live_quota()


@frappe.whitelist(methods=["GET"])
def get_quota_status():
    """
    Get current quota status for widget and billing page display.

    Fetches live data from AR to avoid stale cache issues (e.g., after
    a plan upgrade). Falls back to cached FACO Settings if AR is unreachable.

    This is NOT admin-only - all users can see their organization's quota.

    Returns:
            dict: {
                    "plan": str,
                    "quota_total": int,
                    "quota_used": int,
                    "quota_remaining": int,
                    "percentage_used": float,
                    "credit_balance": float,      # prepaid, always present
                    "in_overage": bool,           # quota spent, prepaid covering
                    "credits_exhausted": bool,    # quota spent, prepaid gone
                    "is_admin": bool
            }

    ``in_overage`` and ``credits_exhausted`` are the admission answer, and
    clients must gate on them rather than on ``percentage_used``, which
    measures the monthly quota alone and so reads as blocked for any tenant
    running on purchased credits.
    """
    try:
        from frappe_assistant_core.chat.quota_cache import get_quota_snapshot

        settings = frappe.get_single("FAC Chat Settings")
        is_admin = "System Manager" in frappe.get_roles(frappe.session.user)

        # Fetch live from AR to get current plan/quota (avoids cache staleness)
        live = _fetch_live_quota_dispatch()
        snap = get_quota_snapshot()
        if live:
            quota_total = live.get("credit_quota") or live.get("quota", 0)
            quota_used = live.get("credits_used") or live.get("used", 0)
            plan = live.get("plan", "Free")
        else:
            # Fallback to cached quota if AR is unreachable
            quota_total = snap.get("quota_total", 0)
            quota_used = snap.get("quota_used", 0)
            plan = snap.get("plan", "Free")

        # The prepaid balance is part of the admission answer, so it has to
        # survive an AR blip. It used to be emitted only on the live path,
        # and a client that scores "absent" as zero then turns a transient
        # network failure into a hard block for a tenant holding credits.
        # `_fetch_live_quota` folds the live figure into the snapshot, so the
        # cached value is the same number one sync behind, never a guess.
        balance_source = live if live and "credit_balance" in live else snap
        credit_balance = float(balance_source.get("credit_balance") or 0)

        is_unlimited = quota_total == -1

        if is_unlimited:
            quota_remaining = -1
            percentage_used = 0
        else:
            quota_remaining = max(0, quota_total - quota_used)
            percentage_used = (quota_used / quota_total * 100) if quota_total > 0 else 0

        # Say what AR's gate would say, rather than leaving each client to
        # re-derive it. `percentage_used >= 100` is NOT that answer: it counts
        # the monthly quota alone, so it reads as blocked for every tenant who
        # bought credits precisely so they would not be. Mirrors
        # payments/runtime_hooks.py — a quota of 0 is spent from the first
        # request, and any balance above zero admits the turn.
        quota_spent = not is_unlimited and quota_used >= quota_total
        in_overage = quota_spent and credit_balance > 0
        credits_exhausted = quota_spent and credit_balance <= 0

        # Pass through pricing info from AR. `estimated_monthly_bill` and
        # `plan_price` are currency-aware (billing country → INR/USD) —
        # the BillingHero card must use those, never the legacy flat
        # `plan_price_usd`, or an Indian tenant sees "$60" next to INR
        # plan cards.
        pricing = {}
        if live:
            pricing = {
                "plan_price": live.get("plan_price", 0),
                "plan_price_annual": live.get("plan_price_annual", 0),
                "plan_price_usd": live.get("plan_price_usd", 0),
                "price_per_user_usd": live.get("price_per_user_usd", 0),
                "price_per_user": live.get("price_per_user", 0),
                "credits_per_user": live.get("credits_per_user", 0),
                "min_users": live.get("min_users", 1),
                "currency": live.get("currency") or "USD",
                "is_per_user": bool(live.get("is_per_user")),
                "estimated_monthly_bill": live.get("estimated_monthly_bill") or {},
            }

        return {
            "success": True,
            "plan": plan,
            "quota_total": quota_total,
            "quota_used": quota_used,
            "quota_remaining": quota_remaining,
            "percentage_used": round(percentage_used, 1),
            "is_unlimited": is_unlimited,
            "credit_balance": credit_balance,
            "in_overage": in_overage,
            "credits_exhausted": credits_exhausted,
            "is_admin": is_admin,
            "registration_status": settings.registration_status,
            **pricing,
        }

    except Exception as e:
        _log(title="FACO Quota Error", message=f"Error getting quota status: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO Quota Error"), "is_admin": False}
