# Frappe Assistant Core - Chat Sessions API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Session lifecycle endpoints — list, history, archive, continue."""

from __future__ import annotations

import frappe
from frappe import _

from frappe_assistant_core.chat.doctype.fac_chat_conversation.fac_chat_conversation import (
    FACChatConversation,
)
from frappe_assistant_core.chat.doctype.fac_chat_project.fac_chat_project import (
    TITLE_MAX_LENGTH,
    FACChatProject,
)
from frappe_assistant_core.chat.doctype.fac_chat_session_state.fac_chat_session_state import (
    FACChatSessionState,
)

from .._helpers import _safe_error
from .._untrusted import wrap_untrusted

SEARCH_MIN_LENGTH = 2
CONTENT_MATCH_LIMIT = 500


def _like_pattern(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _search_session_ids(user: str, archived: int, project: str | None, pattern: str) -> list[str]:
    """Session ids whose title or message text matches. Query Builder parameterises the
    LIKE value on every Frappe version; get_list's own LIKE handling re-escapes backslashes on v15."""
    conv = frappe.qb.DocType("FAC Chat Conversation")
    by_title = (
        frappe.qb.from_(conv)
        .select(conv.name)
        .distinct()
        .where((conv.user == user) & (conv.is_archived == archived) & conv.title.like(pattern))
    )
    msg = frappe.qb.DocType("FAC Chat Message")
    by_content = (
        frappe.qb.from_(msg)
        .select(msg.session_id)
        .distinct()
        .where((msg.user == user) & (msg.is_archived == archived) & msg.content.like(pattern))
    )
    if project:
        by_title = by_title.where(conv.project == project)
    ids = set(by_title.limit(CONTENT_MATCH_LIMIT).run(pluck=True))
    ids.update(by_content.limit(CONTENT_MATCH_LIMIT).run(pluck=True))
    return list(ids)


def _list_conversations(
    archived: int, limit: int, offset: int = 0, project: str | None = None, search: str | None = None
) -> list[dict]:
    """The caller's conversations, newest activity first, in the sidebar's row shape."""
    user = frappe.session.user
    filters = {"user": user, "is_archived": archived}
    if project:
        filters["project"] = project
    term = (search or "").strip()
    if len(term) >= SEARCH_MIN_LENGTH:
        matched = _search_session_ids(user, archived, project, _like_pattern(term))
        if not matched:
            return []
        filters["name"] = ["in", matched]

    rows = frappe.get_list(
        "FAC Chat Conversation",
        filters=filters,
        fields=[
            "name as session_id",
            "title",
            "title_is_custom",
            "project",
            "started",
            "last_activity",
            "message_count",
        ],
        order_by="last_activity desc, name desc",
        limit_start=int(offset),
        limit_page_length=min(int(limit), 100),
    )
    project_titles = (
        dict(
            frappe.get_list(
                "FAC Chat Project",
                filters={"name": ["in", list({r.project for r in rows if r.project})], "user": user},
                fields=["name", "title"],
                as_list=True,
            )
        )
        if any(r.project for r in rows)
        else {}
    )
    fallback = _("Archived conversation") if archived else _("New conversation")
    for row in rows:
        row["preview"] = row.title or fallback
        row["title_is_custom"] = bool(row.title_is_custom)
        row["project_title"] = project_titles.get(row.project)
    return rows


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
def get_user_sessions(
    limit: int = 20, offset: int = 0, project: str | None = None, search: str | None = None
) -> list:
    """
    The caller's non-archived conversations for the sidebar, newest activity first.

    Pages with limit/offset (limit capped at 100) and narrows by project and by a
    search over titles and message text. A failed read raises, so Frappe logs it and
    answers with an error; an empty list only ever means nothing matched.

    Rows keep the pre-3.2 keys (session_id, preview, started, last_activity,
    message_count) that mobile and the Desk widget read; preview is now the title.

    Args:
            limit: Maximum number of sessions to return (default 20, max 100)
            offset: Number of sessions to skip
            project: Only conversations in this project
            search: Case-insensitive text matched against titles and messages

    Returns:
            list: Sessions with session_id, preview, title, title_is_custom, project,
            project_title, started, last_activity, message_count
    """
    return _list_conversations(0, limit, offset, project, search)


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
        frappe.db.set_value(
            "FAC Chat Conversation",
            {"name": session_id, "user": user},
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
        frappe.db.set_value(
            "FAC Chat Conversation",
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

    A failed read raises, as in ``get_user_sessions``: an empty list only
    ever means the user has no archived conversations.

    Returns:
            list: Archived sessions with session_id, preview, started, last_activity
    """
    rows = _list_conversations(1, limit)
    for row in rows:
        row["is_archived"] = True
    return rows


@frappe.whitelist(methods=["POST"])
def rename_session(session_id: str, title: str) -> dict:
    """Rename a conversation. A blank title goes back to the automatic one."""
    FACChatConversation.owned(session_id)
    clean = " ".join((title or "").split())
    if len(clean) > TITLE_MAX_LENGTH:
        frappe.throw(_("Title must be {0} characters or fewer").format(TITLE_MAX_LENGTH))
    values = (
        {"title": clean, "title_is_custom": 1}
        if clean
        else {"title": FACChatConversation.default_title(session_id), "title_is_custom": 0}
    )
    frappe.db.set_value("FAC Chat Conversation", session_id, values, update_modified=False)
    return {"success": True, "title": values["title"], "title_is_custom": bool(values["title_is_custom"])}


@frappe.whitelist(methods=["POST"])
def move_session_to_project(session_id: str, project: str | None = None) -> dict:
    """Put a conversation in one of the caller's projects, or take it out with None."""
    FACChatConversation.owned(session_id)
    project = project or None
    project_title = FACChatProject.owned(project).title if project else None
    frappe.db.set_value("FAC Chat Conversation", session_id, "project", project, update_modified=False)
    return {"success": True, "project": project, "project_title": project_title}


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
            dict: { new_session_id, context_addendum, project }
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
            "project": frappe.db.get_value(
                "FAC Chat Conversation", {"name": old_session_id, "user": user}, "project"
            ),
        }

    except Exception as e:
        frappe.log_error(
            title="FACO Continue Archived Error", message=f"Error continuing archived session: {e!s}"
        )
        return {"success": False, "error": _safe_error(e, "FACO Continue Archived Error")}
