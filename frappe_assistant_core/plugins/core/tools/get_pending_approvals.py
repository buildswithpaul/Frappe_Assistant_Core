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
from frappe.model.document import Document
from frappe.model.workflow import get_workflow_name
from frappe.query_builder import DocType

from frappe_assistant_core.core.base_tool import BaseTool

MAX_TRANSITION_DOCS = 20
# How many documents are counted, so the total matches the home page's approvals card.
COUNT_LIMIT = 200


def _open_workflow_actions(
    user: str, limit: int, doctype: str | None = None, offset: int = 0
) -> list[frappe._dict]:
    """Open Workflow Actions addressed to ``user``, newest first, at most ``limit``.

    An action is addressed to the user by a permitted role or directly by ``user``;
    Administrator sees all. It does not check access to the referenced documents; see ``readable_open_approvals``.
    """
    roles = frappe.get_roles(user)

    WA = DocType("Workflow Action")
    WAPR = DocType("Workflow Action Permitted Role")

    # Subquery: workflow action names where permitted roles overlap user's roles
    role_subquery = (
        frappe.qb.from_(WA).join(WAPR).on(WA.name == WAPR.parent).select(WA.name).where(WAPR.role.isin(roles))
    )

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
        .orderby(WA.name, order=frappe.qb.desc)
        .limit(limit)
        .offset(offset)
    )

    # Administrator sees all; others filtered by role or direct user
    if user != "Administrator":
        query = query.where(WA.name.isin(role_subquery) | (WA.user == user))

    if doctype:
        query = query.where(WA.reference_doctype == doctype)

    return query.run(as_dict=True)


MAX_SCANNED_ACTIONS = 1000
MIN_PAGE_SIZE = 100


def _readable_subset(user: str, actions: list[frappe._dict]) -> list[frappe._dict]:
    """The ``actions`` whose referenced documents ``user`` may read (User Permissions apply)."""
    names_by_doctype: dict[str, set[str]] = {}
    for action in actions:
        names_by_doctype.setdefault(action.reference_doctype, set()).add(action.reference_name)

    readable: set[tuple[str, str]] = set()
    for ref_doctype, names in names_by_doctype.items():
        if not frappe.db.exists("DocType", ref_doctype) or not frappe.has_permission(
            ref_doctype, "read", user=user
        ):
            continue
        visible = frappe.get_list(ref_doctype, filters={"name": ["in", list(names)]}, pluck="name", user=user)
        readable.update((ref_doctype, name) for name in visible)
    return [a for a in actions if (a.reference_doctype, a.reference_name) in readable]


def active_workflow(doctype: str) -> Document | None:
    """The active Workflow of ``doctype``, or ``None``."""
    name = get_workflow_name(doctype)
    return frappe.get_cached_doc("Workflow", name) if name else None


def actionable_states(workflow: Document) -> set[str]:
    """States of ``workflow`` with a next step that neither cancels the document nor is optional.

    Frappe opens a Workflow Action for any state with a non-optional next step, so a submitted
    document whose only step left is Cancel stays in the queue although nothing awaits approval.
    """
    cancelled = {s.state for s in workflow.states if str(s.doc_status) == "2"}
    optional = {s.state for s in workflow.states if s.is_optional_state}
    return {
        t.state
        for t in workflow.transitions
        if t.next_state not in cancelled and t.next_state not in optional
    }


def _awaiting_approval(actions: list[frappe._dict]) -> list[frappe._dict]:
    """The ``actions`` whose state still has an approval step; doctypes without an active Workflow are kept."""
    states_by_doctype: dict[str, set[str] | None] = {}
    for doctype in {a.reference_doctype for a in actions}:
        workflow = active_workflow(doctype)
        states_by_doctype[doctype] = actionable_states(workflow) if workflow else None
    return [
        a
        for a in actions
        if states_by_doctype[a.reference_doctype] is None
        or a.workflow_state in states_by_doctype[a.reference_doctype]
    ]


def readable_open_approvals(user: str, limit: int, doctype: str | None = None) -> list[frappe._dict]:
    """Up to ``limit`` open Workflow Actions for ``user`` whose documents ``user`` may read and approve.

    The Workflow Action query only matches roles and users, so each page is re-checked
    through ``get_list`` to apply User Permissions. Pages of ``max(limit * 3, MIN_PAGE_SIZE)`` newest-first rows
    are scanned until ``limit`` readable rows are found, the source is exhausted, or
    ``MAX_SCANNED_ACTIONS`` rows have been scanned, so hidden rows ahead of readable ones
    do not shrink the result. Ordering is preserved.
    """
    page_size = max(limit * 3, MIN_PAGE_SIZE)
    readable: list[frappe._dict] = []
    offset = 0
    while len(readable) < limit and offset < MAX_SCANNED_ACTIONS:
        page = _open_workflow_actions(user, min(page_size, MAX_SCANNED_ACTIONS - offset), doctype, offset)
        readable.extend(_awaiting_approval(_readable_subset(user, page)))
        if len(page) < min(page_size, MAX_SCANNED_ACTIONS - offset):
            break
        offset += len(page)
    return readable[:limit]


def _one_per_document(actions: list[frappe._dict]) -> list[frappe._dict]:
    """The newest action of each document, keeping order."""
    seen: set[tuple[str, str]] = set()
    unique = []
    for action in actions:
        key = (action.reference_doctype, action.reference_name)
        if key not in seen:
            seen.add(key)
            unique.append(action)
    return unique


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
            "available actions (Approve, Reject, etc.), limited to documents the user can open."
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
                    "description": "Maximum number of documents to list. Default 50. total_pending always counts up to 200.",
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
        try:
            counted = _one_per_document(readable_open_approvals(user, COUNT_LIMIT, doctype_filter))
        except Exception as e:
            frappe.log_error(
                title=_("Pending Approvals Query Error"),
                message=str(e),
            )
            return {"success": False, "error": str(e)}

        pending_actions = counted[:limit]
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
            "total_pending": len(counted),
            "doctypes_with_pending": list(grouped.keys()),
            "pending_approvals": grouped,
            "message": (
                f"Found {len(counted)} document(s) pending your approval "
                f"across {len(grouped)} document type(s)"
            ),
        }

        if len(counted) > len(pending_actions):
            result["listed"] = len(pending_actions)
            result["message"] += f"; listing the {len(pending_actions)} newest"

        if actions_truncated:
            result["actions_truncated"] = True
            result["actions_truncated_note"] = (
                f"Available actions shown for first {MAX_TRANSITION_DOCS} documents only. "
                "Use include_actions=false or filter by doctype for full lists."
            )

        return result


get_pending_approvals = GetPendingApprovals
