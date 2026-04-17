# How to Use submit_document

## Overview

The `submit_document` tool finalizes a draft document, changing its `docstatus` from 0 (Draft) to 1 (Submitted). Only works on **submittable** DocTypes.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doctype` | string | **Yes** | Exact DocType name |
| `name` | string | **Yes** | Document name/ID |

## Response Format

On success:
```json
{
  "success": true,
  "result": {
    "success": true,
    "name": "ACC-SINV-2024-00001",
    "doctype": "Sales Invoice",
    "docstatus": 1,
    "message": "Sales Invoice 'ACC-SINV-2024-00001' submitted successfully"
  }
}
```

On non-submittable DocType:
```json
{
  "success": true,
  "result": {
    "success": false,
    "error": "ToDo is not a submittable DocType",
    "suggestion": "Only submittable DocTypes can be submitted. ToDo doesn't support submission."
  }
}
```

## Best Practices

1. **Check if DocType is submittable** — use `get_doctype_info` and check `is_submittable`. Common submittable DocTypes: Sales Invoice, Purchase Invoice, Journal Entry, Sales Order, Purchase Order, Delivery Note, Stock Entry.
2. **Document must be in Draft state** — `docstatus` must be 0.
3. **Submission triggers business logic** — GL entries, stock ledger updates, workflow transitions, email notifications may all fire.
4. **Submission is hard to undo** — submitted documents can only be cancelled (not reverted to draft) via `run_workflow` with action "Cancel".

## Edge Cases

- **Non-submittable DocTypes** — Customer, Item, ToDo, etc. cannot be submitted. The tool returns a clear error.
- **Validation errors** — submission runs all validations. Missing mandatory fields or invalid data will fail.
- **Already submitted** — submitting a `docstatus=1` document will fail.
- **Alternative** — use `create_document` with `submit: true` to create and submit in one step.
