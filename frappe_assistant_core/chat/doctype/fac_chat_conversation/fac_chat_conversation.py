# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import DocType

TITLE_AUTO_LENGTH = 80


def auto_title(content: str | None) -> str:
    """A title from a message: whitespace collapsed, cut to TITLE_AUTO_LENGTH."""
    text = " ".join((content or "").split())
    if len(text) <= TITLE_AUTO_LENGTH:
        return text
    return text[: TITLE_AUTO_LENGTH - 1].rstrip() + "…"


class FACChatConversation(Document):
    @staticmethod
    def default_title(session_id: str) -> str:
        first = frappe.get_all(
            "FAC Chat Message",
            filters={"session_id": session_id, "role": "user"},
            fields=["content"],
            order_by="creation asc",
            limit_page_length=1,
        )
        return auto_title(first[0].content) if first else ""

    @staticmethod
    def owned(session_id: str, user: str | None = None) -> frappe._dict:
        """The caller's conversation. Missing and someone else's raise the same error."""
        row = frappe.db.get_value(
            "FAC Chat Conversation",
            session_id,
            ["name", "user", "project", "title", "title_is_custom"],
            as_dict=True,
        )
        if not row or row.user != (user or frappe.session.user):
            frappe.throw(_("Conversation not found"), frappe.DoesNotExistError)
        return row

    @staticmethod
    def touch(
        session_id: str,
        user: str,
        role: str,
        content: str | None,
        project: str | None = None,
        is_archived: int = 0,
    ) -> None:
        """Record one more message on the conversation, creating the row on the first.

        Every FAC Chat Message insert lands here (after_insert), so the SPA, the Desk
        widget, mobile and the relay all keep the row current without knowing about it.
        """
        now = frappe.utils.now()
        existing = frappe.db.get_value(
            "FAC Chat Conversation", session_id, ["user", "title", "project"], as_dict=True
        )
        if existing and existing.user != user:
            return
        if not existing:
            if project and not _project_is_owned(project, user):
                project = None
            try:
                frappe.get_doc(
                    {
                        "doctype": "FAC Chat Conversation",
                        "session_id": session_id,
                        "user": user,
                        "title": auto_title(content) if role == "user" else "",
                        "project": project,
                        "started": now,
                        "last_activity": now,
                        "message_count": 1,
                        "is_archived": is_archived,
                    }
                ).insert(ignore_permissions=True)
            except frappe.DuplicateEntryError:
                # A concurrent writer created it between our read and insert.
                existing = frappe._dict(user=user, title=None, project=None)
            else:
                _bump_project(project, now)
                return

        CV = DocType("FAC Chat Conversation")
        (
            frappe.qb.update(CV)
            .set(CV.last_activity, now)
            .set(CV.message_count, CV.message_count + 1)
            .where(CV.name == session_id)
        ).run()
        if role == "user" and not existing.title:
            frappe.db.set_value(
                "FAC Chat Conversation", session_id, "title", auto_title(content), update_modified=False
            )
        _bump_project(existing.project, now)


def _project_is_owned(project: str, user: str) -> bool:
    from frappe_assistant_core.chat.doctype.fac_chat_project.fac_chat_project import FACChatProject

    return FACChatProject.is_owned(project, user)


def _bump_project(project: str | None, now: str) -> None:
    if project:
        frappe.db.set_value("FAC Chat Project", project, "last_activity", now, update_modified=False)
