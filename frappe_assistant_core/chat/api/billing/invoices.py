# Frappe Assistant Core - Invoice Streaming API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""GST invoice PDF download endpoint (proxies bytes from AR via SDK)."""

from __future__ import annotations

import frappe
from frappe import _

from .._helpers import (
    ARBillingUnavailableError,
    _billing_unavailable_response,
    _log,
    _require_system_manager,
    _safe_error,
)


@frappe.whitelist(methods=["GET"])
def download_invoice_pdf(ar_invoice_name: str):
    """Stream the GST invoice PDF for an AR Invoice to the browser.

    The SPA calls this via `window.open(...)` — the session cookie is
    already attached (same-origin), so this endpoint just proxies the
    SDK call and hands the bytes to Frappe's file-download response
    shape. The AR backend enforces tenant ownership before returning.
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

        content_bytes, content_type, filename = client.download_invoice_pdf(ar_invoice_name)

        frappe.local.response.filename = filename or f"{ar_invoice_name}.pdf"
        frappe.local.response.filecontent = content_bytes
        frappe.local.response.type = "download"
    except ARBillingUnavailableError:
        return _billing_unavailable_response()
    except ARError as e:
        _log(
            title="FACO Billing Error",
            message=f"AR error downloading invoice PDF {ar_invoice_name}: {e}",
        )
        return {"success": False, "error": _safe_error(e, "FACO Billing Error")}
    except Exception as e:
        _log(
            title="FACO Billing Error",
            message=f"Error downloading invoice PDF {ar_invoice_name}: {e!s}",
        )
        return {"success": False, "error": _safe_error(e, "FACO Billing Error")}
