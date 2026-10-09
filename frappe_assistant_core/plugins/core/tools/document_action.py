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
Document Action Tool for Core Plugin.
Submits draft documents, cancels submitted documents and amends cancelled ones.
"""

from typing import Any, Dict, List

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import (
    BaseTool,
    exception_message,
    permission_error_result,
)
from frappe_assistant_core.utils.savepoint import (
    open_savepoint,
    release_savepoint,
    rollback_to_savepoint,
)

VALID_ACTIONS = ("submit", "cancel", "amend")

# Frappe writes docstatus=2 and runs on_cancel (ERPNext's GL/stock reversal) before its
# back-link check can raise, and MCP requests are POSTs that Frappe commits at the end.
# Submit, cancel and amend therefore run inside this savepoint so a refused call leaves
# nothing behind (Frappe writes docstatus=1 before on_submit, the same way).
_SAVEPOINT = "fac_document_action"


class DocumentAction(BaseTool):
    """
    Tool for submitting, cancelling and amending documents.

    Provides capabilities for:
    - Submitting draft documents
    - Cancelling submitted documents, with a reason recorded on the timeline
    - Amending cancelled documents into a new draft
    - Validating submit/cancel/amend permissions
    - Providing workflow guidance
    """

    def __init__(self):
        super().__init__()
        self.name = "document_action"
        self.description = (
            "Submit, cancel or amend one document. Choose the action from what the user asked for.\n"
            "- 'submit' (default): draft -> submitted. Only when the user explicitly asks to submit. "
            "Never submit as a step toward cancelling. Refused if the DocType has an active Workflow "
            "(use run_workflow; the refusal names the action).\n"
            "- 'cancel': submitted -> cancelled; reverses accounting and stock entries. Only works on "
            "submitted documents. If the document is a draft, do not submit it: tell the user it is a "
            "draft and offer to delete it or leave it. REQUIRES 'reason': the user's reason copied word "
            "for word; do not summarize, shorten or rephrase it. If they gave none, ask before calling. "
            "Refused if the DocType has an active Workflow (use run_workflow) or submitted documents "
            "are linked to it (they are listed; let the user decide).\n"
            "- 'amend': cancelled -> new draft copy with amended_from set. Fix it with update_document, "
            "then submit it with this tool (or run_workflow under a Workflow).\n"
            "Submittable DocTypes only. Customer, Item and other masters have nothing to cancel: never "
            "offer to delete one instead."
        )
        self.requires_permission = None  # Permission checked dynamically per DocType

        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {
                    "type": "string",
                    "description": "The Frappe DocType name (e.g., 'Customer', 'Sales Invoice', 'Item')",
                },
                "name": {
                    "type": "string",
                    "description": "The document name/ID to submit, cancel or amend (e.g., 'CUST-00001', 'SINV-00001')",
                },
                "action": {
                    "type": "string",
                    "enum": list(VALID_ACTIONS),
                    "default": "submit",
                    "description": (
                        "Choose from what the user asked for. 'submit' (default): only when the user "
                        "explicitly asks to submit; never as a step toward cancelling; under an active "
                        "Workflow use run_workflow instead. 'cancel': only "
                        "works on submitted documents; if it is a draft, do not submit it, tell the user "
                        "it is a draft and offer to delete it or leave it. 'amend': cancelled documents "
                        "only; creates a new draft copy."
                    ),
                },
                "reason": {
                    "type": "string",
                    "description": (
                        "REQUIRED when action is 'cancel'. The user's reason for cancelling, copied word "
                        "for word from their message. Do not summarize, shorten or rephrase it. If the "
                        "user hasn't given a reason, ask them before calling this tool."
                    ),
                },
            },
            "required": ["doctype", "name"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Submit, cancel or amend a document"""
        doctype = arguments.get("doctype")
        name = arguments.get("name")
        action = str(arguments.get("action") or "").strip().lower() or "submit"

        if action == "submit":
            return self._submit(doctype, name)
        if action == "cancel":
            return self._cancel(doctype, name, arguments.get("reason"))
        if action == "amend":
            return self._amend(doctype, name)

        return {
            "success": False,
            "error": f"Invalid action '{arguments.get('action')}'. Valid actions: {', '.join(VALID_ACTIONS)}",
            "valid_actions": list(VALID_ACTIONS),
        }

    def _submit(self, doctype: str, name: str) -> Dict[str, Any]:
        """Submit a draft document"""
        # Import security validation
        from frappe_assistant_core.core.security_config import validate_document_access

        # Validate document access with comprehensive permission checking
        validation_result = validate_document_access(
            user=frappe.session.user, doctype=doctype, name=name, perm_type="submit"
        )

        if not validation_result["success"]:
            return validation_result

        user_role = validation_result["role"]

        marks = None
        try:
            # Check if document exists
            if not frappe.db.exists(doctype, name):
                result = {"success": False, "error": f"{doctype} '{name}' not found"}
                return result

            # Get document
            doc = frappe.get_doc(doctype, name)

            # Check document state
            current_docstatus = getattr(doc, "docstatus", 0)
            current_workflow_state = getattr(doc, "workflow_state", None)

            # Validate document is in draft state
            if current_docstatus != 0:
                state_description = {1: "submitted", 2: "cancelled"}.get(current_docstatus, "unknown")

                result = {
                    "success": False,
                    "error": f"Cannot submit {state_description} document {doctype} '{name}'. Only draft documents can be submitted.",
                    "docstatus": current_docstatus,
                    "workflow_state": current_workflow_state,
                    "suggestion": f"Document is already {state_description}. Use get_document to view its current state.",
                }
                return result

            # Check if DocType is submittable
            meta = frappe.get_meta(doctype)
            if not getattr(meta, "is_submittable", False):
                result = {
                    "success": False,
                    "error": f"{doctype} is not a submittable DocType",
                    "suggestion": f"Only submittable DocTypes can be submitted. {doctype} doesn't support submission.",
                }
                return result

            # On submit Frappe validates the workflow while the state is still unchanged, so no
            # transition is checked, and only then sets the first submitted state. Submitting
            # directly would skip the approval steps and their role rules, so it goes through
            # run_workflow, as cancel does.
            from frappe.model.workflow import get_workflow_name

            workflow_name = get_workflow_name(doctype)
            if workflow_name:
                return self._workflow_refusal(doc, workflow_name, "submit")

            # Perform submission. Frappe writes docstatus=1 before on_submit, so a submit refused
            # partway (after ERPNext's stock entries, before its GL entries) would otherwise be
            # committed as a submitted document missing half its postings.
            marks = open_savepoint(_SAVEPOINT)
            doc.submit()
            release_savepoint(_SAVEPOINT)
            marks = None

            # Get updated document state
            doc.reload()
            updated_docstatus = getattr(doc, "docstatus", 0)
            updated_workflow_state = getattr(doc, "workflow_state", None)

            result = {
                "success": True,
                "name": doc.name,
                "doctype": doctype,
                "docstatus": updated_docstatus,
                "state_description": "Submitted" if updated_docstatus == 1 else "Unknown",
                "workflow_state": updated_workflow_state,
                "owner": doc.owner,
                "modified": str(doc.modified),
                "modified_by": doc.modified_by,
                "message": f"{doctype} '{doc.name}' submitted successfully",
            }

            # Add next steps information
            if updated_docstatus == 1:
                can_cancel = frappe.has_permission(doctype, "cancel", doc=doc)
                result["next_steps"] = [
                    "Document is now submitted and read-only",
                    "Use get_document to view the submitted document",
                    "You can cancel it later with document_action (action 'cancel', with the user's reason)"
                    if can_cancel
                    else "You don't have permission to cancel it",
                ]

                # Add workflow information
                if updated_workflow_state:
                    result["next_steps"].append(f"Current workflow state: {updated_workflow_state}")
            else:
                result["next_steps"] = [
                    f"Submission may have failed - document status: {updated_docstatus}",
                    "Check document validation errors or permissions",
                ]

            # Log successful submission
            return result

        except frappe.PermissionError as e:
            if marks is not None:
                rollback_to_savepoint(_SAVEPOINT, marks, doctype, name)
            # A submit the user may not perform raises with no message. Returning the
            # "required fields" suggestion below for it sends the model editing fields
            # that were never the problem.
            error_msg = exception_message(
                e, _("Insufficient permission to submit {0} '{1}'").format(doctype, name)
            )
            frappe.log_error(
                title=_("Document Submit Error"),
                message=f"Error submitting {doctype} '{name}': {error_msg}",
            )

            return permission_error_result(doctype, error_msg, name)
        except Exception as e:
            if marks is not None:
                rollback_to_savepoint(_SAVEPOINT, marks, doctype, name)
            error_msg = exception_message(e)
            frappe.log_error(
                title=_("Document Submit Error"),
                message=f"Error submitting {doctype} '{name}': {error_msg}",
            )

            result = {
                "success": False,
                "error": error_msg,
                "doctype": doctype,
                "name": name,
                "suggestion": "Check if the document has all required fields filled and passes validation.",
            }

            # Log failed submission
            return result

    def _cancel(self, doctype: str, name: str, reason: Any) -> Dict[str, Any]:
        """Cancel a submitted document and record the user's reason on its timeline"""
        from frappe.model.workflow import get_workflow_name

        from frappe_assistant_core.core.security_config import validate_document_access

        validation_result = validate_document_access(
            user=frappe.session.user, doctype=doctype, name=name, perm_type="cancel"
        )
        if not validation_result["success"]:
            return validation_result

        if not frappe.db.exists(doctype, name):
            return {"success": False, "error": f"{doctype} '{name}' not found"}

        # Every record of a non-submittable DocType has docstatus 0, so the draft branch below
        # would call it a draft and offer to delete it: for a Customer or an Item, that turns
        # "cancel it" into deleting master data.
        if not frappe.get_meta(doctype).is_submittable:
            return self._not_submittable(doctype, "cancel")

        doc = frappe.get_doc(doctype, name)
        current_docstatus = getattr(doc, "docstatus", 0)

        if current_docstatus != 1:
            if current_docstatus == 2:
                error = (
                    f"Cannot cancel {doctype} '{name}' because it is already cancelled. "
                    "Only submitted documents can be cancelled."
                )
                suggestion = "To correct and resubmit it, use document_action with action 'amend' to create a new draft."
            else:
                error = (
                    f"Cannot cancel {doctype} '{name}' because it is a draft. Only submitted documents "
                    "can be cancelled. Do not submit it just to cancel it."
                )
                suggestion = (
                    "Tell the user it is a draft, so there is nothing to cancel, and offer to delete it "
                    "(delete_document) or leave it as it is. Never submit it as a step toward cancelling."
                )
            return {
                "success": False,
                "error": error,
                "docstatus": current_docstatus,
                "suggestion": suggestion,
            }

        # Frappe skips workflow validation on cancel, so cancelling directly would bypass it.
        workflow_name = get_workflow_name(doctype)
        if workflow_name:
            return self._workflow_refusal(doc, workflow_name, "cancel")

        reason = reason.strip() if isinstance(reason, str) else ""
        if not reason:
            return {
                "success": False,
                "error": "A reason is required to cancel a document.",
                "suggestion": (
                    "Ask the user why they want to cancel this document, then call document_action "
                    "again with action 'cancel' and their answer as 'reason'. Do not make up a reason."
                ),
            }

        marks = open_savepoint(_SAVEPOINT)
        try:
            # No flags: Frappe's and ERPNext's own cancel validations must all run.
            doc.cancel()
            doc.add_comment(
                "Comment", f"Cancelled via FAC by {frappe.session.user}. Reason given by user: {reason}"
            )
        except frappe.LinkExistsError as e:
            rollback_to_savepoint(_SAVEPOINT, marks, doctype, name)
            return {
                "success": False,
                "error": f"Cannot cancel {doctype} '{name}' because submitted documents are linked to it. "
                f"{exception_message(e)}",
                "error_type": "LinkExistsError",
                "doctype": doctype,
                "name": name,
                "docstatus": current_docstatus,
                "linked_documents": self._get_submitted_linked_docs(doc),
                "suggestion": (
                    "Show the user the linked documents and let them decide what to do. They have to be "
                    "cancelled before this one; this tool never cancels them automatically."
                ),
            }
        except frappe.PermissionError as e:
            rollback_to_savepoint(_SAVEPOINT, marks, doctype, name)
            error_msg = exception_message(
                e, _("Insufficient permission to cancel {0} '{1}'").format(doctype, name)
            )
            frappe.log_error(
                title=_("Document Cancel Error"),
                message=f"Error cancelling {doctype} '{name}': {error_msg}",
            )
            result = permission_error_result(doctype, error_msg, name)
            result["docstatus"] = current_docstatus
            return result
        except Exception as e:
            rollback_to_savepoint(_SAVEPOINT, marks, doctype, name)
            error_msg = exception_message(e)
            frappe.log_error(
                title=_("Document Cancel Error"),
                message=f"Error cancelling {doctype} '{name}': {error_msg}",
            )
            return {
                "success": False,
                "error": error_msg,
                "error_type": type(e).__name__,
                "doctype": doctype,
                "name": name,
                "docstatus": current_docstatus,
                "suggestion": "The document was not cancelled. Tell the user the reason above.",
            }
        release_savepoint(_SAVEPOINT)

        return {
            "success": True,
            "name": doc.name,
            "doctype": doctype,
            "docstatus": int(doc.docstatus),
            "state_description": "Cancelled",
            "saved_reason": reason,
            "message": f"{doctype} '{doc.name}' cancelled successfully. Reason recorded on its timeline: {reason}",
            "next_steps": [
                "Document is now cancelled and read-only",
                "To correct and resubmit it, use document_action with action 'amend' to create a new draft",
            ],
        }

    def _workflow_refusal(self, doc, workflow_name: str, action: str) -> Dict[str, Any]:
        """Refuse a direct submit or cancel, naming the workflow action that does it from here, if any"""
        target_docstatus, done = {"submit": (1, "submitted"), "cancel": (2, "cancelled")}[action]
        workflow = frappe.get_doc("Workflow", workflow_name)
        current_state = doc.get(workflow.workflow_state_field or "workflow_state")
        target_states = {
            s.state for s in workflow.states if frappe.utils.cint(s.doc_status) == target_docstatus
        }
        # From the workflow definition; run_workflow still enforces the roles and conditions.
        workflow_actions = [
            {"action": t.action, "next_state": t.next_state, "allowed_role": t.allowed}
            for t in workflow.transitions
            if t.state == current_state and t.next_state in target_states
        ]
        state_label = current_state or "no state set"

        result = {
            "success": False,
            "workflow": workflow_name,
            "workflow_state": current_state,
            f"workflow_{action}_actions": workflow_actions,
        }
        if workflow_actions:
            actions = " or ".join(f"'{a['action']}'" for a in workflow_actions)
            result["error"] = (
                f"{doc.doctype} has an active Workflow ('{workflow_name}'), so it cannot be {done} directly."
            )
            result["suggestion"] = (
                f"Use run_workflow on {doc.doctype} '{doc.name}' with action {actions}. From its current "
                f"state '{state_label}', that moves it to a {done} state."
            )
        else:
            result["error"] = (
                f"{doc.doctype} has an active Workflow ('{workflow_name}') with no {action} step from the "
                f"document's current state '{state_label}', so it cannot be {done}."
            )
            result["suggestion"] = (
                f"Tell the user the workflow has no {action} step from this state. They should ask an "
                f"administrator to add a transition that leads to a {done} state from this one, or to "
                "deactivate the workflow."
            )
        return result

    @staticmethod
    def _not_submittable(doctype: str, action: str) -> Dict[str, Any]:
        """Refuse cancel or amend on a DocType that has no submitted state"""
        done = {"cancel": "cancelled", "amend": "amended"}[action]
        suggestion = {
            "cancel": (
                "There is nothing to cancel. Ask the user what they meant. If they want this record "
                "out of use, check get_doctype_info for a field such as 'disabled' or 'status'. Do not "
                "delete it unless they ask for that."
            ),
            "amend": "Amend only applies to cancelled documents. Edit this record with update_document instead.",
        }[action]
        return {
            "success": False,
            "error": f"{doctype} is not a submittable DocType, so its records cannot be {done}.",
            "suggestion": suggestion,
        }

    def _get_submitted_linked_docs(self, doc) -> List[Dict[str, str]]:
        """Submitted documents linked to `doc`, as Desk's "Cancel All" dialog lists them"""
        from frappe.desk.form.linked_with import get_submitted_linked_docs

        try:
            # Skip what the controller told Frappe to ignore on cancel, so only real blockers are listed.
            linked = get_submitted_linked_docs(
                doc.doctype,
                doc.name,
                ignore_doctypes_on_cancel_all=list(doc.get("ignore_linked_doctypes") or []),
            )
        except Exception:
            frappe.log_error(
                title=_("Linked Documents Lookup Error"),
                message=f"Error listing documents linked to {doc.doctype} '{doc.name}':\n{frappe.get_traceback()}",
            )
            return []

        return [{"doctype": d["doctype"], "name": d["name"]} for d in (linked or {}).get("docs", [])]

    def _amend(self, doctype: str, name: str) -> Dict[str, Any]:
        """Create a new draft from a cancelled document, the way Desk's Amend button does"""
        from frappe_assistant_core.core.security_config import validate_document_access

        validation_result = validate_document_access(
            user=frappe.session.user, doctype=doctype, name=name, perm_type="amend"
        )
        if not validation_result["success"]:
            return validation_result

        # The amendment is a new document, so creating one must be allowed too.
        validation_result = validate_document_access(
            user=frappe.session.user, doctype=doctype, name="", perm_type="create"
        )
        if not validation_result["success"]:
            return validation_result

        if not frappe.db.exists(doctype, name):
            return {"success": False, "error": f"{doctype} '{name}' not found"}

        if not frappe.get_meta(doctype).is_submittable:
            return self._not_submittable(doctype, "amend")

        doc = frappe.get_doc(doctype, name)
        current_docstatus = getattr(doc, "docstatus", 0)

        if current_docstatus != 2:
            if current_docstatus == 1:
                state_description = "submitted"
                suggestion = (
                    "Only cancelled documents can be amended. Cancel it first with document_action "
                    "action 'cancel' (ask the user for a reason), then amend it."
                )
            else:
                state_description = "a draft"
                suggestion = "Drafts don't need amending. Edit it directly with update_document."
            return {
                "success": False,
                "error": f"Cannot amend {doctype} '{name}' because it is {state_description}. "
                "Only cancelled documents can be amended.",
                "docstatus": current_docstatus,
                "suggestion": suggestion,
            }

        # Desk's Amend button refuses in both of these cases.
        if not frappe.get_meta(doctype).has_field("amended_from"):
            return {
                "success": False,
                "error": f"{doctype} cannot be amended because it has no 'amended_from' field.",
            }

        existing_amendment = frappe.db.exists(doctype, {"amended_from": name})
        if existing_amendment:
            return {
                "success": False,
                "error": f"{doctype} '{name}' has already been amended as '{existing_amendment}' "
                "and cannot be amended again.",
                "amended_document": existing_amendment,
                "suggestion": f"Work with '{existing_amendment}' instead. Use get_document to view it.",
            }

        amended_doc = frappe.copy_doc(doc)
        amended_doc.amended_from = doc.name
        amended_doc.docstatus = 0
        if amended_doc.meta.has_field("amendment_date"):
            amended_doc.amendment_date = frappe.utils.nowdate()

        # copy_doc carries the cancelled workflow state over, and Frappe refuses a new document
        # that starts anywhere but the workflow's first state. Desk resets it for a new document
        # (workflow.js set_default_state); clearing it lets Frappe set that first state.
        from frappe.model.workflow import get_workflow_name

        if workflow_name := get_workflow_name(doctype):
            state_field = frappe.db.get_value("Workflow", workflow_name, "workflow_state_field")
            amended_doc.set(state_field or "workflow_state", None)

        marks = open_savepoint(_SAVEPOINT)
        try:
            # Frappe names it from amended_from (e.g. '-1'), per Document Naming Settings.
            amended_doc.insert()
        except frappe.PermissionError as e:
            rollback_to_savepoint(_SAVEPOINT, marks, doctype, name)
            error_msg = exception_message(
                e, _("Insufficient permission to amend {0} '{1}'").format(doctype, name)
            )
            frappe.log_error(
                title=_("Document Amend Error"),
                message=f"Error amending {doctype} '{name}': {error_msg}",
            )
            return permission_error_result(doctype, error_msg, name)
        except Exception as e:
            rollback_to_savepoint(_SAVEPOINT, marks, doctype, name)
            error_msg = exception_message(e)
            frappe.log_error(
                title=_("Document Amend Error"),
                message=f"Error amending {doctype} '{name}': {error_msg}",
            )
            return {
                "success": False,
                "error": error_msg,
                "error_type": type(e).__name__,
                "doctype": doctype,
                "name": name,
                "suggestion": "No amended draft was created. Tell the user the reason above.",
            }
        release_savepoint(_SAVEPOINT)

        return {
            "success": True,
            "name": amended_doc.name,
            "doctype": doctype,
            "amended_from": doc.name,
            "docstatus": int(amended_doc.docstatus),
            "state_description": "Draft",
            "message": f"Created draft {doctype} '{amended_doc.name}' as an amendment of '{doc.name}'",
            "next_steps": [
                f"Use update_document on '{amended_doc.name}' to correct the fields that need fixing",
                f"Then use document_action on '{amended_doc.name}' to submit it",
            ],
        }


# Make sure class name matches file name for discovery
document_action = DocumentAction
