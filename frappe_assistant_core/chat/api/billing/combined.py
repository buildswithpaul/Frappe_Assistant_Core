# Frappe Assistant Core - Combined Billing-Page Data & Identity API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Single-call billing-page hydrator + tenant billing-identity proxy.

The combined endpoint replaces 7 sequential frontend HTTP calls
(9 AR round-trips) with one parallel-fanout call.
"""

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
from ..billing._internal import (
    _build_dashboard_response,
    _infer_gateway_from_plans,
)


@frappe.whitelist(methods=["GET"])
def get_billing_page_data(
    usage_history_days: int = 30, invoice_limit: int = 10, billing_history_limit: int = 20
):
    """
    Combined billing page data endpoint.

    Makes all AR billing calls in parallel using ThreadPoolExecutor,
    reducing 7 sequential frontend HTTP calls (9 AR round-trips) down
    to a single request with true parallel execution.

    Admin only.

    Args:
            usage_history_days: Days of usage history for chart (default 30)
            invoice_limit: Max invoices to return (default 10)
            billing_history_limit: Max billing history records (default 20)

    Returns:
            dict: Combined response with dashboard, plans, usage_history,
                    invoices, subscription_status, billing_history, credit_balance
    """
    _require_system_manager()

    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        results = {}

        def _call(name, fn, *args):
            """Execute a single AR call, catching exceptions per-task."""
            try:
                return name, fn(*args)
            except Exception:
                return name, None

        tasks = [
            ("dashboard", client.get_usage_dashboard),
            ("plans", client.get_plan_comparison),
            ("gateway", client.get_recommended_gateway),
            ("usage_history", client.get_usage_history, int(usage_history_days)),
            ("invoices", client.get_invoices, int(invoice_limit)),
            ("upcoming_invoice", client.get_upcoming_invoice),
            ("subscription_status", client.get_subscription_status),
            ("billing_history", client.get_billing_history, int(billing_history_limit)),
            ("credit_balance", client.get_credit_balance),
            # Needed for partner attribution ("Referred by …") in Billing → Settings.
            # The referral block lives under response["subscription"]["referral"].
            ("tenant_info", client.get_tenant_info),
        ]

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(_call, name, fn, *args) for name, fn, *args in tasks]
            for future in as_completed(futures):
                name, result = future.result()
                results[name] = result

        # Assemble response
        from frappe_assistant_core.chat.quota_cache import get_quota_snapshot

        settings = frappe.get_single("FAC Chat Settings")
        snap = get_quota_snapshot()
        gateway_data = results.get("gateway") or _infer_gateway_from_plans(
            (results.get("plans") or {}).get("plans", [])
        )

        return {
            "success": True,
            "dashboard": _build_dashboard_response(
                results.get("dashboard"), settings, tenant_info=results.get("tenant_info")
            ),
            "plans": {
                "success": True,
                "plans": (results.get("plans") or {}).get("plans", []),
                "current_plan": snap.get("plan", "Free"),
                "recommended_gateway": gateway_data.get("gateway", "stripe"),
                "currency": gateway_data.get("currency", "USD"),
            },
            "usage_history": {
                "success": True,
                "history": (results.get("usage_history") or {}).get("history", []),
                "total": (results.get("usage_history") or {}).get("total", 0),
                "average_daily": (results.get("usage_history") or {}).get("average_daily", 0),
            },
            "invoices": {
                "success": True,
                "invoices": (results.get("invoices") or {}).get("invoices", []),
                "upcoming_invoice": results.get("upcoming_invoice"),
            },
            "subscription_status": results.get("subscription_status") or {},
            "billing_history": results.get("billing_history") or {},
            "credit_balance": results.get("credit_balance"),
        }

    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except Exception as e:
        _log(title="FACO Billing Error", message=f"Error getting billing page data: {e!s}")
        return {"error": _safe_error(e, "FACO Billing Error")}


@frappe.whitelist(methods=["GET"])
def get_billing_details():
    """Proxy to AR billing_details.get_billing_details via the SDK.

    Returns the tenant's billing identity (email, phone, GSTIN, address)
    sourced from the ERPNext Customer + Address on the AR server.
    """
    _require_system_manager()

    from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

    client = get_fac_cloud_client()
    if not client:
        frappe.throw(_not_registered_error())

    try:
        return client.get_billing_details()
    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except Exception as e:
        # Raise a user-facing error so the SPA's try/catch sees the failure
        # instead of treating an error-shaped dict as success.
        frappe.throw(_safe_error(e, "FACO Billing Error"))


@frappe.whitelist(methods=["POST"])
def save_billing_details(
    billing_email: str,
    billing_country: str,
    billing_legal_name: str = "",
    gstin: str = "",
    billing_state: str = "",
    billing_city: str = "",
    billing_pincode: str = "",
    billing_address_line1: str = "",
    billing_address_line2: str = "",
    billing_phone: str = "",
):
    """Proxy to AR billing_details.save_billing_details via the SDK.

    Upserts the tenant's billing identity (ERPNext Customer + Address)
    on the AR server. Validation (GSTIN check-digit, required state for
    India, etc.) happens on AR. Errors bubble up as Frappe exceptions so
    the SPA's catch block fires — returning `{"error": ...}` as a 200
    response caused the UI to show "saved" on silent failures.
    """
    _require_system_manager()

    from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

    client = get_fac_cloud_client()
    if not client:
        frappe.throw(_not_registered_error())

    try:
        return client.save_billing_details(
            billing_email=billing_email,
            billing_country=billing_country,
            billing_legal_name=billing_legal_name,
            gstin=gstin,
            billing_state=billing_state,
            billing_city=billing_city,
            billing_pincode=billing_pincode,
            billing_address_line1=billing_address_line1,
            billing_address_line2=billing_address_line2,
            billing_phone=billing_phone,
        )
    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except Exception as e:
        # AR names the offending input on `frappe.local.response["billing_field"]`
        # and the SDK forwards the raw body as `ARAPIError.response_data`.
        # Re-stamp it on our own response so the form can attach the message to
        # that input instead of showing a banner the user has to map onto a
        # field themselves.
        field = (getattr(e, "response_data", None) or {}).get("billing_field")
        if field:
            frappe.local.response["billing_field"] = field
        frappe.throw(_safe_error(e, "FACO Billing Error"))
