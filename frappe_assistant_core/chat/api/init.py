# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""
SPA initialization endpoint.

Combines multiple sequential API calls into a single request with
internal parallelization of external AR calls via ThreadPoolExecutor.
Follows the same pattern as get_billing_page_data in billing.py.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import frappe
from frappe import _

from frappe_assistant_core.chat.cloud_url import PRODUCTION_FAC_CLOUD_URL, get_fac_cloud_url
from frappe_assistant_core.utils.cache import get_cached_server_settings

if TYPE_CHECKING:
    from frappe.model.document import Document


@frappe.whitelist(methods=["POST"])
def initialize_spa() -> dict:
    """
    Combined SPA initialization — replaces 6 sequential frontend calls.

    Aggregates: can_use_faco + get_quota_status + get_capabilities +
    get_user_auth_status + get_user_sessions
    into a single request with parallel AR calls.

    Returns:
            dict: {
                    "access": { can_use, status, is_admin, user, fac_cloud_url, mcp_endpoint_url, preferences },
                    "quota": { plan, quota_total, quota_used, quota_remaining, ... },
                    "outstanding": { amount, currency, invoice } | null (admins only),
                    "capabilities": { features: { billing, memory, workflows, ... } },
                    "user_auth": { ready, site_registered, user_registered, ... },
                    "onboarding": { onboarding_complete, has_conversations } | null,
                    "sessions": [ { session_id, preview, started, last_activity }, ... ]
            }
    """
    settings = frappe.get_single("FAC Chat Settings")
    user = frappe.session.user
    user_roles = frappe.get_roles(user)
    is_admin = "System Manager" in user_roles

    # === Phase 1: Local-only (main thread) ===
    access = _build_access(settings, user, user_roles, is_admin)
    access["mcp_endpoint_url"] = get_cached_server_settings().get("mcp_endpoint_url")
    quota = _build_quota(settings, is_admin)

    # Early exit for non-ready states
    if not access.get("can_use"):
        return {
            "access": access,
            "quota": quota,
            "capabilities": _default_capabilities(),
            "user_auth": None,
            "onboarding": None,
            "sessions": [],
            # Key present on every path so the SPA never has to distinguish
            # "nothing owed" from "this payload predates the field".
            "outstanding": None,
        }

    # Fetch sessions (local DB, main thread)
    sessions = _fetch_sessions()

    # === Phase 2: Parallel AR calls (worker threads) ===
    # Pattern from get_billing_page_data (billing.py:1206-1241):
    # Create the SDK client in the MAIN thread (frappe.db calls happen here),
    # then pass bound methods to workers (HTTP-only, thread-safe).
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

    client = get_fac_cloud_client()  # Main thread — safe for frappe.db

    def _safe_call(name, fn, *args):
        try:
            return name, fn(*args)
        except Exception:
            return name, None

    # Extract settings values in main thread (Frappe docs aren't thread-safe)
    caps_cache = {
        "cached_capabilities": settings.cached_capabilities,
        "capabilities_cached_at": settings.capabilities_cached_at,
        "fac_cloud_url": get_fac_cloud_url(),
    }
    tasks = [("capabilities", _get_cached_or_fetch_capabilities, caps_cache)]
    if client:
        # AR keys AR Tenant Users by email — query with the normalized identity,
        # not the raw Frappe docname. Missing this (the standalone
        # get_user_auth_status normalizes, but this combined boot path did not)
        # made AR find no seat for the Administrator owner → ready=False → the
        # SPA rendered "Connect Your Account" on every load.
        from frappe_assistant_core.chat.api.auth import _ar_user_id

        tasks.append(("user_auth", client.get_user_auth_status, _ar_user_id(user)))
        # AR's terms gate blocks stream_chat AND list_available_models. Without
        # asking at boot the SPA only discovers it by watching those features
        # fail, so ask up front and let it render the acceptance surface.
        tasks.append(("terms", client.get_terms_status))
        # Admin-only: every billing endpoint behind this is System Manager
        # gated, a member cannot settle it, and it would cost every other
        # user an AR round-trip on every boot to tell them so.
        if is_admin:
            from frappe_assistant_core.chat.api.billing._outstanding import (
                resolve_outstanding,
            )

            tasks.append(("outstanding", resolve_outstanding, client))

    ar_results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(_safe_call, *t) for t in tasks]
        for future in as_completed(futures):
            name, result = future.result()
            ar_results[name] = result

    capabilities = ar_results.get("capabilities")
    user_auth = ar_results.get("user_auth")

    # Cache capabilities if freshly fetched (main thread — safe for frappe.db)
    if capabilities and settings.cached_capabilities != json.dumps(capabilities):
        _update_capabilities_cache(settings, capabilities)

    return {
        "access": access,
        "quota": quota,
        "capabilities": capabilities or _default_capabilities(),
        "user_auth": _format_user_auth(user_auth, settings),
        "terms": _format_terms(ar_results.get("terms"), is_admin),
        "onboarding": None,  # Retained for backward compat (mobile). Onboarding chat removed.
        "sessions": sessions,
        # None when nothing is owed, and for non-admins who could not act on it.
        "outstanding": ar_results.get("outstanding"),
    }


