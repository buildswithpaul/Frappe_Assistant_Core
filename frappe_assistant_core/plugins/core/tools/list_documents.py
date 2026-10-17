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

import re
from typing import Any, Dict, List, Optional

import frappe
from frappe import _
from frappe.model import no_value_fields, table_fields

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


def parse_offset(value: Any) -> Optional[int]:
    """Return the offset as an int, or None when it is not a whole number."""
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdecimal():
        return int(value)
    return None


def default_order_by(doctype: str) -> str:
    """The DocType's own sort, table-qualified. get_meta applies Customize Form changes."""
    meta = frappe.get_meta(doctype)
    if not meta.sort_field:
        return f"`tab{doctype}`.`creation` desc"
    direction = meta.sort_order or "desc"
    clauses = []
    for part in meta.sort_field.split(","):
        words = part.split()
        if words:
            clauses.append(f"`tab{doctype}`.`{words[0]}` {words[1] if len(words) > 1 else direction}")
    return ", ".join(clauses)


def stable_order_by(doctype: str, order_by: str) -> str:
    """Append a unique name tie-breaker so LIMIT/OFFSET pages tile the result set.

    A bare or main-table `name` already makes the order total. A joined child table's
    `name` does not, so it still gets the main-table tie-breaker.
    """
    main_name = f"`tab{doctype}`.`name`"
    if order_by == "KEEP_DEFAULT_ORDERING":
        order_by = default_order_by(doctype)
    if main_name in order_by or re.search(r"(?<![.`\w])name\b", order_by):
        return order_by
    return f"{order_by}, {main_name} asc"


# Grouped totals: the database computes them, over only the rows the user may read.
AGGREGATE_FUNCTIONS = ("sum", "count", "avg", "min", "max")
MAX_AGGREGATES = 5
DEFAULT_GROUP_LIMIT = 100
NUMERIC_FIELDTYPES = {"Currency", "Float", "Int", "Percent"}
# Columns every DocType has that are not in its field list. Restricted ones are still
# refused per role by get_restricted_fields.
STANDARD_GROUP_FIELDS = {"name", "owner", "docstatus", "modified_by"}
GROUP_VALUE_KEY = "group_value"


class GroupedQueryError(ValueError):
    """A grouped request the caller must change; the message is shown to them."""


def resolve_queryable_field(doctype: str, fieldname: Any, restricted: set):
    """The DocField (or None for a standard column) behind `fieldname`, if the user may query it.

    Raises GroupedQueryError otherwise. This is also the SQL-injection guard: on Frappe v15 the
    name is interpolated into a function string, so only real fieldnames get past here.
    """
    if not isinstance(fieldname, str) or not fieldname.isidentifier():
        raise GroupedQueryError(_("{0} is not a valid field name.").format(fieldname))

    meta = frappe.get_meta(doctype)
    if fieldname in restricted:
        raise GroupedQueryError(_("The field {0} is restricted and cannot be queried.").format(fieldname))

    if fieldname in STANDARD_GROUP_FIELDS:
        return None

    df = meta.get_field(fieldname)
    if not df or df.fieldtype in no_value_fields or df.fieldtype in table_fields:
        raise GroupedQueryError(_("{0} is not a field of {1}.").format(fieldname, doctype))

    if df.permlevel not in meta.get_permlevel_access("read"):
        raise GroupedQueryError(_("You do not have permission to read the field {0}.").format(fieldname))

    return df


