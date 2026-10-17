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
Which fields a user may name in a query: as a filter, a sort key, or inside a selected expression.

A field the user cannot read must not be usable to narrow a query either, or its value can be
worked out one query at a time from which records match. Frappe v16 refuses such a filter, v15
does not, and neither knows FAC's own SENSITIVE_FIELDS and ADMIN_ONLY_FIELDS. So every field a
tool passes to frappe.get_list on the caller's behalf is checked here first.
"""

import json
import re
from typing import Any, Iterator, Optional, Set, Tuple

import frappe
from frappe import _
from frappe.desk.reportview import extract_fieldnames
from frappe.model import child_table_fields, default_fields, optional_fields

from frappe_assistant_core.core.security_config import ADMIN_ONLY_FIELDS, SENSITIVE_FIELDS

# filter_sensitive_fields shows this role every field, so nothing is restricted for it here either.
UNRESTRICTED_ROLE = "System Manager"
LINKING_FIELDTYPES = {"Link", "Table", "Table MultiSelect"}
SORT_DIRECTION = re.compile(r"\s+(asc|desc)\b", re.IGNORECASE)
# Columns every table has without a DocField. Anything else must match a DocField exactly: MariaDB
# reads `API_KEY` as api_key, and Frappe v15 passes an unknown name or an ifnull(...) key through.
STANDARD_COLUMNS = frozenset(default_fields) | frozenset(optional_fields) | frozenset(child_table_fields)
FILTER_CONJUNCTIONS = {"and", "or"}


class FieldAccessError(ValueError):
    """A field the caller may not query; the message is shown to them."""


def query_restricted_fields(doctype: str, user_role: str) -> Set[str]:
    """Fields of `doctype` whose values FAC withholds from `user_role`, so none may be queried either.

    ADMIN_ONLY_FIELDS["all_doctypes"] is left out: owner, creation, docstatus, _assign and the rest
    are write-protected for an Assistant User, not secret. Every Desk list view filters on them,
    and list_documents itself adds a docstatus filter.
    """
    if user_role == UNRESTRICTED_ROLE:
        return set()

    restricted = set(SENSITIVE_FIELDS.get("all_doctypes", []))
    restricted.update(SENSITIVE_FIELDS.get(doctype, []))
    if user_role == "Assistant User":
        admin_only = ADMIN_ONLY_FIELDS.get(doctype, [])
        if admin_only != "*":
            restricted.update(admin_only)
    return restricted


def is_field_readable(meta, fieldname: str, user_role: str, parenttype: Optional[str] = None) -> bool:
    """Whether `user_role`'s user may read `fieldname` of `meta`, by FAC's lists and by permlevel."""
    if fieldname in query_restricted_fields(meta.name, user_role):
        return False

    df = meta.get_field(fieldname)
    # Standard columns have no DocField, and a permlevel-0 field is readable to anyone who reads
    # the DocType, which is also all a DocType without permission rules (a Single, say) offers.
    if not df or not df.permlevel:
        return True
    return df.permlevel in meta.get_permlevel_access("read", parenttype=parenttype)


def is_column(doctype: str, fieldname: str) -> bool:
    return fieldname in STANDARD_COLUMNS or frappe.get_meta(doctype).get_field(fieldname) is not None


def resolve_field(doctype: str, reference: str) -> Tuple[str, str]:
    """(DocType, fieldname) a filter or column reference points at, or FieldAccessError.

    Accepts `field`, `` `tabChild DocType`.`field` ``, `Child DocType.field`, the Frappe v16 form
    `link_or_table_field.field`, and a bare child-table field, which Frappe v15 looks up in the
    DocType's tables when the DocType itself has no such field.
    """
    reference = reference.replace("`", "").strip()
    if "." not in reference:
        if is_column(doctype, reference):
            return doctype, reference
        for table_field in frappe.get_meta(doctype).get_table_fields():
            if table_field.options and is_column(table_field.options, reference):
                return table_field.options, reference
        raise FieldAccessError(_("{0} is not a field of {1}.").format(reference, doctype))

    prefix, fieldname = reference.split(".", 1)
    df = frappe.get_meta(doctype).get_field(prefix)
    if prefix.startswith("tab") and frappe.db.exists("DocType", prefix[3:]):
        target = prefix[3:]
    elif df and df.fieldtype in LINKING_FIELDTYPES and df.options:
        target = df.options
    elif frappe.db.exists("DocType", prefix):
        target = prefix
    else:
        raise FieldAccessError(_("{0} is not a field of {1}.").format(reference, doctype))

    if not is_column(target, fieldname):
        raise FieldAccessError(_("{0} is not a field of {1}.").format(reference, doctype))
    return target, fieldname


def check_field(doctype: str, reference: str, user_role: str, target_doctype: Optional[str] = None) -> None:
    """Raise FieldAccessError unless the user may query `reference` on a `doctype` query."""
    if target_doctype:
        target = target_doctype.replace("`", "").removeprefix("tab")
        if not frappe.db.exists("DocType", target):
            raise FieldAccessError(_("{0} is not a DocType.").format(target))
        fieldname = reference.replace("`", "").strip()
        if not is_column(target, fieldname):
            raise FieldAccessError(_("{0} is not a field of {1}.").format(fieldname, target))
    else:
        target, fieldname = resolve_field(doctype, reference)

    meta = frappe.get_meta(target)
    parenttype = None
    if target != doctype:
        if meta.istable:
            # A child table has no permissions of its own; Frappe grants them through the parent.
            parenttype = doctype
        elif not frappe.has_permission(target, "read"):
            raise FieldAccessError(_("You do not have permission to query the field {0}.").format(reference))

    if not is_field_readable(meta, fieldname, user_role, parenttype=parenttype):
        raise FieldAccessError(_("You do not have permission to query the field {0}.").format(reference))


def filter_references(filters: Any) -> Iterator[Tuple[Optional[str], str]]:
    """(explicit DocType or None, field reference) for every condition in `filters`."""
    if isinstance(filters, str):
        try:
            filters = json.loads(filters) if filters.strip() else {}
        except ValueError:
            raise FieldAccessError(_("filters must be a JSON object or a list of conditions."))

    if not filters:
        return

    if isinstance(filters, dict):
        for key in filters:
            yield None, str(key)
        return

    if not isinstance(filters, (list, tuple)):
        raise FieldAccessError(_("filters must be a JSON object or a list of conditions."))

    # A single unwrapped condition, e.g. ["status", "=", "Paid"]
    single = isinstance(filters[0], str) and filters[0].lower() not in FILTER_CONJUNCTIONS
    conditions = [filters] if single else filters
    for condition in conditions:
        if isinstance(condition, str) and condition.lower() in FILTER_CONJUNCTIONS:
            continue
        if isinstance(condition, dict):
            yield from filter_references(condition)
        elif (
            isinstance(condition, (list, tuple))
            and condition
            and isinstance(condition[0], (list, tuple, dict))
        ):
            # A Frappe v16 group, e.g. [["status", "=", "Paid"], "or", ["customer", "=", "X"]]
            yield from filter_references(list(condition))
        elif isinstance(condition, (list, tuple)) and condition:
            # ["doctype", "fieldname", op, value] or ["fieldname", op, value]
            if len(condition) >= 4:
                yield str(condition[0]), str(condition[1])
            else:
                yield None, str(condition[0])
        else:
            raise FieldAccessError(
                _("Each filter condition must be a list such as [field, operator, value].")
            )


def expression_columns(expression: str) -> Iterator[str]:
    """The column references inside a selected or sorted expression, e.g. `max(rate) as m` -> rate."""
    try:
        columns = extract_fieldnames(expression)
    except Exception:
        raise FieldAccessError(_("{0} is not a valid field expression.").format(expression))

    for column in columns:
        column = column.strip()
        if column and column != "*" and not column.isnumeric():
            yield column


def check_query_fields(
    doctype: str,
    user_role: str,
    filters: Any = None,
    fields: Any = None,
    order_by: Optional[str] = None,
) -> None:
    """Raise FieldAccessError if a filter, sort key or `fields` expression names an unreadable field.

    A bare field name in `fields` is left to the caller, which strips or masks it in the result;
    an expression or alias would carry the value out under another name, so it is checked here.
    """
    if user_role == "Assistant User" and ADMIN_ONLY_FIELDS.get(doctype) == "*":
        # Every field of such a DocType is withheld from an Assistant User's results.
        raise FieldAccessError(_("Access to {0} is restricted for your role.").format(doctype))

    for target_doctype, reference in filter_references(filters):
        check_field(doctype, reference, user_role, target_doctype=target_doctype)

    if order_by:
        for column in expression_columns(SORT_DIRECTION.sub("", order_by)):
            check_field(doctype, column, user_role)

    # Frappe v15 also accepts fields as one comma-separated string.
    for entry in [fields] if isinstance(fields, str) else fields or []:
        if isinstance(entry, str):
            if entry == "*" or entry.isidentifier():
                continue
            expressions = [entry]
        elif isinstance(entry, dict):
            # Frappe v16 aggregate form, e.g. {"SUM": "grand_total", "as": "total"}
            expressions = [value for key, value in entry.items() if key != "as" and isinstance(value, str)]
        else:
            raise FieldAccessError(_("fields must be a list of field names."))

        for expression in expressions:
            for column in expression_columns(expression):
                check_field(doctype, column, user_role)
