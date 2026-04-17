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


class FACSkill(Document):
    def validate(self):
        """Validate skill before save."""
        self.validate_skill_id()
        self.validate_visibility_settings()
        self.validate_linked_tool()

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
