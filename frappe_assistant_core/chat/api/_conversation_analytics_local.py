# Frappe Assistant Core - Local conversation analytics aggregation
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Pure aggregation over FAC Chat Message rows for the usage analytics page.

Under Zero Data Retention the AR side stores no conversations, so the
per-conversation breakdown is reconstructed from the local FAC Chat Message
rows that FAC mirrors every turn. These helpers are pure (no DB / frappe
calls) so they are unit-testable; the endpoint layer fetches the rows.
"""

from __future__ import annotations

import json


def _row_get(row, key, default=None):
    # Rows may be dicts or frappe._dict — both support .get.
    return row.get(key, default)


def build_conversation_list(rows: list, limit: int = 50, offset: int = 0) -> dict:
    """Group flat FAC Chat Message rows into a per-conversation breakdown.

    Args:
        rows: message dicts with session_id, role, content, credits_used,
              timestamp, user, idx — in any order.
        limit, offset: pagination over the grouped conversation list.

    Returns the conversation-list payload the usage page expects.
    """
    sessions: dict = {}
    for row in rows:
        sid = _row_get(row, "session_id")
        if not sid:
            continue
        s = sessions.get(sid)
        if s is None:
            s = sessions[sid] = {
                "conversation_id": sid,
                "title": None,
                "user_id": _row_get(row, "user"),
                "created_at": _row_get(row, "timestamp"),
                "last_message_at": _row_get(row, "timestamp"),
                "total_credits": 0,
                "message_count": 0,
            }
        s["message_count"] += 1
        s["total_credits"] += float(_row_get(row, "credits_used", 0) or 0)

        ts = _row_get(row, "timestamp")
        if ts:
            if not s["created_at"] or ts < s["created_at"]:
                s["created_at"] = ts
            if not s["last_message_at"] or ts > s["last_message_at"]:
                s["last_message_at"] = ts

        # Title: first user message content (truncated), filled once.
        if s["title"] is None and _row_get(row, "role") == "user":
            content = (_row_get(row, "content") or "").strip()
            if content:
                s["title"] = content[:100]

    convs = list(sessions.values())
    for c in convs:
        if not c["title"]:
            c["title"] = "New conversation"
        c["total_credits"] = round(c["total_credits"], 2)
        c["created_at"] = str(c["created_at"]) if c["created_at"] else None
        c["last_message_at"] = str(c["last_message_at"]) if c["last_message_at"] else None

    # Newest activity first.
    convs.sort(key=lambda c: c["last_message_at"] or "", reverse=True)

    total = len(convs)
    page = convs[offset : offset + limit]

    return {
        "conversations": page,
        "summary": {
            "total_conversations": total,
            "total_credits": round(sum(c["total_credits"] for c in convs), 2),
            "total_messages": sum(c["message_count"] for c in convs),
        },
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total,
        },
    }


def _parse_tool_names(tool_calls_raw) -> list:
    """Extract tool names from a FAC Chat Message ``tool_calls`` JSON value."""
    if not tool_calls_raw:
        return []
    try:
        data = tool_calls_raw if isinstance(tool_calls_raw, list) else json.loads(tool_calls_raw)
    except (json.JSONDecodeError, TypeError):
        return []
    names = []
    if isinstance(data, list):
        for tc in data:
            if isinstance(tc, dict) and tc.get("name"):
                names.append(tc["name"])
    return names


def _parse_model_breakdown(raw) -> list:
    """Parse a FAC Chat Message ``model_breakdown`` JSON value into a list.

    Returns [] for single-model turns (null/empty) and for malformed data, so
    the drill-down can branch purely on length. Raw token counts are dropped —
    the product surfaces credits only; tokens stay in the persisted JSON for
    audit/billing but are never returned to the client.
    """
    if not raw:
        return []
    try:
        data = raw if isinstance(raw, list) else json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return [
        {"model_id": m.get("model_id"), "role": m.get("role"), "credits": m.get("credits")}
        for m in data
        if isinstance(m, dict)
    ]


def build_message_credits(conversation_id: str, rows: list) -> dict:
    """Map ordered FAC Chat Message rows to the per-message drill-down payload."""
    title = None
    user_id = None
    created_at = None
    messages = []
    total_credits = 0

    for row in rows:
        role = _row_get(row, "role")
        content = (_row_get(row, "content") or "").strip()
        credits = round(float(_row_get(row, "credits_used", 0) or 0), 2)
        total_credits += credits

        if user_id is None:
            user_id = _row_get(row, "user")
        ts = _row_get(row, "timestamp")
        if created_at is None and ts:
            created_at = ts
        if title is None and role == "user" and content:
            title = content[:100]

        tool_names = _parse_tool_names(_row_get(row, "tool_calls"))
        messages.append(
            {
                "message_id": _row_get(row, "message_id"),
                "role": role,
                "content_preview": content[:200]
                if content
                else (f"Used tools: {', '.join(tool_names)}" if tool_names else "(processing)"),
                "model_id": _row_get(row, "model"),
                "model_breakdown": _parse_model_breakdown(_row_get(row, "model_breakdown")),
                "credits_used": credits,
                "created_at": str(ts) if ts else None,
                "tool_count": len(tool_names),
                "tool_names": tool_names[:5],
                "had_thinking": False,
            }
        )

    return {
        "conversation_id": conversation_id,
        "title": title or "New conversation",
        "user_id": user_id,
        "created_at": str(created_at) if created_at else None,
        "messages": messages,
        "total_credits": round(total_credits, 2),
        "total_messages": len(messages),
    }
