# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Projects: a user's named groups of conversations, with instructions the model follows."""

from __future__ import annotations

import frappe
from frappe.query_builder.functions import Count

from frappe_assistant_core.chat.doctype.fac_chat_project.fac_chat_project import FACChatProject

_FIELDS = ("name", "title", "instructions", "last_activity")
PROJECT_LIST_LIMIT = 500


def _as_row(doc) -> dict:
    return {key: doc.get(key) for key in _FIELDS}


@frappe.whitelist(methods=["GET"])
def get_projects() -> list:
    """The caller's projects, most recently active first, with live conversation counts."""
    user = frappe.session.user
    projects = frappe.get_list(
        "FAC Chat Project",
        filters={"user": user},
        fields=list(_FIELDS),
        order_by="last_activity desc, creation desc, name desc",
        limit_page_length=PROJECT_LIST_LIMIT,
    )
    if not projects:
        return []
    CV = frappe.qb.DocType("FAC Chat Conversation")
    counts = dict(
        (
            frappe.qb.from_(CV)
            .select(CV.project, Count(CV.name))
            .where(CV.user == user)
            .where(CV.is_archived == 0)
            .where(CV.project.isin([p.name for p in projects]))
            .groupby(CV.project)
        ).run()
    )
    for project in projects:
        project["conversation_count"] = counts.get(project.name, 0)
    return projects


@frappe.whitelist(methods=["POST"])
def create_project(title: str, instructions: str = "") -> dict:
    doc = frappe.get_doc(
        {
            "doctype": "FAC Chat Project",
            "user": frappe.session.user,
            "title": title,
            "instructions": instructions,
            "last_activity": frappe.utils.now(),
        }
    ).insert()
    return {**_as_row(doc), "conversation_count": 0}


@frappe.whitelist(methods=["POST"])
def update_project(project: str, title: str | None = None, instructions: str | None = None) -> dict:
    """None leaves a field as it is; an empty string clears the instructions."""
    doc = FACChatProject.owned(project)
    if title is not None:
        doc.title = title
    if instructions is not None:
        doc.instructions = instructions
    doc.save(ignore_permissions=True)  # ownership checked by owned()
    return _as_row(doc)


@frappe.whitelist(methods=["POST"])
def delete_project(project: str) -> dict:
    """Delete a project. Its conversations stay, moved out to "no project"."""
    FACChatProject.owned(project)
    frappe.db.set_value(
        "FAC Chat Conversation",
        {"project": project, "user": frappe.session.user},
        "project",
        None,
        update_modified=False,
    )
    frappe.delete_doc("FAC Chat Project", project, ignore_permissions=True)
    return {"success": True}
