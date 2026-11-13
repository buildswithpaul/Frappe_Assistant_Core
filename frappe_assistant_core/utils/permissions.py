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


# Field-level read access: what of a record, or of a search-index hit, reaches a user who may read
# the record but not every field of it (GitHub #390). Desk drops such fields, and so must every
# tool that returns record data. Which field is readable is decided by
# core.field_access.is_field_readable (permlevel plus FAC's restricted lists).
# Imports stay inside the functions: hooks load this module for every permission query.

# What frappe.utils.global_search puts between the "Label : value" parts of a hit's content.
INDEX_SEPARATOR = " ||| "


def readable_doc_dict(doc, user_role: str) -> dict:
    """`doc` as a dict holding only what the user may read.

    Fields above the user's permlevel are dropped first, from the parent and its child rows, as
    frappe.client.get does for Desk. FAC's SENSITIVE_FIELDS and ADMIN_ONLY_FIELDS are then masked.
    """
    from frappe_assistant_core.core.security_config import filter_sensitive_fields

    doc.apply_fieldlevel_read_permissions()
    return filter_sensitive_fields(doc.as_dict(), doc.doctype, user_role)


def unwritable_fieldnames(doc, fieldnames) -> list:
    """The `fieldnames` of `doc` above the user's write permlevel.

    Frappe's own rule, from Document.validate_higher_perm_levels: on save it puts back the stored
    value of each such field, and the Administrator is exempt. Desk shows no editor for them.
    """
    from frappe.model import display_fieldtypes

    if frappe.session.user == "Administrator":
        return []

    write_levels = doc.get_permlevel_access("write")
    unwritable = []
    for fieldname in fieldnames:
        df = doc.meta.get_field(fieldname)
        if (
            df
            and df.permlevel
            and df.permlevel not in write_levels
            and df.fieldtype not in display_fieldtypes
        ):
            unwritable.append(fieldname)
    return unwritable


def readable_fieldnames(meta, fieldnames: list, user_role: str) -> list:
    """The `fieldnames` the user may read; matching a text query on any other gives its value away."""
    from frappe_assistant_core.core.field_access import is_field_readable

    return [fieldname for fieldname in fieldnames if is_field_readable(meta, fieldname, user_role)]


def unreadable_field_labels(doctype: str, user_role: str) -> set:
    """Labels of the fields, on `doctype` and its child tables, the user may not read."""
    from frappe_assistant_core.core.field_access import is_field_readable

    meta = frappe.get_meta(doctype)
    labels = {
        df.label for df in meta.fields if df.label and not is_field_readable(meta, df.fieldname, user_role)
    }
    for table_field in meta.get_table_fields():
        child = frappe.get_meta(table_field.options)
        labels.update(
            df.label
            for df in child.fields
            if df.label and not is_field_readable(child, df.fieldname, user_role, parenttype=doctype)
        )
    return labels


def readable_index_content(content: str, hidden_labels: set, query: str, name: str) -> tuple:
    """(keep the hit, its content without the hidden fields), for a __global_search hit.

    Frappe indexes each field as "Label : value" with no regard to permlevel. A hit whose readable
    content and name hold none of the query's words matched only on a hidden field, so returning it
    would confirm that field's value; it is dropped.
    """
    if not content or not hidden_labels:
        return True, content

    parts = content.split(INDEX_SEPARATOR)
    kept = [
        part for part in parts if not any(part.strip().startswith(f"{label} : ") for label in hidden_labels)
    ]
    if len(kept) == len(parts):
        return True, content

    readable = INDEX_SEPARATOR.join(kept)
    searchable = f"{readable} {name}".lower()
    words = (query or "").lower().split()
    return (not words or any(word in searchable for word in words)), readable