def build_aggregate_specs(doctype: str, aggregates: Any, restricted: set) -> List[Dict[str, str]]:
    """Validated [{function, field, alias}] for the requested aggregates (count of name by default)."""
    if aggregates is None or aggregates == []:
        aggregates = [{"function": "count", "field": "name"}]

    if not isinstance(aggregates, list) or len(aggregates) > MAX_AGGREGATES:
        raise GroupedQueryError(_("aggregate must be a list of at most {0} items.").format(MAX_AGGREGATES))

    specs = []
    for item in aggregates:
        if not isinstance(item, dict):
            raise GroupedQueryError(_("Each aggregate must be an object with function and field."))

        function = str(item.get("function") or "").lower()
        if function not in AGGREGATE_FUNCTIONS:
            raise GroupedQueryError(
                _("Unknown aggregate function {0}. Use one of: {1}.").format(
                    item.get("function"), ", ".join(AGGREGATE_FUNCTIONS)
                )
            )

        fieldname = item.get("field")
        df = resolve_queryable_field(doctype, fieldname, restricted)
        if function in ("sum", "avg") and (df is None or df.fieldtype not in NUMERIC_FIELDTYPES):
            raise GroupedQueryError(
                _("{0} needs a numeric field (Currency, Float, Int or Percent); {1} is not one.").format(
                    function, fieldname
                )
            )

        specs.append({"function": function, "field": fieldname, "alias": f"{function}_{fieldname}"})

    return specs


def parse_group_order(order_by: Any, specs: List[Dict[str, str]]) -> Optional[str]:
    """`order_by` for a grouped query: one aggregate alias plus asc/desc, e.g. "sum_grand_total desc".

    Returns the validated clause, or None when no order was asked for. Anything that is not
    an alias built from the requested aggregates is refused, so nothing caller-supplied
    reaches the ORDER BY except a name this module constructed from validated fieldnames.
    """
    if order_by is None or order_by == "":
        return None

    aliases = [spec["alias"] for spec in specs]
    parts = str(order_by).split()
    direction = parts[1].lower() if len(parts) == 2 else "asc"
    if len(parts) not in (1, 2) or parts[0] not in aliases or direction not in ("asc", "desc"):
        raise GroupedQueryError(
            _(
                "With group_by, order_by must be one of the aggregates ({0}) optionally followed by asc or desc."
            ).format(", ".join(aliases))
        )
    return f"{parts[0]} {direction}"


def frappe_major_version() -> int:
    """Major version of the running Frappe (15, 16, ...)."""
    return int(frappe.__version__.split(".")[0])


def aggregate_query_fields(specs: List[Dict[str, str]], group_by: Optional[str], v16_form: bool) -> list:
    """The `fields` argument for frappe.get_list: v16 dict form, or the v15 SQL-string form."""
    fields = [group_by] if group_by else []
    for spec in specs:
        if v16_form:
            fields.append({spec["function"].upper(): spec["field"], "as": spec["alias"]})
        else:
            fields.append(f"{spec['function']}(`{spec['field']}`) as {spec['alias']}")
    return fields


def number(value: Any) -> Any:
    """Decimal/None from the database as a JSON number (None stays None: MIN/MAX of nothing)."""
    if value is None or isinstance(value, (int, float)):
        return value
    return float(value)


