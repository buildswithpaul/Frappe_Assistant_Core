# Frappe Assistant Core - Pricing & Promo Validation API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Tax-inclusive plan-pricing preview + promo/referral code validation."""

from __future__ import annotations

import frappe
from frappe import _

from .._helpers import (
    ARBillingUnavailableError,
    _billing_unavailable_response,
    _log,
    _safe_error,
)


@frappe.whitelist(methods=["GET"])
def preview_plan_pricing(plan: str, billing_cycle: str = "monthly"):
    """Return the tax-inclusive pricing breakdown for a plan.

    Used by the confirm modal to show "subtotal + GST = total due today"
    before opening the Razorpay widget. Reads the tenant's billing
    Address state to decide CGST+SGST vs IGST vs zero-tax.

    Returns:
            {
                    "success": True,
                    "pricing": {
                            "base": float, "tax": float, "total": float,
                            "currency": "INR"|"USD"|...,
                            "tax_rate_percent": float,
                            "components": [{"name", "rate_percent", "amount"}, ...]
                    }
            }
    """
    try:
        from frappe_assistant_core.chat.fac_cloud_client import (
            ARError,
            get_fac_cloud_client,
        )

        client = get_fac_cloud_client()
        if not client:
            return {"success": False, "error": _("This site isn't registered with FAC Cloud.")}

        pricing = client.preview_plan_pricing(plan, billing_cycle)
        if pricing is None:
            return {"success": False, "error": _("Couldn't compute pricing. Please try again.")}
        return {"success": True, "pricing": pricing}
    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error previewing pricing: {e}")
        return {"success": False, "error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error previewing pricing: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["GET"])
def validate_promo_code(promo_code: str | None = None, plan: str | None = None):
    """
    Validate a promotional or referral code for the current tenant.

    Args:
            promo_code: The promo/referral code to validate
            plan: Optional plan name to check code applicability against

    Returns:
            dict: {"valid": True, "discount_type": str, "discount_value": float, ...}
                  or {"valid": False, "error": str}
    """
    if not promo_code:
        return {"valid": False, "error": "Please enter a promo code"}

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"valid": False, "error": _("This site isn't registered with FAC Cloud.")}

        result = client.validate_promo_code(promo_code.upper().strip(), plan=plan)
        return result or {"valid": False, "error": "Unable to validate promo code"}
    except Exception as e:
        _log(title="FACO Promo", message=f"Promo validation error: {e!s}")
        return {"valid": False, "error": "Unable to validate promo code"}
