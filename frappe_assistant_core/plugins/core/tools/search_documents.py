# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Search Documents Tool for Core Plugin.
Global search across all accessible documents.
"""

from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool


class SearchDocuments(BaseTool):
    """
    Tool for global search across all accessible documents.

    Provides capabilities for:
    - Global search across common DocTypes
    - Permission-aware results
    - Structured result formatting
    """

    def __init__(self):
        super().__init__()
        self.name = "search"
        self.description = "Global search across all accessible documents"
        self.requires_permission = None  # Permission checked dynamically per DocType

        self.inputSchema = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "default": 20, "description": "Maximum results"},
            },
            "required": ["query"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute global search"""
        try:
            # Import the search implementation
            from .search_tools import SearchTools

            # Execute search using existing implementation
            return SearchTools.global_search(query=arguments.get("query"), limit=arguments.get("limit", 20))

        except Exception as e:
            frappe.log_error(
                title=_("Search Documents Error"), message=f"Error searching documents: {str(e)}"
            )

            return {"success": False, "error": str(e)}


# Make sure class name matches file name for discovery
search_documents = SearchDocuments