def run_grouped_query(
    doctype: str,
    filters: Any,
    group_by: Optional[str],
    specs: List[Dict[str, str]],
    limit: int,
    order_by: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Grouped totals through frappe.get_list, so User Permissions and sharing still apply.

    Frappe v16 rejects SQL functions as strings in `fields`, so v16 gets the dict form and
    v15 the string form. The form follows the version rather than a try/except fallback, so
    a real error (a bad filter) is reported as itself instead of as the other form's rejection.
    `order_by` is an aggregate clause from parse_group_order; it ranks groups by their total.
    """
    query = {
        "filters": filters,
        "limit": limit,
        "ignore_permissions": False,
    }
    if group_by:
        query["group_by"] = f"`tab{doctype}`.`{group_by}`"
        group_order = f"`tab{doctype}`.`{group_by}` asc"
        query["order_by"] = f"{order_by}, {group_order}" if order_by else group_order
    else:
        # A bare aggregate has no GROUP BY, and the DocType default sort would break it.
        query["order_by"] = None

    v16_form = frappe_major_version() >= 16
    return frappe.get_list(doctype, fields=aggregate_query_fields(specs, group_by, v16_form), **query)


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
        self.description = "Search and list Frappe documents with optional filtering. Use this when users want to find records, get lists of documents, or search for data. For business totals (sales, receivables, stock) try report_list(query=...) first and come here with group_by only when no report fits; cite the DocType and filters you used in the answer. For submittable DocTypes (invoices, orders, entries) only submitted documents are returned unless you pass docstatus explicitly. If a query returns nothing because a Link filter value matches no record, the response carries unresolved_filters with ranked suggestions — check it before reporting that no data exists. When has_more is true the response carries next_offset; pass it as offset to read the next page. For totals by group (sum, count, avg, min, max) pass group_by and aggregate — exact figures computed by the database over records the user may read; never add up listed rows yourself. To rank groups (top customers by sales) pass order_by as an aggregate alias, e.g. 'sum_grand_total desc'. Grouping by a Date field groups by exact day, not by month or year."
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
                "offset": {
                    "type": "integer",
                    "default": 0,
                    "minimum": 0,
                    "description": "Number of matching records to skip. When a response has has_more=true, pass its next_offset here to read the next page.",
                },
                "order_by": {
                    "type": "string",
                    "description": "Order results by field, e.g. 'creation desc', 'name asc'. Omit to use the DocType's own default ordering (usually modified desc). With group_by, order_by must instead be one aggregate alias (function_field, e.g. 'sum_grand_total') plus asc or desc, to rank groups by total; groups otherwise sort by the group value.",
                },
                "group_by": {
                    "type": "string",
                    "description": "Fieldname to group by, for totals per group (e.g. 'customer', 'territory', a custom field). The database computes the totals, over only records the user may read — use this instead of adding up listed rows yourself. Ignores fields and offset. A Date field groups by exact day (each distinct date is its own group), not by month or year.",
                },
                "aggregate": {
                    "type": "array",
                    "maxItems": 5,
                    "items": {
                        "type": "object",
                        "properties": {
                            "function": {
                                "type": "string",
                                "enum": ["sum", "count", "avg", "min", "max"],
                            },
                            "field": {
                                "type": "string",
                                "description": "Fieldname to aggregate. sum and avg need a Currency, Float, Int or Percent field.",
                            },
                        },
                        "required": ["function", "field"],
                    },
                    "description": "Aggregates per group, e.g. [{'function': 'sum', 'field': 'grand_total'}]. With group_by and no aggregate you get the record count per group; without group_by you get one total row.",
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
        # Guard against empty string from API clients.
        order_by = arguments.get("order_by") or "KEEP_DEFAULT_ORDERING"
        offset = parse_offset(arguments.get("offset"))
        if offset is None or offset < 0:
            return {
                "success": False,
                "error": _("offset must be a whole number of 0 or more."),
                "doctype": doctype,
            }

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

        from frappe_assistant_core.core.field_access import FieldAccessError, check_query_fields

        grouped = bool(arguments.get("group_by") or arguments.get("aggregate"))
        try:
            # A grouped query checks its own group_by, aggregate and order fields; filters apply to both.
            check_query_fields(
                doctype,
                user_role,
                filters=filters,
                fields=None if grouped else fields,
                order_by=None if grouped or order_by == "KEEP_DEFAULT_ORDERING" else order_by,
            )
        except FieldAccessError as e:
            return {"success": False, "error": str(e), "doctype": doctype}

        if grouped:
            return self._execute_grouped(doctype, filters, docstatus_defaulted, user_role, arguments)

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
                # limit_start, not offset: the one spelling Frappe v15 and v16 both accept
                # (v16 deprecates it for offset; v15 has no offset), so do not rename it.
                limit_start=offset,
                order_by=stable_order_by(doctype, order_by),
                ignore_permissions=False,  # Ensure permission checking
            )

            # Filter sensitive fields from document data
            filtered_documents = []
            for doc in documents:
                filtered_doc = filter_sensitive_fields(doc, doctype, user_role)
                filtered_documents.append(filtered_doc)

            # Get permission-aware total count for pagination info.
            # Frappe v16 rejects SQL functions passed as strings in `fields`, so try the
            # dict form first and fall back to the string form for older Frappe versions.
            # Both go through frappe.get_list with ignore_permissions=False.
            try:
                try:
                    count_result = frappe.get_list(
                        doctype,
                        filters=filters,
                        fields=[{"COUNT": "name", "as": "count"}],
                        limit=1,
                        ignore_permissions=False,
                    )
                except Exception:
                    count_result = frappe.get_list(
                        doctype,
                        filters=filters,
                        fields=["count(name) as count"],
                        limit=1,
                        ignore_permissions=False,
                    )
                total_count = count_result[0].get("count") if count_result else 0
            except Exception:
                frappe.log_error(
                    title=f"list_documents: count query failed for {doctype}",
                    message=frappe.get_traceback(),
                )
                total_count = None

            message = f"Found {len(filtered_documents)} {doctype} records"
            if docstatus_defaulted:
                message += (
                    " (submitted only — docstatus=1 applied by default; "
                    "pass docstatus explicitly to include drafts or cancelled documents)"
                )

            returned = len(filtered_documents)
            has_more = (total_count > offset + returned) if total_count is not None else returned >= limit

            result = {
                "success": True,
                "doctype": doctype,
                "data": filtered_documents,
                "count": returned,
                "total_count": total_count,
                "has_more": has_more,
                "filters_applied": filters,
                "message": message,
            }
            if has_more:
                result["next_offset"] = offset + returned

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

    def _execute_grouped(
        self,
        doctype: str,
        filters: Any,
        docstatus_defaulted: bool,
        user_role: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Grouped totals; `fields` and `offset` do not apply."""
        from frappe_assistant_core.core.security_config import ADMIN_ONLY_FIELDS, get_restricted_fields

        group_by = arguments.get("group_by") or None
        limit = arguments.get("limit")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            limit = DEFAULT_GROUP_LIMIT
        limit = min(limit, 1000)

        if frappe.get_meta(doctype).is_virtual:
            # Frappe v16 ignores group_by and the aggregate fields for virtual DocTypes and
            # returns one row per record, which would read as a real grouped answer.
            return {
                "success": False,
                "error": _("{0} is a virtual DocType, which cannot be grouped or aggregated.").format(
                    doctype
                ),
                "doctype": doctype,
            }

        # get_restricted_fields skips a whole-DocType "*" entry (create/update rely on that), but
        # the plain path hides every field of such a DocType from an Assistant User, so must this.
        if user_role == "Assistant User" and ADMIN_ONLY_FIELDS.get(doctype) == "*":
            return {
                "success": False,
                "error": _("Access to {0} is restricted for your role.").format(doctype),
                "doctype": doctype,
            }

        try:
            restricted = get_restricted_fields(doctype, user_role)
            if group_by:
                resolve_queryable_field(doctype, group_by, restricted)
            specs = build_aggregate_specs(doctype, arguments.get("aggregate"), restricted)
            group_order = parse_group_order(arguments.get("order_by"), specs)
            if group_order and not group_by:
                raise GroupedQueryError(_("order_by needs group_by: a total without groups has one row."))

            # One extra row tells us whether the groups were cut off by the limit.
            raw_rows = run_grouped_query(doctype, filters, group_by, specs, limit + 1, group_order)
        except GroupedQueryError as e:
            return {"success": False, "error": str(e), "doctype": doctype}
        except Exception as e:
            frappe.log_error(title=_("Document List Error"), message=f"Error grouping {doctype}: {str(e)}")
            return {"success": False, "error": str(e), "doctype": doctype}

        has_more = len(raw_rows) > limit
        rows = []
        for raw in raw_rows[:limit]:
            row = {GROUP_VALUE_KEY: raw.get(group_by)} if group_by else {}
            for spec in specs:
                row[spec["alias"]] = number(raw.get(spec["alias"]))
            rows.append(row)

        result = {
            "success": True,
            "doctype": doctype,
            "group_by": group_by,
            "rows": rows,
            "row_count": len(rows),
            "has_more": has_more,
            "filters_applied": filters,
            "docstatus_defaulted": docstatus_defaulted,
        }
        if has_more:
            result["message"] = _("Only the first {0} groups are shown; raise limit to see the rest.").format(
                limit
            )
        return result


# Make sure class name matches file name for discovery
document_list = DocumentList
