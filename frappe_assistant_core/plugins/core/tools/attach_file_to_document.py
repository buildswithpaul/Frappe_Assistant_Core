# Stergy FAC Tools - Custom tools for Frappe Assistant Core
# Copyright (C) 2026 Stergy Cleantech Private Limited
#
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0),
# to remain compatible with Frappe Assistant Core.

"""
Attach File To Document tool for Frappe Assistant Core.

Adds a missing capability to FAC: attaching a file to any existing Frappe /
ERPNext document. Supports three content sources:

    1. base64 content   -> file bytes supplied inline by the assistant
    2. existing file_url -> re-attach a file already in the File store
    3. remote source_url -> download from an http(s) URL and attach

The tool mirrors the conventions of the built-in core write tools
(create_document, update_document): it subclasses BaseTool, performs a
dynamic per-document permission check, and returns a structured result.
"""

import base64
import binascii
from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool


class AttachFileToDocument(BaseTool):
    """Attach a file to an existing Frappe document."""

    def __init__(self):
        super().__init__()
        self.name = "attach_file_to_document"
        self.description = (
            "Attach a file to an existing Frappe/ERPNext document (e.g. a Purchase "
            "Invoice, Sales Order, BOM, Quotation or any DocType). The file appears in "
            "the document's Attachments sidebar. WORKFLOW: provide the target 'doctype' "
            "and 'name', a 'file_name' (with extension), and exactly ONE content source: "
            "'content_base64' (inline base64 bytes), 'file_url' (re-attach a file already "
            "uploaded to this site), or 'source_url' (download from an http/https URL and "
            "attach). Set 'is_private' to control visibility (defaults to private). The "
            "current user must have write permission on the target document. Returns the "
            "created File record name and its file_url."
        )
        # Permission is checked dynamically against the target document below,
        # exactly as the core create_document / update_document tools do.
        self.requires_permission = None
        self.category = "write"
        self.source_app = "stergy_fac_tools"

        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {
                    "type": "string",
                    "description": "The target DocType the file should be attached to "
                    "(e.g. 'Purchase Invoice', 'Sales Order', 'BOM').",
                },
                "name": {
                    "type": "string",
                    "description": "The exact name/ID of the existing target document "
                    "(e.g. 'PINV-2026-2027-00060').",
                },
                "file_name": {
                    "type": "string",
                    "description": "File name to store, including extension "
                    "(e.g. 'gst-invoice.pdf', 'site-photo.jpg').",
                },
                "content_base64": {
                    "type": "string",
                    "description": "Base64-encoded file content. Use this to attach bytes "
                    "directly. Provide exactly one of content_base64, file_url or source_url.",
                },
                "file_url": {
                    "type": "string",
                    "description": "URL of a file already stored on this site "
                    "(e.g. '/private/files/doc.pdf' or '/files/photo.jpg'). The file is "
                    "re-attached to the target document without re-uploading its bytes.",
                },
                "source_url": {
                    "type": "string",
                    "description": "Public http(s) URL to download the file from and then "
                    "attach. Requires outbound network access from the Frappe server.",
                },
                "is_private": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether the attachment is private (visible only to users "
                    "with permission) or public. Defaults to true (private).",
                },
            },
            "required": ["doctype", "name", "file_name"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype = arguments.get("doctype")
        docname = arguments.get("name")
        file_name = arguments.get("file_name")
        content_base64 = arguments.get("content_base64")
        file_url = arguments.get("file_url")
        source_url = arguments.get("source_url")
        is_private = arguments.get("is_private", True)

        # --- 1. Exactly one content source -----------------------------------
        sources = [s for s in (content_base64, file_url, source_url) if s]
        if len(sources) == 0:
            return {
                "success": False,
                "error": "No content source provided. Supply one of: content_base64, "
                "file_url, or source_url.",
                "error_type": "missing_content_source",
            }
        if len(sources) > 1:
            return {
                "success": False,
                "error": "Multiple content sources provided. Supply exactly one of: "
                "content_base64, file_url, or source_url.",
                "error_type": "ambiguous_content_source",
            }

        # --- 2. Target document must exist -----------------------------------
        if not frappe.db.exists(doctype, docname):
            return {
                "success": False,
                "error": f"Target document not found: {doctype} '{docname}'.",
                "error_type": "document_not_found",
                "doctype": doctype,
                "name": docname,
            }

        # --- 3. Permission check (mirror core write tools) -------------------
        try:
            from frappe_assistant_core.core.security_config import validate_document_access

            validation = validate_document_access(
                user=frappe.session.user,
                doctype=doctype,
                name=docname,
                perm_type="write",
            )
            if not validation.get("success"):
                return validation
        except ImportError:
            # Fallback if FAC internals move: use the framework check directly.
            if not frappe.has_permission(doctype, "write", doc=docname):
                return {
                    "success": False,
                    "error": f"Insufficient permission to attach files to {doctype} "
                    f"'{docname}'. Write permission is required.",
                    "error_type": "permission_error",
                }

        # --- 4. Resolve content ----------------------------------------------
        content = None
        if content_base64:
            try:
                content = base64.b64decode(content_base64, validate=True)
            except (binascii.Error, ValueError) as e:
                return {
                    "success": False,
                    "error": f"content_base64 is not valid base64: {e}",
                    "error_type": "invalid_base64",
                }
        elif source_url:
            if not source_url.lower().startswith(("http://", "https://")):
                return {
                    "success": False,
                    "error": "source_url must start with http:// or https://.",
                    "error_type": "invalid_source_url",
                }
            try:
                import requests

                resp = requests.get(source_url, timeout=30)
                resp.raise_for_status()
                content = resp.content
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to download from source_url: {e}",
                    "error_type": "download_failed",
                    "suggestion": "Verify the URL is reachable and that the Frappe server "
                    "has outbound network access.",
                }

        # --- 5. Create the File record (the attachment) ----------------------
        try:
            file_payload = {
                "doctype": "File",
                "file_name": file_name,
                "attached_to_doctype": doctype,
                "attached_to_name": docname,
                "is_private": 1 if is_private else 0,
            }

            if content is not None:
                # Inline bytes or downloaded content: the File controller writes
                # the bytes to the file store and sets file_url automatically.
                file_payload["content"] = content
            else:
                # Re-attach an existing stored file by its URL. is_private is
                # inferred from the path so the new record stays consistent.
                file_payload["file_url"] = file_url
                file_payload["is_private"] = 1 if file_url.startswith("/private/") else 0

            file_doc = frappe.get_doc(file_payload)
            file_doc.insert()  # respects permissions; do NOT ignore_permissions
            frappe.db.commit()

            return {
                "success": True,
                "message": f"File '{file_doc.file_name}' attached to {doctype} '{docname}'.",
                "file": file_doc.name,
                "file_name": file_doc.file_name,
                "file_url": file_doc.file_url,
                "is_private": bool(file_doc.is_private),
                "file_size": getattr(file_doc, "file_size", None),
                "attached_to_doctype": doctype,
                "attached_to_name": docname,
            }

        except frappe.PermissionError as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "permission_error",
            }
        except Exception as e:
            frappe.log_error(
                title=_("Attach File To Document Error"),
                message=f"{doctype} {docname} / {file_name}: {str(e)}",
            )
            return {
                "success": False,
                "error": str(e),
                "error_type": "attach_failed",
                "doctype": doctype,
                "name": docname,
                "suggestion": "Confirm the file_name has a valid extension and that the "
                "target document is not cancelled/read-only.",
            }


# Class alias kept consistent with FAC discovery conventions.
attach_file_to_document = AttachFileToDocument
