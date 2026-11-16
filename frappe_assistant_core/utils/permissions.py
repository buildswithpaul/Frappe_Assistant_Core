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

import json

import frappe
from frappe import _, get_doc, has_permission

ASSISTANT_ADMIN_ROLES = ("System Manager", "Assistant Admin")
ASSISTANT_ACCESS_ROLES = ASSISTANT_ADMIN_ROLES + ("Assistant User",)


def check_tool_permissions(tool_name: str, user: str) -> bool:
    """Check if the user has permissions to access the specified tool."""
    tool = get_doc("assistant Tool Registry", tool_name)

    if not tool.enabled:
        return False

    required_permissions = json.loads(tool.required_permissions or "[]")

    for perm in required_permissions:
        if isinstance(perm, dict):
            doctype = perm.get("doctype")
            permission_type = perm.get("permission", "read")
            if not has_permission(doctype, permission_type, user=user):
                return False
        elif isinstance(perm, str):
            if perm not in get_roles(user):
                return False

    return True


def get_roles(user: str) -> list:
    """Retrieve roles for the specified user."""
    return [role.role for role in get_doc("User", user).roles] if user else []


# NOTE: get_permission_query_conditions function removed as Assistant Connection Log no longer exists


def get_audit_permission_query_conditions(user=None):
    """Permission query conditions for Assistant Audit Log."""
    if not user:
        user = frappe.session.user

    user_roles = frappe.get_roles(user)
    escaped_user = frappe.db.escape(user)

    # System Manager, Assistant Admin, and Auditor can see all audit logs.
    if any(role in user_roles for role in ASSISTANT_ADMIN_ROLES + ("Auditor",)):
        return ""

    # Assistant Users can only see their own audit logs.
    if "Assistant User" in user_roles:
        return f"`tabAssistant Audit Log`.user = {escaped_user}"

    # No access for others
    return "1=0"


def check_assistant_permission(user=None):
    """Check if user has assistant access permission"""
    if not user:
        user = frappe.session.user

    user_roles = frappe.get_roles(user)

    return any(role in user_roles for role in ASSISTANT_ACCESS_ROLES)


def check_assistant_admin_permission(user=None):
    """Check if user has assistant admin access permission."""
    if not user:
        user = frappe.session.user

    user_roles = frappe.get_roles(user)

    return any(role in user_roles for role in ASSISTANT_ADMIN_ROLES)


def get_prompt_permission_query_conditions(user=None):
    """
    Permission query conditions for Prompt Template.

    Users can see:
    - Their own prompts (any status)
    - Published + Public prompts
    - Published + Shared prompts (if user has required role)
    - Published + System prompts
    """
    if not user:
        user = frappe.session.user

    # System Manager can see all
    if "System Manager" in frappe.get_roles(user):
        return ""

    user_roles = frappe.get_roles(user)
    escaped_user = frappe.db.escape(user)

    # Build the condition
    conditions = []

    # 1. User's own prompts
    conditions.append(f"`tabPrompt Template`.owner_user = {escaped_user}")

    # 2. Published + Public prompts
    conditions.append(
        "(`tabPrompt Template`.status = 'Published' AND `tabPrompt Template`.visibility = 'Public')"
    )

    # 3. Published + System prompts
    conditions.append("(`tabPrompt Template`.status = 'Published' AND `tabPrompt Template`.is_system = 1)")

    # 4. Published + Shared prompts with user's roles
    if user_roles:
        escaped_roles = ", ".join(frappe.db.escape(r) for r in user_roles)
        conditions.append(f"""
            (`tabPrompt Template`.status = 'Published'
             AND `tabPrompt Template`.visibility = 'Shared'
             AND EXISTS (
                SELECT 1 FROM `tabHas Role` hr
                WHERE hr.parent = `tabPrompt Template`.name
                  AND hr.parenttype = 'Prompt Template'
                  AND hr.role IN ({escaped_roles})
             ))
        """)

    return "(" + " OR ".join(conditions) + ")"


