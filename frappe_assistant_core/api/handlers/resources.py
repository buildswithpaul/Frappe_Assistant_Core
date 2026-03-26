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

from typing import Any, Dict, List, Optional

import frappe
from frappe import _

from frappe_assistant_core.utils.logger import api_logger


class SkillManager:
    """
    Centralized manager for skill operations.
    Handles querying, filtering, and permission checking for skills.
    """

    def __init__(self):
        self.logger = frappe.logger("skill_manager")

    def get_user_accessible_skills(self, user: str = None) -> List[Dict[str, Any]]:
        """
        Get all skills accessible to the current user.

        Includes:
        - User's own skills (any status)
        - Published + Public skills
        - Published + Shared skills (if user has required role)
        - Published + System skills

        Args:
            user: User email (defaults to current session user)

        Returns:
            List of skill info dicts
        """
        user = user or frappe.session.user
        user_roles = frappe.get_roles(user)

        skills = []
        seen_ids = set()

        # 1. User's own skills (any status)
        own_skills = frappe.get_all(
            "FAC Skill",
            filters={"owner_user": user},
            fields=[
                "name",
                "skill_id",
                "title",
                "description",
                "status",
                "skill_type",
                "linked_tool",
                "category",
            ],
        )
        for s in own_skills:
            if s.skill_id not in seen_ids:
                seen_ids.add(s.skill_id)
                skills.append(s)

        # 2. Published public skills
        public_skills = frappe.get_all(
            "FAC Skill",
            filters={"status": "Published", "visibility": "Public", "owner_user": ["!=", user]},
            fields=[
                "name",
                "skill_id",
                "title",
                "description",
                "status",
                "skill_type",
                "linked_tool",
                "category",
            ],
        )
        for s in public_skills:
            if s.skill_id not in seen_ids:
                seen_ids.add(s.skill_id)
                skills.append(s)

        # 3. Published shared skills where user has required role
        shared_skills = self._get_shared_skills_for_user(user, user_roles)
        for s in shared_skills:
            if s.skill_id not in seen_ids:
                seen_ids.add(s.skill_id)
                skills.append(s)

        # 4. System skills (is_system=1, status=Published)
        system_skills = frappe.get_all(
            "FAC Skill",
            filters={"is_system": 1, "status": "Published", "owner_user": ["!=", user]},
            fields=[
                "name",
                "skill_id",
                "title",
                "description",
                "status",
                "skill_type",
                "linked_tool",
                "category",
            ],
        )
        for s in system_skills:
            if s.skill_id not in seen_ids:
                seen_ids.add(s.skill_id)
                skills.append(s)

        return skills

    def _get_shared_skills_for_user(self, user: str, user_roles: List[str]) -> List[Dict]:
        """Get skills shared with roles that user has."""
        if not user_roles:
            return []

        try:
            shared_skills = frappe.db.sql(
                """
                SELECT DISTINCT sk.name, sk.skill_id, sk.title, sk.description,
                       sk.status, sk.skill_type, sk.linked_tool, sk.category
                FROM `tabFAC Skill` sk
                INNER JOIN `tabHas Role` hr ON hr.parent = sk.name
                    AND hr.parenttype = 'FAC Skill'
                WHERE sk.status = 'Published'
                  AND sk.visibility = 'Shared'
                  AND hr.role IN %(roles)s
                  AND sk.owner_user != %(user)s
            """,
                {"roles": user_roles, "user": user},
                as_dict=True,
            )
            return shared_skills
        except Exception as e:
            self.logger.warning(f"Error fetching shared skills: {e}")
            return []

    def get_skill_as_resource(self, skill_info: Dict) -> Dict[str, Any]:
        """
        Convert skill info to MCP resource format.

        Args:
            skill_info: Skill info dict (from get_user_accessible_skills)

        Returns:
            Dict in MCP resources/list format
        """
        return {
            "uri": f"fac://skills/{skill_info['skill_id']}",
            "name": skill_info["title"],
            "description": skill_info["description"],
            "mimeType": "text/markdown",
        }

    def read_skill_content(self, skill_id: str) -> Optional[str]:
        """
        Read skill content by skill_id.

        Args:
            skill_id: The skill's unique identifier

        Returns:
            Markdown content string, or None if not found
        """
        skill_name = frappe.db.get_value(
            "FAC Skill",
            {"skill_id": skill_id, "status": ["in", ["Published", "Draft"]]},
            "name",
        )

        if not skill_name:
            return None

        skill_doc = frappe.get_doc("FAC Skill", skill_name)

        if not self._user_can_access_skill(skill_doc):
            frappe.throw(_("You don't have permission to access this skill"), frappe.PermissionError)

        self.increment_usage(skill_name)

        return skill_doc.content

    def get_skill_by_tool(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Find a published skill linked to a specific tool.

        Args:
            tool_name: The MCP tool name

        Returns:
            Skill info dict or None
        """
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
            self.logger.warning(f"Failed to increment usage for {skill_name}: {e}")

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
        Get a map of tool_name -> skill info for all published skills
        with linked tools. Used for token optimization in replace mode.

        Returns:
            Dict mapping tool names to {"description": ..., "skill_id": ...}
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


# Global manager instance
_skill_manager = None


def get_skill_manager() -> SkillManager:
    """Get singleton instance of SkillManager."""
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
    return _skill_manager


def handle_resources_list(request_id: Optional[Any] = None) -> Dict[str, Any]:
    """Handle resources/list request - return available skill resources."""
    try:
        if not _should_use_skills():
            return {"resources": []}

        manager = get_skill_manager()
        skill_infos = manager.get_user_accessible_skills()

        resources = []
        for skill_info in skill_infos:
            if skill_info.get("status") == "Published":
                resources.append(manager.get_skill_as_resource(skill_info))

        api_logger.info(f"Resources list request completed, returned {len(resources)} resources")
        return {"resources": resources}

    except Exception as e:
        api_logger.error(f"Error in handle_resources_list: {e}")
        return {"resources": []}


def handle_resources_read(params: Dict[str, Any], request_id: Optional[Any] = None) -> Dict[str, Any]:
    """Handle resources/read request - return skill content by URI."""
    try:
        uri = params.get("uri", "")

        if not uri.startswith("fac://skills/"):
            raise ValueError(f"Unknown resource URI scheme: {uri}")

        skill_id = uri.replace("fac://skills/", "")
        if not skill_id:
            raise ValueError("Missing skill_id in URI")

        manager = get_skill_manager()
        content = manager.read_skill_content(skill_id)

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

    except frappe.PermissionError as e:
        raise
    except ValueError as e:
        raise
    except Exception as e:
        api_logger.error(f"Error in handle_resources_read: {e}")
        raise


def _should_use_skills() -> bool:
    """Check if FAC Skill table exists and has published skills."""
    try:
        if not frappe.db.table_exists("FAC Skill"):
            return False
        count = frappe.db.count("FAC Skill", {"status": "Published"})
        return count > 0
    except Exception:
        return False
