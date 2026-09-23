# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""
Streaming event history and tool execution statistics.

NOTE: As of 2026-04-11, UI rendering uses snapshot-based blocks persisted on
FACO Message (the ``blocks`` JSON field). These event endpoints are retained
for audit trail, analytics dashboards, and admin debugging only — they are no
longer called by the SPA, widget, or mobile app for message reconstruction.
"""

import json

import frappe
from frappe import _

from ._helpers import _not_registered_error, _require_system_manager, _safe_error


@frappe.whitelist(methods=["GET"])
def get_message_events(
    session_id: str,
    message_id: str | None = None,
    event_types: str | list[str] | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """
    Get persisted streaming events for a conversation.

    Returns thinking blocks, tool calls, and their results that were
    captured during the streaming conversation. Retained for audit trail
    and analytics — UI rendering uses the blocks snapshot on FACO Message.

    Args:
            session_id: Conversation session ID
            message_id: Optional message ID to filter events
            event_types: Optional JSON array of event types to filter
            limit: Number of events to return (default 100)
            offset: Pagination offset (default 0)

    Returns:
            dict: {
                    "events": [...],
                    "pagination": {...}
            }
    """
    try:
        # Ownership check — verify the caller owns at least one message in the
        # requested session before forwarding the request to AR. Prevents
        # cross-user event enumeration via a guessed session_id.
        if not frappe.db.exists(
            "FAC Chat Message",
            {"session_id": session_id, "user": frappe.session.user},
        ):
            frappe.throw(_("Session not found"), frappe.PermissionError)

        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        # Parse event_types if string
        if isinstance(event_types, str) and event_types:
            try:
                event_types = json.loads(event_types)
            except json.JSONDecodeError:
                event_types = None

        result = client.get_message_events(
            conversation_id=session_id,
            message_id=message_id,
            event_types=event_types,
            limit=int(limit),
            offset=int(offset),
        )

        if result:
            return {"success": True, **result}

        return {"success": False, "events": [], "error": "Failed to fetch events"}

    except frappe.PermissionError:
        # Let Frappe return a proper 403 rather than swallowing as a generic error
        raise
    except Exception as e:
        frappe.log_error(title="FACO Events Error", message=f"Error getting message events: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO Events Error")}


@frappe.whitelist(methods=["GET"])
def get_tool_stats(
    session_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
):
    """
    Get aggregated tool execution statistics.

    Admin only - useful for monitoring tool usage patterns.

    Args:
            session_id: Optional - filter stats for specific conversation
            from_date: Optional - filter stats from this date (ISO format)
            to_date: Optional - filter stats until this date (ISO format)

    Returns:
            dict: Aggregated tool statistics
    """
    _require_system_manager()

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"error": _not_registered_error()}

        result = client.get_tool_execution_stats(
            conversation_id=session_id, from_date=from_date, to_date=to_date
        )

        if result:
            return {"success": True, **result}

        return {"success": False, "error": "Failed to fetch tool stats"}

    except Exception as e:
        frappe.log_error(title="FACO Stats Error", message=f"Error getting tool stats: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO Stats Error")}
