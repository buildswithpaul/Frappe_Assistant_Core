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
Search implementation behind the single ``search_documents`` tool.

Three modes live here, and the tool routes between them from its arguments:

  * global      — full-text across every DocType the user can read
  * doctype     — text match within one DocType's declared search fields
  * link_value  — autocomplete-style resolution of a Link field value

Every mode enforces row-level permissions. That is not automatic: Frappe's own
full-text search intersects only with DocType-level read access, so its hits are
re-validated through ``frappe.get_list`` before being returned (issue #189).
"""

from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _

# DocTypes scanned by the fallback global search, used only when the
# __global_search index has nothing for the query.
FALLBACK_GLOBAL_DOCTYPES = [
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

# Rows taken per DocType by that fallback scan.
FALLBACK_ROWS_PER_DOCTYPE = 5

# Longest indexed-content snippet returned per global hit, so a wide result set
# cannot blow up the response.
MAX_CONTENT_SNIPPET = 300

# Fieldtypes whose contents are worth matching a text query against.
SEARCHABLE_FIELDTYPES = {
    "Data",
    "Small Text",
    "Text",
    "Long Text",
    "Text Editor",
    "Select",
    "Link",
    "Read Only",
}

# The subset small enough to also return in each result row. Matching against a
# Text Editor field is useful; echoing its HTML back is not.
RETURNABLE_FIELDTYPES = {"Data", "Small Text", "Select", "Link", "Read Only"}

# Cap on fields joined into one OR query, to keep the SQL sane on wide DocTypes.
MAX_SEARCH_FIELDS = 5

# Default page length for link-value resolution, matching Frappe's own.
DEFAULT_LINK_LIMIT = 10


def resolve_search_fields(meta) -> List[str]:
    """Fields to match a text query against, for one DocType.

    ``meta.search_fields`` is what the DocType author nominated as searchable and
    what Frappe's own link search uses, so it beats guessing from fieldtypes. The
    heuristic is only a fallback for DocTypes that declare nothing.
    """
    nominated = []

    if meta.title_field:
        nominated.append(meta.title_field)

    for fieldname in (meta.search_fields or "").split(","):
        fieldname = fieldname.strip()
        if fieldname and fieldname not in nominated:
            nominated.append(fieldname)

    resolved = []
    for fieldname in nominated:
        field = meta.get_field(fieldname)
        # A title_field of "name" has no DocField and needs no matching — the
        # name column is searched anyway.
        if field and field.fieldtype in SEARCHABLE_FIELDTYPES:
            resolved.append(fieldname)

    if resolved:
        return resolved[:MAX_SEARCH_FIELDS]

    return [
        field.fieldname
        for field in meta.fields
        if field.fieldtype in SEARCHABLE_FIELDTYPES and not field.hidden
    ][:MAX_SEARCH_FIELDS]


def returnable_fields(meta, search_fields: List[str]) -> List[str]:
    """``name`` plus the search fields compact enough to include in each row."""
    fields = ["name"]

    for fieldname in search_fields:
        field = meta.get_field(fieldname)
        if field and field.fieldtype in RETURNABLE_FIELDTYPES and fieldname not in fields:
            fields.append(fieldname)

    return fields


class SearchTools:
    """Permission-aware search primitives for the search_documents tool."""

    @staticmethod
    def global_search(query: str, limit: int = 20, doctype: Optional[str] = None) -> Dict[str, Any]:
        """Full-text search across every DocType the user can read."""
        try:
            query = (query or "").strip()
            if not query:
                return {"success": False, "error": _("A search query is required")}

            results, index_hit = SearchTools._indexed_global_search(query, limit, doctype)

            # Only reach for the fallback when the index had nothing to say. If it
            # returned hits that row-level permissions then removed, an empty
            # result is the correct answer.
            if not index_hit:
                results = SearchTools._fallback_global_search(query, limit, doctype)
                index = "name_scan"
            else:
                index = "__global_search"

            limited = results[:limit]

            response = {
                "success": True,
                "query": query,
                "search_mode": "global",
                "index": index,
                "results": limited,
                "count": len(limited),
                "has_more": len(results) > len(limited),
            }

            # An empty fallback result is ambiguous: the query may match nothing,
            # or the full-text index may simply not cover it. Saying which, as
            # list_documents does for unresolved filters (issue #232), stops the
            # caller reporting "no such record" for something never searched.
            if index == "name_scan" and not limited:
                response["message"] = _(
                    "No match, but the full-text index held nothing for this query, so only "
                    "document IDs were searched across common DocTypes. This is not proof the "
                    "record does not exist — retry with a doctype to search that DocType's fields."
                )

            return response

        except Exception as e:
            frappe.log_error(title=_("Global Search Error"), message=f"Error searching '{query}': {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _indexed_global_search(
        query: str, limit: int, doctype: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Hits from the __global_search index, re-checked for row-level access.

        Returns (results, index_hit). ``index_hit`` says whether the index matched
        anything at all, which is what decides if the fallback scan is worth
        running — distinct from whether anything survived the permission check.
        """
        from frappe.utils import global_search as frappe_global_search

        try:
            raw = frappe_global_search.search(query, limit=limit, doctype=doctype or "")
        except Exception as e:
            # A missing or never-synced index must degrade to the fallback scan,
            # not fail the search.
            frappe.logger("frappe_assistant_core").debug(f"Global search index unavailable: {e}")
            return [], False

        if not raw:
            return [], False

        return SearchTools._filter_by_row_permissions(raw), True

    @staticmethod
    def _filter_by_row_permissions(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Drop indexed hits the user cannot actually read.

        ``frappe.utils.global_search.search`` intersects with DocType-level read
        access only, so a User Permission restricting rows would not be applied.
        Each hit is re-checked through frappe.get_list, which does apply
        row-level permissions (issue #189). Anything that cannot be confirmed
        readable is dropped rather than assumed safe.
        """
        wanted: Dict[str, set] = {}
        for hit in hits:
            doctype, name = hit.get("doctype"), hit.get("name")
            if doctype and name:
                wanted.setdefault(doctype, set()).add(name)

        permitted: Dict[str, set] = {}
        for doctype, names in wanted.items():
            try:
                rows = frappe.get_list(
                    doctype,
                    filters={"name": ["in", list(names)]},
                    fields=["name"],
                    limit=len(names),
                    ignore_permissions=False,
                )
                permitted[doctype] = {row.get("name") for row in rows}
            except Exception:
                # Fail closed — an unreadable DocType contributes nothing.
                permitted[doctype] = set()

        results = []
        seen = set()
        for hit in hits:
            doctype, name = hit.get("doctype"), hit.get("name")
            key = (doctype, name)

            # The index yields one row per matched word, so the same document can
            # appear several times for a multi-word query.
            if key in seen or name not in permitted.get(doctype, set()):
                continue

            seen.add(key)
            content = (hit.get("content") or "").strip()
            results.append(
                {
                    "doctype": doctype,
                    "name": name,
                    "content": content[:MAX_CONTENT_SNIPPET] if content else None,
                }
            )

        return results

    @staticmethod
    def _fallback_global_search(
        query: str, limit: int, doctype: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Name-substring scan over well-known DocTypes.

        Only matches document IDs, so it finds "SINV-0001" but not a customer
        name recorded inside that invoice. It exists so a site whose global search
        index was never synced still gets an answer.
        """
        doctypes = [doctype] if doctype else FALLBACK_GLOBAL_DOCTYPES
        results = []

        for candidate in doctypes:
            if len(results) >= limit:
                break

            try:
                if not frappe.db.exists("DocType", candidate):
                    continue
                if not frappe.has_permission(candidate, "read"):
                    continue

                rows = frappe.get_list(
                    candidate,
                    filters={"name": ["like", f"%{query}%"]},
                    fields=["name"],
                    limit=FALLBACK_ROWS_PER_DOCTYPE,
                    ignore_permissions=False,
                )

                for row in rows:
                    results.append({"doctype": candidate, "name": row.get("name"), "content": None})

            except Exception:
                # One inaccessible DocType must not sink the whole scan.
                continue

        return results

    @staticmethod
    def search_doctype(
        doctype: str, query: str, limit: int = 20, filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Text search within one DocType, across its declared search fields."""
        try:
            if not doctype:
                return {"success": False, "error": _("A doctype is required")}

            if not frappe.db.exists("DocType", doctype):
                return {"success": False, "error": _("DocType '{0}' not found").format(doctype)}

            if not frappe.has_permission(doctype, "read"):
                return {
                    "success": False,
                    "error": _("No read permission for DocType '{0}'").format(doctype),
                }

            query = (query or "").strip()
            if not query and not filters:
                return {"success": False, "error": _("A search query or filters are required")}

            meta = frappe.get_meta(doctype)
            search_fields = resolve_search_fields(meta) or ["name"]

            # An empty query means the caller is filtering only, so no text match
            # should be OR'd in.
            or_filters = None
            if query:
                or_filters = [[doctype, field, "like", f"%{query}%"] for field in search_fields]
                or_filters.append([doctype, "name", "like", f"%{query}%"])

            results = frappe.get_list(
                doctype,
                filters=filters or {},
                or_filters=or_filters,
                fields=returnable_fields(meta, search_fields),
                limit=limit,
                order_by="modified desc",
                ignore_permissions=False,
            )

            return {
                "success": True,
                "doctype": doctype,
                "query": query,
                "search_mode": "doctype",
                "results": results,
                "count": len(results),
                "search_fields": search_fields,
                "filters_applied": filters or {},
            }

        except Exception as e:
            frappe.log_error(title=_("DocType Search Error"), message=f"Error searching {doctype}: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def search_link(
        doctype: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = DEFAULT_LINK_LIMIT,
    ) -> Dict[str, Any]:
        """Resolve valid values for a Link field, autocomplete-style.

        Delegates to Frappe's own link search so per-DocType ``standard_queries``
        hooks and user permissions apply, and labels come back display-ready.
        """
        try:
            if not doctype:
                return {"success": False, "error": _("A doctype is required")}

            if not frappe.db.exists("DocType", doctype):
                return {"success": False, "error": _("DocType '{0}' not found").format(doctype)}

            if not frappe.has_permission(doctype, "read"):
                return {
                    "success": False,
                    "error": _("No read permission for DocType '{0}'").format(doctype),
                }

            from frappe.desk.search import search_link as frappe_search_link

            results = frappe_search_link(
                doctype=doctype,
                txt=(query or "").strip(),
                filters=filters or {},
                page_length=limit,
            )

            return {
                "success": True,
                "doctype": doctype,
                "query": query,
                "search_mode": "link_value",
                "results": results,
                "count": len(results),
                "filters_applied": filters or {},
            }

        except Exception as e:
            frappe.log_error(
                title=_("Link Search Error"), message=f"Error searching {doctype} links: {str(e)}"
            )
            return {"success": False, "error": str(e)}
