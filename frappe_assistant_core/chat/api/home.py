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
from ..home_preferences import clamp_needs_you_count, load_home_preferences, parse_hidden_signals
from ..home_signals import CATALOGUE, applicable_signals, compute_home_signals

HOME_SIGNALS_CACHE_KEY = "fac_home_signals"
HOME_SIGNALS_MAX_AGE = 600
# Computed in the browser from the workflow list, so it has no catalogue entry but can be hidden.
CLIENT_SIDE_SIGNAL_ID = "failed_workflows"


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


def _invalidate_home_cache(user: str) -> None:
    frappe.cache.hdel(HOME_SIGNALS_CACHE_KEY, user)


def _hideable_signal_ids() -> set[str]:
    return {signal.id for signal in CATALOGUE} | {CLIENT_SIDE_SIGNAL_ID}


def _validated_signal_ids(raw: list | str) -> list[str]:
    """Deduplicated signal ids; anything outside the hideable set is rejected."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else []
        except ValueError:
            frappe.throw(_("Hidden signals must be a list of signal ids."), frappe.ValidationError)
    if not isinstance(raw, list):
        frappe.throw(_("Hidden signals must be a list of signal ids."), frappe.ValidationError)
    known = _hideable_signal_ids()
    for signal_id in raw:
        if signal_id not in known:
            frappe.throw(_("Unknown home signal: {0}").format(signal_id), frappe.ValidationError)
    return list(dict.fromkeys(raw))


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
        changes["needs_you_count"] = clamp_needs_you_count(cint(needs_you_count))
    if hidden_signals is not None:
        changes["hidden_home_signals"] = json.dumps(_validated_signal_ids(hidden_signals))
    if show_suggested_prompts is not None:
        changes["show_suggested_prompts"] = _flag(show_suggested_prompts)
    if show_personalized_suggestions is not None:
        changes["show_personalized_suggestions"] = _flag(show_personalized_suggestions)

    if changes:
        prefs = FACChatUserPreferences.get_or_create_preferences(user)
        prefs.update(changes)
        prefs.save(ignore_permissions=True)
        _invalidate_home_cache(user)
    return _preferences_payload(user)


@frappe.whitelist(methods=["POST"])
def hide_home_signal(signal_id: str) -> dict:
    """Add ``signal_id`` to the user's hidden home signals (idempotent)."""
    user = frappe.session.user
    new_ids = _validated_signal_ids([signal_id])
    prefs = FACChatUserPreferences.get_or_create_preferences(user)
    hidden = list(dict.fromkeys([*parse_hidden_signals(prefs.hidden_home_signals), *new_ids]))
    prefs.hidden_home_signals = json.dumps(hidden)
    prefs.save(ignore_permissions=True)
    _invalidate_home_cache(user)
    return {"hidden_signals": hidden}
