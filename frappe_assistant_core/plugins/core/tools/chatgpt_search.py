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
ChatGPT-Compatible Search Tool

This tool provides a search interface compatible with ChatGPT's MCP requirements.
It wraps the existing search_documents functionality but formats results according
to ChatGPT's specific schema requirements.

ChatGPT Requirements:
- Tool name must be exactly "search"
- Input: Single "query" string parameter
- Output: {"results": [{"id": str, "title": str, "url": str}]}
"""

from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool


class ChatGPTSearch(BaseTool):
    """
    ChatGPT-compatible search tool for MCP integration.

    This tool conforms to ChatGPT's specific MCP requirements:
    - Returns results with id, title, and url fields
    - Accepts a simple query string
    - Formats output as required by ChatGPT connectors
    """

    def __init__(self):
        super().__init__()
        self.name = "search"
        self.description = "Search for documents using OpenAI Vector Store search. Returns a list of search results with basic information. Use the fetch tool to get complete document content."

        self.inputSchema = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string. Natural language queries work best for semantic search.",
                }
            },
            "required": ["query"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute search and format results for ChatGPT.

        Args:
            arguments: Dict with "query" key

        Returns:
            Dict with "results" array, each result having:
            - id: Unique identifier (format: "doctype/name")
            - title: Human-readable title
            - url: URL for citation
        """
        try:
            query = arguments.get("query", "").strip()

            if not query:
                return {"results": []}

            # Use existing search functionality
            from .search_tools import SearchTools

            # Execute search
            search_result = SearchTools.global_search(query=query, limit=20)

            # Transform results to ChatGPT format
            results = []

            if search_result.get("success") and search_result.get("results"):
                for item in search_result.get("results", []):
                    doctype = item.get("doctype", "Document")
                    name = item.get("name", "")
                    title = item.get("title") or name or "Untitled"

                    # Create unique ID in format: doctype/name
                    result_id = f"{doctype}/{name}"

                    # Generate URL for citation
                    site_url = frappe.utils.get_url()
                    url = f"{site_url}/app/{frappe.scrub(doctype)}/{name}"

                    results.append({"id": result_id, "title": title, "url": url})

            return {"results": results}

        except Exception as e:
            frappe.log_error(title=_("ChatGPT Search Error"), message=f"Error in ChatGPT search: {str(e)}")

            # Return empty results on error for ChatGPT compatibility
            return {"results": []}


# Export class for discovery
chatgpt_search = ChatGPTSearch
