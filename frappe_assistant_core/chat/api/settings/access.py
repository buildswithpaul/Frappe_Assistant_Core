# Frappe Assistant Core - Access Gate API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Pre-auth gate that decides whether the FACO widget renders + chat is enabled."""

from __future__ import annotations

import frappe
from frappe import _

from frappe_assistant_core.chat.api.auth import _ar_user_id, _is_tenant_owner
from frappe_assistant_core.chat.cloud_url import get_fac_cloud_url
from frappe_assistant_core.chat.gate import is_chat_enabled

# Membership-cache TTLs (seconds). A definitive AR answer is trusted for a
# minute; a fail-OPEN grant (transient blip / internal error) is trusted only
# briefly so a real suspension takes effect quickly once AR is reachable again.
_MEMBER_CACHE_TTL = 60
_FAILOPEN_TTL = 5
# The last definitive AR answer outlives any outage, so a known non-member stays out while AR is
# unreachable; only a user AR has never answered for fails open.
_LAST_KNOWN_TTL = 24 * 60 * 60


_STATUSES = ("Active", "Pending", "none", "unknown")


def _last_known_key(user: str) -> str:
    return f"faco_member_last:{user}"


def _faco_member_status(user: str) -> str:
    """AR's membership status for `user`: "Active", "Pending", "none" or "unknown".

    "none" is a definitive AR no (or an unregistered site); "unknown" covers AR unreachable, an
    open breaker and internal errors. Cached under ``faco_member:{user}`` as the status string
    (a legacy "1"/"0" reads as a miss) for 60 s when definitive, 5 s when AR cannot answer.
    When it cannot, the user's last definitive answer (kept 24 h) is returned instead, and
    "unknown" only when AR has never given one.
    """
    cache_key = f"faco_member:{user}"
    cached = frappe.cache.get_value(cache_key, expires=True)
    if cached in _STATUSES:
        return cached

    status = "unknown"
    definitive = False  # AR gave a real yes/no
    settled = False  # the answer needs no retry soon: definitive, or an unregistered site
    try:
        from frappe_assistant_core.chat import ar_breaker
        from frappe_assistant_core.chat.fac_cloud_client import SHORT_CALL_TIMEOUT, get_fac_cloud_client

        if not ar_breaker.is_open():
            client = get_fac_cloud_client(timeout=SHORT_CALL_TIMEOUT)
            if not client:
                # Unregistered site → not a member (the gate handles this earlier too).
                status = "none"
                settled = True
            else:
                # AR keys AR Tenant Users by email — query with the normalized
                # identity, not the raw Frappe username (else the Administrator
                # owner, whose seat is keyed by email, reads as a non-member).
                result = client.get_user_auth_status(user_id=_ar_user_id(user)) or {}
                if result.get("_ar_unreachable"):
                    if ar_breaker.is_transport_marker(result):
                        ar_breaker.record_failure()
                else:
                    ar_breaker.record_success()
                    ar_status = result.get("user_status")
                    status = ar_status if result.get("user_exists") and ar_status in _STATUSES[:2] else "none"
                    definitive = settled = True
    except Exception:
        frappe.log_error(title="FACO membership check failed")

    if definitive:
        frappe.cache.set_value(_last_known_key(user), status, expires_in_sec=_LAST_KNOWN_TTL)
    elif status == "unknown":
        last_known = frappe.cache.get_value(_last_known_key(user), expires=True)
        if last_known in _STATUSES[:3]:
            status = last_known

    ttl = _MEMBER_CACHE_TTL if settled else _FAILOPEN_TTL
    frappe.cache.set_value(cache_key, status, expires_in_sec=ttl)
    return status


def has_seat(user: str) -> bool | None:
    """True for an Active member, False for Pending or none, None when AR cannot say."""
    status = _faco_member_status(user)
    if status == "unknown":
        return None
    return status == "Active"


