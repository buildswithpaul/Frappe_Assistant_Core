# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""FAC Chat home: the cached "Needs you" signals endpoint."""

import json
import time

import frappe
from frappe import _
from frappe.utils import cint, sbool

from ..doctype.fac_chat_user_preferences.fac_chat_user_preferences import FACChatUserPreferences
from ..home_preferences import HOME_SIGNALS_CACHE_KEY, load_home_preferences, parse_hidden_signals
from ..home_signals import CLIENT_SIDE_SIGNAL_ID, applicable_signals, compute_home_signals

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


def _flag(value: bool | int | str) -> int:
    """0/1 from a bool, an int, or the "true"/"false"/"0"/"1" strings HTTP delivers."""
    return cint(sbool(value))


def _preferences_payload(user: str) -> dict:
    prefs = load_home_preferences(user)
    signals = [{"id": signal.id, "label": str(signal.label)} for signal in applicable_signals(user)]
    signals.append({"id": CLIENT_SIDE_SIGNAL_ID, "label": _("Failed workflows")})
    return {
        "show_needs_you": prefs["show_needs_you"],
        "needs_you_count": prefs["needs_you_count"],
        "hidden_signals": prefs["hidden_signals"],
        "show_suggested_prompts": prefs["show_suggested_prompts"],
        "show_personalized_suggestions": prefs["show_personalized_suggestions"],
        "signals": signals,
    }


@frappe.whitelist(methods=["GET"])
def get_home_preferences() -> dict:
    """The user's home-page preferences plus the signals they may choose to hide."""
    return _preferences_payload(frappe.session.user)


@frappe.whitelist(methods=["POST"])
def update_home_preferences(
    show_needs_you: bool | None = None,
    needs_you_count: int | None = None,
    hidden_signals: list | str | None = None,
    show_suggested_prompts: bool | None = None,
    show_personalized_suggestions: bool | None = None,
) -> dict:
    """Change the provided home preferences only; returns the same shape as ``get_home_preferences``.

    ``hidden_signals`` replaces the hidden list and may be a list or a JSON string.
    """
    user = frappe.session.user
    changes: dict = {}
    if show_needs_you is not None:
        changes["show_needs_you"] = _flag(show_needs_you)
    if needs_you_count is not None:
        changes["needs_you_count"] = cint(needs_you_count)
    if hidden_signals is not None:
        changes["hidden_home_signals"] = (
            hidden_signals if isinstance(hidden_signals, str) else json.dumps(hidden_signals)
        )
    if show_suggested_prompts is not None:
        changes["show_suggested_prompts"] = _flag(show_suggested_prompts)
    if show_personalized_suggestions is not None:
        changes["show_personalized_suggestions"] = _flag(show_personalized_suggestions)

    if changes:
        prefs = FACChatUserPreferences.get_or_create_preferences(user)
        prefs.update(changes)
        prefs.save(ignore_permissions=True)
    return _preferences_payload(user)


@frappe.whitelist(methods=["POST"])
def hide_home_signal(signal_id: str) -> dict:
    """Add ``signal_id`` to the user's hidden home signals (idempotent)."""
    user = frappe.session.user
    prefs = FACChatUserPreferences.get_or_create_preferences(user)
    hidden = [*parse_hidden_signals(prefs.hidden_home_signals), signal_id]
    prefs.hidden_home_signals = json.dumps(hidden)
    prefs.save(ignore_permissions=True)
    return {"hidden_signals": parse_hidden_signals(prefs.hidden_home_signals)}
