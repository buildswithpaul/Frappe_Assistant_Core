# Frappe Assistant Core - Seat Billing API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Per-user seat add / remove / preview / verify endpoints (proxies to AR)."""

from __future__ import annotations

import frappe
from frappe import _

from .._helpers import (
    ARBillingUnavailableError,
    _billing_unavailable_response,
    _log,
    _not_registered_error,
    _require_system_manager,
    _safe_error,
)


@frappe.whitelist(methods=["POST"])
def add_user_seat():
    """Begin the one-time seat-purchase checkout flow.

    Mid-cycle seat additions are billed as plain one-time payments, NOT
    against the saved recurring token. Returns a gateway-specific
    checkout payload (Razorpay order or Stripe Checkout Session URL)
    the SPA opens via its existing widget/redirect helpers.

    On end-of-cycle, no charge is needed — the renewal will pick up the
    new seat count. In that case the seat is added immediately and the
    response carries ``no_charge: True``.

    Once the payment lands (verify_seat_payment for Razorpay, webhook
    for Stripe), ``user_count`` is incremented and an AR Invoice is
    created.
    """
    _require_system_manager()
    try:
        from frappe_assistant_core.chat.fac_cloud_client import (
            ARError,
            get_fac_cloud_client,
        )

        client = get_fac_cloud_client()
        if not client:
            return {"success": False, "error": _("This site isn't registered with FAC Cloud.")}
        return client.add_user_seat()
    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error adding seat: {e}")
        return {"success": False, "error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error adding seat: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["POST"])
def verify_seat_payment(razorpay_payment_id: str, razorpay_order_id: str, razorpay_signature: str):
    """Verify a Razorpay seat-purchase payment from the embedded widget.

    Called after the admin completes the Razorpay widget for a seat
    addition. Proxies to AR ``verify_seat_payment`` which validates the
    signature, increments ``user_count``, and creates an AR Invoice.

    Returns:
            dict: ``{"success": True, "user_count": int, "invoice": str|None, "message": str}``
    """
    _require_system_manager()
    try:
        from frappe_assistant_core.chat.fac_cloud_client import ARError, get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        result = client.verify_seat_payment(razorpay_payment_id, razorpay_order_id, razorpay_signature)

        if result.get("success"):
            return {
                "success": True,
                "user_count": result.get("user_count"),
                "invoice": result.get("invoice"),
                "message": result.get("message", "Seat added successfully."),
            }

        return {"error": result.get("error", "Failed to verify seat payment")}

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error verifying seat payment: {e}")
        return {"error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error verifying seat payment: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["POST"])
def remove_user_seat():
    """Remove one seat. No refund; next renewal reflects the lower count."""
    _require_system_manager()
    try:
        from frappe_assistant_core.chat.fac_cloud_client import (
            ARError,
            get_fac_cloud_client,
        )

        client = get_fac_cloud_client()
        if not client:
            return {"success": False, "error": _("This site isn't registered with FAC Cloud.")}
        return client.remove_user_seat()
    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error removing seat: {e}")
        return {"success": False, "error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error removing seat: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["GET"])
def preview_seat_charge():
    """Preview the prorated cost of adding one seat.

    Returns {prorated_rate, tax, total, days_remaining, currency, components}.
    """
    _require_system_manager()
    try:
        from frappe_assistant_core.chat.fac_cloud_client import (
            ARError,
            get_fac_cloud_client,
        )

        client = get_fac_cloud_client()
        if not client:
            return {"success": False, "error": _("This site isn't registered with FAC Cloud.")}
        result = client.preview_seat_charge()
        return {"success": True, "pricing": result}
    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error previewing seat charge: {e}")
        return {"success": False, "error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error previewing seat charge: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO Billing Error")}
