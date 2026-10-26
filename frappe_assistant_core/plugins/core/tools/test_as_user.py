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
Permission check tool for the Core plugin.
Asks Frappe's permission rules what another user may do, without saving,
running code or switching user.
"""

from typing import Any, Dict, List

import frappe
from frappe import _

from frappe_assistant_core.api.fac_page import can_open_page, roles_that_open_page
from frappe_assistant_core.core.base_tool import BaseTool

PERMISSION_TYPES = [
    "read",
    "write",
    "create",
    "delete",
    "submit",
    "cancel",
    "amend",
    "print",
    "email",
    "share",
    "export",
    "report",
]
MIN_CHECKS = 1
MAX_CHECKS = 20


def _permission_doctype(doctype: str, parent_doctype: str | None, name: str | None) -> str:
    """The DocType whose role table decides ``doctype``: the parent for a child table, else itself."""
    if not frappe.is_table(doctype):
        return doctype
    if name:
        parent = frappe.db.get_value(doctype, name, "parenttype")
        if parent:
            return parent
    return parent_doctype or doctype


def _roles_that_allow(doctype: str, ptype: str) -> List[str]:
    """Roles granting ``ptype`` at permission level 0, in role-table order without repeats."""
    permissions = frappe.get_meta(doctype).get("permissions")
    return list(dict.fromkeys(row.role for row in permissions if row.get(ptype) and not row.get("permlevel")))


def _check_one(user: str, check: Dict[str, Any]) -> Dict[str, Any]:
    """Answer one check as ``allowed``, ``refused`` or ``error``."""
    ptype = check.get("ptype")
    doctype = check.get("doctype")
    name = check.get("name") or None
    parent_doctype = check.get("parent_doctype") or None
    result = {
        "ptype": ptype,
        "doctype": doctype,
        "name": name,
        "outcome": "error",
        "reason": None,
        "roles_that_allow": [],
    }

    if ptype not in PERMISSION_TYPES:
        result["reason"] = _("{0} is not a permission type.").format(ptype)
        return result
    if not isinstance(doctype, str) or not frappe.db.exists("DocType", doctype):
        result["reason"] = _("DocType {0} does not exist.").format(doctype)
        return result
    if not all(value is None or isinstance(value, str) for value in (name, parent_doctype)):
        result["reason"] = _("name and parent_doctype must be text.")
        return result

    meta = frappe.get_meta(doctype)
    if meta.issingle:
        # A Single has one record, named after the DocType; has_permission ignores any name
        name = result["name"] = None
    # has_permission loads the record by name and raises when it is missing
    elif name and not meta.get("is_virtual") and not frappe.db.exists(doctype, name):
        result["reason"] = _("{0} {1} does not exist.").format(doctype, name)
        return result

    if doctype == "FAC Page" and name and ptype == "read":
        # get_page decides who opens a page: its owner if personal, else its roles and published flag.
        allowed = can_open_page(name, user)
        result["roles_that_allow"] = roles_that_open_page(name)
    else:
        allowed = frappe.has_permission(doctype, ptype, doc=name, user=user, parent_doctype=parent_doctype)
        result["roles_that_allow"] = _roles_that_allow(
            _permission_doctype(doctype, parent_doctype, name), ptype
        )
    result["outcome"] = "allowed" if allowed else "refused"
    if not allowed:
        if name:
            result["reason"] = _("{0} may not {1} this {2}.").format(user, ptype, doctype)
        else:
            result["reason"] = _("{0} may not {1} {2} records.").format(user, ptype, doctype)
    return result


def _run_checks(user: str, checks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Run every check, then drop messages permission hooks added to the message log."""
    logged = len(frappe.local.message_log)
    try:
        results = []
        for index, check in enumerate(checks, start=1):
            check = check if isinstance(check, dict) else {}
            try:
                answer = _check_one(user, check)
            except Exception:
                # Not log_error: that would write an Error Log row from a read-only tool
                frappe.logger("frappe_assistant_core").exception("test_as_user check failed")
                answer = {
                    "ptype": check.get("ptype"),
                    "doctype": check.get("doctype"),
                    "name": check.get("name"),
                    "outcome": "error",
                    "reason": _("This check could not be completed."),
                    "roles_that_allow": [],
                }
            results.append({"check": index, **answer})
        return results
    finally:
        del frappe.local.message_log[logged:]


class TestAsUser(BaseTool):
    """
    Tool for checking what another user is allowed to do.

    Read-only: it evaluates roles, User Permissions, sharing and permission hooks
    for the named user and returns only allowed/refused, never record data.
    """

    def __init__(self):
        super().__init__()
        self.name = "test_as_user"
        self.description = (
            "Check what another user is allowed to do, without switching user or saving anything. "
            "Use this after changing roles, User Permissions or sharing for a build, to confirm the "
            "right people can read, write, create, submit or print and the wrong people cannot. "
            "Each check is allowed, refused or error; every check lists roles_that_allow, "
            "the roles that grant that permission on the DocType at permission level 0. "
            "Reading a named FAC Page answers whether the user can open that page, and lists "
            "the roles that open it; a personal page opens for its owner only, with no roles. "
            "Never returns field values."
        )
        self.category = "Builder checks"
        self.requires_permission = None
        self.required_roles = ["System Manager"]

        self.inputSchema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "string",
                    "description": "Email (user id) of the enabled user to check.",
                },
                "checks": {
                    "type": "array",
                    "minItems": MIN_CHECKS,
                    "maxItems": MAX_CHECKS,
                    "description": "Permission checks to answer, 1 to 20.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "ptype": {"type": "string", "enum": PERMISSION_TYPES},
                            "doctype": {"type": "string", "description": "DocType to check."},
                            "name": {
                                "type": "string",
                                "description": "Optional record name; omit for a DocType-level answer.",
                            },
                            "parent_doctype": {
                                "type": "string",
                                "description": "Parent DocType, when doctype is a child table.",
                            },
                        },
                        "required": ["ptype", "doctype"],
                    },
                },
            },
            "required": ["user", "checks"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Answer each permission check for the named user."""
        checks = arguments["checks"]
        if not MIN_CHECKS <= len(checks) <= MAX_CHECKS:
            return {
                "success": False,
                "error": _("Provide between {0} and {1} checks.").format(MIN_CHECKS, MAX_CHECKS),
            }

        # Canonicalised so a differently cased email matches the stored user id
        row = frappe.db.get_value("User", arguments["user"], ["name", "enabled"], as_dict=True)
        if not row or not row.enabled:
            return {"success": False, "error": _("User {0} not found or disabled.").format(arguments["user"])}

        return {"success": True, "user": row.name, "results": _run_checks(row.name, checks)}


test_as_user = TestAsUser
