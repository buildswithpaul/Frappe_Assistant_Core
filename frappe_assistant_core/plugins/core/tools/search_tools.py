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

import re
from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _

from frappe_assistant_core.core.field_access import (
    STANDARD_COLUMNS,
    FieldAccessError,
    check_field,
    check_query_fields,
    filter_references,
)
from frappe_assistant_core.core.security_config import get_user_primary_role
from frappe_assistant_core.utils.permissions import (
    INDEX_SEPARATOR,
    field_reader,
    indexes_unreadable_field,
    readable_fieldnames,
)

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


def like_pattern(word: str) -> Optional[str]:
    """`%word%` for a LIKE filter, where a `%` or `_` the user typed can't match every row; or None.

    Frappe 16 passes the value as a parameter, so they are escaped and matched literally. Frappe 15
    doubles every backslash in a LIKE value itself, so an escape can't get through: there a `%` is
    dropped, as Frappe's own link search does, and a word of only `_` is left out.
    """
    if int(frappe.__version__.split(".")[0]) >= 16:
        return "%" + word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    word = word.replace("%", "")
    return f"%{word}%" if word.strip("_") else None


def has_link_query(doctype: str) -> bool:
    """Whether Frappe's link search for `doctype` runs an app's query (the standard_queries hook)."""
    return doctype in (frappe.get_hooks("standard_queries") or {})


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

        return SearchTools._filter_by_row_permissions(raw, query, limit), True

    @staticmethod
    def _filter_by_row_permissions(
        hits: List[Dict[str, Any]], query: str = "", limit: int = 20
    ) -> List[Dict[str, Any]]:
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
        user_role = get_user_primary_role(frappe.session.user)
        # DocTypes whose index text holds a field this user may not read (#390). Neither that text
        # nor the fact that a record matched can be shown, so they are searched again below,
        # over the fields the user may read.
        blind: Dict[str, bool] = {}
        for hit in hits:
            doctype, name = hit.get("doctype"), hit.get("name")
            key = (doctype, name)

            # The index yields one row per matched word, so the same document can
            # appear several times for a multi-word query.
            if key in seen or name not in permitted.get(doctype, set()):
                continue

            if doctype not in blind:
                blind[doctype] = indexes_unreadable_field(doctype, user_role)
            if blind[doctype]:
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

        for doctype in [doctype for doctype, hides in blind.items() if hides]:
            for row in SearchTools._readable_field_search(doctype, query, limit, user_role):
                key = (doctype, row["name"])
                if key not in seen:
                    seen.add(key)
                    results.append(row)

        return results

    @staticmethod
    def _readable_field_search(doctype: str, query: str, limit: int, user_role: str) -> List[Dict[str, Any]]:
        """Global-search hits on `doctype` found in, and shown from, only the fields the user may read.

        The same fields the index holds (in_global_search, on the record and its rows), less the
        unreadable ones, matched with LIKE through frappe.get_list, so row permissions apply too.
        Frappe splits a global-search query into words on "&"; spaces split it here as well.
        """
        from frappe.utils import strip_html_tags

        words = [word for word in re.split(r"[&\s]+", query or "") if word]
        if not words:
            return []

        meta = frappe.get_meta(doctype)
        can_read = field_reader(meta, user_role)
        fields = [df for df in meta.get_global_search_fields() if can_read(df.fieldname)]
        or_filters = [[doctype, df.fieldname, "like", f"%{word}%"] for df in fields for word in words]
        for table_field in meta.get_table_fields():
            child = frappe.get_meta(table_field.options)
            child_can_read = field_reader(child, user_role, parenttype=doctype)
            or_filters.extend(
                [child.name, df.fieldname, "like", f"%{word}%"]
                for df in child.get_global_search_fields()
                if child_can_read(df.fieldname)
                for word in words
            )
        if not or_filters:
            return []

        shown = [df for df in fields if df.fieldname != "name"]
        try:
            rows = frappe.get_list(
                doctype,
                or_filters=or_filters,
                fields=["name"] + [df.fieldname for df in shown],
                limit=limit,
                distinct=True,
                ignore_permissions=False,
            )
        except Exception:
            # Fail closed, as the row-permission check above does.
            return []

        results = []
        for row in rows:
            content = INDEX_SEPARATOR.join(
                f"{df.label} : {strip_html_tags(str(row.get(df.fieldname)))}"
                for df in shown
                if row.get(df.fieldname) not in (None, "")
            )
            results.append(
                {
                    "doctype": doctype,
                    "name": row.get("name"),
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

            user_role = get_user_primary_role(frappe.session.user)
            if filters:
                # A filter on a field the user cannot read narrows the result to its value (#390).
                try:
                    check_query_fields(doctype, user_role, filters=filters)
                except FieldAccessError as e:
                    return {"success": False, "error": str(e), "doctype": doctype}

            meta = frappe.get_meta(doctype)
            search_fields = readable_fieldnames(meta, resolve_search_fields(meta), user_role) or ["name"]

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
        hooks and user permissions apply, and labels come back display-ready. For a DocType whose
        title or search fields include one the user can't read, FAC searches the readable fields
        itself instead (_readable_link_search).
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

            user_role = get_user_primary_role(frappe.session.user)
            meta = frappe.get_meta(doctype)
            hooked = has_link_query(doctype)
            # Frappe 15's link search runs a filter on a field the user cannot read, so repeated
            # filters narrow down its value (#390).
            try:
                SearchTools._check_link_filters(doctype, user_role, filters, hooked)
            except FieldAccessError as e:
                return {"success": False, "error": str(e), "doctype": doctype}

            if SearchTools._link_search_reads_hidden_field(meta, user_role):
                try:
                    results = SearchTools._readable_link_search(
                        meta, (query or "").strip(), filters, limit, user_role, hooked
                    )
                except FieldAccessError as e:
                    return {"success": False, "error": str(e), "doctype": doctype}
            else:
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

    @staticmethod
    def _check_link_filters(doctype: str, user_role: str, filters, hooked: bool) -> None:
        """Raise FieldAccessError for a link-search filter on anything but a field the user may read.

        A DocType with a standard_queries hook hands its filters to the app's query, which may
        take keys that aren't columns. There a key that names a column is checked, exactly or in
        another case (MariaDB reads `TAX_ID` as tax_id), and anything but a plain ASCII name (an
        expression, an accented variant MariaDB may fold onto a column) is refused.
        """
        if not filters:
            return
        check_query_fields(doctype, user_role, filters=None if hooked else filters)
        if not hooked:
            return

        columns = {name.lower() for name in STANDARD_COLUMNS}
        columns.update(df.fieldname.lower() for df in frappe.get_meta(doctype).fields if df.fieldname)
        for target, reference in filter_references(filters):
            try:
                check_field(doctype, reference, user_role, target_doctype=target)
            except FieldAccessError:
                key = reference.replace("`", "").strip()
                if target or not (key.isascii() and key.isidentifier()) or key.lower() in columns:
                    raise

    @staticmethod
    def _is_query_column(doctype: str, condition) -> bool:
        """Whether a filter condition names a field or column of the query (not an app's own key)."""
        from frappe_assistant_core.core.field_access import is_column, resolve_field

        try:
            for target, reference in filter_references([condition]):
                if target:
                    target = target.replace("`", "").removeprefix("tab")
                    if not (
                        frappe.db.exists("DocType", target) and is_column(target, reference.replace("`", ""))
                    ):
                        return False
                else:
                    resolve_field(doctype, reference)
        except FieldAccessError:
            return False
        return True

    @staticmethod
    def _link_search_reads_hidden_field(meta, user_role: str) -> bool:
        """Whether Frappe's link search for `meta` would match on, or show, a field the user can't read.

        Frappe matches the text against the title and search_fields and shows their values in
        each result's description, with no regard to permlevel. An app's own query (standard_queries)
        is taken to search the same fields.
        """
        can_read = field_reader(meta, user_role)
        return any(
            fieldname and not can_read(fieldname)
            for fieldname in [meta.title_field, *meta.get_search_fields()]
        )

    @staticmethod
    def _readable_link_search(
        meta, query: str, filters, limit: int, user_role: str, hooked: bool = False
    ) -> List[Dict[str, Any]]:
        """Frappe's link search over the fields the user may read: `value` and `description` rows.

        As in frappe.desk.search.search_widget, disabled records are left out and the text is
        matched against the name and the search fields, here only the readable ones. For a
        DocType with an app's query, its own keys that aren't columns (already checked by
        _check_link_filters) can't apply here and are left out; the column keys still apply.
        """
        from frappe.utils import cstr
        from frappe.utils.data import make_filter_tuple

        doctype = meta.name
        if isinstance(filters, dict):
            conditions = [make_filter_tuple(doctype, key, value) for key, value in filters.items()]
        else:
            conditions = [condition for condition in filters or [] if isinstance(condition, (list, tuple))]
        if hooked:
            conditions = [c for c in conditions if SearchTools._is_query_column(doctype, c)]
        check_query_fields(doctype, user_role, filters=conditions)

        search_fields = readable_fieldnames(meta, resolve_search_fields(meta), user_role)
        if meta.get("fields", {"fieldname": "enabled", "fieldtype": "Check"}):
            conditions.append([doctype, "enabled", "=", 1])
        if meta.get("fields", {"fieldname": "disabled", "fieldtype": "Check"}):
            conditions.append([doctype, "disabled", "!=", 1])
        or_filters = None
        if query:
            pattern = like_pattern(query)
            if not pattern:
                return []
            or_filters = [[doctype, field, "like", pattern] for field in ["name", *search_fields]]

        shown = [field for field in returnable_fields(meta, search_fields) if field != "name"]
        rows = frappe.get_list(
            doctype,
            filters=conditions,
            or_filters=or_filters,
            fields=["name", *shown],
            limit=limit,
            order_by="modified desc",
            ignore_permissions=False,
        )
        return [
            {
                "value": row.get("name"),
                "description": ", ".join(cstr(row.get(field)) for field in shown if row.get(field)),
            }
            for row in rows
        ]