def _is_faco_member(user: str) -> bool:
    """True if `user` is an Active or Pending FACO member per AR, cached 60s.

    Source of truth = the AR Tenant User status that Settings > Users manages
    (queried via the cloud client's ``get_user_auth_status``), NOT a local OAuth
    token. The old token proxy was fragile: tokens churn across client families
    and are never removed on cloud-side suspend/deregister, so suspended members
    kept passing while members whose token landed on a superseded client row got
    locked out. Gating on AR status fixes both — suspend/deregister now DO gate
    access here, a correctness improvement over the proxy.

    Pending is admitted so an invited user can enter and auto-activate on first
    use. The result is cached per user for 60s so this is not a cloud round-trip
    on every page load.

    Fail policy (deliberate, this is access control):
      * Transient AR unavailability (``_ar_unreachable``) → fail OPEN (True):
        a network blip must not wall off a logged-in member; trust the session.
        Mirrors get_user_auth_status() in chat/api/auth.py.
      * Unexpected internal error → fail OPEN (True): same rationale. (This is a
        change from the old fail-CLOSED token check.)
      * A definitive AR "no" — user_exists False, or a non-Active/Pending status
        (Suspended/Revoked/None) when AR answered successfully → fail CLOSED
        (False): that is a real no, not a transient failure.
      * No cloud client (unregistered site) → False. The gate's registration
        check runs first; this keeps the helper self-consistent.

    Cache TTL: a definitive AR answer is cached 60s; a fail-OPEN grant (transient
    blip / internal error) is cached only briefly (``_FAILOPEN_TTL``) so a real
    suspension takes effect quickly once AR is reachable again, rather than
    granting a stale 60s of access off one bad call.
    """
    return _faco_member_status(user) != "none"


