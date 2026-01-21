# submit_document

Submit a draft document to finalize it and trigger business logic.

## When to Use

- Finalizing sales invoices for posting
- Confirming purchase orders
- Submitting expense claims for approval
- Completing stock entries
- Any document that needs to move from draft to submitted state

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| doctype | string | Yes | - | The DocType name (e.g., 'Sales Invoice', 'Purchase Order') |
| name | string | Yes | - | The document name/ID to submit |

## Submittable DocTypes

Only certain DocTypes support submission. Common examples:

| Category | DocTypes |
|----------|----------|
| Selling | Sales Invoice, Sales Order, Quotation, Delivery Note |
| Buying | Purchase Invoice, Purchase Order, Purchase Receipt |
| Stock | Stock Entry, Stock Reconciliation, Material Request |
| Accounts | Journal Entry, Payment Entry |
| HR | Leave Application, Expense Claim, Salary Slip |

## Examples

### Submit a Sales Invoice

```json
{
  "doctype": "Sales Invoice",
  "name": "SINV-00001"
}
```

### Submit a Stock Entry

```json
{
  "doctype": "Stock Entry",
  "name": "STE-00001"
}
```

### Submit a Journal Entry

```json
{
  "doctype": "Journal Entry",
  "name": "JV-00001"
}
```

## Response Format

### Success

```json
{
  "success": true,
  "name": "SINV-00001",
  "doctype": "Sales Invoice",
  "docstatus": 1,
  "state_description": "Submitted",
  "workflow_state": null,
  "owner": "user@example.com",
  "modified": "2024-06-15 10:30:00",
  "modified_by": "user@example.com",
  "message": "Sales Invoice 'SINV-00001' submitted successfully",
  "next_steps": [
    "Document is now submitted and read-only",
    "Use document_get to view the submitted document",
    "Submit permissions: Available for cancellation"
  ]
}
```

### Already Submitted

```json
{
  "success": false,
  "error": "Cannot submit submitted document Sales Invoice 'SINV-00001'. Only draft documents can be submitted.",
  "docstatus": 1,
  "workflow_state": null,
  "suggestion": "Document is already submitted. Use document_get to view its current state."
}
```

### Not Submittable

```json
{
  "success": false,
  "error": "Customer is not a submittable DocType",
  "suggestion": "Only submittable DocTypes can be submitted. Customer doesn't support submission."
}
```

### Validation Error

```json
{
  "success": false,
  "error": "Posting Date is required",
  "doctype": "Sales Invoice",
  "name": "SINV-00001",
  "suggestion": "Check if the document has all required fields filled and passes validation."
}
```

## Document States (docstatus)

| Value | State | Description |
|-------|-------|-------------|
| 0 | Draft | Can be edited and submitted |
| 1 | Submitted | Read-only, can be cancelled |
| 2 | Cancelled | Read-only, cannot be modified |

## What Happens on Submission

Submission triggers various business logic depending on the DocType:

| DocType | Actions Triggered |
|---------|-------------------|
| Sales Invoice | GL entries created, revenue posted |
| Stock Entry | Stock ledger updated, valuation adjusted |
| Payment Entry | GL entries for payment, reconciliation |
| Journal Entry | Accounting entries posted |
| Purchase Order | Item availability reserved |

## Workflow Integration

If a document has a workflow configured:
- Submission may require workflow approval first
- Use `run_workflow` tool for workflow-based submissions
- Workflow state will be updated in response

## Permissions

- Submit permission is checked for the specific DocType
- Document-level permissions are verified
- Some documents may have additional role requirements

## Recommended Workflow

1. **Create** the document using `create_document`
2. **Review** the document using `get_document`
3. **Update** any missing fields using `update_document`
4. **Submit** using this tool when ready

## Related Tools

- **create_document** - Create draft documents
- **get_document** - Review document before submission
- **update_document** - Fix issues before submission
- **run_workflow** - For workflow-based submissions
- **delete_document** - Cancel and delete if needed
