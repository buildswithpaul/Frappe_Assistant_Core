# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

TITLE_MAX_LENGTH = 140
INSTRUCTIONS_MAX_LENGTH = 8000


class FACChatProject(Document):
    def before_insert(self):
        if not self.user:
            self.user = frappe.session.user

    def validate(self):
        self.title = " ".join((self.title or "").split())
        if not self.title:
            frappe.throw(_("Project title is required"))
        if len(self.title) > TITLE_MAX_LENGTH:
            frappe.throw(_("Project title must be {0} characters or fewer").format(TITLE_MAX_LENGTH))
        self.instructions = (self.instructions or "").strip()
        if len(self.instructions) > INSTRUCTIONS_MAX_LENGTH:
            frappe.throw(
                _("Project instructions must be {0} characters or fewer").format(INSTRUCTIONS_MAX_LENGTH)
            )

    @staticmethod
    def owned(project: str, user: str | None = None) -> FACChatProject:
        """The caller's project. Missing and someone else's raise the same error, so a
        name never reveals that another user's project exists."""
        user = user or frappe.session.user
        owner = frappe.db.get_value("FAC Chat Project", project, "user") if project else None
        if owner != user:
            frappe.throw(_("Project not found"), frappe.DoesNotExistError)
        return frappe.get_doc("FAC Chat Project", project)

    @staticmethod
    def is_owned(project: str | None, user: str | None = None) -> bool:
        if not project:
            return False
        return frappe.db.get_value("FAC Chat Project", project, "user") == (user or frappe.session.user)


def project_addendum(project: str | None) -> str | None:
    """The project's instructions as a system-prompt block, or None when there are none.

    A title alone is not worth the tokens, so a project without instructions adds nothing.
    """
    if not project:
        return None
    row = frappe.db.get_value("FAC Chat Project", project, ["title", "instructions"], as_dict=True)
    instructions = (row.instructions or "").strip() if row else ""
    if not instructions:
        return None
    return (
        f"\n\n## Project: {row.title}\n"
        "The user is working inside this project. Follow these project instructions:\n"
        f"{instructions}\n"
    )
