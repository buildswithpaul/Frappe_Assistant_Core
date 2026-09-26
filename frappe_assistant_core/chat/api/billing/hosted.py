# Frappe Assistant Core - Hosted Checkout API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Ask FAC Cloud for a link to the page where a purchase is paid for.

Payments are not taken on this site. A payment gateway is onboarded against
one declared website, and this app runs on a different domain for every
customer — so the gateway widget belongs on FAC Cloud's own public site, not
here. This endpoint swaps a purchase intent for a one-shot link to it.
"""

from __future__ import annotations

import frappe
from frappe import _

from .._helpers import _require_system_manager, _safe_error, _user_message_for_ar_error
from ._internal import _quota_summary, _refresh_subscription_cache

PURPOSES = ("Subscription", "Payment Method", "Credits", "Pack", "Seat")

# What an older FAC Cloud answers for an API method it does not have.
_MISSING_METHOD = "Failed to get method"


@frappe.whitelist(methods=["POST"])
def create_hosted_checkout(
    purpose: str,
    params: dict | str | None = None,
    return_url: str | None = None,
):
    """
    Get the URL to send this user to in order to pay.

    Args:
            purpose: One of Subscription, Payment Method, Credits, Pack, Seat.
            params: Purpose-specific arguments, e.g. ``{"plan": "Team"}``.
            return_url: Where FAC Cloud should send the user back to. Defaults
                    to this site; FAC Cloud refuses anything that is not on it.

    Returns:
            dict: ``{"checkout_url": str, "expires_at": str, ...}``
    """
    _require_system_manager()

    if purpose not in PURPOSES:
        frappe.throw(_("Unknown checkout purpose: {0}").format(purpose))

    if isinstance(params, str):
        params = frappe.parse_json(params) or {}
    if params is not None and not isinstance(params, dict):
        frappe.throw(_("params must be an object"))

    if purpose == "Seat":
        # invited_by is an authority claim AR validates against the tenant
        # owner and its Active Admins. Always stamp the acting session's
        # identity here — a client-supplied value must never pass through,
        # whether forged or simply omitted to dodge the check.
        from frappe_assistant_core.chat.api.auth import _ar_user_id

        params = {**(params or {}), "invited_by": _ar_user_id(frappe.session.user)}

    from frappe_assistant_core.chat.fac_cloud_client import (
        ARBillingUnavailableError,
        ARError,
        get_fac_cloud_client,
    )

    client = get_fac_cloud_client()
    if not client:
        frappe.throw(_("Not registered with FAC Cloud"))

    try:
        return client.create_hosted_checkout(
            purpose,
            params=params or {},
            return_url=return_url or frappe.utils.get_url(),
        )
    except ARBillingUnavailableError:
        frappe.throw(_("Billing is not available on this server"))
    except ARError as e:
        frappe.throw(_safe_error(e, "FAC Hosted Checkout Error"))
    except Exception as e:
        frappe.throw(_safe_error(e, "FAC Hosted Checkout Error"))


@frappe.whitelist(methods=["POST"])
def verify_checkout_return(session: str) -> dict:
    """
    Check the purchase the user just returned from, and refresh the plan once it lands.

    FAC Cloud's checkout page sends the user back with ``fac_checkout=<session>``.
    The plan shown here is cached for up to a day, so without this the old plan
    stays on screen after paying. The SPA polls until ``done``.

    Args:
            session: The ``fac_checkout`` value from the return URL.

    Returns:
            dict: ``{"done": bool, "outcome": "applied" | "processing" | "failed"
            | "cancelled" | "unknown", "purpose", "plan", "target_plan"}``, plus
            ``"quota"`` (the refreshed snapshot) whenever the cache was refreshed,
            and ``"error"`` on a transient failure. ``unknown`` means FAC Cloud
            cannot report on the session, so the cache was simply refreshed.
    """
    _require_system_manager()

    if not session:
        frappe.throw(_("A checkout session is required."))

    from frappe_assistant_core.chat.fac_cloud_client import (
        ARAPIError,
        ARBillingUnavailableError,
        ARError,
        get_fac_cloud_client,
    )

    client = get_fac_cloud_client()
    if not client:
        frappe.throw(_("Not registered with FAC Cloud"))

    # An SDK release that predates the status method: nothing to poll.
    if not hasattr(client, "get_checkout_session_status"):
        return _refreshed("unknown")

    try:
        status = client.get_checkout_session_status(session) or {}
    except ARBillingUnavailableError:
        return {"done": True, "outcome": "unknown", "error": _("Billing is not available on this server")}
    except ARAPIError as e:
        if _MISSING_METHOD in f"{e} {getattr(e, 'response_data', '')}":
            return _refreshed("unknown")
        return _still_waiting(e)
    except ARError as e:
        return _still_waiting(e)

    outcome = status.get("outcome") or "processing"
    summary = {
        "done": bool(status.get("done")),
        "outcome": outcome,
        "purpose": status.get("purpose"),
        "plan": status.get("plan"),
        "target_plan": status.get("target_plan"),
    }
    if summary["done"] and outcome == "applied":
        _refresh_subscription_cache()
        summary["quota"] = _quota_summary()
    return summary


def _refreshed(outcome: str) -> dict:
    _refresh_subscription_cache()
    return {"done": True, "outcome": outcome, "quota": _quota_summary()}


def _still_waiting(e: Exception) -> dict:
    """A failed poll is not a failed payment; the caller asks again.

    Logged at warning level rather than as an Error Log: a polling client
    would otherwise file one per attempt.
    """
    frappe.logger("faco.billing").warning(f"verify_checkout_return: {type(e).__name__}: {e}")
    return {"done": False, "outcome": "processing", "error": _user_message_for_ar_error(e)}
