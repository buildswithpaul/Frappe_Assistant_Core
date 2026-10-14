# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""User memory management — view and delete AI-extracted memories."""

import frappe
from frappe import _

from frappe_assistant_core.chat.api.chat.projects import project_memory_enabled
from frappe_assistant_core.chat.doctype.fac_chat_project.fac_chat_project import FACChatProject

from .auth import _ar_user_id


def _require_project_memory(project: str) -> None:
    """Own the project, and refuse when AR would silently ignore project_id (older AR)."""
    FACChatProject.owned(project)
    if not project_memory_enabled():
        frappe.throw(_("Project memory isn't available on this FAC Cloud"), frappe.ValidationError)


@frappe.whitelist(methods=["GET"])
def list_memories(
    memory_type: str | None = None, limit: int = 50, offset: int = 0, project: str | None = None
):
    """
    List memories for the current user, or only those of one of their projects.

    Returns memories with pagination.
    """
    if project:
        _require_project_memory(project)
    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return {
                "memories": [],
                "pagination": {"total": 0, "limit": int(limit), "offset": int(offset), "has_more": False},
            }

        kwargs = {"project_id": project} if project else {}
        return client.list_memories(
            user_id=_ar_user_id(frappe.session.user),
            memory_type=memory_type,
            limit=int(limit),
            offset=int(offset),
            **kwargs,
        )

    except Exception as e:
        frappe.log_error(title="FACO Memories", message=f"Error listing memories: {e!s}")
        if project:
            # An empty list would read as "nothing remembered"; the project page offers Retry.
            frappe.throw(_("Couldn't load this project's memories; try again"))
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
def clear_project_memories(project: str):
    """Delete every memory stored for one of the current user's projects."""
    _require_project_memory(project)

    from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

    client = get_fac_cloud_client()
    if not client:
        frappe.throw(_("Not connected to FAC Cloud"))

    try:
        return client.delete_project_memories(user_id=_ar_user_id(frappe.session.user), project_id=project)
    except Exception as e:
        frappe.log_error(title="FACO Memories", message=f"Error clearing project memories: {e!s}")
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
