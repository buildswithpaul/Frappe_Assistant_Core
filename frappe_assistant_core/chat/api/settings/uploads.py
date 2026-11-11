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
import io
import os
import zipfile

import frappe
from frappe import _
from frappe.core.api.file import get_max_file_size
from frappe.utils import cint
from werkzeug.utils import secure_filename

from .._rate_limits import (
    rate_limit,
    session_user_or_ip,
)

# Chat attachments never exceed this, even on a site that allows larger uploads.
CHAT_UPLOAD_MAX_BYTES = 50 * 1024 * 1024


def _chat_upload_limit() -> int:
    """
    The largest chat attachment this site accepts. Frappe's File rejects anything over
    System Settings → Max File Size (25 MB unless an administrator changed it), so
    checking against that here lets us say how to raise it instead of failing in save.
    Frappe also refuses any request but its own upload_file over the site config's
    max_file_size (25 MB unset) before this code runs (#33987), so that is a limit too.
    """
    request_limit = cint(frappe.conf.get("max_file_size")) or 25 * 1024 * 1024
    return min(CHAT_UPLOAD_MAX_BYTES, get_max_file_size(), request_limit)


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
    ".xlsx",
    ".xls",
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
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
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
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
}


def _magic_bytes_match(content: bytes, claimed_mime: str) -> bool:
    """
    Lightweight magic-byte verification for binary formats. Text-based formats
    (json/xml/csv/md/plain) have no stable first bytes, so they are only
    checked for NUL bytes, which mark binary content.
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
    if claimed_mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        # Every OOXML file (and any plain .zip) starts with PK\x03\x04, so also
        # require the workbook part. Only the central directory is read here.
        if not head.startswith(b"PK\x03\x04"):
            return False
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                return "xl/workbook.xml" in zf.namelist()
        except zipfile.BadZipFile:
            return False
    if claimed_mime == "application/vnd.ms-excel":
        return head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    # text/json/xml/csv/md — no signature, but a NUL in the first 8 KB means
    # binary. UTF-16 text (e.g. Excel's "Unicode Text" export) is full of NULs,
    # so after a UTF-16 BOM the first 8 KB must read as UTF-16 text instead (#34404).
    if content.startswith((b"\xff\xfe", b"\xfe\xff")):
        return _reads_as_utf16_text(content[:8192])
    return b"\x00" not in content[:8192]


def _reads_as_utf16_text(head: bytes) -> bool:
    """Whether ``head`` (BOM first) decodes as UTF-16 with no control character but tab and line ends.
    The sample's cut may split a character in two at its end, so that last half is let go."""
    even = head[: len(head) - len(head) % 2]
    for sample in (even, even[:-2]):
        try:
            text = sample.decode("utf-16")
        except UnicodeDecodeError:
            continue
        return not any(ord(c) < 32 and c not in "\t\r\n" for c in text)
    return False


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

        max_size = _chat_upload_limit()
        if file_size > max_size:
            if max_size < CHAT_UPLOAD_MAX_BYTES:
                frappe.throw(
                    _(
                        "File is larger than this site's {0} MB upload limit. An administrator "
                        "can raise it (up to 50 MB) in System Settings → Max File Size and the "
                        "site config's max_file_size."
                    ).format(f"{max_size / 1048576:g}"),
                    frappe.ValidationError,
                )
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
        #    Also fall back when the declared MIME disagrees with the extension:
        #    Windows browsers label .csv as "application/vnd.ms-excel", and a
        #    text MIME on a binary extension would otherwise skip step 4.
        declared_mime = (mime_type or "").strip().lower()
        expected_mime = _EXT_TO_MIME.get(raw_ext_lower)
        if declared_mime not in ALLOWED_UPLOAD_MIMETYPES or declared_mime != expected_mime:
            fallback_mime = expected_mime
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
                _("File content does not match its extension: {0}").format(raw_ext_lower),
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