# ============================================================================
# Helper: Access check (from settings.py:can_use_faco)
# ============================================================================


def _build_access(settings: Document, user: str, user_roles: list[str], is_admin: bool) -> dict:
    """Access-check response for initialize_spa. Delegates to the single
    authoritative gate (can_use_faco) so the boot path and the standalone
    endpoint can never diverge.

    Previously this REIMPLEMENTED the gate and rotted out of sync: it kept the
    old Frappe-role check ("Assistant User" et al.) after can_use_faco moved to
    authoritative AR membership (_is_faco_member), so real Pending/Active members
    without an assistant role were locked out of the SPA at boot — the exact
    production lockout this collapses.

    can_use_faco reads settings/user/roles from the session itself and returns
    the same shape this used to build (show_widget, is_admin, user,
    fac_cloud_url, can_use, status, reason/preferences). The settings/user/
    user_roles/is_admin params are now unused here; the signature is kept so
    initialize_spa's existing call site (and tests) don't churn. Runs in the
    main thread, so the cloud call _is_faco_member makes (cached 60s) is safe.
    """
    from frappe_assistant_core.chat.api.settings.access import can_use_faco

    return can_use_faco()


# ============================================================================
# Helper: Quota (from billing.py:get_quota_status)
# ============================================================================


def _build_quota(settings: Document, is_admin: bool) -> dict:
    """Build quota status from Redis quota cache."""
    from frappe_assistant_core.chat.quota_cache import get_quota_snapshot

    snap = get_quota_snapshot()
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
        "success": True,
        "plan": snap.get("plan", "Free"),
        "quota_total": quota_total,
        "quota_used": quota_used,
        "quota_remaining": quota_remaining,
        "percentage_used": round(percentage_used, 1),
        "is_unlimited": is_unlimited,
        "is_admin": is_admin,
        "registration_status": settings.registration_status,
    }


# ============================================================================
# Helper: Sessions
# ============================================================================


def _fetch_sessions(limit: int = 20) -> list[dict]:
    """Conversation list for the SPA boot payload.

    Delegates to the sidebar's own endpoint so the list the SPA boots with and
    the list it refetches on every ChatView remount are the same list. A private
    copy here once drifted on the ``is_archived`` filter: a page load hydrated
    the sidebar with archived conversations and the first in-app navigation
    replaced them with the filtered list, emptying the sidebar.
    """
    from frappe_assistant_core.chat.api.chat.sessions import get_user_sessions

    return get_user_sessions(limit=limit)


# ============================================================================
# Helper: Capabilities with caching (5-minute TTL)
# ============================================================================


def _get_cached_or_fetch_capabilities(caps_cache: dict) -> dict | None:
    """Return cached capabilities if fresh (< 5 min), otherwise fetch from AR.

    Args:
            caps_cache: Plain dict with cached_capabilities, capabilities_cached_at,
                        fac_cloud_url — extracted from FACO Settings in the main thread.

    Note: Does NOT update the cache here — this may run in a worker thread.
    The caller (main thread) is responsible for calling _update_capabilities_cache.
    """
    # Check cache
    cached_json = caps_cache.get("cached_capabilities")
    cached_at = caps_cache.get("capabilities_cached_at")

    if cached_json and cached_at:
        from datetime import datetime

        # Pure Python — no frappe.local needed (thread-safe)
        if isinstance(cached_at, str):
            cached_dt = datetime.fromisoformat(cached_at)
        else:
            cached_dt = cached_at
        age_seconds = (datetime.now() - cached_dt).total_seconds()
        if age_seconds < 300:  # 5 minutes
            try:
                return json.loads(cached_json)
            except (json.JSONDecodeError, TypeError):
                pass  # Corrupted cache, fetch fresh

    # Fetch fresh from AR (HTTP call only — thread-safe)
    from frappe_assistant_core.chat.fac_cloud_client import (
        get_capabilities as fetch_capabilities,
    )

    # NOT get_fac_cloud_url() — frappe.conf is a thread-local proxy and raises
    # "object is not bound" in this worker. The caller resolves it on the main
    # thread and hands it over in caps_cache.
    fac_cloud_url = caps_cache.get("fac_cloud_url") or PRODUCTION_FAC_CLOUD_URL

    try:
        return fetch_capabilities(fac_cloud_url)
    except Exception:
        return None


def _update_capabilities_cache(settings: Document, caps: dict) -> None:
    """Cache capabilities in FACO Settings.

    Runs in the main request thread — Frappe auto-commits at end of request,
    so no explicit frappe.db.commit() is needed.
    """
    from frappe.utils import now

    try:
        settings.db_set("cached_capabilities", json.dumps(caps), update_modified=False)
        settings.db_set("capabilities_cached_at", now(), update_modified=False)

        # Also maintain billing_enabled in quota cache
        from frappe_assistant_core.chat.quota_cache import set_field

        billing_enabled = caps.get("features", {}).get("billing", True)
        set_field("billing_enabled", billing_enabled)
    except Exception:
        pass  # Non-critical — cache update failure shouldn't break init


