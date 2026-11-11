"""Circuit breaker for short, non-streaming calls from FAC to AR.

Opens after FAILURE_THRESHOLD consecutive transport failures and stays open for OPEN_SECONDS,
during which callers skip AR. When the open key's TTL lapses, the next call is the probe: a
success closes the breaker, a failure reopens it. Chat streams never use the breaker.
"""

from collections.abc import Callable
from typing import TypeVar

import frappe
from assistant_runtime_sdk import ARAPIError, ARConnectionError, ARTimeoutError

T = TypeVar("T")

FAILURE_THRESHOLD = 3
OPEN_SECONDS = 60
FAILURE_WINDOW_SECONDS = 600  # isolated failures this far apart never add up to an open

_FAILURES_KEY = "faco_ar_breaker_failures"
_OPEN_KEY = "faco_ar_breaker_open"
_WAS_OPEN_KEY = "faco_ar_breaker_was_open"


class BreakerOpen(Exception):
    """AR calls are being skipped while the breaker is open."""


def _key(name: str) -> str:
    return frappe.cache.make_key(name)


def _log():
    return frappe.logger("faco.ar_breaker")


def is_transport_failure(exc: BaseException) -> bool:
    """A timeout, a refused connection or a 5xx answer. Other 4xx answers are not outages."""
    if isinstance(exc, ARTimeoutError | ARConnectionError):
        return True
    return isinstance(exc, ARAPIError) and (getattr(exc, "status_code", None) or 0) >= 500


def is_transport_marker(result: dict) -> bool:
    """True when an SDK ``_ar_unreachable`` marker stands for a timeout or a refused connection.

    The SDK builds the marker from ``str(exception)`` for any exception, 401 and 429 included,
    so only its own timeout and connection texts count.
    """
    if not result.get("_ar_unreachable"):
        return False
    error = str(result.get("error") or "")
    return error.startswith("Failed to connect to") or (
        error.startswith("Request to") and error.endswith("timed out")
    )


def is_open() -> bool:
    # exists() applies make_key itself
    return bool(frappe.cache.exists(_OPEN_KEY))


def record_success() -> None:
    frappe.cache.delete(_key(_FAILURES_KEY))
    if frappe.cache.delete(_key(_WAS_OPEN_KEY)):
        _log().info("AR breaker closed")


def record_failure() -> None:
    failures = frappe.cache.incr(_key(_FAILURES_KEY))
    frappe.cache.expire(_key(_FAILURES_KEY), FAILURE_WINDOW_SECONDS)
    if failures < FAILURE_THRESHOLD:
        return
    # A failed half-open probe lands here with the open key already lapsed: reopen quietly.
    frappe.cache.set_value(_OPEN_KEY, 1, expires_in_sec=OPEN_SECONDS)
    first_open = frappe.cache.setnx(_key(_WAS_OPEN_KEY), 1)
    if first_open:
        _log().warning(f"AR breaker opened after {failures} consecutive transport failures")


def call(fn: Callable[[], T]) -> T:
    if is_open():
        raise BreakerOpen
    try:
        result = fn()
    except Exception as exc:
        if is_transport_failure(exc):
            record_failure()
        raise
    record_success()
    return result
