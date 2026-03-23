# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Skill Listing Tool for Core Plugin.
Lists available skills with optional filtering by type, tool, or category.
"""

from typing import Any, Dict

import frappe

from frappe_assistant_core.core.base_tool import BaseTool


class SkillList(BaseTool):
    """
    Tool for listing available skills.
    Returns skills accessible to the current user with optional filtering.
    """

    def __init__(self):
        super().__init__()
        self.name = "list_skills"
        self.description = "List available skills that provide guidance on how to use tools effectively. Skills contain best practices, examples, and edge cases for specific tools or workflows."
        self.requires_permission = None

        self.inputSchema = {
            "type": "object",
            "properties": {
                "skill_type": {
                    "type": "string",
                    "description": "Filter by skill type: 'Tool Usage' or 'Workflow'",
                    "enum": ["Tool Usage", "Workflow"],
                },
                "linked_tool": {
                    "type": "string",
                    "description": "Filter by linked tool name (e.g., 'list_documents')",
                },
                "category": {
                    "type": "string",
                    "description": "Filter by Prompt Category name",
                },
            },
            "required": [],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute skill listing with optional filters."""
        try:
            from frappe_assistant_core.api.handlers.resources import get_skill_manager

            manager = get_skill_manager()
            skills = manager.get_user_accessible_skills()

            # Apply optional filters
            skill_type = arguments.get("skill_type")
            linked_tool = arguments.get("linked_tool")
            category = arguments.get("category")

            if skill_type:
                skills = [s for s in skills if s.get("skill_type") == skill_type]
            if linked_tool:
                skills = [s for s in skills if s.get("linked_tool") == linked_tool]
            if category:
                skills = [s for s in skills if s.get("category") == category]

            # Filter to published only and format output
            results = []
            for s in skills:
                if s.get("status") == "Published":
                    results.append(
                        {
                            "skill_id": s["skill_id"],
                            "title": s["title"],
                            "description": s["description"],
                            "skill_type": s.get("skill_type"),
                            "linked_tool": s.get("linked_tool"),
                        }
                    )

            return {
                "success": True,
                "skills": results,
                "total": len(results),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
