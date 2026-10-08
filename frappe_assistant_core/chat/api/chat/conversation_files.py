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

import hashlib

import frappe

from .._untrusted import wrap_untrusted

# Per-file and whole-section caps on extracted text. The section rides on every turn, so one
# large PDF must not crowd out the rest of the conversation's files or the context window.
MAX_FILE_CHARS = 20_000
MAX_TOTAL_CHARS = 60_000
# Below this much remaining budget a file is listed without text rather than as a stub.
MIN_TEXT_CHARS = 500

# Extraction runs OCR on images and parses PDFs, synchronously inside the send. A file's bytes
# never change, so its text is extracted once. A file that yields no text (a photo, or a site
# without the OCR dependencies) is remembered too, for less time, so a retry stays possible.
TEXT_CACHE_TTL = 7 * 24 * 3600
NO_TEXT_CACHE_TTL = 24 * 3600

# The image types the composer accepts (ALLOWED_UPLOAD_EXTENSIONS); they reach the model as images.
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")

PREAMBLE = (
    "\n\nThe user attached the files below to their messages in this conversation. "
    "Refer to a file by its File ID when a tool needs it."
)
READ_MORE = "Read it with extract_file_content and this File ID."


def conversation_files_addendum(session_id: str, user: str) -> str:
    """The prompt section listing every file attached in the conversation, or "" if none."""
    files = _conversation_files(session_id, user)
    if not files:
        return ""

    # Oldest first, so a newly attached file never changes the text listed before it: the
    # section stays a stable prompt prefix that the provider can keep cached.
    budget = MAX_TOTAL_CHARS
    blocks = []
    for f in files:
        text = _file_text(f)
        allowance = min(MAX_FILE_CHARS, budget)
        if len(text) > allowance:
            if allowance < MIN_TEXT_CHARS:
                blocks.append(_describe(f, f"Content: not included, over the size limit. {READ_MORE}"))
                continue
            text = text[:allowance] + f"\n[Truncated. {READ_MORE}]"
        budget -= len(text)
        blocks.append(_describe(f, f"Content:\n{text}" if text else _no_text_note(f.file_name)))

    listing = "[Files attached in this conversation]\n\n" + "\n\n".join(blocks)
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

    files = frappe.get_all(
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
    # A file sent twice is one file to the model: keep its first listing, so its ID never shifts.
    first = {}
    for f in files:
        first.setdefault(f.file_url, f)
    return list(first.values())


def text_cache_key(file_name: str, file_url: str) -> str:
    # The URL is part of the key: re-pointing a File at other bytes must not serve the old text.
    url_hash = hashlib.sha1((file_url or "").encode()).hexdigest()[:12]
    return f"fac_chat_file_text:{file_name}:{url_hash}"


def _file_text(file_info) -> str:
    cache_key = text_cache_key(file_info.name, file_info.file_url)
    cached = frappe.cache.get_value(cache_key)
    if cached is not None:
        return cached["text"]

    text = _extract(file_info)
    frappe.cache.set_value(
        cache_key, {"text": text}, expires_in_sec=TEXT_CACHE_TTL if text else NO_TEXT_CACHE_TTL
    )
    return text


def _extract(file_info) -> str:
    from frappe_assistant_core.plugins.data_science.tools.extract_file_content import (
        ExtractFileContent,
    )

    # By File ID: identical bytes share a file_url, so a URL lookup can land on another
    # user's copy and fail their access check.
    try:
        result = ExtractFileContent().execute({"file_id": file_info.name, "operation": "extract"})
    except Exception:
        frappe.log_error(title="FAC Chat file extraction", message=frappe.get_traceback())
        return ""
    return (result.get("content") or "") if result.get("success") else ""


def _describe(file_info, content_line: str) -> str:
    return "\n".join(
        [
            f"File: {file_info.file_name}",
            f"File ID: {file_info.name}",
            f"File URL: {file_info.file_url}",
            f"Size: {_human_size(file_info.file_size or 0)}",
            content_line,
        ]
    )


def _no_text_note(file_name: str) -> str:
    if (file_name or "").lower().endswith(IMAGE_EXTENSIONS):
        # The image itself rides in the conversation, but a model without vision, or a
        # history window that has dropped that turn, no longer has it.
        return (
            "Content: an image, sent to you with the message it was attached to. "
            "If you can no longer see it, ask the user to attach it again."
        )
    return "Content: its text could not be extracted."


def _human_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"
