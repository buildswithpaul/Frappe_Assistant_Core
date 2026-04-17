# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Resources handlers for MCP protocol - Skill-based implementation.
Handles resources/list and resources/read requests backed by the Skill DocType.
"""

import re
from typing import Any, Dict, List, Optional

import frappe
from frappe import _

from frappe_assistant_core.utils.logger import api_logger

_SKILL_URI_PREFIX = "fac://skills/"
_SKILL_ID_RE = re.compile(r"^[a-z0-9_-]+$")


class SkillManager:
    """
    Stateless helper for skill queries, filtering, and permission checks.
    Construct per call — no shared state across requests.
    """

    _LIST_FIELDS = (
        "name",
        "skill_id",
        "title",
        "description",
        "status",
        "skill_type",
        "linked_tool",
        "category",
        "owner_user",
        "visibility",
        "is_system",
    )

    def get_user_accessible_skills(self, user: str = None) -> List[Dict[str, Any]]:
        """
        Return all skills accessible to ``user``. A skill is accessible when:

        - the user owns it (any status), OR
        - it is Published AND one of: Public, is_system, or Shared with a role
          the user has.

        Results are deduplicated by ``skill_id``.
        """
        user = user or frappe.session.user
        user_roles = frappe.get_roles(user)

        # Single OR-filter covers own skills (any status) + published public/system.
        base = frappe.get_all(
            "FAC Skill",
            filters={},
            or_filters=[
                ["owner_user", "=", user],
                ["visibility", "=", "Public"],
                ["is_system", "=", 1],
            ],
            fields=list(self._LIST_FIELDS),
        )

        # The or_filter doesn't express "status must be Published unless owner".
        # Filter that in Python (cheap — result set is already scoped).
        skills = [s for s in base if s.owner_user == user or s.status == "Published"]

        # Add Shared-with-role skills (requires a join against Has Role).
        if user_roles:
            shared = self._get_shared_skills_for_user(user, user_roles)
            seen = {s.skill_id for s in skills}
            for s in shared:
                if s.skill_id not in seen:
                    skills.append(s)
                    seen.add(s.skill_id)

        # Dedup (own skill may also be Public/system).
        deduped: List[Dict[str, Any]] = []
        seen_ids = set()
        for s in skills:
            if s.skill_id in seen_ids:
                continue
            seen_ids.add(s.skill_id)
            deduped.append(s)
        return deduped

    def _get_shared_skills_for_user(self, user: str, user_roles: List[str]) -> List[Dict]:
        """Skills shared with roles the user has (Published only)."""
        try:
            return frappe.db.sql(
                """
                SELECT DISTINCT sk.name, sk.skill_id, sk.title, sk.description,
                       sk.status, sk.skill_type, sk.linked_tool, sk.category,
                       sk.owner_user, sk.visibility, sk.is_system
                FROM `tabFAC Skill` sk
                INNER JOIN `tabHas Role` hr
                    ON hr.parent = sk.name AND hr.parenttype = 'FAC Skill'
                WHERE sk.status = 'Published'
                  AND sk.visibility = 'Shared'
                  AND hr.role IN %(roles)s
                  AND sk.owner_user != %(user)s
                """,
                {"roles": user_roles, "user": user},
                as_dict=True,
            )
        except Exception as e:
            frappe.logger("skill_manager").warning(f"Error fetching shared skills: {e}")
            return []

    def get_skill_as_resource(self, skill_info: Dict) -> Dict[str, Any]:
        """Convert a skill row to an MCP resource descriptor."""
        return {
            "uri": f"{_SKILL_URI_PREFIX}{skill_info['skill_id']}",
            "name": skill_info["title"],
            "description": skill_info["description"],
            "mimeType": "text/markdown",
        }

    def read_skill_content(self, skill_id: str) -> Optional[str]:
        """
        Return a skill's markdown content. Published skills are readable per
        the standard permission model; Drafts are readable only by the owner.

        Raises ``frappe.PermissionError`` when the caller is not permitted.
        Returns None when the skill does not exist.
        """
        skill_name = frappe.db.get_value("FAC Skill", {"skill_id": skill_id}, "name")
        if not skill_name:
            return None

        skill_doc = frappe.get_doc("FAC Skill", skill_name)
        user = frappe.session.user

        is_owner = skill_doc.owner_user == user
        if skill_doc.status != "Published" and not is_owner:
            frappe.throw(_("You don't have permission to access this skill"), frappe.PermissionError)

        if not self._user_can_access_skill(skill_doc):
            frappe.throw(_("You don't have permission to access this skill"), frappe.PermissionError)

        # TODO: batch usage-counter writes if traffic grows.
        self.increment_usage(skill_name)

        return skill_doc.content

    def get_skill_by_tool(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Find a Published skill linked to ``tool_name`` that the caller can see."""
        skill_name = frappe.db.get_value(
            "FAC Skill",
            {"linked_tool": tool_name, "status": "Published"},
            "name",
        )
        if not skill_name:
            return None

        skill_doc = frappe.get_doc("FAC Skill", skill_name)
        if not self._user_can_access_skill(skill_doc):
            return None

        return {
            "name": skill_doc.name,
            "skill_id": skill_doc.skill_id,
            "title": skill_doc.title,
            "description": skill_doc.description,
            "content": skill_doc.content,
            "skill_type": skill_doc.skill_type,
            "linked_tool": skill_doc.linked_tool,
        }

    def increment_usage(self, skill_name: str):
        """Increment usage counter for analytics."""
        try:
            frappe.db.sql(
                """
                UPDATE `tabFAC Skill`
                SET use_count = use_count + 1, last_used = NOW()
                WHERE name = %s
                """,
                (skill_name,),
            )
        except Exception as e:
            frappe.logger("skill_manager").warning(f"Failed to increment usage for {skill_name}: {e}")

    def _user_can_access_skill(self, skill_doc) -> bool:
        """Check if current user can access the skill."""
        user = frappe.session.user

        if skill_doc.owner_user == user:
            return True

        if "System Manager" in frappe.get_roles(user):
            return True

        if skill_doc.visibility == "Public" and skill_doc.status == "Published":
            return True

        if skill_doc.visibility == "Shared" and skill_doc.status == "Published":
            user_roles = set(frappe.get_roles(user))
            shared_roles = {r.role for r in skill_doc.shared_with_roles}
            if user_roles & shared_roles:
                return True

        if skill_doc.is_system and skill_doc.status == "Published":
            return True

        return False

    def get_tool_skill_map(self) -> Dict[str, Dict[str, str]]:
        """
        Map of ``tool_name -> {description, skill_id}`` for all Published
        Tool-Usage skills. Drives token-optimization in replace mode.
        """
        skills = frappe.get_all(
            "FAC Skill",
            filters={
                "status": "Published",
                "skill_type": "Tool Usage",
                "linked_tool": ["is", "set"],
            },
            fields=["linked_tool", "description", "skill_id"],
        )
        return {s.linked_tool: {"description": s.description, "skill_id": s.skill_id} for s in skills}


