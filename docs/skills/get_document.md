# How to Use get_document

## Overview

The `get_document` tool retrieves a single Frappe document by its name (ID), with its child tables. It returns only the fields that hold a value: a field that is missing from the result is empty.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doctype` | string | **Yes** | Exact DocType name |
| `name` | string | **Yes** | Document name (ID) |
| `fields` | array of strings | No | Only these fields, plus `name`. A child table's fieldname returns its rows. Omit for every filled-in field. |

## Response Format

```json
{
  "success": true,
  "result": {
    "success": true,
    "doctype": "User",
    "name": "Administrator",
    "data": {
      "name": "Administrator",
      "email": "admin@example.com",
      "first_name": "Administrator",
      "enabled": 1,
      "roles": [
        { "name": "a1b2c3", "idx": 1, "role": "Administrator" },
        { "name": "d4e5f6", "idx": 2, "role": "System Manager" }
      ],
      ...
    },
    "message": "User 'Administrator' retrieved successfully"
  }
}
```

Key points about the response:
- `data` holds every field that has a value, including metadata (`creation`, `modified`, `owner`, `docstatus`). Empty fields (null, empty text, empty tables) are left out; zeros are kept, so an `outstanding_amount` of 0 is there.
- **Child tables** are included as arrays of objects under their fieldname (e.g., `roles`, `items`, `accounts`)
- Each child table row keeps its `name` and `idx` (row order). The bookkeeping it shares with the parent (`parent`, `parentfield`, `parenttype`, `owner`, `creation`, `modified`, `modified_by`, `docstatus`, `doctype`) is left out.

## Best Practices

1. **Know the exact document name** — use `list_documents` or `search_documents` first if you don't know it.
2. **Use for detail views** — when you need the full document with its child tables. Pass `fields` when you need only a few fields, e.g. `["customer", "grand_total", "items"]`.
3. **For bulk reads, use `list_documents`** — `get_document` fetches one document at a time.
4. **Check `docstatus`** — 0 = Draft, 1 = Submitted, 2 = Cancelled.

## Common Patterns

### Get full document details
```json
{
  "doctype": "Sales Invoice",
  "name": "ACC-SINV-2024-00001"
}
```

### Follow up from list_documents result
First list: `list_documents` with `doctype: "Customer"` to find names.
Then detail: `get_document` with `doctype: "Customer", name: "Grant Plastics Ltd."`.

## Edge Cases

- **Child tables are always included** — they appear as arrays under their fieldname (e.g., `items`, `taxes`, `roles`).
- **Large documents** — documents with many child table rows return all rows. Use `fields` to leave out tables you don't need.
- **A missing field is empty**, not unknown: to see every field a DocType has, use `get_doctype_info`.
- **Permission checks** are enforced — user must have "read" permission on the DocType.
- **Amended documents** — amended document names follow patterns like "ORIG-NAME-1", "ORIG-NAME-2".
- **Not found** — returns `{"success": false, "error": "..."}` if the document doesn't exist.
