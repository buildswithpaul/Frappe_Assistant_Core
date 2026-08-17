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
Document Listing Tool for Core Plugin.
Lists and searches Frappe documents with filtering capabilities.
"""

from typing import Any, Dict, List

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool

# Operators Frappe accepts as the first element of a list-style filter value.
# Anything else in that position means the list is a set of values, not [op, value].
FILTER_OPERATORS = {
    "=",
    "!=",
    ">",
    "<",
    ">=",
    "<=",
    "like",
    "not like",
    "in",
    "not in",
    "is",
    "between",
    "descendants of",
    "not descendants of",
    "ancestors of",
    "not ancestors of",
}


def is_submittable(doctype: str) -> bool:
    """Whether the DocType carries docstatus semantics (draft/submitted/cancelled)."""
    try:
        return bool(frappe.get_meta(doctype).is_submittable)
    except Exception:
        # Missing or virtual DocTypes are treated as non-submittable — the caller's
        # filters are then passed through untouched and Frappe reports the real error.
        return False


def filters_reference_docstatus(filters: Any) -> bool:
    """True when the caller already constrained docstatus, in any supported filter form."""
    if isinstance(filters, dict):
        return "docstatus" in filters

    if isinstance(filters, (list, tuple)):
        # A single unwrapped condition, e.g. ["docstatus", "=", 1]
        if filters and isinstance(filters[0], str):
            return "docstatus" in filters

        for condition in filters:
            if not isinstance(condition, (list, tuple)) or not condition:
                continue
            # ["doctype", "fieldname", op, value] or ["fieldname", op, value]
            fieldname = condition[1] if len(condition) >= 4 else condition[0]
            if fieldname == "docstatus":
                return True

    return False


def normalize_docstatus_filter(filters: Any) -> Any:
    """Accept a bare list of docstatus values, e.g. [0, 1], as an `in` filter.

    Frappe reads a list filter value as [operator, value], so an explicit
    {"docstatus": [0, 1]} would otherwise be parsed as the operator "0".
    """
    if not isinstance(filters, dict):
        return filters

    value = filters.get("docstatus")
    if not isinstance(value, (list, tuple)) or not value:
        return filters

    first = value[0]
    if isinstance(first, str) and first.lower() in FILTER_OPERATORS:
        return filters

    normalized = dict(filters)
    normalized["docstatus"] = ["in", list(value)]
    return normalized


def apply_default_docstatus(doctype: str, filters: Any) -> tuple:
    """Default submittable DocTypes to submitted documents only.

    Without this, cancelled (docstatus=2) and draft (docstatus=0) documents are
    returned alongside submitted ones with their monetary fields intact, and any
    consumer aggregating the result set gets a silently wrong total.

    Returns (filters, applied) where `applied` says whether the default was added.
    """
    if not is_submittable(doctype):
        return filters, False

    if filters_reference_docstatus(filters):
        return normalize_docstatus_filter(filters), False

    if isinstance(filters, dict):
        defaulted = dict(filters)
        defaulted["docstatus"] = 1
        return defaulted, True

    if isinstance(filters, (list, tuple)):
        # An unwrapped condition such as ["status", "=", "Paid"] has to be nested first.
        conditions = [list(filters)] if filters and isinstance(filters[0], str) else list(filters)
        return conditions + [["docstatus", "=", 1]], True

    return {"docstatus": 1}, True


# Ranked candidates offered per unmatched Link filter value.
MAX_LINK_SUGGESTIONS = 5


def equality_filter_pairs(filters: Any) -> List[tuple]:
    """(fieldname, value) pairs for filters compared to a single value by equality.

    Only these can be checked for existence — an operator like `like` or `in`
    already expresses that the caller does not know the exact value.
    """
    pairs = []

    if isinstance(filters, dict):
        for fieldname, value in filters.items():
            if isinstance(value, str):
                pairs.append((fieldname, value))
            elif isinstance(value, (list, tuple)) and len(value) == 2:
                operator, operand = value
                if isinstance(operator, str) and operator == "=" and isinstance(operand, str):
                    pairs.append((fieldname, operand))
        return pairs

    if isinstance(filters, (list, tuple)):
        conditions = [filters] if filters and isinstance(filters[0], str) else filters
        for condition in conditions:
            if not isinstance(condition, (list, tuple)) or len(condition) < 3:
                continue
            # ["doctype", "fieldname", op, value] or ["fieldname", op, value]
            fieldname, operator, value = condition[1:4] if len(condition) >= 4 else condition[0:3]
            if operator == "=" and isinstance(value, str):
                pairs.append((fieldname, value))

    return pairs


def link_filter_targets(doctype: str, filters: Any) -> Dict[str, tuple]:
    """Map fieldname -> (target DocType, value) for Link fields filtered by equality."""
    pairs = equality_filter_pairs(filters)
    if not pairs:
        return {}

    try:
        meta = frappe.get_meta(doctype)
    except Exception:
        return {}

    targets = {}
    for fieldname, value in pairs:
        if not value:
            continue
        field = meta.get_field(fieldname)
        if not field or field.fieldtype != "Link" or not field.options:
            continue
        targets[fieldname] = (field.options, value)

    return targets


def link_suggestions(target_doctype: str, value: str) -> List[str]:
    """Ranked candidate names for an unmatched Link value, via search_link resolution.

    Falls back to the first word of a multi-word value, since search_link matches
    on substrings and a typo late in the value would otherwise return nothing.
    """
    from .search_tools import SearchTools

    queries = [value]
    words = value.split()
    if words and words[0] != value:
        queries.append(words[0])

    for query in queries:
        response = SearchTools.search_link(doctype=target_doctype, query=query)
        if not response.get("success"):
            return []

        suggestions = [
            candidate.get("value") for candidate in response.get("results") or [] if candidate.get("value")
        ]
        if suggestions:
            return suggestions[:MAX_LINK_SUGGESTIONS]

    return []


def resolve_unmatched_link_filters(doctype: str, filters: Any) -> Dict[str, Dict[str, Any]]:
    """Explain a zero-row result caused by Link filter values that match no record.

    "No records" and "that entity does not exist" are indistinguishable to a
    consumer otherwise, so an approximate name passed straight into a filter reads
    as a legitimate business answer. Only called when the result set is empty.
    """
    unresolved = {}

    for fieldname, (target_doctype, value) in link_filter_targets(doctype, filters).items():
        try:
            if not frappe.db.exists("DocType", target_doctype):
                continue

            # Without read access on the target, neither existence nor candidates
            # are ours to report.
            if not frappe.has_permission(target_doctype, "read"):
                continue

            # The value resolves — zero rows is a real answer, not a bad filter.
            if frappe.db.exists(target_doctype, value):
                continue

            unresolved[fieldname] = {
                "value": value,
                "matched": False,
                "target_doctype": target_doctype,
                "suggestions": link_suggestions(target_doctype, value),
            }
        except Exception as e:
            # Diagnostics must never turn a successful query into a failure.
            frappe.log_error(
                title=_("Link Filter Resolution Error"),
                message=f"Error resolving {doctype}.{fieldname}: {str(e)}",
            )

    return unresolved


class DocumentList(BaseTool):
    """
    Tool for listing and searching Frappe documents.

    Provides capabilities for:
    - Searching documents with filters
    - Pagination support
    - Field selection
    - Permission checking
    """

    def __init__(self):
        super().__init__()
        self.name = "list_documents"
        self.description = "Search and list Frappe documents with optional filtering. Use this when users want to find records, get lists of documents, or search for data. This is the primary tool for data exploration and discovery. For submittable DocTypes (invoices, orders, entries) only submitted documents are returned unless you pass docstatus explicitly. If a query returns nothing because a Link filter value matches no record, the response carries unresolved_filters with ranked suggestions — check it before reporting that no data exists."
        self.requires_permission = None  # Permission checked dynamically per DocType

        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {
                    "type": "string",
                    "description": "The Frappe DocType to search (e.g., 'Customer', 'Sales Invoice', 'Item', 'User'). Must match exact DocType name.",
                },
                "filters": {
                    "type": "object",
                    "default": {},
                    "description": "Search filters as key-value pairs. Examples: {'status': 'Active'}, {'customer_type': 'Company'}, {'creation': ['>', '2024-01-01']}. Use empty {} to get all records. For submittable DocTypes, docstatus=1 (submitted) is applied automatically unless you set docstatus yourself — pass {'docstatus': 2} for cancelled, {'docstatus': [0, 1]} for drafts and submitted.",
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific fields to retrieve. Examples: ['name', 'customer_name', 'email'], ['name', 'item_name', 'item_code']. Leave empty to get standard fields.",
                },
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "maximum": 1000,
                    "description": "Maximum number of records to return. Default is 20, maximum is 1000.",
                },
                "order_by": {
                    "type": "string",
                    "description": "Order results by field. Examples: 'creation desc', 'name asc', 'modified desc'. Default is 'creation desc'.",
                },
            },
            "required": ["doctype"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """List documents with filters"""
        doctype = arguments.get("doctype")
        filters = arguments.get("filters", {})
        fields = arguments.get("fields", ["name", "creation", "modified"])
        limit = arguments.get("limit", 20)
        order_by = arguments.get("order_by", "creation desc")

        # Get current user context

        current_user = frappe.session.user

        # Import security validation
        from frappe_assistant_core.core.security_config import (
            filter_sensitive_fields,
            validate_document_access,
        )

        # Validate document access with comprehensive permission checking
        validation_result = validate_document_access(
            user=frappe.session.user,
            doctype=doctype,
            name=None,  # No specific document for list operation
            perm_type="read",
        )

        if not validation_result["success"]:
            return validation_result

        user_role = validation_result["role"]

        # SECURITY: Special handling for User DocType - non-admins can only see themselves
        if doctype == "User" and user_role in ["Assistant User", "Default"]:
            # Filter to only show current user
            if not filters:
                filters = {}
            filters["name"] = current_user

        # Submittable DocTypes default to submitted documents only, so cancelled and
        # draft records never reach a consumer that is summing monetary fields.
        filters, docstatus_defaulted = apply_default_docstatus(doctype, filters)

        try:
            # Filter sensitive fields from requested fields for Assistant Users
            from frappe_assistant_core.core.security_config import ADMIN_ONLY_FIELDS, SENSITIVE_FIELDS

            if user_role == "Assistant User":
                # Get restricted fields
                restricted_fields = set()
                restricted_fields.update(SENSITIVE_FIELDS.get("all_doctypes", []))
                restricted_fields.update(SENSITIVE_FIELDS.get(doctype, []))
                restricted_fields.update(ADMIN_ONLY_FIELDS.get("all_doctypes", []))

                doctype_admin_fields = ADMIN_ONLY_FIELDS.get(doctype, [])
                if doctype_admin_fields != "*":
                    restricted_fields.update(doctype_admin_fields)

                # Filter out restricted fields from requested fields
                filtered_fields = [field for field in fields if field not in restricted_fields]
                if not filtered_fields:
                    filtered_fields = ["name"]  # Always allow name field
                fields = filtered_fields

            # Get documents with Frappe's permission-aware list API.
            documents = frappe.get_list(
                doctype,
                filters=filters,
                fields=fields,
                limit=limit,
                order_by=order_by,
                ignore_permissions=False,  # Ensure permission checking
            )

            # Filter sensitive fields from document data
            filtered_documents = []
            for doc in documents:
                filtered_doc = filter_sensitive_fields(doc, doctype, user_role)
                filtered_documents.append(filtered_doc)

            # Get permission-aware total count for pagination info.
            try:
                count_result = frappe.get_list(
                    doctype,
                    filters=filters,
                    fields=[{"COUNT": "name", "as": "count"}],
                    limit=1,
                    ignore_permissions=False,
                )
            except AttributeError:
                count_result = frappe.get_list(
                    doctype,
                    filters=filters,
                    fields=["count(name) as count"],
                    limit=1,
                    ignore_permissions=False,
                )
            total_count = count_result[0].get("count") if count_result else 0

            message = f"Found {len(filtered_documents)} {doctype} records"
            if docstatus_defaulted:
                message += (
                    " (submitted only — docstatus=1 applied by default; "
                    "pass docstatus explicitly to include drafts or cancelled documents)"
                )

            result = {
                "success": True,
                "doctype": doctype,
                "data": filtered_documents,
                "count": len(filtered_documents),
                "total_count": total_count,
                "has_more": total_count > limit,
                "filters_applied": filters,
                "message": message,
            }

            # A zero-row result may mean the filter value itself never existed.
            # Additive metadata only — the query still succeeded.
            if not filtered_documents:
                unresolved_filters = resolve_unmatched_link_filters(doctype, filters)
                if unresolved_filters:
                    result["unresolved_filters"] = unresolved_filters
                    result["message"] += (
                        f" — but these filter values match no record: "
                        f"{', '.join(sorted(unresolved_filters))}. This is an unresolved filter, "
                        "not an empty result. See unresolved_filters for candidates."
                    )

            # Log successful access
            return result

        except Exception as e:
            frappe.log_error(title=_("Document List Error"), message=f"Error listing {doctype}: {str(e)}")

            return {"success": False, "error": str(e), "doctype": doctype}


# Make sure class name matches file name for discovery
document_list = DocumentList