def get_skill_permission_query_conditions(user=None):
    """
    Permission query conditions for Skill.

    Users can see:
    - Their own skills (any status)
    - Published + Public skills
    - Published + Shared skills (if user has required role)
    - Published + System skills
    """
    if not user:
        user = frappe.session.user

    # System Manager can see all
    if "System Manager" in frappe.get_roles(user):
        return ""

    user_roles = frappe.get_roles(user)
    escaped_user = frappe.db.escape(user)

    conditions = []

    # 1. User's own skills
    conditions.append(f"`tabFAC Skill`.owner_user = {escaped_user}")

    # 2. Published + Public skills
    conditions.append("(`tabFAC Skill`.status = 'Published' AND `tabFAC Skill`.visibility = 'Public')")

    # 3. Published + System skills
    conditions.append("(`tabFAC Skill`.status = 'Published' AND `tabFAC Skill`.is_system = 1)")

    # 4. Published + Shared skills with user's roles
    if user_roles:
        escaped_roles = ", ".join(frappe.db.escape(r) for r in user_roles)
        conditions.append(f"""
            (`tabFAC Skill`.status = 'Published'
             AND `tabFAC Skill`.visibility = 'Shared'
             AND EXISTS (
                SELECT 1 FROM `tabHas Role` hr
                WHERE hr.parent = `tabFAC Skill`.name
                  AND hr.parenttype = 'FAC Skill'
                  AND hr.role IN ({escaped_roles})
             ))
        """)

    return "(" + " OR ".join(conditions) + ")"


# Field-level access: what of a record reaches a user who may read the record but not every field
# of it (GitHub #390). The rule is Frappe's own: Meta.get_permitted_fieldnames for reading,
# Meta/Document.get_permlevel_access and BaseDocument.reset_values_if_no_permlevel_access for
# writing. Each helper asks Frappe once per DocType. With a `user_role`, FAC's own SENSITIVE_FIELDS
# and ADMIN_ONLY_FIELDS are withheld as well (core.field_access.query_restricted_fields).
# Imports stay inside the functions: hooks load this module for every permission query.

# What frappe.utils.global_search puts between the "Label : value" parts of a hit's content.
INDEX_SEPARATOR = " ||| "


def field_reader(meta, user_role: str = None, parenttype: str = None):
    """A `can_read(fieldname)` check for `meta`: FAC's one rule for reading a field.

    The rule of Frappe 16's filter check (DatabaseQuery._check_field_permission): a field above
    permlevel 0 is readable only at a level the user's roles grant (Meta.get_permlevel_access); a
    level-0 field goes with the record the user may already query; a DocType with no permission
    rules shows every field. Meta.get_permitted_fieldnames, which Frappe uses to strip read
    results, is stricter for a select-only user and for a child with no parent; FAC strips
    results through Frappe itself, so this rule only decides what a user may query or is shown
    by FAC. A child table's levels come from a parent (`parenttype`) that embeds it; with no such
    parent, only its level-0 fields are readable.

    This answers for a known field. A name with no DocField (a standard column such as name or
    owner) counts as readable, so a name the caller typed must be resolved first
    (core.field_access.check_field), which refuses one it can't match.
    """
    from frappe_assistant_core.core.field_access import query_restricted_fields

    restricted = query_restricted_fields(meta.name, user_role) if user_role else set()
    if frappe.session.user == "Administrator":
        # Document.apply_fieldlevel_read_permissions exempts the Administrator.
        return lambda fieldname: fieldname not in restricted

    if meta.istable and not _embeds(parenttype, meta.name):
        levels = {0}
    elif not meta.get_permissions(parenttype=parenttype):
        return lambda fieldname: fieldname not in restricted
    else:
        levels = {0, *meta.get_permlevel_access("read", parenttype=parenttype)}

    def can_read(fieldname: str) -> bool:
        if fieldname in restricted:
            return False
        df = meta.get_field(fieldname)
        return df is None or (df.permlevel or 0) in levels

    return can_read


