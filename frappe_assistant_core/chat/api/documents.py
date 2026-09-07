# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Knowledge base / RAG document management."""

import frappe
from frappe import _

from .auth import _ar_user_id


@frappe.whitelist(methods=["GET"])
def list_documents(limit: int = 50, offset: int = 0):
    """
    List RAG documents visible to the current user.

    Returns documents with pagination and storage info.
    Visibility filtering is handled by the backend based on user_id.
    """
    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {
                "documents": [],
                "pagination": {"total": 0, "limit": int(limit), "offset": int(offset), "has_more": False},
                "storage": {
                    "quota_mb": 0,
                    "used_mb": 0,
                    "available_mb": 0,
                    "usage_percentage": 0,
                    "document_count": 0,
                },
            }

        return client.list_documents(
            limit=int(limit),
            offset=int(offset),
            user_id=_ar_user_id(frappe.session.user),
        )

    except Exception as e:
        frappe.log_error(title="FACO Knowledge Base", message=f"Error listing documents: {e!s}")
        return {"documents": [], "pagination": {"total": 0}, "storage": {}}


@frappe.whitelist(methods=["GET"])
def get_document(document_id: str | None = None):
    """Get details for a specific RAG document."""
    if not document_id:
        frappe.throw(_("document_id is required"), frappe.ValidationError)

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        return client.get_document(document_id)

    except Exception as e:
        frappe.log_error(title="FACO Knowledge Base", message=f"Error getting document: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["GET"])
def list_chunks(
    document_id: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List stored chunks for a RAG document (read-only chunk browser)."""
    if not document_id:
        frappe.throw(_("document_id is required"), frappe.ValidationError)

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"chunks": [], "total": 0, "pagination": {"total": 0}}

        return client.list_chunks(
            document_id=document_id,
            user_id=_ar_user_id(frappe.session.user),
            search=search,
            limit=int(limit),
            offset=int(offset),
        )

    except Exception as e:
        frappe.log_error(title="FACO Knowledge Base", message=f"Error listing chunks: {e!s}")
        return {"chunks": [], "total": 0, "pagination": {"total": 0}}


@frappe.whitelist(methods=["POST"])
def upload_document():
    """
    Upload a document for RAG processing.

    Any authenticated user can upload. Accepts multipart form data with
    a 'file' field plus optional 'visibility' and 'shared_with' fields.
    Supported formats: PDF, Markdown (.md), plain text (.txt).
    """
    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        file = frappe.request.files.get("file")
        if not file:
            frappe.throw(_("No file provided"), frappe.ValidationError)

        visibility = frappe.form_dict.get("visibility") or None
        shared_with = frappe.form_dict.get("shared_with") or None

        return client.upload_document(
            file_data=file.read(),
            file_name=file.filename,
            content_type=file.content_type,
            user_id=_ar_user_id(frappe.session.user),
            visibility=visibility,
            shared_with=shared_with,
        )

    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Knowledge Base", message=f"Error uploading document: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["POST"])
def delete_document(document_id: str | None = None):
    """
    Delete a RAG document.

    The backend enforces ownership — only the document owner can delete
    private/shared documents. Admins can delete public documents.
    """
    if not document_id:
        frappe.throw(_("document_id is required"), frappe.ValidationError)

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        return client.delete_document(document_id, user_id=_ar_user_id(frappe.session.user))

    except Exception as e:
        frappe.log_error(title="FACO Knowledge Base", message=f"Error deleting document: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["POST"])
def update_document_access(
    document_id: str | None = None,
    visibility: str | None = None,
    add_users: list | None = None,
    remove_users: list | None = None,
):
    """
    Update document visibility and sharing.

    Only the document owner can manage access.
    """
    if not document_id:
        frappe.throw(_("document_id is required"), frappe.ValidationError)

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        return client.update_document_access(
            document_id=document_id,
            user_id=_ar_user_id(frappe.session.user),
            visibility=visibility,
            add_users=add_users,
            remove_users=remove_users,
        )

    except Exception as e:
        frappe.log_error(title="FACO Knowledge Base", message=f"Error updating document access: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["GET"])
def get_document_content(document_id: str | None = None, download: str | None = None):
    """
    Proxy endpoint to serve document file content from AR backend.

    Bridges browser session authentication to AR's HMAC-authenticated
    content endpoint. The AR backend enforces visibility rules so only
    users with access can retrieve file content.

    Returns raw file bytes with appropriate Content-Type for inline
    preview (PDF iframe, Markdown/Text fetch) or download.
    """
    if not document_id:
        frappe.throw(_("document_id is required"), frappe.ValidationError)

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        file_bytes, content_type, filename = client.get_document_content(
            document_id=document_id,
            user_id=_ar_user_id(frappe.session.user),
        )

        frappe.local.response.filename = filename
        frappe.local.response.filecontent = file_bytes
        frappe.local.response.type = "download"
        frappe.local.response.content_type = content_type
        if download:
            frappe.local.response["display_content_as"] = "attachment"
        else:
            frappe.local.response["display_content_as"] = "inline"

    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Knowledge Base", message=f"Error serving document content: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["GET"])
def get_storage_info():
    """Get storage quota and usage for RAG documents."""
    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {
                "quota_mb": 0,
                "used_mb": 0,
                "available_mb": 0,
                "usage_percentage": 0,
                "document_count": 0,
            }

        return client.get_storage_info()

    except Exception as e:
        frappe.log_error(title="FACO Knowledge Base", message=f"Error getting storage info: {e!s}")
        return {"quota_mb": 0, "used_mb": 0, "available_mb": 0, "usage_percentage": 0, "document_count": 0}
