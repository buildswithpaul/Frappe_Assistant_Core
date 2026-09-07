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

from .._helpers import _require_system_manager, _safe_error

PURPOSES = ("Subscription", "Payment Method", "Credits", "Pack", "Seat")


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
