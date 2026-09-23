# Frappe Assistant Core - Prepaid Credits API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Prepaid credit balance read + purchase checkout (proxies to AR)."""

from __future__ import annotations

import frappe
from frappe import _

from .._helpers import (
    _billing_unavailable_response,
    _log,
    _require_system_manager,
    _safe_error,
)


@frappe.whitelist(methods=["GET"])
def get_credit_balance():
    """
    Get prepaid credit balance and recent transactions.

    Returns:
            dict: {
                    "balance": int,
                    "transactions": [...]
            }
    """
    _require_system_manager()

    from frappe_assistant_core.chat.fac_cloud_client import (
        ARBillingUnavailableError,
        ARError,
        get_fac_cloud_client,
    )

    client = get_fac_cloud_client()
    if not client:
        return {"error": "Not registered with FAC Cloud"}

    try:
        return client.get_credit_balance()
    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Credit Error", message=f"AR error getting credit balance: {e}")
        return {"error": _safe_error(e, "FACO Credit Error")}
    except Exception as e:
        _log(title="FACO Credit Error", message=f"Error getting credit balance: {e!s}")
        return {"error": _safe_error(e, "FACO Credit Error")}


@frappe.whitelist(methods=["POST"])
def purchase_credits(credit_amount: int, gateway: str | None = None):
    """
    Initiate a prepaid credit purchase checkout.

    Args:
            credit_amount: Number of credits to purchase. Pack-rate pricing
                    is flat across plans — see AR Payment Gateway Settings.
            gateway: "stripe" or "razorpay" (optional).

    Returns:
            dict: Gateway-specific checkout data (checkout_url or order_id).
    """
    _require_system_manager()

    from frappe_assistant_core.chat.fac_cloud_client import (
        ARBillingUnavailableError,
        ARError,
        get_fac_cloud_client,
    )

    client = get_fac_cloud_client()
    if not client:
        frappe.throw(_("Not registered with FAC Cloud"))

    try:
        return client.purchase_credits(int(credit_amount), gateway)
    except ARBillingUnavailableError:
        frappe.throw(_("Billing is not available on this server"))
    except ARError as e:
        frappe.throw(_safe_error(e, "FACO Credit Error"))
    except Exception as e:
        frappe.throw(_safe_error(e, "FACO Credit Error"))


@frappe.whitelist(methods=["GET"])
def get_expiring_credits():
    """List unallocated credit batches expiring within 7 days.

    Returns:
            dict: ``{"batches": [{name, credits_remaining, source, expires_at,
            days_remaining}]}`` — sorted by expiry ASC.
    """
    _require_system_manager()

    from frappe_assistant_core.chat.fac_cloud_client import (
        ARBillingUnavailableError,
        ARError,
        get_fac_cloud_client,
    )

    client = get_fac_cloud_client()
    if not client:
        return {"error": "Not registered with FAC Cloud"}

    try:
        return client.get_expiring_credits()
    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Credit Error", message=f"AR error fetching expiring credits: {e}")
        return {"error": _safe_error(e, "FACO Credit Error")}
    except Exception as e:
        _log(title="FACO Credit Error", message=f"Error fetching expiring credits: {e!s}")
        return {"error": _safe_error(e, "FACO Credit Error")}


@frappe.whitelist(methods=["GET"])
def get_consumption_breakdown(days: int = 30):
    """Daily credit-consumption rollup grouped by source for the OverviewTab chart."""
    _require_system_manager()

    from frappe_assistant_core.chat.fac_cloud_client import (
        ARBillingUnavailableError,
        ARError,
        get_fac_cloud_client,
    )

    client = get_fac_cloud_client()
    if not client:
        return {"error": "Not registered with FAC Cloud"}

    try:
        return client.get_consumption_breakdown(int(days))
    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Credit Error", message=f"AR error fetching consumption breakdown: {e}")
        return {"error": _safe_error(e, "FACO Credit Error")}
    except Exception as e:
        _log(title="FACO Credit Error", message=f"Error fetching consumption breakdown: {e!s}")
        return {"error": _safe_error(e, "FACO Credit Error")}
