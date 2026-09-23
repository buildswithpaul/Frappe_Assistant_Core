# Frappe Assistant Core - Chat Sessions API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Session lifecycle endpoints — list, history, archive, continue."""

from __future__ import annotations

import frappe
from frappe import _

from frappe_assistant_core.chat.doctype.fac_chat_session_state.fac_chat_session_state import (
    FACChatSessionState,
)

from .._helpers import _safe_error
from .._untrusted import wrap_untrusted


@frappe.whitelist(methods=["GET"])
def get_session_history(session_id: str, limit: int = 30, offset: int = 0) -> dict:
    """
    Get messages for a session with pagination.

    Reads from the local FAC Chat Message rows, which are authoritative under
    the stateless default (and a stateful app still mirrors every turn locally).
    Returns most recent messages (ordered chronologically), with has_more flag
    for pagination.

    Args:
            session_id: Conversation session ID
            limit: Max messages to return (default 30, max 100)
            offset: Number of messages to skip from the end (for loading older messages)

    Returns:
            dict: { "messages": [...], "has_more": bool }
    """
    from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import (
        FACChatMessage,
    )

    limit = min(int(limit or 30), 100)
    offset = int(offset or 0)

    # Ownership check — prevent cross-user session read (IDOR).
    # A user may only read a session that contains at least one of their own messages.
    user = frappe.session.user
    has_local = frappe.db.exists("FAC Chat Message", {"session_id": session_id})
    if has_local and not frappe.db.exists("FAC Chat Message", {"session_id": session_id, "user": user}):
        frappe.throw(_("Session not found"), frappe.PermissionError)

    # Local read is authoritative — includes tool_calls and attachments.
    # Pass user to scope the query even for edge cases (e.g. shared assistant rows).
    local_messages = FACChatMessage.get_session_messages(session_id, limit=limit, offset=offset, user=user)
    if local_messages is not None:
        return local_messages

    return {"messages": [], "has_more": False}


@frappe.whitelist(methods=["GET"])
def get_user_sessions(limit: int = 20) -> list:
    """
    Get user's recent chat sessions for history sidebar.

    Returns sessions grouped with preview (first message) and timestamps.

    Args:
            limit: Maximum number of sessions to return (default 20)

    Returns:
            list: Sessions with session_id, preview, started, last_activity
    """
    try:
        user = frappe.session.user
        limit = min(int(limit), 100)  # Cap at 100

        # Query 1: Get session aggregates (distinct sessions with timestamps)
        from pypika.functions import Count, Max, Min

        FM = frappe.qb.DocType("FAC Chat Message")
        session_query = (
            frappe.qb.from_(FM)
            .select(
                FM.session_id,
                Min(FM.creation).as_("started"),
                Max(FM.creation).as_("last_activity"),
                Count(FM.name).as_("message_count"),
            )
            .where(FM.user == user)
            .where(FM.is_archived == 0)
            .groupby(FM.session_id)
            .orderby("last_activity", order=frappe.qb.desc)
            .limit(limit)
        )
        sessions = session_query.run(as_dict=True)

        if not sessions:
            return []

        # Query 2: Get first user message per session for preview
        session_ids = [s["session_id"] for s in sessions]
        first_messages = frappe.get_all(
            "FAC Chat Message",
            filters={
                "session_id": ["in", session_ids],
                "user": user,
                "role": "user",
            },
            fields=["session_id", "content", "creation"],
            order_by="creation asc",
        )

        # Keep only the first message per session
        preview_map: dict[str, str] = {}
        for msg in first_messages:
            if msg.session_id not in preview_map:
                content = (msg.content or "")[:100]
                preview_map[msg.session_id] = content + ("..." if len(msg.content or "") > 100 else "")

        for session in sessions:
            session["preview"] = preview_map.get(session["session_id"], _("New conversation"))

        return sessions

    except Exception as e:
        frappe.log_error(title="FACO Sessions Error", message=f"Error getting user sessions: {e!s}")
        return []


@frappe.whitelist(methods=["POST"])
def create_session() -> dict:
    """
    Create a new chat session for the current user.

    Returns:
            dict: Session information with session_id
    """
    import uuid

    try:
        session_id = str(uuid.uuid4())
        return {
            "success": True,
            "session_id": session_id,
            "user": frappe.session.user,
            "created": frappe.utils.now(),
        }
    except Exception as e:
        frappe.log_error(title="FACO Session Create Error", message=f"Error creating session: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO Session Create Error")}


@frappe.whitelist(methods=["POST"])
def archive_session(session_id: str) -> dict:
    """
    Archive a conversation locally and drop its zero-retention state blob.

    The local FAC Chat Messages are preserved (marked is_archived=1) so the
    user retains their data on their own instance. Under the stateless default
    AR holds no conversation to delete, so cleanup is purely local: archive the
    rows and drop the session-state blob.

    Args:
            session_id: The session ID to archive

    Returns:
            dict: Success status
    """
    try:
        user = frappe.session.user

        # Verify the session belongs to the current user
        count = frappe.db.count("FAC Chat Message", {"session_id": session_id, "user": user})
        if not count:
            return {"success": False, "error": _("Session not found or access denied")}

        # Archive locally — mark all messages, preserve data
        frappe.db.set_value(
            "FAC Chat Message",
            {"session_id": session_id, "user": user},
            "is_archived",
            1,
            update_modified=False,
        )

        # Delete-with-messages: drop the zero-retention session blob so it never
        # outlives the conversation it belongs to (no separate TTL).
        FACChatSessionState.delete_for_sessions(session_id)

        return {"success": True, "archived_count": count}

    except Exception as e:
        frappe.log_error(title="FACO Session Archive Error", message=f"Error archiving session: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO Session Archive Error")}