# ============================================================================
# Helper: Format user auth status
# ============================================================================


def _format_terms(terms: dict | None, is_admin: bool) -> dict:
    """Format AR's terms status for the SPA's blocking gate.

    Fails SOFT on a missing/unreachable answer: a terms lookup that did not
    come back must never wall off a working site. AR still enforces the real
    gate on every request, so the cost of guessing "fine" here is a clear
    error later, whereas guessing "blocked" locks users out over a blip.

    ``can_accept`` is the admin split — acceptance binds the whole tenant, so
    only a System Manager gets the accept action; everyone else is told to ask
    one.
    """
    if not terms or terms.get("_ar_unreachable"):
        return {"acceptance_required": False, "can_accept": is_admin}

    return {
        "acceptance_required": bool(terms.get("acceptance_required")),
        "can_accept": is_admin,
        "error_code": terms.get("error_code"),
        "required_version": terms.get("required_version"),
        "accepted_version": terms.get("accepted_version"),
        "days_remaining": terms.get("days_remaining"),
    }


def _format_user_auth(user_auth: dict | None, settings: Document) -> dict:
    """Format SDK auth response into the frontend-expected shape.

    Distinguishes three states:

    - Site not registered → ``user_registered=False``, expected to show the
      admin "register your site" flow.
    - AR unreachable (network/timeout/5xx, signalled by ``_ar_unreachable``
      on the SDK response) → fail soft. Assume the user is fine and let
      them keep using the app; a transient AR hiccup must NOT bounce a
      logged-in user to the connect-account screen. The SPA can show a
      small "billing service is having trouble" hint elsewhere.
    - AR responded → trust its ``user_exists`` / ``ready_for_streaming``.
    """
    if settings.registration_status != "Registered":
        return {
            "success": True,
            "ready": False,
            "site_registered": False,
            "user_registered": False,
            "has_mcp_servers": False,
        }

    # AR was unreachable. Trust the user's prior session — don't kick them
    # to connect-account on a transient failure. Caller (SPA) can render a
    # subtle "AR temporarily unreachable" indicator from `ar_unreachable`.
    if user_auth and user_auth.get("_ar_unreachable"):
        return {
            "success": True,
            "ready": True,
            "site_registered": True,
            "user_registered": True,
            "has_mcp_servers": False,
            "ar_unreachable": True,
            "ar_error": user_auth.get("error"),
        }

    if not user_auth:
        return {
            "success": True,
            "ready": False,
            "site_registered": True,
            "user_registered": False,
            "has_mcp_servers": False,
            "message": _("Please connect your account to use FACO"),
        }

    user_exists = user_auth.get("user_exists", False)
    has_mcp_servers = user_auth.get("has_mcp_servers", False)
    active_server_count = user_auth.get("active_server_count", 0)
    expired_servers = user_auth.get("servers_with_expired_tokens", [])
    expired_count = len(expired_servers) if isinstance(expired_servers, list) else 0
    ar_ready = user_auth.get("ready_for_streaming", False)

    # Soft-degrade for stale-token-only failures: AR refreshes near-expiry
    # tokens proactively inside get_user_auth_status; if expired_count is
    # still >0 here it means refresh failed (e.g. revoked OAuth client).
    # Keep the user in the chat UI with a `needs_reconnect` banner rather
    # than yanking them to UserSetup — they can still browse history, and
    # the next streaming call will surface a clearer error if they try to
    # chat.
    if not ar_ready and user_exists and has_mcp_servers and active_server_count > 0:
        ar_ready = True

    return {
        "success": True,
        "ready": ar_ready,
        "site_registered": True,
        "user_registered": user_exists,
        "user_status": user_auth.get("user_status", "unknown"),
        "has_mcp_servers": has_mcp_servers,
        "active_server_count": active_server_count,
        "servers_with_expired_tokens": expired_count,
        "expired_server_names": expired_servers,
        "needs_reconnect": expired_count > 0,
    }


# ============================================================================
# Helper: Default capabilities (fail-safe)
# ============================================================================


def _default_capabilities() -> dict:
    """Return safe defaults when AR is unreachable.

    Companion-app features (rag, memory, workflows) default to False
    so the UI hides them rather than showing broken functionality.
    Marketplace defaults: enabled=True (kill-switch off only when AR
    explicitly says so), user_publishing_enabled=False (closed by default).
    """
    return {
        "billing_enabled": True,
        "available_gateways": [],
        "version": "unknown",
        "features": {
            "streaming": True,
            "mcp_servers": True,
            "rag": False,
            "memory": False,
            "billing": True,
            "workflows": False,
            "web_search": False,
        },
        "marketplace": {
            "marketplace_enabled": False,
            "user_publishing_enabled": False,
            "listing_types": [],
        },
    }
