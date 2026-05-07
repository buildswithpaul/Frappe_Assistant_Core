# How to Use update_document

## Overview

The `update_document` tool modifies field values on an existing Frappe document. Only include fields that need to change. Supports both top-level scalar fields and child-table rows.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doctype` | string | **Yes** | Exact **parent** DocType name (e.g., `Sales Order`, not `Sales Order Item`) |
| `name` | string | **Yes** | Document name/ID to update |
| `data` | object | **Yes** | Only the fields to change. For child tables, pass a list of row dicts under the table fieldname |

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

## Updating child-table rows

Always update child rows by calling `update_document` on the **parent** document and passing the child rows under the table fieldname. The tool refuses direct calls on child-table doctypes (see [Edge Cases](#edge-cases)).

The tool picks **patch mode** or **replace mode** automatically based on whether any input row carries a `name` key.

### Patch mode — when any input row has a `name`

Used to surgically edit specific rows. Behaviour per row:

- Row has `name` → **update**: matched row's named fields are overwritten, untouched fields preserved.
- Row has `name` and `"_delete": true` → **remove**: the row is deleted from the table.
- Row has no `name` → **append**: a new row is added to the end.
- Existing rows whose `name` is **not mentioned** in the input → **left untouched**.

```json
{
  "doctype": "Sales Order",
  "name": "SO-0001",
  "data": {
    "items": [
      {"name": "abc-123", "qty": 5},
      {"name": "abc-456", "rate": 250},
      {"item_code": "NEW-SKU", "qty": 1, "rate": 100},
      {"name": "abc-789", "_delete": true}
    ]
  }
}
```

This: changes qty on row `abc-123`, changes rate on row `abc-456`, appends a new row, deletes row `abc-789`. Any other rows on the SO are left alone.

### Replace mode — when no input row has a `name`

Clears the child table and re-fills it with the rows you supply. Use this for first-time population or a deliberate "wipe and refill". Be careful: rows you omit are lost.

```json
{
  "doctype": "Sales Order",
  "name": "SO-0001",
  "data": {
    "items": [
      {"item_code": "SKU-A", "qty": 2, "rate": 100},
      {"item_code": "SKU-B", "qty": 1, "rate": 250}
    ]
  }
}
```

### Why call on the parent, not the child

ERPNext (and Frappe in general) computes derived fields — row `amount`, parent `total`, `total_qty`, `grand_total`, taxes, etc. — inside the parent doc's `validate()` pipeline. Calling `update_document` directly on a child-table doctype like `Sales Order Item` saves the row in isolation and **bypasses that pipeline**, leaving the row's `amount` and the parent's totals stale. The tool detects this and refuses.

## Best Practices

1. **Fetch first with `get_document`** — understand current values (and child-row `name`s) before updating.
2. **Only include changed fields** — don't send the entire document.
3. **Use the parent doctype for child-row edits** — never target a child-table doctype directly.
4. **Prefer patch mode for child tables** — it's surgical and won't drop rows you didn't mean to.
5. **Use replace mode only when you intend a wipe-and-refill** — it discards any row you omit.
6. **Link fields use the `name`** — not the display title. Use `search_link` to find valid values.
7. **Cannot update submitted documents** — `docstatus=1` documents must be amended or cancelled first.

## Edge Cases

- **Direct child-doctype updates are rejected.** Calling `update_document` with `doctype: "Sales Order Item"` (or any other child-table doctype) returns `error_type: "child_doctype_direct_update"` along with the parent doctype, parent name, and parent table fieldname so you can retry on the parent.

  ```json
  {
    "success": false,
    "error_type": "child_doctype_direct_update",
    "child_doctype": "Sales Order Item",
    "parent_doctype": "Sales Order",
    "parent_name": "SO-0001",
    "parent_table_fieldname": "items",
    "suggestion": "Call update_document with doctype='Sales Order', name='SO-0001', and data={'items': [{'name': '...', ...fields to change...}]}. Patch mode will update only the named row; other rows are untouched."
  }
  ```

- **Patch references a row `name` that doesn't exist** → `error_type: "child_row_not_found"`. No silent skipping.
- **`_delete: true` without a `name`** → rejected. Deletion is only meaningful for rows already on the doc.
- **Restricted fields in a child row** — sensitive fields registered for the *child* doctype (e.g., `secret_key`) are blocked the same way as on the parent. Error names the offending field and child doctype.
- **Submitted documents** (`docstatus=1`) — cannot update. Use `run_workflow` to amend/cancel.
- **Read-only fields** — computed fields (e.g., `grand_total`) cannot be set; they recompute on save.
- **Validation runs on save** — invalid field combinations will fail.
- **`workflow_state`** — don't update directly, use `run_workflow` instead.
