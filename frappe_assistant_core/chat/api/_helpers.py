# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Shared utilities used across FACO API modules."""

import json
import re

import frappe
from frappe import _

try:
    from frappe_assistant_core.chat.fac_cloud_client import (
        ARAPIError,
        ARAuthenticationError,
        ARBillingUnavailableError,
        ARConnectionError,
        ARError,
        ARRateLimitError,
        ARTimeoutError,
    )
except ImportError:
    # fac_cloud_client will be available after Task 3.8 migration. Stubs prevent import
    # failures during the transition period.
    class _ARStubBase(Exception):
        pass

    ARError = _ARStubBase
    ARAPIError = _ARStubBase
    ARAuthenticationError = _ARStubBase
    ARBillingUnavailableError = _ARStubBase
    ARConnectionError = _ARStubBase
    ARRateLimitError = _ARStubBase
    ARTimeoutError = _ARStubBase


def _require_system_manager():
    """Check if current user is System Manager. Throws if not."""
    if "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw(_("Only System Managers can access billing features"), frappe.PermissionError)


def _billing_unavailable_response():
    """Standard response when billing features are not available on the AR server."""
    return {"billing_available": False, "error": _("Billing is not available on this server.")}


def _not_registered_error() -> str:
    """Friendly message when FACO isn't registered with Assistant Runtime."""
    return _(
        "This site isn't registered with FAC Cloud yet. Please register from FAC Chat Settings and try again."
    )


def _marketplace_enabled() -> bool:
    """Return True if the AR backend has the marketplace companion app installed.

    Reads ``FACO Settings.cached_capabilities`` (populated by ``initialize_spa``
    every 5 minutes). Defaults to False on missing/corrupted cache so callers
    skip marketplace endpoints rather than emitting ``ModuleNotFoundError`` rows.
    """
    try:
        cached = frappe.db.get_single_value("FAC Chat Settings", "cached_capabilities")
        if not cached:
            return False
        caps = json.loads(cached) if isinstance(cached, str) else cached
        return bool(caps.get("marketplace", {}).get("marketplace_enabled", False))
    except Exception:
        return False


# The Error Log `title` column is capped at 140 chars by Frappe. Keep a safe
# margin so our titles never trip CharacterLengthExceededError.
_ERROR_LOG_TITLE_MAX = 120

# Stripped from SDK error messages before we show them to users. Frappe wraps
# dynamic values in <strong> tags for its own UI — that's noise in a toast.
_STRONG_TAG_RE = re.compile(r"</?strong>", re.IGNORECASE)

# Cloud-service internals that must never land in a tenant Error Log.
_UPSTREAM_TABLE_RE = re.compile(r"`tabAR [^`]+`")
_UPSTREAM_TABLE_BARE_RE = re.compile(r"\btabAR [A-Za-z0-9 ]+")
_UPSTREAM_MODULE_RE = re.compile(r"assistant_runtime(?:_[a-z]+)?(?:\.[A-Za-z0-9_.]+)?")
_RECORD_CHANGED_RE = re.compile(
    r"Record has changed since last read in table '[^']+'",
    re.IGNORECASE,
)


def _strip_noise(text: str) -> str:
    """Remove Frappe-internal HTML markup that leaks through server_messages."""
    if not text:
        return ""
    return _STRONG_TAG_RE.sub("", text).strip()


def _redact_upstream_internals(text: str) -> str:
    """Strip cloud-service table names, modules, and SQL from log text.

    Tenant Error Log is visible to the site's System Managers. Raw exceptions
    from the assistant service (``tabAR …``, MariaDB 1020, module paths) must
    not appear there.
    """
    if not text:
        return ""
    out = _UPSTREAM_TABLE_RE.sub("[internal table]", text)
    out = _UPSTREAM_TABLE_BARE_RE.sub("[internal table]", out)
    out = _UPSTREAM_MODULE_RE.sub("[service]", out)
    out = _RECORD_CHANGED_RE.sub("Record has changed since last read", out)
    out = out.replace("AR stream_error", "FAC Chat stream error")
    return out


def _summarize_stream_error_for_log(error_code: str | None) -> str:
    """Error Log body for a stream failure — code only, never the raw exception."""
    code = error_code or "UNKNOWN"
    return (
        f"error_code: {code}\n"
        "The assistant service reported a failure. "
        "Technical detail is not stored on this site."
    )


