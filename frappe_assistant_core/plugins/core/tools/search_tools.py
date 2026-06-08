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

from typing import Any, Dict, List

import frappe
from frappe import _
from frappe.desk.search import search_widget


class SearchTools:
    """assistant tools for Frappe search operations"""

    @staticmethod
    def get_tools() -> List[Dict]:
        """Return list of search-related assistant tools"""
        return [
            {
                "name": "search_documents",
                "description": "Global search across all accessible documents",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "default": 20, "description": "Maximum results"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "search_doctype",
                "description": "Search within a specific DocType",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "doctype": {"type": "string", "description": "DocType to search in"},
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "default": 20, "description": "Maximum results"},
                    },
                    "required": ["doctype", "query"],
                },
            },
            {
                "name": "search_link",
                "description": "Search for link field options",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "doctype": {"type": "string", "description": "Target DocType for link"},
                        "query": {"type": "string", "description": "Search query"},
                        "filters": {"type": "object", "default": {}, "description": "Additional filters"},
                    },
                    "required": ["doctype", "query"],
                },
            },
        ]

    @staticmethod
    def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a search tool with given arguments"""
        if tool_name == "search_documents":
            return SearchTools.global_search(**arguments)
        elif tool_name == "search_doctype":
            return SearchTools.search_doctype(**arguments)
        elif tool_name == "search_link":
            return SearchTools.search_link(**arguments)
        else:
            raise Exception(f"Unknown search tool: {tool_name}")

    @staticmethod
    def global_search(query: str, limit: int = 20) -> Dict[str, Any]:
        """Global search across all accessible documents"""
        try:
            results = []

            # Search across common DocTypes that users typically have access to
            common_doctypes = [
                "User",
                "DocType",
                "Contact",
                "Customer",
                "Supplier",
                "Item",
                "Company",
                "Employee",
                "Task",
                "Project",
            ]

            for doctype in common_doctypes:
                try:
                    # Check if doctype exists and user has permission
                    if not frappe.db.exists("DocType", doctype):
                        continue
                    if not frappe.has_permission(doctype, "read"):
                        continue

                    # Simple search using name field. Use frappe.get_list (not
                    # get_all) so DocType-level AND user/row-level permissions are
                    # applied — get_all bypasses permissions and would leak
                    # records the user cannot read (issue #189).
                    doctype_results = frappe.get_list(
                        doctype,
                        filters={"name": ["like", f"%{query}%"]},
                        fields=["name"],
                        limit=5,  # Limit per doctype
                        ignore_permissions=False,
                    )

                    # Add doctype info to results
                    for result in doctype_results:
                        result["doctype"] = doctype
                        results.append(result)

                except Exception:
                    # Skip doctype if there's an error
                    continue

            # Limit total results
            limited_results = results[:limit]

            return {
                "success": True,
                "query": query,
                "results": limited_results,
                "count": len(limited_results),
                "total_found": len(results),
                "searched_doctypes": [
                    dt
                    for dt in common_doctypes
                    if frappe.db.exists("DocType", dt) and frappe.has_permission(dt, "read")
                ],
            }

        except Exception as e:
            frappe.log_error(f"assistant Global Search Error: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def search_doctype(doctype: str, query: str, limit: int = 20) -> Dict[str, Any]:
        """Search within a specific DocType"""
        try:
            if not frappe.db.exists("DocType", doctype):
                return {"success": False, "error": f"DocType '{doctype}' not found"}

            if not frappe.has_permission(doctype, "read"):
                return {"success": False, "error": f"No read permission for DocType '{doctype}'"}

            # Get DocType meta to identify search fields
            meta = frappe.get_meta(doctype)
            search_fields = []

            # Add title field and other searchable fields
            if meta.title_field:
                search_fields.append(meta.title_field)

            # Add common searchable fields
            for field in meta.fields:
                if field.fieldtype in ["Data", "Text", "Small Text"] and not field.hidden:
                    search_fields.append(field.fieldname)

            # Limit search fields to avoid too complex queries
            search_fields = search_fields[:5]

            if not search_fields:
                search_fields = ["name"]

            # Build search filters
            filters = []
            for field in search_fields:
                filters.append([doctype, field, "like", f"%{query}%"])

            # Execute search. Use frappe.get_list (not get_all) so the results
            # are filtered by the user's read permissions — get_all bypasses
            # permissions and would leak inaccessible records (issue #189).
            results = frappe.get_list(
                doctype,
                or_filters=filters,
                fields=["name"] + search_fields,
                limit=limit,
                order_by="modified desc",
                ignore_permissions=False,
            )

            return {
                "success": True,
                "doctype": doctype,
                "query": query,
                "results": results,
                "count": len(results),
                "search_fields": search_fields,
            }

        except Exception as e:
            frappe.log_error(f"assistant DocType Search Error: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def search_link(doctype: str, query: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Search for link field options"""
        try:
            if not frappe.db.exists("DocType", doctype):
                return {"success": False, "error": f"DocType '{doctype}' not found"}

            if not frappe.has_permission(doctype, "read"):
                return {"success": False, "error": f"No read permission for DocType '{doctype}'"}

            # Use Frappe's link search functionality
            from frappe.desk.search import search_link

            results = search_link(doctype=doctype, txt=query, filters=filters or {})

            return {
                "success": True,
                "doctype": doctype,
                "query": query,
                "results": results,
                "count": len(results),
                "filters_applied": filters or {},
            }

        except Exception as e:
            frappe.log_error(f"assistant Link Search Error: {str(e)}")
            return {"success": False, "error": str(e)}
