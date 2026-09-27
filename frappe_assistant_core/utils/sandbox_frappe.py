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
Permission-checked Frappe data access for the run_python_code sandbox.

Sandbox code gets ``frappe``, ``db``, ``get_list`` and friends from here
instead of the real framework objects, and the ``tools`` API reads through
the same functions. Every read goes through ``frappe.get_list`` (lists,
counts, lookups) or ``Document.check_permission`` (single documents), so role
permissions, User Permissions, permission query hooks, sharing and field-level
read permissions apply exactly as they do in Desk. Raw SQL is not offered
because it cannot be permission-checked.

This makes the documented paths correct. It is not a security boundary: code
that deliberately walks object attributes can still reach the real module.
"""

import re

import frappe
import frappe.utils

# get_list kwargs that would widen what the session user can see, or write user settings.
_BLOCKED_KWARGS = (
    "ignore_permissions",
    "user",
    "save_user_settings",
    "save_user_settings_fields",
    "user_settings",
)

_AGGREGATES = frozenset({"COUNT", "SUM", "AVG", "MIN", "MAX"})
_STRING_AGGREGATE = re.compile(
    r"^\s*(count|sum|avg|min|max)\s*\(\s*(\*|[\w.`]+)\s*\)\s*(?:as\s+`?(\w+)`?)?\s*$", re.IGNORECASE
)
_AGGREGATE_ARGUMENT = re.compile(r"^(\*|[\w.]+)$")
_ALIAS = re.compile(r"^\w+$")

_UTILS = (
    "add_days",
    "add_months",
    "add_to_date",
    "add_years",
    "cint",
    "cstr",
    "date_diff",
    "flt",
    "fmt_money",
    "format_date",
    "format_datetime",
    "format_time",
    "formatdate",
    "get_datetime",
    "get_first_day",
    "get_first_day_of_week",
    "get_last_day",
    "get_last_day_of_week",
    "get_quarter_ending",
    "get_quarter_start",
    "get_time",
    "get_timespan_date_range",
    "get_year_ending",
    "get_year_start",
    "getdate",
    "global_date_format",
    "money_in_words",
    "month_diff",
    "now",
    "now_datetime",
    "nowdate",
    "nowtime",
    "pretty_date",
    "rounded",
    "time_diff",
    "time_diff_in_hours",
    "time_diff_in_seconds",
    "today",
)


# ---------------------------------------------------------------------------
# Aggregate fields: v15 accepts only SQL strings, v16 accepts only dicts
# ---------------------------------------------------------------------------


def _dict_aggregates() -> bool:
    return int(frappe.__version__.split(".")[0]) >= 16


def normalize_field(field):
    """Rewrite an aggregate field into the form the running Frappe version accepts.

    Accepts ``{"SUM": "grand_total", "as": "total"}`` or ``"sum(grand_total) as total"``
    for COUNT, SUM, AVG, MIN and MAX. Every other field passes through unchanged.
    """
    if isinstance(field, dict):
        functions = [key for key in field if key != "as"]
        if len(functions) != 1 or functions[0].upper() not in _AGGREGATES:
            return field
        function, argument, alias = functions[0].upper(), str(field[functions[0]]), field.get("as")
        if _dict_aggregates():
            return {function: argument, "as": alias} if alias else {function: argument}
        if not _AGGREGATE_ARGUMENT.match(argument) or (alias and not _ALIAS.match(alias)):
            raise frappe.ValidationError(f"Invalid aggregate field: {field}")
        sql = f"{function.lower()}({argument})"
        return f"{sql} as {alias}" if alias else sql

    if isinstance(field, str) and _dict_aggregates():
        match = _STRING_AGGREGATE.match(field)
        if match:
            function, argument, alias = match.groups()
            spec = {function.upper(): argument.replace("`", "")}
            if alias:
                spec["as"] = alias
            return spec

    return field


def _normalize_fields(fields):
    if isinstance(fields, (list, tuple)):
        return [normalize_field(field) for field in fields]
    return fields


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def get_list(doctype, *args, **kwargs):
    """``frappe.get_list`` as the session user. Kwargs that would widen access are dropped.

    Only ``fields`` and ``filters`` may be positional; everything else must be a
    keyword so it passes through the blocklist below.
    """
    if len(args) > 2:
        raise TypeError(
            "run_python_code: pass get_list options other than fields and filters as keywords, "
            "e.g. frappe.get_list(doctype, fields=[...], filters={...}, limit=10)"
        )
    if len(args) >= 1:
        kwargs.setdefault("fields", args[0])
    if len(args) == 2:
        kwargs.setdefault("filters", args[1])
    for key in _BLOCKED_KWARGS:
        kwargs.pop(key, None)
    if "fields" in kwargs:
        kwargs["fields"] = _normalize_fields(kwargs["fields"])
    return frappe.get_list(doctype, **kwargs)


def get_all(doctype, *args, **kwargs):
    """``frappe.get_all``'s signature and no default row limit, but permission-checked."""
    if "limit_page_length" not in kwargs:
        kwargs["limit_page_length"] = 0
    return get_list(doctype, *args, **kwargs)


class ReadOnlyDoc(frappe._dict):
    """Document data with attribute access. Write methods fail loudly instead of returning None."""

    _WRITE_METHODS = frozenset(
        {"save", "insert", "submit", "cancel", "delete", "db_set", "db_update", "run_method", "add_comment"}
    )

    def __getattribute__(self, key):
        # Document fields win over dict methods, so a child table named `items`
        # (every ERPNext invoice/order) returns its rows, as on a real Document.
        if not key.startswith("_") and dict.__contains__(self, key):
            return dict.__getitem__(self, key)
        return super().__getattribute__(key)

    def __getattr__(self, key):
        if key in ReadOnlyDoc._WRITE_METHODS:
            raise frappe.PermissionError(f"run_python_code is read-only: doc.{key}() is not available")
        return self.get(key)

    def as_dict(self, *args, **kwargs):
        return self


