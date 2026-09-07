# Frappe Assistant Core - Subscription Lifecycle API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Cancel / reactivate / downgrade + invoice / usage / payment-method endpoints."""

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
from ..billing.sync import sync_subscription_status


@frappe.whitelist(methods=["GET"])
def get_usage_history(days: int = 30):
    """
    Get daily usage history for charts.

    Args:
            days: Number of days to fetch (default 30, max 90)

    Returns:
            dict: {
                    "history": [{"date": "2025-01-01", "tokens": 1234}, ...],
                    "total": int,
                    "average_daily": float
            }
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import ARError, get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        # Cap days at 90
        days = min(int(days), 90)

        result = client.get_usage_history(days)

        return {
            "success": True,
            "history": result.get("history", []),
            "total": result.get("total", 0),
            "average_daily": result.get("average_daily", 0),
        }

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error getting usage history: {e}")
        return {"error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error getting usage history: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["GET"])
def get_invoices(limit: int = 10):
    """
    Get invoice history.

    Args:
            limit: Maximum number of invoices to return (default 10)

    Returns:
            dict: {
                    "invoices": [...],
                    "upcoming_invoice": {...}
            }
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import ARError, get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        # Get invoice history
        invoices = client.get_invoices(min(int(limit), 50))

        # Get upcoming invoice (may fail independently)
        try:
            upcoming = client.get_upcoming_invoice()
        except ARError:
            upcoming = None

        return {"success": True, "invoices": invoices.get("invoices", []), "upcoming_invoice": upcoming}

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error getting invoices: {e}")
        return {"error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error getting invoices: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["GET"])
def get_subscription_status():
    """
    Get subscription status including scheduled plan changes.

    Returns subscription details with scheduled_change info if a downgrade
    is pending (e.g., user scheduled downgrade to Starter at period end).

    Admin only.

    Returns:
            dict: {
                    "success": bool,
                    "subscription": {
                            "plan": str,
                            "status": str,
                            "payment_status": str,
                            "quota": int,
                            "used": int,
                            "remaining": int,
                            "billing_cycle_start": str,
                            "billing_cycle_end": str,
                            "cancel_at_period_end": bool,
                            "payment_gateway": str,
                            "scheduled_change": {
                                    "new_plan": str,
                                    "effective_date": str
                            } or None
                    }
            }
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import ARError, get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        return client.get_subscription_status()

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error getting subscription status: {e}")
        return {"error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error getting subscription status: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["GET"])
def get_billing_history(limit: int = 20):
    """
    Get billing/payment history.

    Returns a list of payment events (charges, subscription changes, etc.)
    and a portal_url for Stripe customers to download PDF invoices.

    Admin only.

    Args:
            limit: Maximum number of records to return (default 20)

    Returns:
            dict: {
                    "success": bool,
                    "history": [
                            {
                                    "date": str,
                                    "datetime": str,
                                    "event": str,
                                    "event_type": str,
                                    "amount": float,
                                    "currency": str,
                                    "status": str,
                                    "gateway": str
                            }
                    ],
                    "portal_url": str (optional, for Stripe customers)
            }
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import ARError, get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        return client.get_billing_history(int(limit))

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error getting billing history: {e}")
        return {"error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error getting billing history: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["POST"])
def downgrade_to_free():
    """
    Schedule downgrade to Free plan at end of billing period.

    This cancels the active subscription at the end of the current billing period
    and switches to the Free tier. User retains current plan benefits until the
    effective date.

    Admin only.

    Returns:
            dict: {
                    "success": bool,
                    "message": str,
                    "effective_date": str
            }
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import ARError, get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        return client.downgrade_to_free()

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error downgrading to free: {e}")
        return {"error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error downgrading to free: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["POST"])
def cancel_scheduled_change():
    """
    Cancel a pending downgrade that was scheduled for the end of the billing period.

    Use this to undo a scheduled downgrade before it takes effect.
    If the user has scheduled a downgrade to Free (which cancels the subscription at
    period end), this will also reactivate the subscription with the payment gateway.

    Admin only.

    Returns:
            dict: {
                    "success": bool,
                    "message": str
            }
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import ARError, get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        return client.cancel_scheduled_change()

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error cancelling scheduled change: {e}")
        return {"error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error cancelling scheduled change: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["POST"])
def cancel_subscription(cancel_immediately: bool = False):
    """
    Cancel subscription.

    Args:
            cancel_immediately: If True, cancel immediately.
                    If False, cancel at end of billing period.

    Returns:
            dict: {
                    "success": bool,
                    "message": str,
                    "effective_date": str
            }
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import ARError, get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        # Convert string to bool if needed
        if isinstance(cancel_immediately, str):
            cancel_immediately = cancel_immediately.lower() in ("true", "1", "yes")

        result = client.cancel_subscription(cancel_immediately)

        if result.get("success"):
            # If immediate cancellation, update quota cache
            if cancel_immediately:
                from frappe_assistant_core.chat.quota_cache import update_from_ar

                update_from_ar({"plan": "Free", "quota": 50000, "used": 0})

            return {
                "success": True,
                "message": result.get("message", "Subscription cancelled"),
                "effective_date": result.get("effective_date"),
                "cancel_at_period_end": not cancel_immediately,
            }

        return {"error": result.get("error", "Failed to cancel subscription")}

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error cancelling subscription: {e}")
        return {"error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error cancelling subscription: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["POST"])
def reactivate_subscription():
    """
    Reactivate a cancelled subscription (before period end).

    Only works if subscription was cancelled with cancel_at_period_end=True
    and the period hasn't ended yet.

    Returns:
            dict: {
                    "success": bool,
                    "message": str
            }
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import ARError, get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        result = client.reactivate_subscription()

        if result.get("success"):
            # Sync subscription status
            sync_subscription_status()

            return {"success": True, "message": result.get("message", "Subscription reactivated")}

        return {"error": result.get("error", "Failed to reactivate subscription")}

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error reactivating subscription: {e}")
        return {"error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error reactivating subscription: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["GET"])
def get_payment_methods():
    """
    Get saved payment methods for the tenant.

    Admin only - returns payment methods from the payment gateway.

    Returns:
            dict: {
                    "success": bool,
                    "payment_methods": [...]
            }
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import ARError, get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        result = client.get_payment_methods()

        return {"success": True, "payment_methods": result.get("payment_methods", [])}

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error getting payment methods: {e}")
        return {"error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error getting payment methods: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["GET"])
def get_payment_instrument():
    """
    Get the instrument on file for automatic payments.

    Admin only.

    Returns:
            dict: {
                    "success": bool,
                    "gateway": str,
                    "autopay": dict | None,
                    "can_update": bool,
                    "update_mode": "settle" | "swap" | "portal",
                    "amount_due": dict | None,
            }
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import ARError, get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        result = client.get_payment_instrument() or {}

        return {"success": True, **result}

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error getting payment instrument: {e}")
        return {"error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error getting payment instrument: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["POST"])
def update_payment_method(
    payment_method: str | None = None,
    billing_name: str | None = None,
):
    """
    Start a checkout that changes the instrument paying for this subscription.

    Razorpay: settles an outstanding renewal with the new instrument when one
    exists, otherwise authorizes a refunded token swap. Stripe: returns a
    Customer Portal URL.

    Admin only.

    Args:
            payment_method: Razorpay only — "upi" or "card". Defaults per country.
            billing_name: Name prefilled in the checkout widget.

    Returns:
            dict: checkout payload with "update_mode", or {"portal_url": str}
    """
    _require_system_manager()

    if payment_method is not None and payment_method not in ("upi", "card"):
        frappe.throw(_("Invalid payment method. Choose UPI Autopay or Card."))

    try:
        from frappe_assistant_core.chat.fac_cloud_client import ARError, get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        result = (
            client.update_payment_method(
                payment_method=payment_method,
                billing_name=billing_name,
            )
            or {}
        )

        return {"success": True, **result}

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error updating payment method: {e}")
        return {"error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error updating payment method: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}
