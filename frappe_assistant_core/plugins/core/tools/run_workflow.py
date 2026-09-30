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
Comprehensive workflow tool that properly uses Frappe's workflow system.
Handles all workflow complexities: permissions, conditions, notifications, document status changes.
"""

from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool


class RunWorkflow(BaseTool):
    """
    Comprehensive workflow tool that properly leverages Frappe's workflow system.

    This tool:
    1. Uses Frappe's native workflow API correctly
    2. Handles all workflow side effects (document status, emails, etc.)
    3. Provides clear feedback about what happened
    4. Shows available transitions when actions fail

    WHEN TO USE:
    - User wants to "submit", "approve", "reject", or perform any workflow action
    - Document has a workflow configured (Sales Order, Purchase Order, etc.)
    - Need to trigger business process automation
    - Want proper notifications and permissions to be enforced

    WHEN NOT TO USE:
    - Simple field updates (use update_document instead)
    - Document has no workflow configured
    - Direct workflow_state manipulation (this bypasses business logic)

    EXAMPLES:
    - Submit a Sales Order: {"doctype": "Sales Order", "name": "SO-001", "action": "Submit"}
    - Approve a Purchase Order: {"doctype": "Purchase Order", "name": "PO-001", "action": "Approve"}
    - Reject a Leave Application: {"doctype": "Leave Application", "name": "LA-001", "action": "Reject"}
    """

    def __init__(self):
        super().__init__()
        self.name = "run_workflow"
        self.description = "Execute workflow actions on documents (Submit, Approve, Reject, etc.). Use this for business process automation - NOT for simple field updates. This tool properly handles workflow permissions, notifications, state transitions, and business rules. Always use this instead of directly updating workflow_state fields, as it ensures proper workflow execution with all side effects (emails, status changes, validations). If action fails, tool shows available actions for current state."
        self.requires_permission = None  # Dynamic permission checking

        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {
                    "type": "string",
                    "description": "Document type (e.g., 'Sales Order', 'Purchase Order')",
                },
                "name": {"type": "string", "description": "Document name/ID"},
                "action": {
                    "type": "string",
                    "description": "Exact workflow action name to execute. Common examples: 'Submit', 'Approve', 'Reject', 'Submit for Review', 'Cancel', 'Reopen'. Use the exact action name as defined in the workflow - case sensitive. If unsure of available actions, the tool will show them when it fails.",
                },
                "workflow": {
                    "type": "string",
                    "description": "Workflow name (optional - will be auto-detected)",
                },
            },
            "required": ["doctype", "name", "action"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute workflow action using Frappe's workflow system"""
        try:
            doctype = arguments.get("doctype")
            name = arguments.get("name")
            action = arguments.get("action")
            workflow_name = arguments.get("workflow")

            # Validate document exists
            if not frappe.db.exists(doctype, name):
                return {"success": False, "error": f"Document {doctype} '{name}' not found"}

            # Get the document
            doc = frappe.get_doc(doctype, name)
            original_state = getattr(doc, "workflow_state", None)

            # Get workflow name if not provided
            if not workflow_name:
                from frappe.model.workflow import get_workflow_name

                workflow_name = get_workflow_name(doctype)

                if not workflow_name:
                    requested = str(action or "").strip().lower()
                    direct_action = requested if requested in ("cancel", "amend") else "submit"
                    return {
                        "success": False,
                        "error": f"No workflow configured for {doctype}",
                        "explanation": f"The {doctype} document type doesn't have any workflows set up. Workflows are used for business processes like approval flows.",
                        "suggestion": f"Use the 'document_action' tool with action '{direct_action}' instead, or ask the administrator to configure a workflow for this document type.",
                    }

            # Get available transitions to provide helpful feedback
            available_transitions = self._get_available_transitions(doc, workflow_name)

            # Check if the requested action is available
            available_actions = [t.get("action") for t in available_transitions]
            if action not in available_actions:
                return {
                    "success": False,
                    "error": f"Action '{action}' is not available for document in state '{original_state}'",
                    "explanation": f"The document is currently in '{original_state}' state. From this state, you can only perform certain actions based on the workflow configuration and your permissions.",
                    "current_state": original_state,
                    "available_actions": available_actions,
                    "transitions_details": available_transitions,
                    "suggestion": f"Try one of these available actions: {', '.join(available_actions) if available_actions else 'None available'}",
                }

            # Execute the workflow using Frappe's API
            from frappe.model.workflow import apply_workflow

            # Get document state before workflow execution
            before_docstatus = doc.docstatus

            # Apply the workflow action
            updated_doc = apply_workflow(doc, action)

            # Get the new state and document status
            new_state = getattr(updated_doc, "workflow_state", None)
            new_docstatus = updated_doc.docstatus

            # Determine what happened during workflow execution
            changes = []
            if original_state != new_state:
                changes.append(f"State: {original_state} → {new_state}")

            if before_docstatus != new_docstatus:
                status_names = {0: "Draft", 1: "Submitted", 2: "Cancelled"}
                old_status = status_names.get(before_docstatus, str(before_docstatus))
                new_status = status_names.get(new_docstatus, str(new_docstatus))
                changes.append(f"Status: {old_status} → {new_status}")

            # Get workflow information for the response
            workflow_info = self._get_workflow_info(updated_doc, workflow_name)

            return {
                "success": True,
                "message": f"Workflow action '{action}' executed successfully",
                "changes": changes,
                "document": {
                    "doctype": doctype,
                    "name": name,
                    "previous_state": original_state,
                    "current_state": new_state,
                    "docstatus": new_docstatus,
                },
                "workflow": workflow_name,
                "next_available_actions": [
                    t.get("action") for t in self._get_available_transitions(updated_doc, workflow_name)
                ],
            }

        except frappe.exceptions.WorkflowTransitionError as e:
            # Get helpful information for workflow errors
            try:
                doc = frappe.get_doc(doctype, name)
                available_transitions = self._get_available_transitions(doc, workflow_name)

                return {
                    "success": False,
                    "error": str(e),
                    "error_type": "WorkflowTransitionError",
                    "current_state": getattr(doc, "workflow_state", None),
                    "available_actions": [t.get("action") for t in available_transitions],
                    "help": "Check available actions and try again with a valid action",
                }
            except Exception:
                return {"success": False, "error": str(e), "error_type": "WorkflowTransitionError"}

        except frappe.exceptions.WorkflowPermissionError as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "WorkflowPermissionError",
                "help": "You don't have permission to execute this workflow action",
            }

        except Exception as e:
            frappe.log_error(
                title=_("Workflow Execution Error"), message=f"Error executing workflow action: {str(e)}"
            )

            return {
                "success": False,
                "error": f"Workflow execution failed: {str(e)}",
                "error_type": "ExecutionError",
            }

    def _get_available_transitions(self, doc, workflow_name):
        """Get available workflow transitions for the current user and document state"""
        try:
            from frappe.model.workflow import get_transitions

            transitions = get_transitions(doc)

            # Add additional context to each transition
            enhanced_transitions = []
            for t in transitions:
                enhanced_transitions.append(
                    {
                        "action": t.get("action"),
                        "next_state": t.get("next_state"),
                        "allowed_roles": t.get("allowed", "").split(",") if t.get("allowed") else [],
                        "condition": t.get("condition"),
                        "allow_self_approval": t.get("allow_self_approval", 0),
                    }
                )

            return enhanced_transitions

        except Exception as e:
            frappe.log_error(f"Error getting workflow transitions: {e}")
            return []

    def _get_workflow_info(self, doc, workflow_name):
        """Get comprehensive workflow information"""
        try:
            workflow_doc = frappe.get_doc("Workflow", workflow_name)
            current_state = getattr(doc, workflow_doc.workflow_state_field, None)

            # Get state information
            state_info = {}
            for state in workflow_doc.states:
                if state.state == current_state:
                    state_info = {
                        "state": state.state,
                        "doc_status": state.doc_status,
                        "allow_edit": state.allow_edit,
                        "is_optional_state": getattr(state, "is_optional_state", 0),
                    }
                    break

            return {
                "workflow_name": workflow_name,
                "current_state": current_state,
                "state_info": state_info,
                "workflow_field": workflow_doc.workflow_state_field,
            }

        except Exception as e:
            frappe.log_error(f"Error getting workflow info: {e}")
            return {"workflow_name": workflow_name}


# Make sure class name matches file name for discovery
run_workflow = RunWorkflow