@frappe.whitelist(methods=["POST"])
def delete_session(session_id: str) -> dict:
    """
    Archive a session (backward compatibility wrapper for mobile).

    Calls archive_session() internally — local data is preserved,
    AR-side data is hard-deleted.
    """
    return archive_session(session_id)


@frappe.whitelist(methods=["POST"])
def archive_all_conversations() -> dict:
    """
    Archive all conversations for the current user.

    Marks all local FAC Chat Messages as archived and drops each session's
    zero-retention state blob. Under the stateless default AR holds no
    conversation to delete, so cleanup is purely local.

    Returns:
            dict: Success status with count of archived messages
    """
    try:
        user = frappe.session.user

        # Get distinct session IDs before archiving
        messages = frappe.get_all(
            "FAC Chat Message",
            filters={"user": user, "is_archived": 0},
            fields=["session_id"],
            limit_page_length=0,
        )

        if not messages:
            return {"success": True, "archived_count": 0}

        session_ids = list({msg.session_id for msg in messages if msg.session_id})

        # Archive all local messages
        frappe.db.set_value(
            "FAC Chat Message",
            {"user": user, "is_archived": 0},
            "is_archived",
            1,
            update_modified=False,
        )

        # Delete-with-messages: drop every zero-retention session blob in one
        # pass. Without this, bulk "Archive all" orphans every state row.
        FACChatSessionState.delete_for_sessions(session_ids)

        return {"success": True, "archived_count": len(messages)}

    except Exception as e:
        frappe.log_error(title="FACO Archive All Error", message=f"Error archiving conversations: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO Archive All Error")}


@frappe.whitelist(methods=["POST"])
def clear_all_conversations() -> dict:
    """Backward compatibility — now archives instead of deleting."""
    return archive_all_conversations()


@frappe.whitelist(methods=["GET"])
def get_archived_sessions(limit: int = 50) -> list:
    """
    Get user's archived chat sessions.

    Returns:
            list: Archived sessions with session_id, preview, started, last_activity
    """
    try:
        user = frappe.session.user
        limit = min(int(limit), 100)

        from pypika.functions import Count, Max, Min

        FM = frappe.qb.DocType("FAC Chat Message")
        session_query = (
            frappe.qb.from_(FM)
            .select(
                FM.session_id,
                Min(FM.creation).as_("started"),
                Max(FM.creation).as_("last_activity"),
                Count(FM.name).as_("message_count"),
            )
            .where(FM.user == user)
            .where(FM.is_archived == 1)
            .groupby(FM.session_id)
            .orderby("last_activity", order=frappe.qb.desc)
            .limit(limit)
        )
        sessions = session_query.run(as_dict=True)

        if not sessions:
            return []

        # Get first user message per session for preview
        session_ids = [s["session_id"] for s in sessions]
        first_messages = frappe.get_all(
            "FAC Chat Message",
            filters={
                "session_id": ["in", session_ids],
                "user": user,
                "role": "user",
            },
            fields=["session_id", "content", "creation"],
            order_by="creation asc",
        )

        preview_map: dict[str, str] = {}
        for msg in first_messages:
            if msg.session_id not in preview_map:
                content = (msg.content or "")[:100]
                preview_map[msg.session_id] = content + ("..." if len(msg.content or "") > 100 else "")

        for session in sessions:
            session["preview"] = preview_map.get(session["session_id"], _("Archived conversation"))
            session["is_archived"] = True

        return sessions

    except Exception as e:
        frappe.log_error(
            title="FACO Archived Sessions Error", message=f"Error getting archived sessions: {e!s}"
        )
        return []


@frappe.whitelist(methods=["POST"])
def continue_archived_session(old_session_id: str) -> dict:
    """
    Create a new session with context from an archived conversation.

    Loads recent messages from the archived session and formats them as
    a context addendum that can be passed as system_prompt_addendum on
    the first message in the new session, giving the agent prior context.

    Args:
            old_session_id: The archived session to continue from

    Returns:
            dict: { new_session_id, context_addendum }
    """
    import uuid

    try:
        user = frappe.session.user

        # Load recent messages from the archived session
        messages = frappe.get_all(
            "FAC Chat Message",
            filters={
                "session_id": old_session_id,
                "user": user,
                "is_archived": 1,
            },
            fields=["role", "content", "creation"],
            order_by="creation desc",
            limit_page_length=20,
        )

        if not messages:
            return {"success": False, "error": _("Archived session not found")}

        # Reverse to chronological order
        messages.reverse()

        # Build context addendum from message history.
        # Wrap the transcript in an untrusted envelope so the LLM doesn't
        # treat archived USER/ASSISTANT lines as instructions
        # (FACO-H15 / FACO-M10 prompt injection via history).
        history_lines = []
        for msg in messages:
            content = (msg.content or "")[:2000]
            role_label = "USER" if msg.role == "user" else "ASSISTANT"
            history_lines.append(f"{role_label}: {content}")

        transcript = "\n\n".join(history_lines)
        context_addendum = (
            "## Prior Conversation Context\n"
            "The user is continuing a previous conversation. "
            "Here is the recent history:"
            + wrap_untrusted(transcript, kind="prior_conversation")
            + "\nContinue naturally from this context. "
            "The user may reference things discussed above."
        )

        # Create a new session
        new_session_id = str(uuid.uuid4())

        return {
            "success": True,
            "new_session_id": new_session_id,
            "context_addendum": context_addendum,
            "messages_included": len(messages),
        }

    except Exception as e:
        frappe.log_error(
            title="FACO Continue Archived Error", message=f"Error continuing archived session: {e!s}"
        )
        return {"success": False, "error": _safe_error(e, "FACO Continue Archived Error")}
