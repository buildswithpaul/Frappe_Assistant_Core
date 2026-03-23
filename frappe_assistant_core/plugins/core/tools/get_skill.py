# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Skill Retrieval Tool for Core Plugin.
Retrieves full skill content by skill_id or linked tool name.
"""

from typing import Any, Dict

import frappe

from frappe_assistant_core.core.base_tool import BaseTool


class SkillGet(BaseTool):
    """
    Tool for retrieving skill content.
    Returns the full markdown content of a skill, looked up by skill_id or tool_name.
    """

    def __init__(self):
        super().__init__()
        self.name = "get_skill"
        self.description = "Get detailed guidance for using a specific tool or workflow. Returns the full skill content with best practices, examples, and edge cases. Look up by skill_id or tool_name."
        self.requires_permission = None

        self.inputSchema = {
            "type": "object",
            "properties": {
                "skill_id": {
                    "type": "string",
                    "description": "The unique skill identifier (e.g., 'list-documents-usage')",
                },
                "tool_name": {
                    "type": "string",
                    "description": "The MCP tool name to find guidance for (e.g., 'list_documents')",
                },
            },
            "required": [],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute skill retrieval."""
        try:
            from frappe_assistant_core.api.handlers.resources import get_skill_manager

            skill_id = arguments.get("skill_id")
            tool_name = arguments.get("tool_name")

            if not skill_id and not tool_name:
                return {
                    "success": False,
                    "error": "Either skill_id or tool_name must be provided",
                }

            manager = get_skill_manager()

            if skill_id:
                content = manager.read_skill_content(skill_id)
                if content is None:
                    return {
                        "success": False,
                        "error": f"Skill not found: {skill_id}",
                    }
                return {
                    "success": True,
                    "skill_id": skill_id,
                    "content": content,
                }

            # Look up by tool_name
            skill_info = manager.get_skill_by_tool(tool_name)
            if skill_info is None:
                return {
                    "success": False,
                    "error": f"No skill found for tool: {tool_name}",
                }

            # Increment usage
            manager.increment_usage(skill_info["name"])

            return {
                "success": True,
                "skill_id": skill_info["skill_id"],
                "title": skill_info["title"],
                "content": skill_info["content"],
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
