"""Per-user cache of the credit status AR reports.

Aged in code, not by a Redis TTL: a TTL'd key reads back as a miss within the request that set
it on Frappe v15 (see chat/api/models.py). An entry past FRESH_SECONDS is kept so it can be served
stale when AR cannot answer.
"""

import time

import frappe

FRESH_SECONDS = 45


def _key(user: str) -> str:
    return f"faco_credit_status:{user}"


def get(user: str) -> dict | None:
    return frappe.cache.get_value(_key(user))


def is_fresh(entry: dict) -> bool:
    return time.time() - entry["at"] < FRESH_SECONDS


def put(user: str, value: dict) -> None:
    frappe.cache.set_value(_key(user), {"value": value, "at": time.time()})


def invalidate(user: str) -> None:
    """End freshness, keep the value so a later AR outage can still show the last figure."""
    entry = get(user)
    if entry:
        frappe.cache.set_value(_key(user), {"value": entry["value"], "at": 0})
