# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Per-user FAC Chat home-page preferences, read without creating a row.

Everything is on by default, so a user with no preferences row (or an unset field)
reads the defaults below.
"""

import json

import frappe

PREFERENCES_DOCTYPE = "FAC Chat User Preferences"
NEEDS_YOU_MIN_COUNT = 1
NEEDS_YOU_MAX_COUNT = 3

HOME_PREFERENCE_FIELDS = (
    "show_needs_you",
    "needs_you_count",
    "hidden_home_signals",
    "show_suggested_prompts",
    "show_personalized_suggestions",
)


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
    }
