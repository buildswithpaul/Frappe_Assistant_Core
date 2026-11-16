# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""FAC Chat: the per-user "Load tools as needed" preference."""

import frappe
from frappe.utils import sbool

from ..doctype.fac_chat_user_preferences.fac_chat_user_preferences import FACChatUserPreferences
from ..tool_loading import TOOL_LOADING_FIELD, load_tools_as_needed


@frappe.whitelist(methods=["GET"])
def get_tool_loading() -> dict:
    """Whether the session user has tools loaded as needed (the default)."""
    return {"load_tools_as_needed": load_tools_as_needed(frappe.session.user)}


@frappe.whitelist(methods=["POST"])
def set_tool_loading(load_as_needed: bool) -> dict:
    """Save the session user's choice; ``False`` gives FACO every tool on every message."""
    prefs = FACChatUserPreferences.get_or_create_preferences()
    prefs.set(TOOL_LOADING_FIELD, 1 if sbool(load_as_needed) else 0)
    prefs.save(ignore_permissions=True)
    return {"load_tools_as_needed": bool(prefs.get(TOOL_LOADING_FIELD))}
