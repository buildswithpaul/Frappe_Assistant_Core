"""Curated-suggestion cache + background regeneration (stale-while-revalidate).

The landing endpoint serves ONLY from this cache — it never blocks on AR.
A cache miss enqueues one deduplicated background job per user.
"""

import hashlib

import frappe

from frappe_assistant_core.chat.api.auth import _ar_user_id
from frappe_assistant_core.chat.api.suggestion_signals import gather_suggestion_signals
from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

CACHE_TTL = 86400  # 24h — AR's 20h rate limit stays under this
# An empty or failed generation is remembered briefly, so a home page that
# keeps missing does not queue a fresh job on every visit.
NEGATIVE_TTL = 900


def _cache_key(user: str) -> str:
    return f"faco_curated_sugg:{user}"


def curated_row_name(text: str) -> str:
    return f"curated_{hashlib.sha1(text.encode()).hexdigest()[:8]}"


def get_cached_curated(user: str) -> list:
    cached = frappe.cache.get_value(_cache_key(user))
    if not isinstance(cached, dict):
        return []
    suggestions = cached.get("suggestions")
    return suggestions if isinstance(suggestions, list) else []


def schedule_regeneration_if_stale(user: str) -> None:
    if frappe.cache.get_value(_cache_key(user)) is not None:
        return
    frappe.enqueue(
        "frappe_assistant_core.chat.api.curated.regenerate_curated_suggestions",
        queue="short",
        deduplicate=True,
        job_id=f"curated-sugg-{user}",
        for_user=user,
    )


def regenerate_curated_suggestions(for_user: str) -> None:
    """Background job: gather local signals, call AR, cache the result.

    frappe.enqueue reserves the `user` kwarg — hence `for_user`.
    """
    client = get_fac_cloud_client()
    if not client:
        return
    try:
        signals = gather_suggestion_signals(for_user)
        res = client.generate_curated_suggestions(user_id=_ar_user_id(for_user), signals=signals, timeout=45)
    except Exception:
        frappe.log_error(
            title=f"Curated suggestions failed: {for_user}",
            message=frappe.get_traceback(),
        )
        return

    suggestions = (res or {}).get("suggestions") or []
    frappe.cache.set_value(
        _cache_key(for_user),
        {"suggestions": suggestions, "generated_at": (res or {}).get("generated_at")},
        expires_in_sec=CACHE_TTL if suggestions else NEGATIVE_TTL,
    )
