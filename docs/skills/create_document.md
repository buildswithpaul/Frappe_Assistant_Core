# How to Use create_document

## Overview

The `create_document` tool creates new Frappe documents (records). It handles field validation, mandatory field checks, and permission verification automatically.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `doctype` | string | **Yes** | — | Exact DocType name |
| `data` | object | **Yes** | — | Field values as key-value pairs |
| `submit` | boolean | No | `false` | Submit after creation (for submittable DocTypes). Under an active Workflow the document is created as a draft instead |
| `validate_only` | boolean | No | `false` | Validate without saving — use to test data format |

## Response Format

```json
{
  "success": true,
  "result": {
    "success": true,
    "doctype": "ToDo",
    "name": "TODO-00001",
    "data": { ... full document ... },
    "message": "ToDo 'TODO-00001' created successfully"
  }
}
```

## Best Practices

1. **Check required fields first** — use `get_doctype_info` to see mandatory fields before creating.
2. **Use `validate_only: true` first** — test your data structure without actually creating the document.
3. **Link fields expect the `name` (ID)** — not the display title. Use `search_documents` with `purpose: "link_value"` to find valid values.
4. **Don't set auto-generated fields** — `name`, `creation`, `modified`, `owner` are set automatically.
5. **Handle naming series** — DocTypes with naming series auto-generate names; don't pass `name` unless it uses manual naming.
6. **Use `submit: true` carefully** — only when explicitly requested. Creates and submits in one step. If the submit is refused (a validation, a closed period), the document is kept as a clean draft and `submit_error` says why. If the DocType has an active Workflow, it is created as a draft and not submitted: continue with `run_workflow`, which applies the workflow's approval rules.

## Common Patterns

### Simple document
```json
{
  "doctype": "ToDo",
  "data": {
    "description": "Follow up with client",
    "priority": "Medium",
    "date": "2024-06-15"
  }
}
```

### Document with child table
```json
{
  "doctype": "Sales Invoice",
  "data": {
    "customer": "Grant Plastics Ltd.",
    "items": [
      {
        "item_code": "ITEM-001",
        "qty": 5,
        "rate": 100
      }
    ]
  }
}
```

### Document with a Table MultiSelect field
A Table MultiSelect takes an array of its link values, as Desk sends it. Each value fills the field `get_doctype_info` reports as that table's `link_field`. Objects work too: `[{"user": "jane@example.com"}]`.
```json
{
  "doctype": "User Group",
  "data": {
    "name": "Reviewers",
    "user_group_members": ["jane@example.com", "raj@example.com"]
  }
}
```

### Validate before creating
```json
{
  "doctype": "Customer",
  "data": {
    "customer_name": "New Corp",
    "customer_type": "Company"
  },
  "validate_only": true
}
```

### Create and submit in one step
```json
{
  "doctype": "Journal Entry",
  "data": { ... },
  "submit": true
}
```

## Edge Cases

- **Submittable DocTypes** are created in Draft state (`docstatus=0`) by default — use `submit: true` or `document_action` tool separately.
- **Mandatory fields** that are missing cause a validation error — check with `get_doctype_info` first.
- **Unique constraints** — if a field has `unique=1`, duplicate values will fail.
- **Permission errors** — the current user must have "create" permission on the DocType. A refusal returns `error_type: "permission_error"` with Frappe's own reason in `error`; it is not a field problem, so do not retry with different values.
- **ToDo** — Frappe decides who may create a ToDo. Before Frappe v16.32.0 / v15.119.0, a user without a role that grants ToDo create (such as System Manager) may create only a ToDo that names them (`allocated_to` or `assigned_by`), so one that names nobody is allocated to them, and one naming someone else is refused; from those releases a user may create any ToDo. Omitting `allocated_to`, as the example above does, therefore works on every release. If Frappe refuses, `error` gives its reason.
- **Default values** — fields with defaults are auto-populated if not specified.
- **Child table rows** — pass as arrays of objects under the child table fieldname. A Table MultiSelect also accepts an array of its link values (see the example above). A plain Table does not, because no single field says what a bare value means; that returns `error_type: "child_table_handling_error"` with the `field`.
- **Restricted fields in a child row** — each row is checked against its child doctype's restricted fields, as on the parent. When you copy rows from another document, leave out system fields such as `owner`, `creation`, `docstatus` and `idx`.
- **Child-table doctypes** — `create_document` with a child doctype such as `Sales Invoice Item` is refused with `error_type: "child_table_doctype"` and the `parent_doctypes` it belongs to. A row exists only inside its parent, so add it with `update_document` on the parent document.
