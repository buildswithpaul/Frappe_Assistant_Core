# metadata_workflow

Get workflow information for a DocType.

## When to Use

- Understanding approval flows before using `run_workflow`
- Discovering available workflow actions
- Checking workflow states and transitions
- Planning document processing paths

## Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| doctype | string | Yes | DocType name |

## Examples

### Check Workflow for Sales Order

```json
{
  "doctype": "Sales Order"
}
```

### Check Workflow for Leave Application

```json
{
  "doctype": "Leave Application"
}
```

## Response Format

### With Workflow

```json
{
  "success": true,
  "doctype": "Sales Order",
  "has_workflow": true,
  "workflow_name": "Sales Order Approval",
  "workflow_state_field": "workflow_state",
  "states": [
    {
      "state": "Draft",
      "doc_status": 0,
      "allow_edit": 1,
      "message": "Document is in draft state"
    },
    {
      "state": "Pending Approval",
      "doc_status": 0,
      "allow_edit": 0,
      "message": "Waiting for manager approval"
    },
    {
      "state": "Approved",
      "doc_status": 1,
      "allow_edit": 0,
      "message": "Order has been approved"
    },
    {
      "state": "Rejected",
      "doc_status": 0,
      "allow_edit": 1,
      "message": "Order was rejected"
    }
  ],
  "transitions": [
    {
      "state": "Draft",
      "action": "Submit for Approval",
      "next_state": "Pending Approval",
      "allowed": "Sales User",
      "allow_self_approval": 0
    },
    {
      "state": "Pending Approval",
      "action": "Approve",
      "next_state": "Approved",
      "allowed": "Sales Manager",
      "allow_self_approval": 0
    },
    {
      "state": "Pending Approval",
      "action": "Reject",
      "next_state": "Rejected",
      "allowed": "Sales Manager",
      "allow_self_approval": 0
    },
    {
      "state": "Rejected",
      "action": "Resubmit",
      "next_state": "Pending Approval",
      "allowed": "Sales User",
      "allow_self_approval": 0
    }
  ]
}
```

### Without Workflow

```json
{
  "success": true,
  "doctype": "Customer",
  "has_workflow": false,
  "message": "No workflow defined for DocType 'Customer'"
}
```

## Understanding Workflow States

| Property | Description |
|----------|-------------|
| state | State name displayed to users |
| doc_status | Document status (0=Draft, 1=Submitted, 2=Cancelled) |
| allow_edit | Whether document can be edited in this state |
| message | Message shown to users |

## Understanding Transitions

| Property | Description |
|----------|-------------|
| state | Starting state |
| action | Action name (use this in `run_workflow`) |
| next_state | State after action completes |
| allowed | Role required to perform action |
| allow_self_approval | Whether user can approve their own document |

## Workflow Flow Visualization

From the example above:

```
Draft
  ↓ [Submit for Approval] (Sales User)
Pending Approval
  ↓ [Approve] (Sales Manager)      ↓ [Reject] (Sales Manager)
Approved                           Rejected
                                     ↓ [Resubmit] (Sales User)
                                   Pending Approval
```

## Using with run_workflow

1. **Get workflow info**:
   ```json
   {"doctype": "Sales Order"}
   ```

2. **Identify current state** (from document)

3. **Find available actions** from transitions where `state` matches current

4. **Execute action**:
   ```json
   {
     "doctype": "Sales Order",
     "name": "SO-00001",
     "action": "Approve"
   }
   ```

## Common Workflow Patterns

### Simple Approval
Draft → Pending → Approved/Rejected

### Multi-Level Approval
Draft → L1 Review → L2 Review → Approved

### With Amendment
Draft → Approved → Cancelled → Amended Draft

## Related Tools

- **run_workflow** - Execute workflow actions
- **get_document** - Check current workflow_state
- **metadata_permissions** - Check role permissions
- **submit_document** - Direct submission (no workflow)
