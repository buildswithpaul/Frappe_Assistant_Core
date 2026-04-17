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
Pending Approvals Discovery Tool for Core Plugin.
Queries Workflow Actions to find documents awaiting the current user's approval.
"""

from typing import Any, Dict

import frappe
from frappe import _
from frappe.query_builder import DocType

from frappe_assistant_core.core.base_tool import BaseTool

MAX_TRANSITION_DOCS = 20


class GetPendingApprovals(BaseTool):
    """
    Tool for discovering documents pending the current user's approval.

    Resolves pending approvals via two paths:
    1. Role-based: Workflow Action Permitted Role matches user's roles
    2. Direct user: Workflow Action.user matches current user (legacy)
    """

    def __init__(self):
        super().__init__()
        self.name = "get_pending_approvals"
        self.description = (
            "Get documents pending the current user's approval. Use this when users ask "
            "about pending approvals, documents awaiting action, workflow items needing "
            "review, or approval queues. Queries the Workflow Action system — NOT Todos "
            "or Notifications. Returns documents grouped by type with workflow state and "
            "available actions (Approve, Reject, etc.)."
        )
        self.requires_permission = None

        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {
                    "type": "string",
                    "description": "Optional: filter to a specific doctype (e.g. 'Purchase Order').",
                },
                "limit": {
                    "type": "integer",
                    "default": 50,
                    "maximum": 200,
                    "description": "Maximum number of pending actions to return. Default 50.",
                },
                "include_actions": {
                    "type": "boolean",
                    "default": True,
                    "description": (
                        "Whether to include available workflow actions (Approve, Reject, etc.) "
                        "for each document. Set to false for faster results on large lists."
                    ),
                },
            },
            "required": [],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Find open Workflow Actions assigned to the current user."""
        doctype_filter = arguments.get("doctype")
        limit = min(arguments.get("limit", 50), 200)
        include_actions = arguments.get("include_actions", True)

        user = frappe.session.user
        roles = frappe.get_roles(user)

        WA = DocType("Workflow Action")
        WAPR = DocType("Workflow Action Permitted Role")

        # Subquery: workflow action names where permitted roles overlap user's roles
        role_subquery = (
            frappe.qb.from_(WA)
            .join(WAPR)
            .on(WA.name == WAPR.parent)
            .select(WA.name)
            .where(WAPR.role.isin(roles))
        )

        # Main query
        query = (
            frappe.qb.from_(WA)
            .select(
                WA.name,
                WA.reference_doctype,
                WA.reference_name,
                WA.workflow_state,
                WA.user,
                WA.creation,
            )
            .where(WA.status == "Open")
            .orderby(WA.creation, order=frappe.qb.desc)
            .limit(limit)
        )

        # Administrator sees all; others filtered by role or direct user
        if user != "Administrator":
            query = query.where(WA.name.isin(role_subquery) | (WA.user == user))

        if doctype_filter:
            query = query.where(WA.reference_doctype == doctype_filter)

        try:
            pending_actions = query.run(as_dict=True)
        except Exception as e:
            frappe.log_error(
                title=_("Pending Approvals Query Error"),
                message=str(e),
            )
            return {"success": False, "error": str(e)}

        if not pending_actions:
            return {
                "success": True,
                "total_pending": 0,
                "doctypes_with_pending": [],
                "pending_approvals": {},
                "message": "No documents pending your approval",
            }

        # Batch-fetch permitted roles for all returned actions
        action_names = [a.name for a in pending_actions]
        all_roles = frappe.get_all(
            "Workflow Action Permitted Role",
            filters={"parent": ["in", action_names]},
            fields=["parent", "role"],
        )
        roles_map: Dict[str, list] = {}
        for r in all_roles:
            roles_map.setdefault(r.parent, []).append(r.role)

        # Fetch available transitions per document (capped)
        transitions_map: Dict[tuple, list] = {}
        if include_actions:
            seen = set()
            for action in pending_actions:
                key = (action.reference_doctype, action.reference_name)
                if key in seen:
                    continue
                seen.add(key)
                if len(seen) > MAX_TRANSITION_DOCS:
                    break
                try:
                    from frappe.model.workflow import get_transitions

                    doc = frappe.get_doc(action.reference_doctype, action.reference_name)
                    transitions = get_transitions(doc)
                    transitions_map[key] = [
                        {"action": t.get("action"), "next_state": t.get("next_state")} for t in transitions
                    ]
                except Exception:
                    transitions_map[key] = []

        # Group results by doctype
        grouped: Dict[str, list] = {}
        for action in pending_actions:
            dt = action.reference_doctype
            key = (dt, action.reference_name)
            entry = {
                "document_name": action.reference_name,
                "workflow_state": action.workflow_state,
                "permitted_roles": roles_map.get(action.name, []),
                "creation": str(action.creation),
            }
            if include_actions and key in transitions_map:
                entry["available_actions"] = transitions_map[key]
            grouped.setdefault(dt, []).append(entry)

        actions_truncated = (
            include_actions
            and len({(a.reference_doctype, a.reference_name) for a in pending_actions}) > MAX_TRANSITION_DOCS
        )

        result = {
            "success": True,
            "total_pending": len(pending_actions),
            "doctypes_with_pending": list(grouped.keys()),
            "pending_approvals": grouped,
            "message": (
                f"Found {len(pending_actions)} document(s) pending your approval "
                f"across {len(grouped)} document type(s)"
            ),
        }

        if actions_truncated:
            result["actions_truncated"] = True
            result["actions_truncated_note"] = (
                f"Available actions shown for first {MAX_TRANSITION_DOCS} documents only. "
                "Use include_actions=false or filter by doctype for full lists."
            )

        return result


get_pending_approvals = GetPendingApprovals
