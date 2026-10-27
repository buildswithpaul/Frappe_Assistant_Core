# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Usage analytics — admin-only team-wide dashboards and conversation drill-down."""

import frappe
from frappe import _

from ._helpers import (
    _not_registered_error,
    _safe_error,
)

# Allowlist: only these AR keys reach a member; anything team-wide stays out.
MY_USAGE_KEYS = ("period", "summary", "daily", "by_model", "by_source")


def _get_client():
    """Get AR client, returning None if not registered."""
    from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

    return get_fac_cloud_client()


def _is_admin() -> bool:
    """Check if the current user has System Manager role."""
    return "System Manager" in frappe.get_roles(frappe.session.user)


def _require_admin() -> None:
    """Reject non-admins. Usage analytics are team-wide and admin-only."""
    if not _is_admin():
        frappe.throw(_("Only administrators can view usage analytics."), frappe.PermissionError)


def _with_full_names(rows: list[dict]) -> list[dict]:
    """Add ``full_name`` to each usage row, matching ``user_id`` the way AR keys a user.

    AR keys a user by the User docname when it contains "@", else by User.email (see
    ``auth._ar_user_id``). So a user whose email changed after they were seated is still
    reported under the old docname. Match both, docname first, case-insensitively.
    Unknown users get None.
    """
    ids = [row["user_id"] for row in rows if row.get("user_id")]
    names: dict[str, str] = {}
    if ids:
        users = frappe.get_all(
            "User",
            or_filters={"name": ["in", ids], "email": ["in", ids]},
            fields=["name", "email", "full_name"],
        )
        for user in users:
            if "@" in (user.get("name") or ""):
                names[user["name"].lower()] = user["full_name"]
        for user in users:
            if user.get("email"):
                names.setdefault(user["email"].lower(), user["full_name"])
    for row in rows:
        row["full_name"] = names.get(str(row.get("user_id") or "").lower()) or None
    return rows


@frappe.whitelist(methods=["GET"])
def get_analytics_data(days: int = 30):
    """
    Get team-wide token usage analytics.

    Args:
        days: Time range in days (7, 30, or 90)

    Returns:
        dict with period, summary, daily, by_user (each with full_name), by_model, by_source, is_admin
    """
    _require_admin()

    try:
        client = _get_client()
        if not client:
            return {"error": _not_registered_error()}

        result = client.get_token_analytics(days=int(days), user_id=None)
        result["by_user"] = _with_full_names(result.get("by_user") or [])
        result["is_admin"] = True
        return result

    except Exception as e:
        frappe.log_error(title="FACO Analytics Error", message=f"Error fetching analytics: {e!s}")
        return {"error": _safe_error(e, "FACO Analytics Error")}


@frappe.whitelist(methods=["GET"])
def get_my_usage(days: int | None = 30) -> dict:
    """
    Get the session user's own token usage. Open to any logged-in member.

    The scope is set here from the session, never from a request parameter, so a
    member cannot read anyone else's usage. ``by_user`` is dropped: it only holds
    team-wide rows.

    Args:
        days: Time range in days (7, 30, or 90; anything else becomes 30)

    Returns:
        dict with period, summary, daily, by_model, by_source
    """
    from .auth import _ar_user_id

    user_id = _ar_user_id(frappe.session.user) if frappe.session.user != "Guest" else None
    if not user_id:
        frappe.throw(_("Log in to view your usage."), frappe.PermissionError)

    try:
        days = int(days)
    except (TypeError, ValueError):
        days = 30
    if days not in (7, 30, 90):
        days = 30

    try:
        client = _get_client()
        if not client:
            return {"error": _not_registered_error()}

        result = client.get_token_analytics(days=days, user_id=user_id)
        return {key: result.get(key) for key in MY_USAGE_KEYS}

    except Exception as e:
        frappe.log_error(title="FACO Analytics Error", message=f"Error fetching my usage: {e!s}")
        return {"error": _safe_error(e, "FACO Analytics Error")}


@frappe.whitelist(methods=["GET"])
def get_conversation_analytics(days: int = 30, limit: int = 50, offset: int = 0):
    """
    Get team-wide per-conversation credit breakdown.

    Sourced from local FAC Chat Message rows, which are authoritative under
    zero retention — AR stores no conversations, so the SDK has nothing to
    return. FAC mirrors every turn locally regardless of the app's retention
    mode, so this works uniformly. Aggregates across all users (admin view).

    Args:
        days: Time range in days (7, 30, or 90)
        limit: Page size (default: 50)
        offset: Pagination offset (default: 0)

    Returns:
        dict with conversations, summary, pagination
    """
    _require_admin()

    try:
        from frappe.utils import add_days, today

        from ._conversation_analytics_local import build_conversation_list

        days = int(days)
        if days not in (7, 30, 90):
            days = 30
        start = add_days(today(), -days)

        # Archived conversations are included on purpose. Archiving hides a
        # conversation from the user's chat list; it is not erasure (GDPR
        # erase deletes the rows outright). Their credits are still counted by
        # every other panel on this page, so excluding them here reported
        # spend with nothing to attribute it to. ``get_message_credits`` never
        # filtered on it either, so the drill-down already returned them.
        rows = frappe.get_all(
            "FAC Chat Message",
            filters={"creation": [">=", start]},
            fields=[
                "session_id",
                "role",
                "content",
                "credits_used",
                "timestamp",
                "user",
                "idx",
            ],
            order_by="creation asc",
            limit_page_length=0,
        )
        result = build_conversation_list(rows, limit=int(limit), offset=int(offset))
        result["is_admin"] = True
        return result

    except Exception as e:
        frappe.log_error(
            title="FACO Analytics Error", message=f"Error fetching conversation analytics: {e!s}"
        )
        return {"error": _safe_error(e, "FACO Analytics Error")}


@frappe.whitelist(methods=["GET"])
def get_message_credits(conversation_id: str | None = None):
    """
    Get per-message credit breakdown for a conversation.

    Reads the conversation's local FAC Chat Message rows (authoritative under
    zero retention) ordered by message index.

    Args:
        conversation_id: The conversation to drill into

    Returns:
        dict with conversation metadata, messages with credits, totals
    """
    _require_admin()

    if not conversation_id:
        frappe.throw(_("conversation_id is required"))

    try:
        from ._conversation_analytics_local import build_message_credits

        rows = frappe.get_all(
            "FAC Chat Message",
            filters={"session_id": conversation_id},
            fields=[
                "message_id",
                "role",
                "content",
                "model",
                "model_breakdown",
                "credits_used",
                "timestamp",
                "user",
                "tool_calls",
                "idx",
            ],
            order_by="idx asc",
            limit_page_length=0,
        )
        if not rows:
            frappe.throw(_("Conversation not found"), frappe.DoesNotExistError)
        return build_message_credits(conversation_id, rows)

    except frappe.DoesNotExistError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Analytics Error", message=f"Error fetching message credits: {e!s}")
        return {"error": _safe_error(e, "FACO Analytics Error")}
