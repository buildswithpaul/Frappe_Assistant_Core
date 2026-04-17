# How to Use delete_document

## Overview

The `delete_document` tool permanently removes a Frappe document. This action is **irreversible**.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `doctype` | string | **Yes** | — | Exact DocType name |
| `name` | string | **Yes** | — | Document name/ID |
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