def _log(title: str, detail: str | None = None, *, message: str | None = None) -> None:
    """Write a server-side Error Log entry with correct title/message order.

    Frappe's signature is `log_error(title, message, ...)` — passing a long
    dynamic f-string as the first positional trips the 140-char Title cap and
    raises `CharacterLengthExceededError`. Always pass the short identifier
    as title and the variable detail as message.

    `message=` is accepted as an alias for `detail=` to match the kwarg name
    older callers used; either works. When both are passed, `detail` wins.

    When called from inside an `except` block, the active exception's
    traceback is appended automatically so callers don't have to remember
    to include it. This makes shallow legacy callers traceback-rich without
    a 50-site rewrite.
    """
    import sys

    try:
        safe_title = _redact_upstream_internals(title or "FAC Chat Error")[:_ERROR_LOG_TITLE_MAX]
        message = (detail if detail is not None else message) or ""
        # If we're inside an `except` block, sys.exc_info() returns the
        # active triple. Append the traceback unless the caller already
        # included one (avoid duplicates from `_handle_ar_error`).
        exc_type, exc_val, _tb = sys.exc_info()
        if exc_val is not None and "Traceback" not in message:
            message = f"{message}\n\n{frappe.get_traceback(with_context=False)}"
        message = _redact_upstream_internals(message)
        frappe.log_error(title=safe_title, message=message)
    except Exception:
        # log_error itself can fail (read-only replica, DB gone, nested
        # transaction). Don't mask the original error — but emit a
        # stderr-level breadcrumb so we know the log persistence failed.
        try:
            frappe.logger("faco").exception(f"FACO _log: failed to persist Error Log (title={title!r})")
        except Exception:
            pass


def _user_message_for_ar_error(e: Exception) -> str:
    """Translate an SDK exception into a user-friendly sentence.

    Never includes technical detail (URLs, tenant ids, stack info, SQL). Those
    go to the Error Log via `_log`; the sentence returned here is safe to show
    in a toast on an admin UI.
    """
    if isinstance(e, ARBillingUnavailableError):
        return _("Billing features aren't available on this server yet.")
    if isinstance(e, ARAuthenticationError):
        return _(
            "This site isn't authenticated with FAC Cloud. "
            "Please re-register from FAC Chat Settings and try again."
        )
    if isinstance(e, ARRateLimitError):
        return _("Too many requests right now. Please wait a few seconds and try again.")
    if isinstance(e, ARTimeoutError | ARConnectionError):
        return _(
            "Couldn't reach the billing service. Please check your internet " "connection and try again."
        )
    if isinstance(e, ARAPIError):
        status = getattr(e, "status_code", None)
        if status and 400 <= status < 500:
            # 4xx: usually a validation or permission problem. AR's error text
            # is typically end-user-appropriate (e.g. "GSTIN is invalid").
            return _strip_noise(str(e)) or _("The billing service rejected the request.")
        if status and 500 <= status < 600:
            return _("Billing service is having trouble. Please try again in a moment.")
        return _("Couldn't complete the billing request. Please try again.")
    # Generic / unknown SDK error
    return _("Something went wrong with billing. Please try again or contact support.")


def _handle_ar_error(context: str, e: Exception) -> str:
    """Log the error server-side with full detail and return a friendly string.

    Usage:
            try:
                    client.preview_plan_pricing(...)
            except ARError as e:
                    return {"success": False, "error": _handle_ar_error("preview pricing", e)}

    `context` becomes the Error Log title (short, static, searchable).
    `e` provides the server-side detail (stored in the message field, unbounded).
    """
    detail_parts = [
        f"context: {context}",
        f"type: {type(e).__name__}",
        f"error: {e}",
    ]
    if isinstance(e, ARAPIError):
        detail_parts.append(f"status_code: {getattr(e, 'status_code', None)}")
    detail_parts.append(frappe.get_traceback())
    _log(title=f"FACO: {context}", detail="\n".join(detail_parts))
    return _user_message_for_ar_error(e)


def _handle_generic_error(context: str, e: Exception, *, user_message: str | None = None) -> str:
    """Log + translate for exceptions that aren't from the SDK.

    Like `_handle_ar_error` but without AR-specific message mapping. Use for
    local Frappe errors (DB, validation, etc.). Framework-level ValidationError
    and PermissionError messages are already user-written, so we pass those
    through verbatim.
    """
    detail = f"context: {context}\ntype: {type(e).__name__}\nerror: {e}\n{frappe.get_traceback()}"
    _log(title=f"FACO: {context}", detail=detail)

    # Framework errors are safe to surface as-is — Frappe authors write them
    # for end users (e.g. "Mandatory fields required: Billing Email").
    if isinstance(e, frappe.ValidationError | frappe.PermissionError):
        return _strip_noise(str(e))
    return user_message or _("Something went wrong. Please try again or contact support.")


def _safe_error(e: Exception, log_title: str, *, default: str | None = None) -> str:
    """Backwards-compatible wrapper around the new helpers.

    Preserved so existing callers keep working; new code should call
    `_handle_ar_error` / `_handle_generic_error` directly.
    """
    if isinstance(e, ARError):
        return _handle_ar_error(log_title, e)
    return _handle_generic_error(log_title, e, user_message=default)