def get_doc(doctype, name=None):
    """Load an existing document the session user may read, as a read-only dict."""
    if not isinstance(doctype, str):
        raise frappe.PermissionError(
            "run_python_code can only load existing documents: frappe.get_doc(doctype, name)"
        )
    doc = frappe.get_doc(doctype, doctype if name is None else name)
    doc.check_permission("read")
    doc.apply_fieldlevel_read_permissions()
    return ReadOnlyDoc(doc.as_dict())


def get_single(doctype):
    return get_doc(doctype, doctype)


def count(doctype, filters=None, *args, **kwargs):
    rows = get_list(doctype, filters=filters, fields=[{"COUNT": "name", "as": "count"}], limit=1)
    return rows[0].get("count", 0) if rows else 0


def get_value(
    doctype,
    filters=None,
    fieldname="name",
    ignore=None,
    as_dict=False,
    debug=False,
    order_by=None,
    *args,
    **kwargs,
):
    """Mirrors ``frappe.db.get_value``'s positional order; reads through get_list."""
    single_field = isinstance(fieldname, (str, dict))
    if isinstance(fieldname, dict) and "as" not in fieldname:
        fieldname = {**fieldname, "as": "value"}
    fields = [fieldname] if single_field else list(fieldname)
    as_dict = as_dict or fieldname == "*"

    if frappe.get_meta(doctype).issingle:
        doc = get_single(doctype)
        if fieldname == "*":
            return doc
        row = frappe._dict({field: doc.get(field) for field in fields})
    elif filters is None:
        return None
    else:
        if isinstance(filters, (str, int)):
            filters = {"name": filters}
        list_kwargs = {"filters": filters, "fields": fields, "limit": 1}
        if order_by:
            list_kwargs["order_by"] = order_by
        rows = get_list(doctype, **list_kwargs)
        if not rows:
            return None
        row = rows[0]

    if as_dict:
        return row
    values = tuple(row.get(_result_key(field)) for field in fields)
    return values[0] if single_field else values


def _result_key(field) -> str:
    """Key a requested field comes back under: alias, else last dotted part."""
    if isinstance(field, dict):
        return field["as"]
    lowered = field.lower()
    if " as " in lowered:
        field = field[lowered.rindex(" as ") + 4 :]
    return field.strip().strip("`").split(".")[-1]


def get_single_value(doctype, fieldname, *args, **kwargs):
    return get_single(doctype).get(fieldname)


def exists(doctype, name=None, *args, **kwargs):
    if isinstance(doctype, dict):
        filters = {key: value for key, value in doctype.items() if key != "doctype"}
        doctype = doctype["doctype"]
    elif isinstance(name, (dict, list)):
        filters = name
    elif name is None:
        filters = {}
    else:
        filters = {"name": name}
    rows = get_list(doctype, filters=filters, pluck="name", limit=1)
    return rows[0] if rows else None


def _sql_unavailable(*args, **kwargs):
    raise frappe.PermissionError(
        "frappe.db.sql is not available in run_python_code: raw SQL skips role permissions and "
        "User Permissions. Use frappe.get_list or tools.get_documents with group_by and aggregate "
        'fields such as {"SUM": "grand_total", "as": "total"}, or aggregate in pandas.'
    )


def fetch_data_query(data_query: dict) -> list:
    """Rows for run_python_code's ``data_query`` argument."""
    return get_list(
        data_query.get("doctype"),
        fields=data_query.get("fields", ["*"]),
        filters=data_query.get("filters", {}),
        limit_page_length=data_query.get("limit", 100),
    )


# ---------------------------------------------------------------------------
# The ``frappe`` object sandbox code sees
# ---------------------------------------------------------------------------


class _Namespace:
    """Read-only attribute bag. A miss names what is available instead of leaking the real attribute."""

    def __init__(self, label, attrs):
        object.__setattr__(self, "_label", label)
        object.__setattr__(self, "_attrs", attrs)

    def __getattr__(self, name):
        try:
            return self._attrs[name]
        except KeyError:
            raise AttributeError(
                f"{self._label}.{name} is not available in run_python_code. "
                f"Available: {', '.join(sorted(self._attrs))}"
            ) from None

    def __setattr__(self, name, value):
        raise AttributeError(f"{self._label} is read-only in run_python_code")

    def __dir__(self):
        return sorted(self._attrs)

    def __repr__(self):
        return f"<{self._label} (run_python_code)>"


def build_sandbox_frappe(user: str) -> _Namespace:
    db = _Namespace(
        "frappe.db",
        {
            "get_list": get_list,
            "get_all": get_all,
            "get_value": get_value,
            "get_single_value": get_single_value,
            "count": count,
            "exists": exists,
            "sql": _sql_unavailable,
        },
    )
    utils = _Namespace(
        "frappe.utils", {name: getattr(frappe.utils, name) for name in _UTILS if hasattr(frappe.utils, name)}
    )
    return _Namespace(
        "frappe",
        {
            "get_list": get_list,
            "get_all": get_all,
            "get_doc": get_doc,
            "get_single": get_single,
            "get_value": get_value,
            "db": db,
            "utils": utils,
            "session": _Namespace("frappe.session", {"user": user}),
            "as_json": frappe.as_json,
            "parse_json": frappe.parse_json,
            "PermissionError": frappe.PermissionError,
            "ValidationError": frappe.ValidationError,
            "DoesNotExistError": frappe.DoesNotExistError,
        },
    )
