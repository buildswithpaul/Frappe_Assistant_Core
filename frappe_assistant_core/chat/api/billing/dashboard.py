# Frappe Assistant Core - Billing Dashboard & Plans API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Read-only dashboard, plan listing, gateway listing endpoints."""

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
    _build_dashboard_response,
    _infer_gateway_from_plans,
)


@frappe.whitelist(methods=["GET"])
def get_billing_dashboard():
    """
    Get comprehensive billing dashboard data.

    Combines subscription info, usage data, and quota status.
    Admin only - regular users should see "Contact administrator".

    Returns:
            dict: {
                    "subscription": {...},
                    "usage": {...},
                    "quota": {...},
                    "billing_cycle": {...}
            }
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import ARError, get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        # Get usage dashboard from AR
        try:
            usage_data = client.get_usage_dashboard()
        except ARError as e:
            # Log but continue with local data if AR is unreachable
            _log(title="FACO Billing Error", message=f"AR error getting usage dashboard: {e}")
            usage_data = {}

        settings = frappe.get_single("FAC Chat Settings")
        return _build_dashboard_response(usage_data, settings)

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error getting billing dashboard: {e}")
        return {"error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error getting billing dashboard: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["GET"])
def get_plan_options():
    """
    Get available plans for upgrade modal.

    Returns plan comparison data from AR including pricing,
    features, and quota limits.

    Returns:
            dict: {
                    "plans": [...],
                    "current_plan": str,
                    "recommended_gateway": str
            }
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import ARError, get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        # Get plan comparison from AR
        plans = client.get_plan_comparison()

        # Get recommended gateway
        try:
            gateway = client.get_recommended_gateway()
        except ARError:
            # Infer from plan pricing keys instead of hardcoding stripe/USD
            gateway = _infer_gateway_from_plans(plans.get("plans", []))

        from frappe_assistant_core.chat.quota_cache import get_field

        return {
            "success": True,
            "plans": plans.get("plans", []),
            "current_plan": get_field("plan", "Free"),
            "recommended_gateway": gateway.get("gateway", "stripe"),
            "currency": gateway.get("currency", "USD"),
        }

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error getting plan options: {e}")
        return {"error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error getting plan options: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["GET"])
def get_available_gateways():
    """
    Get available payment gateways with pricing for all plans.

    Admin only - returns gateway options with localized pricing.

    Returns:
            dict: {
                    "success": bool,
                    "gateways": [
                            {
                                    "name": "razorpay",
                                    "display_name": "Razorpay",
                                    "currency": "INR",
                                    "currency_symbol": "₹",
                                    "description": "UPI, Cards, NetBanking",
                                    "is_recommended": true,
                                    "plans": {
                                            "Starter": {"monthly": 1599, "annual": 15999},
                                            "Pro": {"monthly": 4199, "annual": 41999}
                                    }
                            },
                            ...
                    ],
                    "recommended_gateway": "razorpay",
                    "tenant_country": "IN"
            }
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import ARError, get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        # Get available gateways from AR
        result = client.get_available_gateways()

        if result.get("gateways"):
            return {
                "success": True,
                "gateways": result["gateways"],
                "recommended_gateway": result.get("recommended_gateway"),
                "tenant_country": result.get("tenant_country"),
            }

        return {"error": result.get("error", "Failed to get gateway options")}

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(title="FACO Billing Error", message=f"AR error getting gateways: {e}")
        return {"error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error getting gateways: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}
