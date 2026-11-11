"""Circuit breaker for short, non-streaming calls from FAC to AR.

Opens after FAILURE_THRESHOLD consecutive transport failures and stays open for OPEN_SECONDS,
during which callers skip AR. When the open key's TTL lapses, the next call is the probe: a
success closes the breaker, a failure reopens it. Chat streams never use the breaker.
"""

from collections.abc import Callable
from typing import TypeVar

import frappe
from assistant_runtime_sdk import ARConnectionError, ARTimeoutError

T = TypeVar("T")

FAILURE_THRESHOLD = 3
OPEN_SECONDS = 60

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
    return isinstance(exc, ARTimeoutError | ARConnectionError)


def is_open() -> bool:
    # exists() applies make_key itself
    return bool(frappe.cache.exists(_OPEN_KEY))


def record_success() -> None:
    frappe.cache.delete(_key(_FAILURES_KEY))
    if frappe.cache.exists(_WAS_OPEN_KEY):
        frappe.cache.delete_value(_WAS_OPEN_KEY)
        _log().info("AR breaker closed")


def record_failure() -> None:
    failures = frappe.cache.incr(_key(_FAILURES_KEY))
    if failures < FAILURE_THRESHOLD:
        return
    # A failed half-open probe lands here with the open key already lapsed: reopen quietly.
    first_open = not frappe.cache.exists(_WAS_OPEN_KEY)
    frappe.cache.set_value(_OPEN_KEY, 1, expires_in_sec=OPEN_SECONDS)
    if first_open:
        frappe.cache.set_value(_WAS_OPEN_KEY, 1)
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
