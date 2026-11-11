# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Per-user FAC Chat home-page preferences, read without creating a row.

Everything is on by default, so a user with no preferences row (or an unset field)
reads the defaults below.
"""

import json
import re

import frappe

PREFERENCES_DOCTYPE = "FAC Chat User Preferences"
HOME_SIGNALS_CACHE_KEY = "fac_home_signals"
NEEDS_YOU_MIN_COUNT = 1
NEEDS_YOU_MAX_COUNT = 3

HOME_PREFERENCE_FIELDS = (
    "show_needs_you",
    "needs_you_count",
    "hidden_home_signals",
    "show_suggested_prompts",
    "show_personalized_suggestions",
    "show_tips",
    "show_whats_new",
    "show_progress",
)

# What the SPA may keep in ``discovery_state``: lists of ids, the tour flag and a few dates. Anything
# else is dropped, so a bad or oversized save can never grow the row.
DISCOVERY_LIST_KEYS = ("seen", "used", "celebrated", "stories_seen")
DISCOVERY_LIST_MAX = 50
DISCOVERY_ID_MAX = 140
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def clamp_needs_you_count(value: int) -> int:
    return max(NEEDS_YOU_MIN_COUNT, min(NEEDS_YOU_MAX_COUNT, value))


def parse_hidden_signals(raw: list | str | None) -> list[str]:
    """Signal ids from a stored JSON string or a list; malformed input reads as empty."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else []
        except ValueError:
            return []
    if not isinstance(raw, list):
        return []
    return list(dict.fromkeys(item for item in raw if isinstance(item, str)))


def load_home_preferences(user: str) -> dict:
    """The user's home preferences as plain values; defaults when nothing is stored."""
    row = frappe.db.get_value(PREFERENCES_DOCTYPE, user, list(HOME_PREFERENCE_FIELDS), as_dict=True) or {}

    def flag(field: str) -> bool:
        value = row.get(field)
        return True if value is None else bool(int(value))

    count = row.get("needs_you_count")
    return {
        "show_needs_you": flag("show_needs_you"),
        "needs_you_count": clamp_needs_you_count(NEEDS_YOU_MAX_COUNT if count is None else int(count)),
        "hidden_signals": parse_hidden_signals(row.get("hidden_home_signals")),
        "show_suggested_prompts": flag("show_suggested_prompts"),
        "show_personalized_suggestions": flag("show_personalized_suggestions"),
        "show_tips": flag("show_tips"),
        "show_whats_new": flag("show_whats_new"),
        "show_progress": flag("show_progress"),
    }


def _date_or_none(value) -> str | None:
    return value if isinstance(value, str) and _ISO_DATE.match(value) else None


def parse_discovery_state(raw: dict | str | None) -> dict:
    """The stored feature-discovery state, keeping only known keys and types; malformed input reads as empty.

    Opened features (``seen``), features really used (``used``), unlocks already celebrated,
    stories already watched, the tour, and today's tip. Losing any of it only means a tip,
    a dot or a story shows once more.
    """
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else {}
        except ValueError:
            raw = {}
    if not isinstance(raw, dict):
        raw = {}
    state: dict = {}
    for key in DISCOVERY_LIST_KEYS:
        items = raw.get(key)
        items = items if isinstance(items, list) else []
        ids = [i for i in items if isinstance(i, str) and 0 < len(i) <= DISCOVERY_ID_MAX]
        state[key] = list(dict.fromkeys(ids))[-DISCOVERY_LIST_MAX:]
    state["coach_done"] = raw.get("coach_done") is True
    tip = raw.get("tip")
    tip_id = tip.get("id") if isinstance(tip, dict) else None
    tip_date = _date_or_none(tip.get("date")) if isinstance(tip, dict) else None
    valid_tip = isinstance(tip_id, str) and 0 < len(tip_id) <= DISCOVERY_ID_MAX and tip_date
    state["tip"] = {"id": tip_id, "date": tip_date} if valid_tip else None
    state["tip_hidden_on"] = _date_or_none(raw.get("tip_hidden_on"))
    state["first_day"] = _date_or_none(raw.get("first_day"))
    return state
