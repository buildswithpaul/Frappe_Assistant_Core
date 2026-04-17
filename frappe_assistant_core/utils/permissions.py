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
