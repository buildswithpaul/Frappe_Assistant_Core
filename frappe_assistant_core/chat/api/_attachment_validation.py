# Frappe Assistant Core - Ticket Attachment Validation
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Pure-logic validator for support-ticket attachments (images + PDF, <=10MB).

Mirrors the hardened extension -> MIME -> magic-byte logic of
`chat/api/settings/uploads.py`, narrowed to the ticket allowlist so the
FAC support proxy can validate before forwarding to the SDK.
"""

from __future__ import annotations

import os

import frappe
from frappe import _
from werkzeug.utils import secure_filename

TICKET_MAX_SIZE = 10 * 1024 * 1024  # 10MB

TICKET_ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
TICKET_ALLOWED_MIMETYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
}
_EXT_TO_MIME = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _magic_bytes_match(content: bytes, claimed_mime: str) -> bool:
    head = content[:12]
    if claimed_mime == "application/pdf":
        return head.startswith(b"%PDF-")
    if claimed_mime == "image/png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if claimed_mime in ("image/jpeg", "image/jpg"):
        return head.startswith(b"\xff\xd8\xff")
    if claimed_mime == "image/gif":
        return head.startswith((b"GIF87a", b"GIF89a"))
    if claimed_mime == "image/webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    return False


def _sanitize_filename(original: str) -> str:
    _, original_ext = os.path.splitext(original or "")
    original_ext_lower = original_ext.lower()
    safe = secure_filename(original or "")
    if not safe:
        safe = f"attachment_{frappe.generate_hash(length=8)}"
    if original_ext_lower in TICKET_ALLOWED_EXTENSIONS:
        _, safe_ext = os.path.splitext(safe)
        if not safe_ext:
            safe = f"{safe}{original_ext_lower}"
    if len(safe) > 100:
        stem, ext = os.path.splitext(safe)
        keep = max(1, 100 - len(ext))
        safe = f"{stem[:keep]}{ext}"
    return safe


def is_ticket_image(filename: str, mime_type: str = "") -> bool:
    ext = os.path.splitext((filename or "").lower())[1]
    return ext in _IMAGE_EXTENSIONS or (mime_type or "").lower().startswith("image/")


def validate_ticket_attachment(content: bytes, filename: str, mime_type: str) -> tuple[str, str]:
    """Validate raw bytes for a ticket attachment.

    Returns (sanitized_filename, canonical_mime). Raises frappe.ValidationError
    on any failure (size, extension, MIME, or magic-byte mismatch).
    """
    if not content:
        frappe.throw(_("No file uploaded"), frappe.ValidationError)

    if len(content) > TICKET_MAX_SIZE:
        frappe.throw(_("File size exceeds 10MB limit"), frappe.ValidationError)

    if not filename or len(filename) > 255:
        frappe.throw(_("Invalid filename: must be 1-255 characters"), frappe.ValidationError)

    _stem, raw_ext = os.path.splitext(filename)
    raw_ext_lower = raw_ext.lower()
    if raw_ext_lower not in TICKET_ALLOWED_EXTENSIONS:
        frappe.throw(
            _("File type not allowed: {0}").format(raw_ext or _("(no extension)")),
            frappe.ValidationError,
        )

    declared_mime = (mime_type or "").strip().lower()
    if declared_mime not in TICKET_ALLOWED_MIMETYPES:
        fallback = _EXT_TO_MIME.get(raw_ext_lower)
        if fallback:
            declared_mime = fallback
        else:
            frappe.throw(
                _("File type not allowed: {0}").format(mime_type or _("(unknown)")),
                frappe.ValidationError,
            )

    if not _magic_bytes_match(content, declared_mime):
        frappe.throw(_("File content does not match declared type"), frappe.ValidationError)

    return _sanitize_filename(filename), declared_mime
