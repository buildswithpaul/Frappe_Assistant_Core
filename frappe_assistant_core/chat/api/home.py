# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""FAC Chat home: the cached "Needs you" signals endpoint."""

import time

import frappe

from ..home_signals import compute_home_signals

HOME_SIGNALS_CACHE_KEY = "fac_home_signals"
HOME_SIGNALS_MAX_AGE = 600


@frappe.whitelist(methods=["GET"])
def get_home_signals() -> dict:
    """Signals for the current user, served from cache while younger than 10 minutes.

    No TTL on the cache entry (Frappe v15 TTL'd keys miss for the rest of a
    request); freshness is judged from ``computed_at``.
    """
    user = frappe.session.user
    cached = frappe.cache.hget(HOME_SIGNALS_CACHE_KEY, user)
    if cached and time.time() - cached["computed_at"] < HOME_SIGNALS_MAX_AGE:
        return cached["payload"]

    payload = compute_home_signals(user)
    frappe.cache.hset(HOME_SIGNALS_CACHE_KEY, user, {"computed_at": time.time(), "payload": payload})
    return payload
