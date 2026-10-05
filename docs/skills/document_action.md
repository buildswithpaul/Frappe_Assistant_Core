# How to Use document_action

## Overview

The `document_action` tool moves **one** document through its docstatus lifecycle. Pick what it does with `action`:

| Action | From | To | What it does |
|--------|------|----|--------------|
| `submit` (default) | Draft (0) | Submitted (1) | Finalizes a draft |
| `cancel` | Submitted (1) | Cancelled (2) | Cancels a submitted document and **reverses its accounting and stock entries** |
| `amend` | Cancelled (2) | new Draft (0) | Creates a new draft copy of a cancelled document, with `amended_from` set |

Only works on **submittable** DocTypes. One document per call — no lists, no bulk.

## Choosing the action

Choose the action from what the user asked for, not from the document's state.

- **`submit`** — only when the user explicitly asks to submit. **Never submit as a step toward cancelling.**
- **`cancel`** — only works on submitted documents. If the document is a draft, **do not submit it**: tell the user it is a draft and offer to delete it (`delete_document`) or leave it as it is.
- **`amend`** — only for cancelled documents.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doctype` | string | **Yes** | Exact DocType name |
| `name` | string | **Yes** | Document name/ID |
| `action` | string | No | `"submit"` (default), `"cancel"` or `"amend"`. `"submit"` only when the user explicitly asks to submit, never as a step toward cancelling. `"cancel"` only works on submitted documents: if it is a draft, do not submit it; tell the user it is a draft and offer to delete it or leave it |
| `reason` | string | For `cancel` | REQUIRED when action is `cancel`. The user's reason for cancelling, copied word for word from their message. Do not summarize, shorten or rephrase it. If the user hasn't given a reason, ask them before calling this tool. Recorded on the document's timeline. Ignored for other actions |

Calls without `action` submit, exactly as before.

## Response Format

Submit, on success:
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

Cancel, on success:
```json
{
  "success": true,
  "result": {
    "success": true,
    "name": "ACC-SINV-2024-00001",
    "doctype": "Sales Invoice",
    "docstatus": 2,
    "saved_reason": "Customer was billed twice for the same order, this one is the duplicate",
    "message": "Sales Invoice 'ACC-SINV-2024-00001' cancelled successfully. Reason recorded on its timeline: Customer was billed twice for the same order, this one is the duplicate"
  }
}
```

Show the user `saved_reason` so they can see exactly what was recorded.

Amend, on success (`name` is the **new** draft):
```json
{
  "success": true,
  "result": {
    "success": true,
    "name": "ACC-SINV-2024-00001-1",
    "doctype": "Sales Invoice",
    "amended_from": "ACC-SINV-2024-00001",
    "docstatus": 0,
    "message": "Created draft Sales Invoice 'ACC-SINV-2024-00001-1' as an amendment of 'ACC-SINV-2024-00001'"
  }
}
```

Cancel blocked by linked documents:
```json
{
  "success": true,
  "result": {
    "success": false,
    "error": "Cannot cancel Sales Order 'SAL-ORD-2024-00001' because submitted documents are linked to it. ...",
    "error_type": "LinkExistsError",
    "linked_documents": [
      {"doctype": "Sales Invoice", "name": "ACC-SINV-2024-00001"},
      {"doctype": "Delivery Note", "name": "MAT-DN-2024-00001"}
    ]
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

## Cancel Rules

1. **The reason is never skipped and never reworded** — `reason` is required and must not be blank. Copy it word for word from the user's message; do not summarize, shorten or rephrase it. If the user hasn't given a reason, ask them before calling this tool. Never invent one. It is added to the document's timeline as "Cancelled via FAC by <user>. Reason given by user: <reason>", and returned as `saved_reason`.
2. **Only submitted documents** — drafts (`docstatus=0`) and already-cancelled documents (`docstatus=2`) are refused.
   - **Never submit a draft as a step toward cancelling it.** A draft has nothing to cancel. Tell the user it is a draft and offer to delete it (`delete_document`) or leave it as it is.
3. **Workflow DocTypes use `run_workflow`** — if the DocType has an active Workflow, the tool refuses:
   - If the workflow has a transition from the document's current state to a cancelled state, the refusal names that action (`workflow_cancel_actions`). Use `run_workflow` with it.
   - If it has none, the workflow has no cancel step from this state. Tell the user to ask an administrator to add one or to deactivate the workflow.
4. **Linked documents are never cancelled for you** — if submitted documents link to this one (e.g. an invoice against a sales order), the cancel is refused and `linked_documents` lists them. Show the list to the user and let them decide; they must be cancelled first, one call each.
5. **Cancelling reverses ledgers** — GL entries and stock ledger entries are reversed. Confirm with the user before cancelling.
6. **ERPNext can still refuse** — closed accounting periods, frozen accounts and other validations return their real error message. Nothing is changed when a cancel is refused.

## Amend Rules

1. **Only cancelled documents** — submitted and draft documents are refused. Cancel first, then amend.
2. **One amendment per document** — if the document was already amended, the tool refuses and returns the existing amendment's name.
3. **No field changes in this call** — amend only creates the draft copy. Then:
   - `update_document` on the new draft to correct fields
   - `document_action` on the new draft to submit it
4. **Naming** — Frappe names the new draft from the original, usually with a `-1`, `-2` suffix.

## Best Practices

1. **Check if DocType is submittable** — use `get_doctype_info` and check `is_submittable`. Common submittable DocTypes: Sales Invoice, Purchase Invoice, Journal Entry, Sales Order, Purchase Order, Delivery Note, Stock Entry.
2. **Submit needs a draft** — `docstatus` must be 0.
3. **Submission triggers business logic** — GL entries, stock ledger updates, workflow transitions, email notifications may all fire.
4. **Submission is hard to undo** — submitted documents cannot go back to draft. Correcting one means `cancel` (with the user's reason), then `amend`, then `update_document`, then `submit`.

## Edge Cases

- **Non-submittable DocTypes** — Customer, Item, ToDo, etc. cannot be submitted. The tool returns a clear error.
- **Validation errors** — submission runs all validations. Missing mandatory fields or invalid data will fail.
- **Permission errors** — a refused `submit`, `cancel` or `amend` returns `error_type: "permission_error"` with Frappe's own reason in `error`. The request was refused, not malformed: retrying with different field values cannot succeed, and nothing is changed.
- **Already submitted** — submitting a `docstatus=1` document will fail.
- **Invalid action** — anything other than `submit`, `cancel` or `amend` is refused with the list of valid actions.
- **Alternative** — use `create_document` with `submit: true` to create and submit in one step.
