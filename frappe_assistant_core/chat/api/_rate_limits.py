# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Per-user and per-IP rate limiting for expensive FACO endpoints.

Frappe ships a ``frappe.rate_limiter.rate_limit`` decorator, but it keys
off ``frappe.form_dict.get(key)`` — inconvenient for session-user keying
and IP fallback. This module provides a thin wrapper that picks the
correct identity automatically.

See FACO-H12 (missing rate limits on expensive endpoints).
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

import frappe
from frappe import _


def _client_ip() -> str:
    """Best-effort client IP, falling back to ``unknown`` if unavailable."""
    ip = getattr(frappe.local, "request_ip", None)
    if ip:
        return ip
    req = getattr(frappe, "request", None)
    if req is not None:
        return req.headers.get("X-Forwarded-For", req.remote_addr or "unknown").split(",")[0].strip()
    return "unknown"


def session_user_or_ip() -> str:
    """Identity for user-keyed limits; falls back to IP for Guest sessions."""
    user = getattr(frappe.session, "user", None)
    if user and user != "Guest":
        return f"user:{user}"
    return f"ip:{_client_ip()}"


def ip_only() -> str:
    """Identity for IP-keyed limits (guest / pre-auth endpoints)."""
    return f"ip:{_client_ip()}"


def _too_many_requests_exc() -> type[Exception]:
    """Pick the most specific 429-ish exception Frappe exposes."""
    for attr in ("RateLimitExceededError", "TooManyRequestsError"):
        exc = getattr(frappe, attr, None)
        if isinstance(exc, type) and issubclass(exc, Exception):
            return exc
    return frappe.ValidationError


def rate_limit(identity_fn: Callable[[], str], limit: int, seconds: int) -> Callable:
    """Rate-limit a whitelisted endpoint by the identity returned from ``identity_fn``.

    Uses ``frappe.cache.incrby`` with a per-window TTL. Skips silently
    when there is no active request (e.g. during unit tests or internal
    calls) so the decorator is safe to apply unconditionally.

    Args:
            identity_fn: Callable returning a stable string identity
                    (``session_user_or_ip`` or ``ip_only``).
            limit: Maximum requests allowed per ``seconds`` window.
            seconds: Rolling window length in seconds.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not getattr(frappe, "request", None):
                return fn(*args, **kwargs)

            try:
                identity = identity_fn()
            except Exception:
                identity = f"ip:{_client_ip()}"

            cache_key = f"faco_rl:{fn.__module__}.{fn.__name__}:{identity}:{seconds}"

            try:
                count = frappe.cache.incrby(cache_key, 1)
                if count == 1:
                    # First hit in this window — arm TTL.
                    frappe.cache.expire(cache_key, seconds)
            except Exception:
                # Cache backend unreachable — fail open rather than
                # break the endpoint entirely. The next request retries.
                return fn(*args, **kwargs)

            if count > limit:
                frappe.throw(
                    _("Rate limit exceeded. Please try again in {0} seconds.").format(seconds),
                    _too_many_requests_exc(),
                )

            return fn(*args, **kwargs)

        return wrapper

    return decorator
