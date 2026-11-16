# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Per-user "Load tools as needed" choice, sent to AR in the tools/list ``_meta``.

On by default: a user with no preferences row, an unset field, or a site where the column has not
been migrated yet reads as dynamic. Only an explicit 0 means every tool on every message.
"""

import frappe

PREFERENCES_DOCTYPE = "FAC Chat User Preferences"
TOOL_LOADING_FIELD = "load_tools_as_needed"
DYNAMIC = "dynamic"
ALL_TOOLS = "all"


def load_tools_as_needed(user: str) -> bool:
    """Whether ``user`` wants tools loaded as needed; True unless they switched it off."""
    if not frappe.db.has_column(PREFERENCES_DOCTYPE, TOOL_LOADING_FIELD):
        return True
    value = frappe.db.get_value(PREFERENCES_DOCTYPE, user, TOOL_LOADING_FIELD)
    return True if value is None else bool(int(value))


def tool_loading_mode(user: str) -> str:
    """``"dynamic"`` or ``"all"``: the value of the listing's ``fac/tool_loading``."""
    return DYNAMIC if load_tools_as_needed(user) else ALL_TOOLS
