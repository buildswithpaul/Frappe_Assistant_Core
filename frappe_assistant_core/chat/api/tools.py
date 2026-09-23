# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""
Tool Permissions API — list tools and manage per-user approval preferences.

Bridges the FACO settings UI to:
- FAC's local tool registry (for the tool catalog shown in the UI)
- AR's AR Tool Trust DocType (for Block / Ask / Always Allow preferences)

Each FACO session corresponds to a user on the local Frappe site, so
``frappe.session.user`` is the correct ``user_id`` to pass through to AR.
"""

import frappe
from frappe import _

from .auth import _ar_user_id

# Tools that trigger HITL approval by default when no preference is set.
# Kept in sync with DEFAULT_APPROVAL_TOOLS in AR's approval_hook.py — the UI
# surfaces this as a "requires approval by default" hint.
_DEFAULT_APPROVAL_TOOLS = frozenset(
    {
        "create_document",
        "update_document",
        "delete_document",
        "submit_document",
    }
)


def _tool_to_ui_dict(tool_meta: dict, read_only: bool = False) -> dict:
    """Project a FAC tool metadata dict down to the fields the UI needs.

    ``read_only`` mirrors the tool's MCP ``readOnlyHint`` (resolved from the
    same FAC category source the MCP endpoint uses). The UI defaults read-only
    tools to "always allow" and write tools to "ask" — matching what AR's
    approval hook actually does at runtime, so the displayed default is truthful.
    """
    name = tool_meta.get("name", "")
    return {
        "name": name,
        "description": tool_meta.get("description", ""),
        "category": tool_meta.get("category") or "General",
        "requires_permission": tool_meta.get("requires_permission"),
        "default_requires_approval": name in _DEFAULT_APPROVAL_TOOLS,
        "read_only": read_only,
    }


def _resolve_read_only_map(tool_names: list, registry) -> dict:
    """Map each tool name to whether it is read-only (MCP readOnlyHint == true).

    Reuses the MCP endpoint's category resolver and annotation mapping so the
    settings UI and the tools/list annotation AR keys on stay in lockstep.
    Any failure degrades a tool to NOT read-only (safe default: it will "ask").
    """
    try:
        from frappe_assistant_core.api.fac_endpoint import _resolve_tool_categories
        from frappe_assistant_core.utils.tool_category_detector import category_to_annotations
    except ImportError:
        return {}

    try:
        categories = _resolve_tool_categories(tool_names, registry)
    except Exception:
        return {}

    return {
        name: bool(category_to_annotations(categories.get(name, "read_write")).get("readOnlyHint"))
        for name in tool_names
    }


@frappe.whitelist(methods=["GET"])
def list_available_tools():
    """
    List all tools the current user can access on this Frappe site.

    Reads directly from FAC's tool registry (same-site Python call — no
    MCP round-trip) so category / description come from the source of truth.

    Returns:
            {"tools": [{name, description, category, requires_permission,
                        default_requires_approval}, ...]}
    """
    try:
        from frappe_assistant_core.core.tool_registry import get_tool_registry
    except ImportError:
        frappe.log_error(
            title="FACO Tool Permissions", message="frappe_assistant_core not installed — cannot list tools"
        )
        return {"tools": []}

    registry = get_tool_registry()
    tools_meta = registry.get_available_tools(user=frappe.session.user)

    tool_names = [t.get("name", "") for t in tools_meta]
    read_only_map = _resolve_read_only_map(tool_names, registry)

    projected = [
        _tool_to_ui_dict(t, read_only=read_only_map.get(t.get("name", ""), False)) for t in tools_meta
    ]
    projected.sort(key=lambda t: (t["category"], t["name"]))
    return {"tools": projected}


@frappe.whitelist(methods=["GET"])
def list_tool_preferences():
    """
    Fetch the current user's tool approval preferences from AR.

    Returns:
            {"preferences": {tool_name: "always_allow" | "block" | "ask", ...}}
            Tools without a persistent preference are omitted (UI defaults them to "ask").
    """
    from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

    client = get_fac_cloud_client()
    if not client:
        # Not registered with AR yet — return empty, don't error the UI.
        return {"preferences": {}}

    result = client.list_tool_preferences(user_id=_ar_user_id(frappe.session.user))
    return result or {"preferences": {}}


@frappe.whitelist(methods=["POST"])
def set_tool_preference(tool_name: str | None = None, preference: str | None = None):
    """
    Set the current user's approval preference for one tool.

    Args:
            tool_name: MCP tool name (e.g. "create_document")
            preference: One of "ask", "always_allow", "block"

    Returns:
            {"success": True, "tool_name": ..., "preference": ...}
    """
    if not tool_name:
        frappe.throw(_("tool_name is required"), frappe.ValidationError)
    if preference not in ("ask", "always_allow", "block"):
        frappe.throw(
            _("preference must be one of: ask, always_allow, block"),
            frappe.ValidationError,
        )

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        return client.set_tool_preference(
            user_id=_ar_user_id(frappe.session.user),
            tool_name=tool_name,
            preference=preference,
        )

    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Tool Permissions", message=f"Error setting tool preference: {e}")
        frappe.throw(_("Error saving preference: {0}").format(str(e)))


@frappe.whitelist(methods=["GET"])
def get_skipped_tools():
    """Diagnostic: list tools that failed to load (import/dependency errors),
    with the reason. Helps explain why a tool is missing from the tool list
    on a given server. System Manager only."""
    frappe.only_for("System Manager")
    from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

    pm = get_plugin_manager()
    # Ensure tools have been loaded so skipped_tools is populated.
    try:
        pm.get_all_tools()
    except Exception:
        pass
    return {"skipped_tools": getattr(pm, "skipped_tools", {})}
