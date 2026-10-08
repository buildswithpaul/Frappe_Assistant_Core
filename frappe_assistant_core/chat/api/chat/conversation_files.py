# Frappe Assistant Core - Files attached in a chat conversation
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The files a user attached anywhere in a conversation, as the model sees them on every turn.

The system prompt addendum lasts one turn, so a file's text sent only with the message that
carried it was gone by the next one, and the model never learned which File doc it was. This is
rebuilt each turn from the files linked to the conversation's messages: every file is listed by
its File ID and URL, so a tool can act on it, with its extracted text, so a follow-up can read it.
"""

from __future__ import annotations

import frappe

from .._untrusted import wrap_untrusted

# Per-file and whole-section caps on extracted text. The section rides on every turn, so one
# large PDF must not crowd out the rest of the conversation's files or the context window.
MAX_FILE_CHARS = 20_000
MAX_TOTAL_CHARS = 60_000

# Extraction runs OCR on images and parses PDFs; a file's bytes never change, so its text is
# extracted once and reused on later turns.
TEXT_CACHE_TTL = 7 * 24 * 3600

PREAMBLE = (
    "\n\nThe user attached the files below to their messages in this conversation. "
    "Refer to a file by its File ID when a tool needs it."
)


def conversation_files_addendum(session_id: str, user: str) -> str:
    """The prompt section listing every file attached in the conversation, or "" if none."""
    files = _conversation_files(session_id, user)
    if not files:
        return ""

    # The newest file is the likeliest subject of the turn, so it claims the budget first.
    budget = MAX_TOTAL_CHARS
    sections = {}
    for f in reversed(files):
        text = _file_text(f)
        if len(text) > MAX_FILE_CHARS:
            text = text[:MAX_FILE_CHARS] + "\n[Truncated: the rest of this file is not included.]"
        if text and len(text) > budget:
            text = "[Not included: the conversation's files exceed the size limit.]"
        budget -= len(text)
        sections[f.name] = _describe(f, text)

    listing = "[Files attached in this conversation]\n\n" + "\n\n".join(sections[f.name] for f in files)
    return PREAMBLE + wrap_untrusted(listing, kind="user_attached_files")


def _conversation_files(session_id: str, user: str) -> list:
    # get_all skips permission checks, so both lookups are scoped to the user: a conversation
    # is only ever theirs, and only their own uploads are ever linked to its messages.
    message_names = frappe.get_all(
        "FAC Chat Message",
        filters={"session_id": session_id, "user": user, "role": "user"},
        pluck="name",
        order_by="creation asc",
        limit_page_length=0,
    )
    if not message_names:
        return []

    return frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "FAC Chat Message",
            "attached_to_name": ["in", message_names],
            "owner": user,
        },
        fields=["name", "file_name", "file_url", "file_size"],
        order_by="creation asc",
        limit_page_length=0,
    )


def _file_text(file_info) -> str:
    cache_key = f"fac_chat_file_text:{file_info.name}"
    cached = frappe.cache.get_value(cache_key)
    if cached is not None:
        return cached

    text = _extract(file_info)
    # A failed extraction is not cached, so the next turn tries again.
    if text:
        frappe.cache.set_value(cache_key, text, expires_in_sec=TEXT_CACHE_TTL)
    return text


def _extract(file_info) -> str:
    from frappe_assistant_core.plugins.data_science.tools.extract_file_content import (
        ExtractFileContent,
    )

    try:
        result = ExtractFileContent().execute({"file_url": file_info.file_url, "operation": "extract"})
    except Exception:
        frappe.log_error(title="FAC Chat file extraction", message=frappe.get_traceback())
        return ""
    return (result.get("content") or "") if result.get("success") else ""


def _describe(file_info, text: str) -> str:
    lines = [
        f"File: {file_info.file_name}",
        f"File ID: {file_info.name}",
        f"File URL: {file_info.file_url}",
        f"Size: {_human_size(file_info.file_size or 0)}",
    ]
    if text:
        lines += ["Content:", text]
    return "\n".join(lines)


def _human_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"
