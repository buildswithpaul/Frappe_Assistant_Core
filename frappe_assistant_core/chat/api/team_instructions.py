# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Shared knowledge management — editable markdown document in the knowledge base."""

import frappe
from frappe import _

from .auth import _ar_user_id


@frappe.whitelist(methods=["GET"])
def get_shared_knowledge():
    """Get shared knowledge for the current tenant."""
    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {
                "content": "",
                "embedding_status": "Pending",
                "total_chunks": 0,
                "document_id": None,
            }

        return client.get_shared_knowledge()

    except Exception as e:
        frappe.log_error(title="FACO Team Notes", message=f"Error getting shared knowledge: {e!s}")
        return {"content": "", "embedding_status": "Pending", "total_chunks": 0}


@frappe.whitelist(methods=["POST"])
def update_shared_knowledge(content: str | None = None):
    """Update shared knowledge content. Admin only."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only administrators can edit team notes"), frappe.PermissionError)

    if content is None:
        content = ""

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        return client.update_shared_knowledge(content=content)

    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Team Notes", message=f"Error updating shared knowledge: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["POST"])
def share_memory_to_knowledge(memory_id: str | None = None):
    """Share a personal memory to the shared knowledge document. Any authenticated user."""
    if not memory_id:
        frappe.throw(_("memory_id is required"), frappe.ValidationError)

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        return client.share_memory_to_knowledge(user_id=_ar_user_id(frappe.session.user), memory_id=memory_id)

    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Team Notes", message=f"Error sharing memory to knowledge: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))
