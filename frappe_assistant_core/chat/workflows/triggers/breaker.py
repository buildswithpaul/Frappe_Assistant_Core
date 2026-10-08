# Frappe Assistant Core - Powered by FAC Cloud
# Copyright (C) 2026 Paul Clinton
# AGPLv3

"""Trigger loop circuit breaker.

The static DocType blocklist cannot see the loop that actually happens in
production: an agent node calls ``update_document`` on the customer's own MCP
server, that ends in a bare ``doc.save()``, and the save re-enters
``on_update``. So the first workflow anyone builds — "on Sales Order update,
summarize and write it back" — bills a full run per lap until a rate limit
stops it. Each (trigger, document) pair is bounded by two windows: a burst
window that stops a tight save loop, and an hourly window that stops a slow
one which stays under the burst limit.

Counting is a raw Redis ``INCR`` on a site-namespaced key, so concurrent
workers share one counter. It deliberately does not go through
``set_value``/``get_value``: those pickle their payload and read-modify-write
would lose laps under concurrency.

Limits are per-site overridable in ``site_config.json``:
``fac_trigger_breaker_max_fires`` and ``fac_trigger_breaker_window_seconds``
for the burst window, and ``fac_trigger_breaker_max_fires_per_hour`` for the
hourly one. Setting a limit to 0 disables only its own window.
"""

from typing import NamedTuple

import frappe
from frappe import _

DEFAULT_MAX_FIRES = 5
DEFAULT_WINDOW_SECONDS = 60
DEFAULT_MAX_FIRES_PER_HOUR = 20
HOUR_SECONDS = 3600

_COUNT_KEY = "fac_trigger_breaker"
_REPORTED_KEY = "fac_trigger_breaker_reported"
_HOURLY_COUNT_KEY = "fac_trigger_breaker_hourly"
_HOURLY_REPORTED_KEY = "fac_trigger_breaker_hourly_reported"


class BreakerDecision(NamedTuple):
    """``reason`` is set only on the fire that should write a log row."""

    allowed: bool
    reason: str | None


def check_dispatch(trigger_id: str, doctype: str, docname: str) -> BreakerDecision:
    """Count this fire and decide whether it may be dispatched.

    Two windows per (trigger, document): a burst limit (default 5 per 60s)
    stops a tight save loop, and an hourly limit (default 20) stops a slow one
    that stays under the burst limit.
    """
    burst = _window_decision(
        _count_key(trigger_id, doctype, docname),
        _reported_key(trigger_id, doctype, docname),
        _config("fac_trigger_breaker_max_fires", DEFAULT_MAX_FIRES),
        _config("fac_trigger_breaker_window_seconds", DEFAULT_WINDOW_SECONDS),
        doctype,
        docname,
    )
    if not burst.allowed:
        return burst

    return _window_decision(
        f"{_HOURLY_COUNT_KEY}:{trigger_id}:{doctype}:{docname}",
        f"{_HOURLY_REPORTED_KEY}:{trigger_id}:{doctype}:{docname}",
        _config("fac_trigger_breaker_max_fires_per_hour", DEFAULT_MAX_FIRES_PER_HOUR),
        HOUR_SECONDS,
        doctype,
        docname,
    )


def _window_decision(
    count_key: str, reported_key: str, max_fires: int, window: int, doctype: str, docname: str
) -> BreakerDecision:
    """Count one fire in one window; refuse past ``max_fires``. 0 disables the window."""
    if max_fires <= 0 or window <= 0:
        return BreakerDecision(True, None)

    count = _bump(count_key, window)
    if count is None or count <= max_fires:
        # `None` means Redis is unreachable. Fail open: a cache outage must not
        # silently stop every customer trigger on the site.
        return BreakerDecision(True, None)

    # Report once per window. A runaway loop must not flood the very log it is
    # meant to make visible.
    reason = None
    if claim_once(reported_key, window):
        reason = _(
            "Loop guard: more than {0} fires for {1} {2} within {3}s. Further fires are "
            "refused until the window clears. Check whether this workflow writes back to "
            "the document that triggers it."
        ).format(max_fires, doctype, docname, window)
    return BreakerDecision(False, reason)


def claim_once(key: str, ttl_seconds: int) -> bool:
    """True for the first caller within ``ttl_seconds``. Samples noisy log rows.

    Fails closed — when Redis is unreachable nothing is written, because the
    alternative is an unsampled row per doc save.
    """
    # Raw set, not set_value: nx is the whole point — the claim has to be
    # atomic, and set_value cannot express set-if-absent. make_key supplies the
    # site prefix, so this stays per-site despite the raw call.
    try:
        return bool(
            frappe.cache().set(_namespaced(key), b"1", ex=ttl_seconds, nx=True)  # nosemgrep
        )
    except Exception:
        return False


def reset(trigger_id: str, doctype: str, docname: str) -> None:
    """Clear both windows' counters for one (trigger, document) pair."""
    suffix = f"{trigger_id}:{doctype}:{docname}"
    try:
        frappe.cache().delete(
            _namespaced(_count_key(trigger_id, doctype, docname)),
            _namespaced(_reported_key(trigger_id, doctype, docname)),
            _namespaced(f"{_HOURLY_COUNT_KEY}:{suffix}"),
            _namespaced(f"{_HOURLY_REPORTED_KEY}:{suffix}"),
        )
    except Exception:
        pass


def _namespaced(key: str) -> str:
    """Site-prefixed Redis key, so one site's counters never see another's."""
    return frappe.cache().make_key(key)


def _count_key(trigger_id: str, doctype: str, docname: str) -> str:
    return f"{_COUNT_KEY}:{trigger_id}:{doctype}:{docname}"


def _reported_key(trigger_id: str, doctype: str, docname: str) -> str:
    return f"{_REPORTED_KEY}:{trigger_id}:{doctype}:{docname}"


def _bump(key: str, ttl_seconds: int) -> int | None:
    """Atomically increment ``key``, setting its TTL on first use."""
    try:
        cache = frappe.cache()
        redis_key = _namespaced(key)
        count = int(cache.incrby(redis_key, 1))
        if count == 1:
            cache.expire(redis_key, ttl_seconds)
        return count
    except Exception:
        return None


def _config(key: str, default: int) -> int:
    try:
        return int(frappe.conf.get(key, default))
    except (TypeError, ValueError):
        return default
