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

## Confirmation by the user's client

An action that moves the document to a cancelled state is confirmed; other actions are not. When the MCP client can show the user a confirmation form, the first call changes nothing: the client asks the user "Cancel Sales Invoice ACC-SINV-0001? Its accounting and stock entries will be reversed." and sends the call again with their answer. Your call returns only after the user has answered.

- **Accepted** — the call runs once, as normal.
- **Declined** — the result is an error: "The user did not confirm, so nothing was changed." Do not retry the call; ask the user what they want instead.
- Clients without a confirmation form run the call at once, and so does FAC Chat, which shows its own approval card. Still confirm with the user before calling.

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
- **No workflow defined** — some DocTypes don't have workflows; use `document_action` for simple submit.
- **Workflow defined** — `document_action` refuses to submit or cancel a document whose DocType has an active Workflow, and names the `run_workflow` action to use instead. `document_action` with `amend` still works for a document cancelled here.
- **Permission denied** — workflow actions are permission-controlled per state/role.
- **A record the user may not read** — refused with `error_type: "permission_error"` before anything else, with no state or actions. Don't retry another action; tell the user they don't have access to it. A user who may read no record of the DocType gets this for every name, existing or not.
