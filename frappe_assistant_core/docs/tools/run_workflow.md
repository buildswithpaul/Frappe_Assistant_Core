# run_workflow

Execute workflow actions on documents (Submit, Approve, Reject, etc.) with proper business logic.

## When to Use

- Approving or rejecting documents in approval flows
- Submitting documents that have workflows configured
- Transitioning documents through business processes
- Any workflow action that requires proper permissions and notifications

## When NOT to Use

- Simple field updates (use `update_document` instead)
- Documents without workflow configured
- Direct workflow_state manipulation (bypasses business logic)

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| doctype | string | Yes | - | Document type (e.g., 'Sales Order', 'Leave Application') |
| name | string | Yes | - | Document name/ID |
| action | string | Yes | - | Exact workflow action name (case-sensitive) |
| workflow | string | No | Auto-detected | Workflow name (optional) |

## Common Workflow Actions

| Action | Description |
|--------|-------------|
| Submit | Submit for review or processing |
| Approve | Approve the document |
| Reject | Reject the document |
| Submit for Review | Send for manager review |
| Cancel | Cancel an approved document |
| Reopen | Reopen a cancelled/rejected document |

> **Note:** Action names are case-sensitive and must match exactly as defined in the workflow.

## Examples

### Submit a Sales Order

```json
{
  "doctype": "Sales Order",
  "name": "SO-00001",
  "action": "Submit"
}
```

### Approve a Purchase Order

```json
{
  "doctype": "Purchase Order",
  "name": "PO-00001",
  "action": "Approve"
}
```

### Reject a Leave Application

```json
{
  "doctype": "Leave Application",
  "name": "LA-00001",
  "action": "Reject"
}
```

### Submit for Review

```json
{
  "doctype": "Expense Claim",
  "name": "EC-00001",
  "action": "Submit for Review"
}
```

## Response Format

### Success

```json
{
  "success": true,
  "message": "Workflow action 'Approve' executed successfully",
  "changes": [
    "State: Pending Approval → Approved",
    "Status: Draft → Submitted"
  ],
  "document": {
    "doctype": "Purchase Order",
    "name": "PO-00001",
    "previous_state": "Pending Approval",
    "current_state": "Approved",
    "docstatus": 1
  },
  "workflow": "Purchase Order Approval",
  "next_available_actions": ["Cancel", "Reopen"]
}
```

### Action Not Available

```json
{
  "success": false,
  "error": "Action 'Approve' is not available for document in state 'Draft'",
  "explanation": "The document is currently in 'Draft' state. From this state, you can only perform certain actions based on the workflow configuration and your permissions.",
  "current_state": "Draft",
  "available_actions": ["Submit for Review"],
  "transitions_details": [
    {
      "action": "Submit for Review",
      "next_state": "Pending Approval",
      "allowed_roles": ["Sales User"],
      "condition": null,
      "allow_self_approval": 0
    }
  ],
  "suggestion": "Try one of these available actions: Submit for Review"
}
```

### No Workflow Configured

```json
{
  "success": false,
  "error": "No workflow configured for Customer",
  "explanation": "The Customer document type doesn't have any workflows set up. Workflows are used for business processes like approval flows.",
  "suggestion": "Use the 'update_document' tool instead to modify document fields directly, or ask the administrator to configure a workflow for this document type."
}
```

### Permission Error

```json
{
  "success": false,
  "error": "You do not have permission to execute this workflow action",
  "error_type": "WorkflowPermissionError",
  "help": "You don't have permission to execute this workflow action"
}
```

## Workflow vs Direct Submission

| Method | Use Case |
|--------|----------|
| `run_workflow` | Documents with workflows, approval flows |
| `submit_document` | Simple submission without workflow |
| `update_document` | Direct field updates (avoid for workflow_state) |

## What Happens During Workflow Execution

1. **Permission check** - Verifies user can perform the action
2. **Condition evaluation** - Checks workflow transition conditions
3. **State transition** - Updates workflow_state field
4. **Document status change** - May change docstatus (Draft/Submitted/Cancelled)
5. **Notifications** - Sends configured email alerts
6. **Side effects** - Triggers any configured actions

## Workflow States vs Document Status

| Concept | Description | Example |
|---------|-------------|---------|
| Workflow State | Business process state | "Pending Approval", "Approved" |
| Document Status (docstatus) | Technical status | 0=Draft, 1=Submitted, 2=Cancelled |

A workflow action can change both simultaneously.

## Finding Available Actions

If you don't know the available actions:
1. Call with any action - the error response shows available actions
2. Check `available_actions` in the error response
3. Use `transitions_details` for complete information including roles

## Permissions

Workflow actions require:
- Permission to access the document
- Role specified in the workflow transition
- Self-approval permission (if configured)

## Related Tools

- **get_document** - Check current workflow state
- **submit_document** - Simple submission without workflow
- **update_document** - Direct field updates (not recommended for workflows)
- **list_documents** - Find documents by workflow state