# Called on every page load to decide whether to render the chat widget.
# Must work pre-auth so guests see an onboarding CTA; returns only a
# boolean + a public reason string, never tenant data or tokens.
@frappe.whitelist(allow_guest=True, methods=["GET"])  # nosemgrep: guest-whitelisted-method
def can_use_faco() -> dict:
    """
    Check if the current user can use FACO.

    show_widget controls whether the launcher renders at all: it is hidden
    (False) for a logged-in user who is neither a FACO member nor an admin
    (System Manager / Administrator). Admins always see the widget even without
    a seat; members see it via _is_faco_member. can_use is separate — it stays
    gated on membership alone, so a non-member admin sees the launcher but
    cannot chat until seated.

    Checks in order:
    1. Master FAC Chat gate (Assistant Core Settings.enable_fac_chat)
    2. AR registration status
    3. User is a FACO member (_is_faco_member) or an admin

    Returns:
            dict: {
                    "show_widget": bool (member or admin; else False),
                    "can_use": bool,
                    "status": str (ready|not_registered|disabled|no_role|error),
                    "is_admin": bool,
                    "fac_cloud_url": str,
                    "reason": str (if can_use is False),
                    "reason_code": "assistant_disabled" (no_role because
                            Enable Assistant Access is off, not for want of a seat),
                    "preferences": dict (UI settings and subscription info),
                    "enable_browser_diagnostics": bool (recorder kill switch;
                            see widget_diagnostics_recorder.js's setEnabled)
            }
    """
    try:
        # Master gate: FAC-level enable_fac_chat (Assistant Core Settings).
        # When off, the widget is fully hidden and no further checks run.
        # This is what allows runtime toggling without a worker restart.
        #
        # With chat off, diagnostics is unconditionally False regardless of
        # the per-feature flag: there is no assistant to consume the buffers,
        # so recording would be pure cost with nothing to show for it.
        if not is_chat_enabled():
            return {
                "show_widget": False,
                "can_use": False,
                "status": "chat_module_disabled",
                "is_admin": "System Manager" in frappe.get_roles(frappe.session.user),
                "user": frappe.session.user,
                "enable_browser_diagnostics": False,
            }

        settings = frappe.get_single("FAC Chat Settings")
        user = frappe.session.user
        user_roles = frappe.get_roles(user)
        is_admin = "System Manager" in user_roles or user == "Administrator"

        # Computed once, here, so every return path below carries it via
        # base_response — the field the browser diagnostics recorder's kill
        # switch reads BEFORE any launcher-visibility decision, so a
        # non-member or an admin-disabled user still gets the operator's real
        # setting instead of running the recorder forever unreachable.
        enable_browser_diagnostics = bool(getattr(settings, "enable_browser_diagnostics", True))

        # Master gate already passed above — widget can render
        base_response = {
            "show_widget": True,
            "is_admin": is_admin,
            "user": user,
            "fac_cloud_url": get_fac_cloud_url(),
            "enable_browser_diagnostics": enable_browser_diagnostics,
        }

        # Check AR registration status FIRST
        if settings.registration_status != "Registered":
            return {
                **base_response,
                "can_use": False,
                "status": "not_registered",
                "reason": _("FACO needs to be connected to FAC Cloud"),
            }

        # Verify tenant credentials are actually present
        # This catches edge cases where status is "Registered" but credentials are missing
        if not settings.tenant_id or not settings.tenant_secret:
            return {
                **base_response,
                "can_use": False,
                "status": "not_registered",
                "reason": _("FACO registration is incomplete. Please re-register."),
            }

        # Access follows FACO membership (a seat), not Frappe role.
        # Admins (System Manager / Administrator) always see the widget even
        # without a seat, but can_use stays gated on membership alone — a
        # non-member admin sees the launcher but still cannot chat (no seat).
        has_access = _is_faco_member(user)
        if not has_access:
            # The tenant owner has no seat on first login (registration creates
            # the tenant, not a seat). Send them to the Connect flow
            # (ready + needs_user_setup) instead of the "ask your admin"
            # AccessDenied screen, so they can self-provision. A plain
            # non-member is still routed to AccessDenied (no_role).
            if _is_tenant_owner(_ar_user_id(user)):
                return {
                    **base_response,
                    "show_widget": True,
                    "can_use": False,
                    "needs_user_setup": True,
                    "status": "ready",
                }
            return {
                **base_response,
                "show_widget": is_admin,
                "can_use": False,
                "status": "no_role",
                "reason": _(
                    "Your administrator needs to add you to FACO. Please ask them to add you from Settings > Users."
                ),
            }

        # A seat does not open the MCP endpoint: handle_mcp also refuses a user
        # whose Enable Assistant Access was switched off after they were added.
        # Letting them into chat makes every load call FAC Cloud, which calls
        # back into that refusal.
        from frappe_assistant_core.api.fac_endpoint import _check_assistant_enabled

        if not _check_assistant_enabled(user):
            return {
                **base_response,
                "show_widget": is_admin,
                "can_use": False,
                "status": "no_role",
                "reason_code": "assistant_disabled",
                "reason": _(
                    "Assistant access is turned off for your account. Ask your administrator to tick Enable Assistant Access on your User record."
                ),
            }

        # Get or create user preferences (UI settings only)
        from frappe_assistant_core.chat.doctype.fac_chat_user_preferences.fac_chat_user_preferences import (
            FACChatUserPreferences,
        )

        prefs = FACChatUserPreferences.get_or_create_preferences()

        # Calculate quota remaining from cached subscription info
        from frappe_assistant_core.chat.quota_cache import get_quota_snapshot

        snap = get_quota_snapshot()
        quota_total = snap.get("quota_total", 0)
        quota_used = snap.get("quota_used", 0)
        is_unlimited = quota_total == -1

        if is_unlimited:
            quota_remaining = -1
        else:
            quota_remaining = quota_total - quota_used

            # If locally exhausted but cache is stale, sync before reporting exhaustion
            last_sync = snap.get("last_sync", "")
            if quota_remaining <= 0 and last_sync:
                from frappe.utils import now, time_diff_in_hours

                hours_since_sync = time_diff_in_hours(now(), last_sync)
                if hours_since_sync > 1:
                    from ..billing import (
                        sync_subscription_status,
                    )

                    sync_subscription_status()
                    snap = get_quota_snapshot()
                    quota_total = snap.get("quota_total", 0)
                    quota_used = snap.get("quota_used", 0)
                    is_unlimited = quota_total == -1
                    quota_remaining = -1 if is_unlimited else max(0, quota_total - quota_used)

        return {
            **base_response,
            "can_use": True,
            "status": "ready",
            "preferences": {
                "keyboard_shortcut": (
                    prefs.keyboard_shortcut
                    if prefs.keyboard_shortcut and prefs.keyboard_shortcut != "Ctrl+K"
                    else "Ctrl+Shift+K"
                )
                if prefs.enable_keyboard_shortcut
                else None,
                "show_suggested_prompts": prefs.show_suggested_prompts,
                "hide_widget": int(getattr(prefs, "hide_widget", 0) or 0),
                "privacy_consent_complete": bool(getattr(prefs, "privacy_consent_complete", 0)),
                "subscription_plan": snap.get("plan", "Free"),
                "quota_total": quota_total,
                "quota_used": quota_used,
                "quota_remaining": quota_remaining,
                "is_unlimited": is_unlimited,
            },
        }

    except Exception as e:
        frappe.log_error(title="FACO API Error", message=f"Error in can_use_faco: {e!s}")
        return {
            "show_widget": False,  # Don't show widget on error
            "can_use": False,
            "status": "error",
            "is_admin": False,
            "fac_cloud_url": "",  # Empty - widget won't show anyway on error
            "reason": _("Error checking FACO availability"),
            # No enable_browser_diagnostics key here, deliberately: its
            # ABSENCE is what tells the client this is an inferred fail-open
            # value, not a real answer to persist. Returning True would
            # overwrite a genuine persisted "off" from an earlier, successful
            # response — the widget.js defect this same fix closed, one
            # layer up.
        }
