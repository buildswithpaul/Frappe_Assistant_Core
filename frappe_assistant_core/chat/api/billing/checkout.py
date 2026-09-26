# Frappe Assistant Core - Plan-Change Checkout API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Plan upgrade checkout, mandate reauth, and post-checkout payment verification."""

from __future__ import annotations

import frappe

from .._helpers import (
    ARBillingUnavailableError,
    _billing_unavailable_response,
    _log,
    _not_registered_error,
    _require_system_manager,
    _safe_error,
)
from ..billing._internal import (
    _quota_summary,
    _refresh_subscription_cache,
)
from ..billing.sync import sync_subscription_status


@frappe.whitelist(methods=["POST"])
def initiate_plan_upgrade(
    plan: str,
    billing_cycle: str = "monthly",
    gateway: str | None = None,
    billing_name: str | None = None,
    billing_email: str | None = None,
    promo_code: str | None = None,
    payment_method: str | None = None,
):
    """
    Initiate plan upgrade or downgrade.

    Uses AR's upgrade_plan endpoint which handles all plan change scenarios:
    - Upgrades: Creates checkout session for immediate upgrade with proration
    - Downgrades to paid plan: Schedules for end of billing period
    - Downgrades to Free: Cancels subscription at period end

    Args:
            plan: Target plan name (e.g., "Free", "Starter", "Pro", "Enterprise")
            billing_cycle: "monthly" or "annual"
            gateway: Payment gateway to use ("stripe" or "razorpay"). If None, uses recommended.
            billing_name: Customer/company name for billing (required for first-time checkout)
            billing_email: Email for billing notifications (required for first-time checkout)
            promo_code: Promotional/referral code (optional)
            payment_method: Razorpay-only — "upi" (UPI Autopay) or "card". Defaults
                    to "upi" for India and "card" for international when omitted.

    Returns:
            dict: {
                    "success": bool,
                    "checkout_url": str (for upgrades requiring payment),
                    "session_id": str,
                    "gateway": str,
                    "message": str (for downgrades),
                    "effective_date": str (for downgrades scheduled at period end)
            }
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import ARError, get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        # Validate billing cycle
        if billing_cycle not in ("monthly", "annual"):
            return {"error": "Invalid billing cycle. Use 'monthly' or 'annual'"}

        # Validate gateway if provided
        if gateway and gateway not in ("stripe", "razorpay"):
            return {"error": "Invalid gateway. Use 'stripe' or 'razorpay'"}

        # Validate payment_method if provided
        if payment_method and payment_method not in ("upi", "card"):
            return {"error": "Invalid payment_method. Use 'upi' or 'card'"}

        # Defense in depth: AR also rejects this. Short-circuit here so FAC
        # callers get a clear error before any gateway session is created.
        try:
            status = client.get_subscription_status() or {}
            sub = status.get("subscription") or status
            if sub.get("cancel_at_period_end"):
                scheduled = sub.get("scheduled_change") or {}
                if isinstance(scheduled, dict):
                    target = (scheduled.get("new_plan") or "").strip().lower()
                else:
                    target = str(sub.get("scheduled_plan_change") or "").strip().lower()
                if not target or target == "free":
                    return {
                        "success": False,
                        "error": "cancel_at_period_end",
                        "message": (
                            "Your subscription is scheduled to cancel at the end of "
                            "the billing period. Keep your current plan first, then "
                            "change plans."
                        ),
                    }
        except Exception:
            # Fall through to AR upgrade_plan, which enforces the same rule.
            pass

        frappe.logger("faco.billing").info(
            f"initiate_plan_upgrade: plan={plan} cycle={billing_cycle} "
            f"gateway={gateway or 'auto'} method={payment_method or 'default'}"
        )

        # Use upgrade_plan endpoint which handles all scenarios including Free downgrade
        result = client.upgrade_plan(
            plan,
            billing_cycle,
            gateway=gateway,
            billing_name=billing_name,
            billing_email=billing_email,
            promo_code=promo_code,
            payment_method=payment_method,
        )

        # Handle successful downgrade (no checkout needed)
        if result.get("success") and result.get("message"):
            return {
                "success": True,
                "message": result.get("message"),
                "effective_date": result.get("effective_date"),
            }

        # Handle Stripe redirect flow (upgrade requiring payment)
        if result.get("checkout_url"):
            return {
                "success": True,
                "checkout_url": result["checkout_url"],
                "session_id": result.get("session_id"),
                "gateway": result.get("gateway", gateway or "stripe"),
            }

        # Handle Razorpay embedded widget flow. Under the recurring-token
        # model the widget needs `razorpay_order_id` + `recurring:"1"`;
        # we pass through everything the frontend needs to open it.
        if result.get("razorpay_order_id"):
            frappe.logger("faco.billing").info(
                f"initiate_plan_upgrade: Razorpay widget ready for plan {plan} "
                f"(order={result.get('razorpay_order_id')} currency={result.get('currency')})"
            )
            return {
                "success": True,
                "gateway": "razorpay",
                "session_id": result.get("session_id"),
                "razorpay_key": result.get("razorpay_key"),
                "razorpay_order_id": result.get("razorpay_order_id"),
                "amount": result.get("amount"),
                "currency": result.get("currency"),
                "customer_id": result.get("customer_id"),
                "prefill": result.get("prefill", {}),
            }

        # Handle error responses
        if result.get("success") is False:
            frappe.logger("faco.billing").warning(
                f"initiate_plan_upgrade rejected for plan {plan}: " f"{result.get('message', '(no message)')}"
            )
            return {"error": result.get("message", "Plan change failed")}

        return {"error": result.get("error", "Failed to initiate plan change")}

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error initiating plan change: {e}")
        return {"error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error initiating plan change: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["POST"])
def reauthorize_mandate(
    billing_name: str | None = None,
    payment_method: str | None = None,
):
    """Open a fresh recurring-mandate authorization on the customer's
    current plan. Used when ``upgrade_plan`` would reject the request as
    a same-plan no-op but the saved Razorpay token is exhausted (the
    renewal cron flagged ``needs_mandate_reauth`` because the projected
    debit exceeded the per-debit cap).

    Returns the same Razorpay-checkout payload shape as
    ``initiate_plan_upgrade`` so the SPA reuses its existing widget-
    launching code path.
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import (
            ARError,
            get_fac_cloud_client,
        )

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        if payment_method and payment_method not in ("upi", "card"):
            return {"error": "Invalid payment_method. Use 'upi' or 'card'"}

        frappe.logger("faco.billing").info(f"reauthorize_mandate: method={payment_method or 'default'}")

        result = client.reauthorize_mandate(
            billing_name=billing_name,
            payment_method=payment_method,
        )

        if result.get("razorpay_order_id"):
            return {
                "success": True,
                "gateway": "razorpay",
                "session_id": result.get("session_id"),
                "razorpay_key": result.get("razorpay_key"),
                "razorpay_order_id": result.get("razorpay_order_id"),
                "amount": result.get("amount"),
                "currency": result.get("currency"),
                "customer_id": result.get("customer_id"),
                "prefill": result.get("prefill", {}),
            }

        # Stripe portal-URL response
        if result.get("portal_url") or result.get("checkout_url"):
            return {
                "success": True,
                "portal_url": result.get("portal_url"),
                "checkout_url": result.get("checkout_url"),
                "gateway": result.get("gateway", "stripe"),
            }

        if result.get("success") is False:
            return {"error": result.get("message", "Re-authorization failed")}

        return {"error": result.get("error", "Failed to start re-authorization")}

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error reauthorizing mandate: {e}")
        return {"error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error reauthorizing mandate: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["POST"])
def verify_payment(session_id: str | None = None):
    """
    Verify payment completion after checkout redirect.

    Called when user returns from payment gateway. Verifies the payment
    status with AR and updates local subscription data.

    Args:
            session_id: Checkout session ID (optional, AR may use tenant context)

    Returns:
            dict: {
                    "success": bool,
                    "subscription": {...},
                    "message": str
            }
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import ARError, get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        # Verify checkout with AR
        result = client.verify_checkout(session_id)

        if result.get("success"):
            # Refresh quota cache from AR for accurate plan/quota/used
            _refresh_subscription_cache()
            summary = _quota_summary()

            return {
                "success": True,
                "subscription": summary,
                "message": result.get("message") or f"Successfully upgraded to {summary['plan']} plan!",
                "invoice": result.get("invoice"),
            }

        return {
            "success": False,
            "error": result.get("error", "Payment verification failed"),
            "status": result.get("status", "unknown"),
        }

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error verifying payment: {e}")
        return {"error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error verifying payment: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["POST"])
def verify_razorpay_payment(razorpay_payment_id: str, razorpay_subscription_id: str, razorpay_signature: str):
    """
    Verify Razorpay payment from embedded checkout widget.

    Called after user completes payment in the Razorpay widget.
    Proxies to AR verify_razorpay_payment API.

    Args:
            razorpay_payment_id: Payment ID from Razorpay widget response
            razorpay_subscription_id: Subscription ID from Razorpay widget response
            razorpay_signature: Signature from Razorpay widget response

    Returns:
            dict: {
                    "success": bool,
                    "message": str,
                    "subscription_status": str,
                    "plan": str
            }
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import ARError, get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        result = client.verify_razorpay_payment(
            razorpay_payment_id, razorpay_subscription_id, razorpay_signature
        )

        if result.get("success"):
            # Sync subscription status
            sync_subscription_status()

            return {
                "success": True,
                "message": result.get("message", "Payment verified successfully"),
                "subscription_status": result.get("subscription_status"),
                "plan": result.get("plan"),
            }

        return {"error": result.get("error", "Failed to verify payment")}

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error verifying Razorpay payment: {e}")
        return {"error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error verifying Razorpay payment: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["POST"])
def verify_razorpay_credit_payment(razorpay_payment_id: str, razorpay_order_id: str, razorpay_signature: str):
    """
    Verify Razorpay payment for a credit purchase.

    Called after user completes a credit purchase in the Razorpay widget.
    Proxies to AR verify_razorpay_credit_payment API which verifies the
    signature and adds credits to the tenant's balance.

    Args:
            razorpay_payment_id: Payment ID from Razorpay widget response
            razorpay_order_id: Order ID from Razorpay widget response
            razorpay_signature: Signature from Razorpay widget response

    Returns:
            dict: {"success": bool, "balance": int, "credits_added": int, "message": str}
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import ARError, get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        result = client.verify_razorpay_credit_payment(
            razorpay_payment_id, razorpay_order_id, razorpay_signature
        )

        if result.get("success"):
            return {
                "success": True,
                "balance": result.get("balance"),
                "credits_added": result.get("credits_added", result.get("tokens_added")),
                "message": result.get("message", "Credits added successfully"),
            }

        return {"error": result.get("error", "Failed to verify credit payment")}

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error verifying Razorpay credit payment: {e}")
        return {"error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error verifying Razorpay credit payment: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}
