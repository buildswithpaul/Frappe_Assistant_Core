# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Skill DocType controller.
Handles validation and lifecycle management for skills.
"""

import re
from typing import Any, Dict, List

import frappe
from frappe import _
from frappe.model.document import Document

from frappe_assistant_core.utils.permissions import check_assistant_admin_permission

#: Fields an admin implicitly signs off on when publishing a skill beyond its
#: owner. The LLM consumes ``content`` as instructions and ``description`` as the
#: replace-mode tool description, and ``linked_tool`` decides which tool those
#: instructions are attached to — so all of them are part of the approval, not
#: incidental metadata. Ref: security issue #239.
APPROVED_CONTENT_FIELDS = ("title", "description", "content", "linked_tool")

#: Visibility values that expose a Published skill to users other than its owner.
EXPOSED_VISIBILITIES = ("Shared", "Public")


class FACSkill(Document):
    def validate(self):
        """Validate skill before save."""
        self.validate_skill_id()
        self.validate_visibility_settings()
        self.validate_linked_tool()
        self.validate_publish_permission()

    def validate_publish_permission(self):
        """
        Only System Manager / Assistant Admin may create or transition a skill
        into a Published status or a Shared/Public visibility. Non-admins are
        restricted to Draft + Private. Ref: security issue #225 — without this
        gate any Desk User could publish agent-instruction content org-wide.
        """
        if check_assistant_admin_permission():
            return

        if self.is_new():
            if self.status != "Draft" or self.visibility != "Private":
                frappe.throw(
                    _(
                        "Only an Assistant Admin or System Manager can create a skill that is not Draft/Private"
                    ),
                    frappe.PermissionError,
                )
            self.validate_is_system_flag()
            return

        status_elevated = self.has_value_changed("status") and self.status == "Published"
        visibility_elevated = self.has_value_changed("visibility") and self.visibility in EXPOSED_VISIBILITIES
        if status_elevated or visibility_elevated:
            frappe.throw(
                _("Only an Assistant Admin or System Manager can publish or share this skill"),
                frappe.PermissionError,
            )

        self.validate_is_system_flag()
        self.validate_approved_content_unchanged()

    def validate_is_system_flag(self):
        """
        Block non-admins from marking a skill as app-shipped.

        ``is_system`` is ``read_only`` on the form, but Frappe does not enforce
        docfield read-only server-side — ``frappe.client.set_value`` and friends
        write it happily. A user-set flag would take top precedence in
        ``get_tool_skill_map()`` and make the row undeletable via ``on_trash``.
        Ref: security issue #239.
        """
        if not self.is_system:
            return

        if self.is_new() or self.has_value_changed("is_system"):
            frappe.throw(
                _("Only an Assistant Admin or System Manager can mark a skill as a system skill"),
                frappe.PermissionError,
            )

    def validate_approved_content_unchanged(self):
        """
        Freeze the approved payload of a skill that is published beyond its owner.

        The #225 gate only guards the status/visibility *transition*, which left
        the content that transition authorizes editable by a non-admin owner: an
        admin publishes a reviewed draft, the owner then rewrites ``content`` (served
        verbatim through ``resources/read``) or repoints ``linked_tool`` at another
        tool, and the approval no longer describes what ships. Ref: issue #239.

        De-escalation stays open — this checks the *post-change* status and
        visibility, so setting the skill back to Draft or Private in the same save
        as a content edit is allowed. The result is no longer exposed to anyone
        else, and re-publishing still needs an admin.
        """
        if self.status != "Published" or self.visibility not in EXPOSED_VISIBILITIES:
            return

        changed = [f for f in APPROVED_CONTENT_FIELDS if self.has_value_changed(f)]
        if self.shared_roles_changed():
            changed.append("shared_with_roles")

        if not changed:
            return

        frappe.throw(
            _(
                "This skill is published to other users, so only an Assistant Admin or "
                "System Manager can change {0}. Set the status back to Draft (or the "
                "visibility to Private) first, or ask an admin to make the change."
            ).format(", ".join(self.meta.get_label(f) or f for f in changed)),
            frappe.PermissionError,
        )

    def shared_roles_changed(self) -> bool:
        """
        True when the ``shared_with_roles`` role set differs from what is stored.

        Compares role names rather than delegating to ``has_value_changed``, which
        compares child-row objects and would report a change on every save. Widening
        this table lets a non-admin owner hand a Published + Shared skill to
        privileged roles without touching ``visibility``.
        """
        previous = self.get_doc_before_save()
        if not previous:
            # Unknown baseline — fail closed. Only reachable for a non-admin on an
            # already-exposed skill, where refusing the save is the safe answer.
            return True

        before = {r.role for r in (previous.get("shared_with_roles") or [])}
        after = {r.role for r in (self.get("shared_with_roles") or [])}
        return before != after

    def validate_skill_id(self):
        """Ensure skill_id is URL-safe and unique."""
        if not self.skill_id:
            frappe.throw(_("Skill ID is required"))

        if not re.match(r"^[a-z0-9_-]+$", self.skill_id):
            frappe.throw(_("Skill ID must contain only lowercase letters, numbers, underscores, and hyphens"))

        existing = frappe.db.get_value(
            "FAC Skill", {"skill_id": self.skill_id, "name": ["!=", self.name or ""]}, "name"
        )
        if existing:
            frappe.throw(_("Skill ID '{0}' already exists").format(self.skill_id))

    def validate_visibility_settings(self):
        """Validate visibility and sharing configuration."""
        if self.visibility == "Shared" and not self.shared_with_roles:
            frappe.throw(_("Please specify roles to share with when visibility is 'Shared'"))

    def validate_linked_tool(self):
        """Validate linked_tool is set for Tool Usage skills."""
        if self.skill_type == "Tool Usage" and not self.linked_tool:
            frappe.msgprint(
                _("Consider linking a tool name for Tool Usage skills"),
                indicator="orange",
            )

    def on_update(self):
        """Clear caches after update."""
        self.clear_skill_cache()

    def on_trash(self):
        """
        Prevent deletion of system skills unless one of:
        - ``allow_system_delete`` flag is set (internal lifecycle code), or
        - the owning ``source_app`` is no longer installed (orphan cleanup).
        """
        if self.is_system and not self.flags.get("allow_system_delete"):
            if not self._source_app_is_orphaned():
                frappe.throw(_("System skills cannot be deleted"))
        self.clear_skill_cache()

    def _source_app_is_orphaned(self) -> bool:
        """True when source_app is set and that app is no longer installed."""
        if not self.source_app:
            return False
        try:
            return self.source_app not in frappe.get_installed_apps()
        except Exception:
            return False

    def clear_skill_cache(self):
        """Clear skill-related caches."""
        frappe.cache.hdel("skills", frappe.local.site)
