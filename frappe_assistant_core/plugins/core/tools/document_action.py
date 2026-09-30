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

from frappe_assistant_core.core.base_tool import BaseTool

VALID_ACTIONS = ("submit", "cancel", "amend")

# Frappe writes docstatus=2 and runs on_cancel (ERPNext's GL/stock reversal) before its
# back-link check can raise, and MCP requests are POSTs that Frappe commits at the end.
# Cancel and amend therefore run inside this savepoint so a refused call leaves nothing behind.
_SAVEPOINT = "fac_document_action"


def _error_message(error: Exception) -> str:
    """Readable text of a Frappe/ERPNext exception, whose messages often carry HTML links."""
    return frappe.utils.strip_html(str(error)).strip() or type(error).__name__


def _rollback_to_savepoint(doctype: str, name: str) -> None:
    try:
        frappe.db.rollback(save_point=_SAVEPOINT)
    except Exception:
        # The savepoint only disappears if something inside the call committed, in which
        # case its partial changes are already persisted and need a human to look at them.
        frappe.log_error(
            title=_("Document Rollback Error"),
            message=f"Could not roll back {doctype} '{name}':\n{frappe.get_traceback()}",
        )
    # A doc cached while the rolled-back changes were visible would otherwise outlive them.
    frappe.clear_document_cache(doctype, name)


def _release_savepoint() -> None:
    try:
        frappe.db.release_savepoint(_SAVEPOINT)
    except Exception:
        pass  # Already gone because something inside the call committed; the work succeeded.


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
            "Never submit as a step toward cancelling.\n"
            "- 'cancel': submitted -> cancelled; reverses accounting and stock entries. Only works on "
            "submitted documents. If the document is a draft, do not submit it: tell the user it is a "
            "draft and offer to delete it or leave it. REQUIRES 'reason': the user's reason copied word "
            "for word; do not summarize, shorten or rephrase it. If they gave none, ask before calling. "
            "Refused if the DocType has an active Workflow (use run_workflow) or submitted documents "
            "are linked to it (they are listed; let the user decide).\n"
            "- 'amend': cancelled -> new draft copy with amended_from set. Fix it with update_document, "
            "then submit it with this tool."
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
                        "explicitly asks to submit; never as a step toward cancelling. 'cancel': only "
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

            # Perform submission
            doc.submit()

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

        except Exception as e:
            frappe.log_error(
                title=_("Document Submit Error"), message=f"Error submitting {doctype} '{name}': {str(e)}"
            )

            result = {
                "success": False,
                "error": str(e),
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
            return self._workflow_refusal(doc, workflow_name)

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

        frappe.db.savepoint(_SAVEPOINT)
        try:
            # No flags: Frappe's and ERPNext's own cancel validations must all run.
            doc.cancel()
            doc.add_comment(
                "Comment", f"Cancelled via FAC by {frappe.session.user}. Reason given by user: {reason}"
            )
        except frappe.LinkExistsError as e:
            _rollback_to_savepoint(doctype, name)
            return {
                "success": False,
                "error": f"Cannot cancel {doctype} '{name}' because submitted documents are linked to it. "
                f"{_error_message(e)}",
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
        except Exception as e:
            _rollback_to_savepoint(doctype, name)
            frappe.log_error(
                title=_("Document Cancel Error"), message=f"Error cancelling {doctype} '{name}': {str(e)}"
            )
            return {
                "success": False,
                "error": _error_message(e),
                "error_type": type(e).__name__,
                "doctype": doctype,
                "name": name,
                "docstatus": current_docstatus,
                "suggestion": "The document was not cancelled. Tell the user the reason above.",
            }
        _release_savepoint()

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

    def _workflow_refusal(self, doc, workflow_name: str) -> Dict[str, Any]:
        """Refuse a direct cancel, naming the workflow action that cancels from the current state, if any"""
        workflow = frappe.get_doc("Workflow", workflow_name)
        current_state = doc.get(workflow.workflow_state_field or "workflow_state")
        cancelled_states = {s.state for s in workflow.states if frappe.utils.cint(s.doc_status) == 2}
        # From the workflow definition; run_workflow still enforces the roles and conditions.
        cancel_actions = [
            {"action": t.action, "next_state": t.next_state, "allowed_role": t.allowed}
            for t in workflow.transitions
            if t.state == current_state and t.next_state in cancelled_states
        ]
        state_label = current_state or "no state set"

        result = {
            "success": False,
            "workflow": workflow_name,
            "workflow_state": current_state,
            "workflow_cancel_actions": cancel_actions,
        }
        if cancel_actions:
            actions = " or ".join(f"'{a['action']}'" for a in cancel_actions)
            result["error"] = (
                f"{doc.doctype} has an active Workflow ('{workflow_name}'), so it cannot be cancelled directly."
            )
            result["suggestion"] = (
                f"Use run_workflow on {doc.doctype} '{doc.name}' with action {actions}. From its current "
                f"state '{state_label}', that moves it to a cancelled state."
            )
        else:
            result["error"] = (
                f"{doc.doctype} has an active Workflow ('{workflow_name}') with no cancel step from the "
                f"document's current state '{state_label}', so it cannot be cancelled."
            )
            result["suggestion"] = (
                "Tell the user the workflow has no cancel step from this state. They should ask an "
                "administrator to add a transition that cancels it from this state, or to deactivate "
                "the workflow."
            )
        return result

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

        frappe.db.savepoint(_SAVEPOINT)
        try:
            # Frappe names it from amended_from (e.g. '-1'), per Document Naming Settings.
            amended_doc.insert()
        except Exception as e:
            _rollback_to_savepoint(doctype, name)
            frappe.log_error(
                title=_("Document Amend Error"), message=f"Error amending {doctype} '{name}': {str(e)}"
            )
            return {
                "success": False,
                "error": _error_message(e),
                "error_type": type(e).__name__,
                "doctype": doctype,
                "name": name,
                "suggestion": "No amended draft was created. Tell the user the reason above.",
            }
        _release_savepoint()

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
