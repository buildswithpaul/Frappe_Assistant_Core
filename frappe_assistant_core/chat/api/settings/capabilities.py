# Frappe Assistant Core - Capabilities & Terms API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Read-only proxies that return AR's capability flags + terms."""

from __future__ import annotations

import frappe
from frappe import _

from ...cloud_url import get_fac_cloud_url
from .._helpers import _safe_error


@frappe.whitelist(methods=["GET"])
def get_capabilities() -> dict:
    """
    Get backend capabilities including billing availability.

    Returns server capabilities from Assistant Runtime.
    Caches billing_enabled in FACO Settings for quick access.

    Returns:
            dict: {
                    "billing_enabled": bool,
                    "available_gateways": list,
                    "version": str,
                    "features": {
                            "streaming": bool,
                            "mcp_servers": bool,
                            "rag": bool,
                            "memory": bool,
                            "billing": bool,
                            "web_search": bool
                    }
            }
    """
    from frappe_assistant_core.chat.fac_cloud_client import (
        get_capabilities as fetch_capabilities,
    )

    result = fetch_capabilities(get_fac_cloud_url())
    if result:
        # Cache billing_enabled in quota cache
        from frappe_assistant_core.chat.quota_cache import set_field

        billing_enabled = result.get("features", {}).get("billing", True)
        set_field("billing_enabled", billing_enabled)
        return result

    # Default: companion-app features off so UI hides them when AR is unreachable
    return {
        "billing_enabled": True,
        "available_gateways": [],
        "version": "unknown",
        "features": {
            "streaming": True,
            "mcp_servers": True,
            "rag": False,
            "memory": False,
            "billing": True,
            "workflows": False,
            "web_search": False,
        },
    }


@frappe.whitelist(methods=["GET"])
def get_ar_terms() -> dict:
    """
    Fetch Terms and Conditions from AR for display before registration.

    No authentication required - allows display before tenant is registered.

    Returns:
            dict: {
                    "version": "1.0",
                    "effective_date": "2025-01-01",
                    "terms_of_service": "<p>Terms of Service content...</p>",
                    "privacy_policy": "<p>Privacy Policy content...</p>",
                    "data_processing_agreement": "<p>DPA content...</p>",
                    "summary": "By using Assistant Runtime, you agree to our terms...",
                    "grace_period_days": 30
            }
    """
    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_terms

        result = get_terms(get_fac_cloud_url())

        if result:
            return result

        return {"error": _("Failed to fetch Terms and Conditions from FAC Cloud")}

    except Exception as e:
        frappe.log_error(title="FACO Terms Error", message=f"Error fetching AR terms: {e!s}")
        return {"error": _safe_error(e, "FACO Terms Error")}
