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

The single text-search entry point. It replaces the former search_documents /
search_doctype / search_link trio, which differed only in whether a doctype was
supplied and how results were shaped — a parameter, not three tools. Three
near-identical tool descriptions gave the model nothing to choose between, and
the routing rules now live in this one description instead of in a skill
document written to undo the confusion.
"""

from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool

# Hard ceiling on rows returned, whatever the caller asks for.
MAX_LIMIT = 100

DEFAULT_LIMIT = 20


class SearchDocuments(BaseTool):
    """
    Unified document search.

    Routes on its arguments:
    - no ``doctype``            -> full-text search across everything readable
    - ``doctype``               -> text search within that DocType
    - ``purpose="link_value"``  -> autocomplete-style Link field resolution
    """

    def __init__(self):
        super().__init__()
        self.name = "search_documents"
        self.description = (
            "Find documents by text. Omit 'doctype' to search across everything the user can read; "
            "pass 'doctype' to search within one DocType. Set purpose='link_value' to resolve a valid "
            "value for a Link field before creating or updating a document (returns display-ready "
            "candidates). This is a text search — for exact filtering by status, date range, or amount, "
            "and for counting records, use list_documents instead."
        )
        self.requires_permission = None  # Permission checked dynamically per DocType

        self.inputSchema = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to search for. Short queries work best — a name, code, or single phrase.",
                },
                "doctype": {
                    "type": "string",
                    "description": "Optional DocType to search within (e.g. 'Customer', 'Sales Invoice'). Omit to search globally. Required when purpose is 'link_value'.",
                },
                "purpose": {
                    "type": "string",
                    "enum": ["documents", "link_value"],
                    "default": "documents",
                    "description": "'documents' (default) finds records. 'link_value' resolves a valid value for a Link field, honouring that DocType's custom search query.",
                },
                "filters": {
                    "type": "object",
                    "default": {},
                    "description": "Optional filters narrowing the search, e.g. {'status': 'Active'}. Applied together with the text match. Requires 'doctype'.",
                },
                "limit": {
                    "type": "integer",
                    "default": DEFAULT_LIMIT,
                    "maximum": MAX_LIMIT,
                    "description": f"Maximum results to return. Default {DEFAULT_LIMIT}, maximum {MAX_LIMIT}.",
                },
            },
            "required": ["query"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Route to the search mode implied by the arguments."""
        try:
            from .search_tools import SearchTools

            query = arguments.get("query")
            doctype = arguments.get("doctype")
            purpose = arguments.get("purpose") or "documents"
            filters = arguments.get("filters") or {}
            limit = self._clamp_limit(arguments.get("limit"))

            if purpose == "link_value":
                if not doctype:
                    return {
                        "success": False,
                        "error": _("purpose='link_value' needs a doctype — the Link field's target."),
                    }
                return SearchTools.search_link(doctype=doctype, query=query, filters=filters, limit=limit)

            if doctype:
                return SearchTools.search_doctype(doctype=doctype, query=query, limit=limit, filters=filters)

            if filters:
                # Filters need a DocType to resolve fieldnames against, so silently
                # dropping them would return a broader result set than asked for.
                return {
                    "success": False,
                    "error": _("Filters require a doctype. Omit filters for a global search."),
                }

            return SearchTools.global_search(query=query, limit=limit)

        except Exception as e:
            frappe.log_error(
                title=_("Search Documents Error"), message=f"Error searching documents: {str(e)}"
            )

            return {"success": False, "error": str(e)}

    def _clamp_limit(self, limit: Any) -> int:
        """Keep limit within bounds; a non-numeric value falls back to the default."""
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            return DEFAULT_LIMIT

        if limit < 1:
            return DEFAULT_LIMIT

        return min(limit, MAX_LIMIT)


# Make sure class name matches file name for discovery
search_documents = SearchDocuments
