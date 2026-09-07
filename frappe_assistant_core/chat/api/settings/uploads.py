# Frappe Assistant Core - Message-File Upload API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""File upload endpoint for FACO chat attachments + the FACO-H11 validators.

Supports two input modes:
- Multipart FormData (web app)
- Base64 JSON payload (mobile app — avoids CSRF issues with FormData)
"""

from __future__ import annotations

import base64
import os

import frappe
from frappe import _
from werkzeug.utils import secure_filename

from .._rate_limits import (
    rate_limit,
    session_user_or_ip,
)

# --- FACO-H11: upload validation allowlists ------------------------------------
# Explicit extension / MIME whitelist for `upload_message_file`. Any file whose
# extension or claimed MIME falls outside these sets is rejected outright.
ALLOWED_UPLOAD_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".md",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".csv",
    ".json",
    ".xml",
}
ALLOWED_UPLOAD_MIMETYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
    "text/xml",
    "application/json",
    "application/xml",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
}

# Extension -> canonical MIME used when the client-supplied content-type is
# missing or obviously wrong (e.g. "application/octet-stream"). This lets us
# still run the magic-byte check against a sensible declared type.
_EXT_TO_MIME = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
    ".xml": "application/xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _magic_bytes_match(content: bytes, claimed_mime: str) -> bool:
    """
    Lightweight magic-byte verification for binary formats. Text-based formats
    (json/xml/csv/md/plain) are accepted without inspection since their first
    bytes are not stable.
    """
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
    # text/json/xml/csv/md — accept without magic check
    return True


def _sanitize_upload_filename(original_filename: str) -> str:
    """
    Run `secure_filename` while preserving the original (allowlisted) extension
    and capping total length at 100 characters. Falls back to a generated name
    if sanitization strips everything.
    """
    _, original_ext = os.path.splitext(original_filename or "")
    original_ext_lower = original_ext.lower()

    safe_name = secure_filename(original_filename or "")
    if not safe_name:
        safe_name = f"upload_{frappe.generate_hash(length=8)}"

    # Preserve the original extension if it was in the allowlist but got
    # stripped (e.g. because the stem was entirely non-ascii).
    if original_ext_lower in ALLOWED_UPLOAD_EXTENSIONS:
        _, safe_ext = os.path.splitext(safe_name)
        if not safe_ext:
            safe_name = f"{safe_name}{original_ext_lower}"

    # Cap final length at 100 chars, preserving extension.
    if len(safe_name) > 100:
        stem, ext = os.path.splitext(safe_name)
        # Guarantee at least one char of stem remains.
        keep = max(1, 100 - len(ext))
        safe_name = f"{stem[:keep]}{ext}"

    return safe_name


@frappe.whitelist(methods=["POST"])
@rate_limit(session_user_or_ip, limit=10, seconds=60)
def upload_message_file(
    file_data: str | None = None,
    file_name: str | None = None,
    content_type: str | None = None,
    is_private: int = 1,
) -> dict:
    """
    Upload a file for FACO message attachment.

    Supports two input modes:
      1. Multipart FormData (web app) — file in request.files['file']
      2. Base64 JSON payload (mobile app) — file_data, file_name, content_type as params

    For images, also returns base64-encoded data for vision API support.
    """
    # Local import avoids the package-init circular reference back to access.py
    # (access.py → settings.billing → quota → may pull settings package).
    from ..settings.access import can_use_faco

    try:
        access_check = can_use_faco()
        if not access_check.get("can_use"):
            frappe.throw(access_check.get("reason", _("Cannot use FACO")))

        # Path 1: Standard multipart FormData (web app)
        files = frappe.request.files if frappe.request else None
        if files and "file" in files:
            file = files["file"]
            content = file.read()
            filename = file.filename
            mime_type = file.mimetype or ""
        # Path 2: Base64 JSON payload (mobile app — avoids CSRF issues with FormData)
        elif file_data:
            import base64 as b64

            content = b64.b64decode(file_data)
            filename = file_name or "upload"
            mime_type = content_type or ""
        else:
            frappe.throw(_("No file uploaded"))

        file_size = len(content)

        max_size = 50 * 1024 * 1024  # 50MB
        if file_size > max_size:
            frappe.throw(_("File size exceeds 50MB limit"), frappe.ValidationError)

        # --- FACO-H11: filename, extension, MIME, and magic-byte validation -----
        # 1. Filename length cap BEFORE sanitization (pre-sanitized >255 rejected).
        if not filename or len(filename) > 255:
            frappe.throw(
                _("Invalid filename: must be 1-255 characters"),
                frappe.ValidationError,
            )

        # 2. Extension allowlist (checked against the pre-sanitized name so that
        #    `secure_filename` cannot silently drop a bad extension and let us
        #    through). Use `_stem` instead of `_` because `_` is bound to
        #    frappe's translator in this module — rebinding it locally would
        #    shadow earlier/later `_("...")` calls in the same function.
        _stem, raw_ext = os.path.splitext(filename)
        raw_ext_lower = raw_ext.lower()
        if raw_ext_lower not in ALLOWED_UPLOAD_EXTENSIONS:
            frappe.throw(
                _("File type not allowed: {0}").format(raw_ext or _("(no extension)")),
                frappe.ValidationError,
            )

        # 3. MIME allowlist. Browsers and mobile clients sometimes send
        #    "application/octet-stream" or an empty string; fall back to the
        #    extension-derived canonical MIME so we can still magic-check it.
        declared_mime = (mime_type or "").strip().lower()
        if declared_mime not in ALLOWED_UPLOAD_MIMETYPES:
            fallback_mime = _EXT_TO_MIME.get(raw_ext_lower)
            if fallback_mime:
                declared_mime = fallback_mime
            else:
                frappe.throw(
                    _("File type not allowed: {0}").format(mime_type or _("(unknown)")),
                    frappe.ValidationError,
                )

        # 4. Magic-byte sanity check — claimed MIME must match first bytes for
        #    binary formats. Text formats pass through.
        if not _magic_bytes_match(content, declared_mime):
            frappe.throw(
                _("File content does not match declared type"),
                frappe.ValidationError,
            )

        # 5. Sanitize filename (werkzeug) and cap to 100 chars while keeping ext.
        filename = _sanitize_upload_filename(filename)
        # Keep the validated MIME going forward.
        mime_type = declared_mime

        # `fac_pending_chat_attachment` marks the file as uploaded-but-not-sent.
        # Uploads fire on file selection, so a user who attaches and then walks
        # away would otherwise leave a private File behind forever. The flag is
        # cleared in `send_message` and swept after 24h if it never is.
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": filename,
                "content": content,
                "is_private": 1,
                "folder": "Home/Attachments",
                "fac_pending_chat_attachment": 1,
            }
        )
        file_doc.save(ignore_permissions=True)

        # Determine file type and format
        filename_lower = filename.lower()
        mime_type = mime_type or ""

        # Check if it's an image (for vision API)
        image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
        is_image = any(filename_lower.endswith(ext) for ext in image_extensions) or mime_type.startswith(
            "image/"
        )

        # Determine format from extension or mime type
        if filename_lower.endswith(".png"):
            file_format = "png"
        elif filename_lower.endswith(".jpg") or filename_lower.endswith(".jpeg"):
            file_format = "jpeg"
        elif filename_lower.endswith(".gif"):
            file_format = "gif"
        elif filename_lower.endswith(".webp"):
            file_format = "webp"
        elif filename_lower.endswith(".pdf"):
            file_format = "pdf"
        elif filename_lower.endswith(".txt"):
            file_format = "txt"
        else:
            file_format = filename_lower.split(".")[-1] if "." in filename_lower else "unknown"

        response = {
            "success": True,
            "file": {
                "name": file_doc.name,
                "file_name": file_doc.file_name,
                "file_url": file_doc.file_url,
                "file_size": file_size,
                "is_private": file_doc.is_private,
                "format": file_format,
                "type": "image" if is_image else "document",
            },
        }

        # For images under 10MB, include base64 for vision API
        max_vision_size = 10 * 1024 * 1024  # 10MB limit for vision API
        if is_image and file_size <= max_vision_size:
            response["file"]["base64_data"] = base64.b64encode(content).decode("utf-8")

        return response

    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO File Upload Error", message=f"Error uploading file: {e!s}")
        frappe.throw(_("Error uploading file: {0}").format(str(e)))
