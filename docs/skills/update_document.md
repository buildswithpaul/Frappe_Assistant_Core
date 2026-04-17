# How to Use update_document

## Overview

The `update_document` tool modifies field values on an existing Frappe document. Only include fields that need to change.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doctype` | string | **Yes** | Exact DocType name |
| `name` | string | **Yes** | Document name/ID to update |
| `data` | object | **Yes** | Only the fields to change |

## Response Format

```json
{
  "success": true,
  "result": {
    "success": true,
    "name": "ckot534a7s",
    "doctype": "ToDo",
    "updated_fields": ["priority", "description"],
    "docstatus": 0,
    "state_description": "Draft",
    "workflow_state": null,
    "message": "ToDo 'ckot534a7s' updated successfully",
    "can_submit": true,
    "next_steps": [
      "Document remains in draft state",
      "You can continue updating this document",
      "Submit permission: Available"
    ]
  }
}
```

The response confirms which fields were updated and shows the document's current state.

## Best Practices

1. **Fetch first with `get_document`** — understand current values before updating.
2. **Only include changed fields** — don't send the entire document.
3. **Link fields use the `name`** — not the display title. Use `search_link` to find valid values.
4. **Cannot update submitted documents** — `docstatus=1` documents must be amended or cancelled first.
5. **Child table updates replace all rows** — passing a child table array replaces ALL existing rows. Omitting leaves unchanged.

## Edge Cases

- **Submitted documents** (`docstatus=1`) — cannot update. Use `run_workflow` to amend/cancel.
- **Read-only fields** — computed fields (e.g., `grand_total`) cannot be set.
- **Validation runs on save** — invalid field combinations will fail.
- **workflow_state** — don't update directly, use `run_workflow` instead.
