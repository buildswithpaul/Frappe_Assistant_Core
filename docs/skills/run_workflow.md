# How to Use run_workflow

## Overview

The `run_workflow` tool executes workflow actions on documents — Submit, Approve, Reject, Cancel, etc. Use this for business process automation instead of directly updating `workflow_state` fields.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doctype` | string | **Yes** | DocType name |
| `name` | string | **Yes** | Document name/ID |
| `action` | string | **Yes** | Exact workflow action name (case sensitive) |
| `workflow` | string | No | Workflow name (auto-detected if omitted) |

## Best Practices

1. **Use exact action names** — case sensitive. Common: `"Submit"`, `"Approve"`, `"Reject"`, `"Cancel"`, `"Submit for Review"`, `"Reopen"`.
2. **Let workflow auto-detect** — omit the `workflow` parameter unless you have multiple workflows on the same DocType.
3. **If unsure of actions** — try any action; the error response shows available actions for the current state.
4. **Use this instead of `update_document`** — never directly update `workflow_state` field, as it bypasses workflow logic (notifications, permissions, validations).
5. **Handles side effects** — emails, status changes, permissions checks all execute properly.

## Common Actions

| Action | Effect |
|--------|--------|
| `Submit` | Move from Draft to Submitted |
| `Cancel` | Cancel a submitted document |
| `Approve` | Approve a pending document |
| `Reject` | Reject a pending document |
| `Amend` | Create amendment of cancelled document |

## Edge Cases

- **Document not found** — returns `{"success": false, "error": "Document Sales Order 'X' not found"}`.
- **Invalid action** — returns error with list of available actions for the current state.
- **No workflow defined** — some DocTypes don't have workflows; use `submit_document` for simple submit.
- **Permission denied** — workflow actions are permission-controlled per state/role.