def _embeds(parenttype: str, child: str) -> bool:
    """Whether `parenttype` is a DocType of its own with a table of `child` rows."""
    if not parenttype or not frappe.db.exists("DocType", parenttype):
        return False
    parent = frappe.get_meta(parenttype)
    return not parent.istable and any(df.options == child for df in parent.get_table_fields())


def readable_value(doc, fieldname: str):
    """``doc``'s value of ``fieldname`` if the user may read that field, else None.

    For a tool that falls back on a value the user didn't give (a lead's email or phone): a field
    above the user's permlevel must not be used, nor echoed back, on their behalf.
    """
    return doc.get(fieldname) if field_reader(doc.meta)(fieldname) else None


def readable_doc_dict(doc, user_role: str) -> dict:
    """`doc` as a dict holding only what the user may read.

    Fields above the user's permlevel are dropped first, from the parent and its child rows, as
    frappe.client.get does for Desk. FAC's SENSITIVE_FIELDS and ADMIN_ONLY_FIELDS are then masked.
    """
    from frappe_assistant_core.core.security_config import filter_sensitive_fields

    doc.apply_fieldlevel_read_permissions()
    return filter_sensitive_fields(doc.as_dict(), doc.doctype, user_role)


def readable_fieldnames(meta, fieldnames: list, user_role: str, parenttype: str = None) -> list:
    """The `fieldnames` the user may read; matching a text query on any other gives its value away."""
    can_read = field_reader(meta, user_role, parenttype)
    return [fieldname for fieldname in fieldnames if can_read(fieldname)]


def _reset_fieldnames(meta, write_levels, ignored=()) -> set:
    """Fields of `meta` Frappe puts back on save for a user who may write only `write_levels`.

    BaseDocument.reset_values_if_no_permlevel_access: a field above those levels, not a display
    field, and not named in the document's flags.ignore_permlevel_for_fields.
    """
    from frappe.model import display_fieldtypes

    return {
        df.fieldname
        for df in meta.get_high_permlevel_fields()
        if df.permlevel not in write_levels
        and df.fieldtype not in display_fieldtypes
        and df.fieldname not in ignored
    }


def _skips_permlevel_reset(doc) -> bool:
    # Document.validate_higher_perm_levels returns early in these cases.
    return bool(
        frappe.session.user == "Administrator" or doc.flags.ignore_permissions or frappe.flags.in_install
    )


def unwritable_fieldnames(doc, fieldnames) -> list:
    """The `fieldnames` of `doc` itself Frappe will not take from this user when it is saved.

    Frappe's rule, from Document.validate_higher_perm_levels: on save it puts back the stored value
    (the default, on a new record) of each field above the user's write permlevel. Child rows:
    unwritable_row_fields.
    """
    if _skips_permlevel_reset(doc):
        return []
    ignored = doc.flags.get("ignore_permlevel_for_fields") or ()
    reset = _reset_fieldnames(doc.meta, doc.get_permlevel_access("write"), ignored)
    return [fieldname for fieldname in fieldnames if fieldname in reset]


def unwritable_row_fields(doc, data: dict, table_fields: dict) -> list:
    """`table.field` for each child-row field in `data` Frappe puts back when `doc` is saved.

    Frappe resets child rows only on a record that already exists; a new record's rows keep what
    they were given.
    """
    if doc.is_new() or _skips_permlevel_reset(doc):
        return []
    write_levels = doc.get_permlevel_access("write")
    not_applied = []
    for field, rows in data.items():
        if field not in table_fields or not isinstance(rows, list):
            continue
        keys = sorted({key for row in rows if isinstance(row, dict) for key in row})
        reset = _reset_fieldnames(frappe.get_meta(table_fields[field].options), write_levels)
        not_applied.extend(f"{field}.{key}" for key in keys if key in reset)
    return not_applied


