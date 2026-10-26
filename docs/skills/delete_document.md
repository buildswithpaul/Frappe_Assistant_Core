# How to Use delete_document

## Overview

The `delete_document` tool permanently removes a Frappe document. This action is **irreversible**.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `doctype` | string | **Yes** | — | Exact DocType name |
| `name` | string | One of `name`/`names` | — | Document name/ID |
| `names` | array | One of `name`/`names` | — | Several documents to delete |
| `mode` | string | No | `all_or_nothing` | For `names`: `all_or_nothing` or `continue` |
| `force` | boolean | No | `false` | Force deletion even with dependencies |

## Response Format

```json
{
  "success": true,
  "result": {
    "success": true,
    "doctype": "ToDo",
    "name": "ckot534a7s",
    "message": "ToDo 'ckot534a7s' deleted successfully"
  }
}
```

## Deleting many records

```json
{"doctype": "ToDo", "names": ["abc123", "def456"]}
```

Each record goes through the single-delete path. With `all_or_nothing`, a record that cannot be deleted (for example, one another record links to) restores the ones already deleted in that call.
- At most 100 records per call; split a larger job into several calls.
- `mode: "all_or_nothing"` (the default) saves nothing if any record fails, and `failed_record` names the record and its error. `mode: "continue"` saves the records that pass and lists each record's outcome in `results`.
- Customisation DocTypes (Custom Field, Property Setter, Server Script, Client Script, DocType, Workflow, Report, Print Format, Notification and similar) are refused in a batch: write them one at a time so each one is previewed.

## Best Practices

1. **Always confirm with the user** — deletion is permanent.
2. **Check dependencies first** — documents linked to others fail without `force: true`.
3. **Use `force` with extreme caution** — leaves orphaned references.
4. **Cancel before deleting** — submitted documents (`docstatus=1`) must be cancelled first.

## Edge Cases

- **Linked documents** — can't delete an Item with Sales Invoices referencing it unless `force: true`.
- **Submitted documents** — must be cancelled (`docstatus=2`) before deletion.
- **System records** — some records (Administrator user, default roles) cannot be deleted.
- **Permission required** — user needs "delete" permission on the DocType.
