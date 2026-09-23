# Frappe Assistant Core - Industry Packs settings API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Wrappers around the marketplace tenant-pack endpoints.

In multi-server deployments (FACO and AR on different Frappe benches) we
cannot import the marketplace module directly. All calls go through the
SDK and hit the signed endpoints in
``assistant_runtime_marketplace.api.tenant_packs_signed``.
"""

import frappe
from frappe import _

try:
    from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client
except ImportError:
    get_fac_cloud_client = None  # type: ignore[assignment]  # fac_cloud_client pending Task 3.8

from ._helpers import _marketplace_enabled, _not_registered_error, _require_system_manager, _safe_error
from .auth import _ar_user_id


def _client_or_throw():
    """Return a configured SDK client or throw a registration-required error."""
    client = get_fac_cloud_client()
    if client is None:
        frappe.throw(_not_registered_error())
    return client


@frappe.whitelist(methods=["GET"])
def list_packs():
    """Return every active pack with eligibility + enablement annotations.

    Admin only — used by Settings > Industry Packs and the onboarding
    IndustryPackStep.
    """
    _require_system_manager()
    if not _marketplace_enabled():
        return {"packs": [], "marketplace_enabled": False}
    try:
        client = _client_or_throw()
        result = client.list_packs() or {}
        return {"packs": result.get("packs", [])}
    except Exception as e:
        frappe.log_error(
            title="FACO Industry Packs Error",
            message=f"list_packs: {e!s}",
        )
        return {"packs": [], "error": _safe_error(e, "FACO Industry Packs Error")}


@frappe.whitelist(methods=["GET"])
def get_pack_contents(pack_id: str):
    """Return the named prompts + skills of an owned pack. Admin only."""
    _require_system_manager()
    if not _marketplace_enabled():
        return {"pack_id": pack_id, "prompts": [], "skills": [], "marketplace_enabled": False}
    try:
        client = _client_or_throw()
        return client.get_pack_contents(pack_id) or {"pack_id": pack_id, "prompts": [], "skills": []}
    except Exception as e:
        frappe.log_error(
            title="FACO Pack Contents Error",
            message=f"get_pack_contents({pack_id}): {e!s}",
        )
        return {
            "pack_id": pack_id,
            "prompts": [],
            "skills": [],
            "error": _safe_error(e, "FACO Pack Contents Error"),
        }


@frappe.whitelist(methods=["POST"])
def set_industry(industry: str | None, auto_enable: bool | int | str = True):
    """Set this tenant's industry and optionally auto-enable its pack.

    Used by the onboarding industry step. Admin only.
    """
    _require_system_manager()
    if not _marketplace_enabled():
        frappe.throw(_("Industry packs are not available on this server."))
    auto_enable_bool = str(auto_enable).lower() in ("1", "true", "yes")
    client = _client_or_throw()
    return client.set_industry(industry, auto_enable=auto_enable_bool)


@frappe.whitelist(methods=["POST"])
def set_pack_enabled(pack_id: str, enabled: bool | int | str, source: str = "User"):
    """Toggle a pack on or off for this tenant. Admin only."""
    _require_system_manager()
    if not _marketplace_enabled():
        frappe.throw(_("Industry packs are not available on this server."))
    enabled_bool = enabled.lower() in ("1", "true", "yes") if isinstance(enabled, str) else bool(enabled)
    client = _client_or_throw()
    return client.set_pack_enabled(pack_id, enabled_bool, source=source)


@frappe.whitelist(methods=["GET"])
def get_recommended_pack():
    """Return at most one pack to surface in the onboarding toast.

    Open to any logged-in user (the toast is per-user). Returns
    ``{"pack": <dict|null>}``.
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    if not _marketplace_enabled():
        return {"pack": None}

    try:
        client = get_fac_cloud_client()
        if client is None:
            return {"pack": None}
        return client.get_recommended_pack(user_id=_ar_user_id(frappe.session.user)) or {"pack": None}
    except Exception:
        # Toast is best-effort — never break the chat experience.
        return {"pack": None}


@frappe.whitelist(methods=["POST"])
def dismiss_pack_recommendation():
    """Mark the onboarding toast as dismissed for the current user."""
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)
    if not _marketplace_enabled():
        return {"dismissed": True}
    client = _client_or_throw()
    return client.dismiss_pack_recommendation(user_id=_ar_user_id(frappe.session.user))


@frappe.whitelist(methods=["POST"])
def activate_free_pack(pack_id: str):
    """Activate the tenant's free-grant pack (Pro/Team only).

    Calls the marketplace enable_pack_as_free_grant signed endpoint.
    Permanent — once picked, cannot be replaced.
    """
    _require_system_manager()
    if not _marketplace_enabled():
        frappe.throw(_("Industry packs are not available on this server."))
    client = _client_or_throw()
    return client.enable_pack_as_free_grant(pack_id)


@frappe.whitelist(methods=["POST"])
def toggle_purchased_pack(pack_id: str, enabled: bool | int | str):
    """Toggle a purchased pack on or off.

    Only `acquisition=purchased` packs can be toggled — free grants and
    admin grants are locked at the marketplace layer.
    """
    _require_system_manager()
    if not _marketplace_enabled():
        frappe.throw(_("Industry packs are not available on this server."))
    enabled_bool = enabled.lower() in ("1", "true", "yes") if isinstance(enabled, str) else bool(enabled)
    client = _client_or_throw()
    return client.toggle_purchased_pack(pack_id, enabled_bool)


@frappe.whitelist(methods=["POST"])
def initiate_pack_checkout(pack_id: str):
    """Create a Razorpay one-time order for a pack purchase.

    Returns the SPA checkout payload (key, order_id, amount, currency,
    prefill, notes). SPA opens window.Razorpay with this payload.
    """
    _require_system_manager()
    if not _marketplace_enabled():
        frappe.throw(_("Industry packs are not available on this server."))
    client = _client_or_throw()
    return client.initiate_pack_checkout(pack_id)


@frappe.whitelist(methods=["POST"])
def verify_pack_payment(
    razorpay_payment_id: str,
    razorpay_order_id: str,
    razorpay_signature: str,
):
    """Verify a Razorpay pack payment from the embedded widget.

    Idempotent — safe to call multiple times. The handler short-circuits
    on duplicate payment_id.
    """
    _require_system_manager()
    if not _marketplace_enabled():
        frappe.throw(_("Industry packs are not available on this server."))
    client = _client_or_throw()
    return client.verify_razorpay_pack_payment(razorpay_payment_id, razorpay_order_id, razorpay_signature)


@frappe.whitelist(methods=["GET"])
def list_pack_purchases():
    """Return the calling tenant's AR Pack Purchase history."""
    _require_system_manager()
    if not _marketplace_enabled():
        return {"purchases": []}
    try:
        client = _client_or_throw()
        result = client.list_pack_purchases() or {}
        return {"purchases": result.get("purchases", [])}
    except Exception as e:
        frappe.log_error(
            title="FAC Pack Purchases Error",
            message=f"list_pack_purchases: {e!s}",
        )
        return {"purchases": [], "error": _safe_error(e, "FAC Pack Purchases Error")}
