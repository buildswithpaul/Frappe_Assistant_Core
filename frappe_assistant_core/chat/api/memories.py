# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""User memory management — view and delete AI-extracted memories."""

import frappe
from frappe import _

from .auth import _ar_user_id


@frappe.whitelist(methods=["GET"])
def list_memories(memory_type: str | None = None, limit: int = 50, offset: int = 0):
    """
    List memories for the current user.

    Returns memories with pagination.
    """
    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {
                "memories": [],
                "pagination": {"total": 0, "limit": int(limit), "offset": int(offset), "has_more": False},
            }

        return client.list_memories(
            user_id=_ar_user_id(frappe.session.user),
            memory_type=memory_type,
            limit=int(limit),
            offset=int(offset),
        )

    except Exception as e:
        frappe.log_error(title="FACO Memories", message=f"Error listing memories: {e!s}")
        return {"memories": [], "pagination": {"total": 0}}


@frappe.whitelist(methods=["POST"])
def delete_memory(memory_id: str | None = None):
    """Delete a single memory for the current user."""
    if not memory_id:
        frappe.throw(_("memory_id is required"), frappe.ValidationError)

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        return client.delete_memory(user_id=_ar_user_id(frappe.session.user), memory_id=memory_id)

    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Memories", message=f"Error deleting memory: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["POST"])
def update_memory(memory_id: str | None = None, content: str | None = None):
    """Update a memory's content for the current user."""
    if not memory_id:
        frappe.throw(_("memory_id is required"), frappe.ValidationError)
    if not content or not content.strip():
        frappe.throw(_("content is required"), frappe.ValidationError)

    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        return client.update_memory(
            user_id=_ar_user_id(frappe.session.user),
            memory_id=memory_id,
            content=content.strip(),
        )

    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Memories", message=f"Error updating memory: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["POST"])
def delete_all_memories():
    """Delete all memories for the current user."""
    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            frappe.throw(_("Not connected to FAC Cloud"))

        return client.delete_all_memories(user_id=_ar_user_id(frappe.session.user))

    except Exception as e:
        frappe.log_error(title="FACO Memories", message=f"Error deleting all memories: {e!s}")
        frappe.throw(_("Error: {0}").format(str(e)))


@frappe.whitelist(methods=["GET"])
def get_memory_stats():
    """Get memory statistics for the current user."""
    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {"total": 0, "by_type": {"preference": 0, "summary": 0, "fact": 0}, "total_accesses": 0}

        return client.get_memory_stats(user_id=_ar_user_id(frappe.session.user))

    except Exception as e:
        frappe.log_error(title="FACO Memories", message=f"Error getting memory stats: {e!s}")
        return {"total": 0, "by_type": {"preference": 0, "summary": 0, "fact": 0}, "total_accesses": 0}


@frappe.whitelist(methods=["GET"])
def get_memory_summary(force: bool = False):
    """Get AI-generated narrative summary of user's memories."""
    from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

    client = get_fac_cloud_client()
    if not client:
        return None

    force_bool = force in (True, "true", "1", 1)
    return client.get_memory_summary(user_id=_ar_user_id(frappe.session.user), force=force_bool)