def get_skill_manager() -> SkillManager:
    """Construct a fresh SkillManager. Kept for backwards compatibility."""
    return SkillManager()


def handle_resources_list(request_id: Optional[Any] = None) -> Dict[str, Any]:
    """Handle resources/list request - return available skill resources."""
    try:
        if not frappe.db.table_exists("FAC Skill"):
            return {"resources": []}

        manager = SkillManager()
        skill_infos = manager.get_user_accessible_skills()

        resources = [manager.get_skill_as_resource(s) for s in skill_infos if s.get("status") == "Published"]

        api_logger.info(f"Resources list request completed, returned {len(resources)} resources")
        return {"resources": resources}

    except Exception as e:
        api_logger.error(f"Error in handle_resources_list: {e}")
        return {"resources": []}


def handle_resources_read(params: Dict[str, Any], request_id: Optional[Any] = None) -> Dict[str, Any]:
    """Handle resources/read request - return skill content by URI."""
    uri = params.get("uri", "")

    if not uri.startswith(_SKILL_URI_PREFIX):
        raise ValueError(f"Unknown resource URI scheme: {uri}")

    skill_id = uri[len(_SKILL_URI_PREFIX) :]
    if not skill_id or not _SKILL_ID_RE.match(skill_id):
        raise ValueError(f"Invalid skill_id in URI: {uri!r}")

    try:
        manager = SkillManager()
        content = manager.read_skill_content(skill_id)
    except frappe.PermissionError:
        raise
    except Exception as e:
        api_logger.error(f"Error in handle_resources_read: {e}")
        raise

    if content is None:
        raise ValueError(f"Skill not found: {skill_id}")

    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": "text/markdown",
                "text": content,
            }
        ]
    }