def unwritable_meta_fieldnames(meta) -> set:
    """Fields of `meta` a new record of it would not take from the session user (Data Import)."""
    if frappe.session.user == "Administrator":
        return set()
    return _reset_fieldnames(meta, meta.get_permlevel_access("write"))


def hidden_query_fields(
    doctype: str,
    filters=None,
    order_by: str = None,
    group_by: str = None,
    user_role: str = None,
    parent_doctype: str = None,
    aliases=(),
    fields=None,
) -> list:
    """The references in `filters`, `order_by`, `group_by` and `fields` expressions that aren't a
    field the user may read.

    frappe.get_list strips an unreadable bare field from `fields`, but Frappe 15 runs a filter on
    it, so repeated filters narrow down its value, and keeps an expression such as
    `max(salary)*1`. Frappe 16 refuses such a filter; this applies that rule on both. Each
    reference must resolve to a DocField or standard column exactly, as check_query_fields
    requires: MariaDB reads `SALARY` as salary, and Frappe 15 passes an unknown name or an
    ifnull(...) through, so anything that doesn't resolve is refused too. A bare name in `fields`
    is left to frappe.get_list, which drops it when unreadable.

    `parent_doctype` is the parent a child-table query is made through, as in frappe.get_list.
    `aliases` are names the query's `fields` give their expressions (`count(name) as total`):
    order_by may name one that matches no column in any case, since the expressions themselves
    are checked here.
    """
    from frappe_assistant_core.core.field_access import (
        SORT_DIRECTION,
        STANDARD_COLUMNS,
        FieldAccessError,
        check_field,
        expression_columns,
        filter_references,
    )

    def refused(reference: str, target: str = None) -> bool:
        try:
            check_field(doctype, reference, user_role, target_doctype=target, parent_doctype=parent_doctype)
        except FieldAccessError:
            return True
        return False

    hidden = [reference for target, reference in filter_references(filters) if refused(reference, target)]

    for entry in [fields] if isinstance(fields, (str, dict)) else fields or []:
        if isinstance(entry, dict):
            expressions = [value for key, value in entry.items() if key != "as" and isinstance(value, str)]
        elif isinstance(entry, str) and entry != "*" and not entry.isidentifier():
            expressions = [entry]
        else:
            continue
        hidden += [
            column
            for expression in expressions
            for column in expression_columns(expression)
            if refused(column)
        ]

    columns = {name.lower() for name in STANDARD_COLUMNS}
    columns.update(df.fieldname.lower() for df in frappe.get_meta(doctype).fields if df.fieldname)
    safe_aliases = {alias for alias in aliases if alias.lower() not in columns}
    for clause, allowed in ((order_by, safe_aliases), (group_by, set())):
        if not clause or not isinstance(clause, str):
            continue
        for column in expression_columns(SORT_DIRECTION.sub("", clause)):
            if column.replace("`", "").strip() in allowed:
                continue
            if refused(column):
                hidden.append(column)
    return hidden


def indexes_unreadable_field(doctype: str, user_role: str) -> bool:
    """Whether the global-search index holds a field of `doctype`, or of its rows, the user may not read.

    Frappe indexes every in_global_search field as "Label : value" with no regard to permlevel, so
    for such a DocType neither the indexed text nor the fact that a record matched can be shown.
    """
    meta = frappe.get_meta(doctype)
    can_read = field_reader(meta, user_role)
    if any(not can_read(df.fieldname) for df in meta.get_global_search_fields()):
        return True
    for table_field in meta.get_table_fields():
        child = frappe.get_meta(table_field.options)
        fields = child.get_global_search_fields()
        if fields:
            child_can_read = field_reader(child, user_role, parenttype=doctype)
            if any(not child_can_read(df.fieldname) for df in fields):
                return True
    return False
