# How to Use get_document

## Overview

The `get_document` tool retrieves a single Frappe document by its name (ID). It returns all fields including child table data.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doctype` | string | **Yes** | Exact DocType name |
| `name` | string | **Yes** | Document name (ID) |

**Note:** There is no `fields` parameter — this tool always returns all fields. For selective field retrieval, use `list_documents` with `fields` and a name filter instead.

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
        { "role": "Administrator", "parent": "Administrator", ... },
        { "role": "System Manager", "parent": "Administrator", ... }
      ],
      ...
    },
    "message": "User 'Administrator' retrieved successfully"
  }
}
```

Key points about the response:
- `data` contains ALL fields for the document, including metadata (`creation`, `modified`, `owner`, `docstatus`)
- **Child tables** are included as arrays of objects under their fieldname (e.g., `roles`, `items`, `accounts`)
- Each child table row includes `parent`, `parentfield`, `parenttype`, and `idx` (row order)

## Best Practices

1. **Know the exact document name** — use `list_documents` or `search_documents` first if you don't know it.
2. **Use for detail views** — when you need the full document with all fields and child tables.
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
- **Large documents** — documents with many child table rows return all rows. This can be verbose.
- **Permission checks** are enforced — user must have "read" permission on the DocType.
- **Amended documents** — amended document names follow patterns like "ORIG-NAME-1", "ORIG-NAME-2".
- **Not found** — returns `{"success": false, "error": "..."}` if the document doesn't exist.
