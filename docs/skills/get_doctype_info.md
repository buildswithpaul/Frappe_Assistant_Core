# How to Use get_doctype_info

## Overview

The `get_doctype_info` tool retrieves metadata about a Frappe DocType — its fields, types, options, required flags, link fields, and permissions. This is essential for understanding a DocType's structure before creating or querying documents.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doctype` | string | **Yes** | DocType name (e.g., `"Customer"`, `"Sales Invoice"`) |

## Response Format

```json
{
  "success": true,
  "result": {
    "success": true,
    "doctype": "Customer",
    "module": "Selling",
    "is_submittable": 0,
    "is_tree": 0,
    "is_single": 0,
    "naming_rule": "By \"Naming Series\" field",
    "title_field": "customer_name",
    "fields": [
      {
        "fieldname": "customer_type",
        "label": "Customer Type",
        "fieldtype": "Select",
        "options": "Company\nIndividual\nPartnership",
        "reqd": 1,
        "read_only": 0,
        "hidden": 0,
        "default": "Company",
        "description": null
      },
      ...
    ],
    "link_fields": [
      { "fieldname": "customer_group", "label": "Customer Group", "options": "Customer Group" },
      { "fieldname": "territory", "label": "Territory", "options": "Territory" },
      ...
    ],
    "permissions": [ ... ]
  }
}
```

## Key Response Fields

- **`fields`** — complete list of all fields with:
  - `fieldname` — the API field name (use this in filters, data, fields)
  - `fieldtype` — Data, Link, Select, Int, Currency, Table, Check, Date, etc.
  - `options` — for Select: newline-separated values; for Link: target DocType; for Table: child DocType
  - `reqd` — 1 if mandatory
  - `read_only` / `hidden` — field visibility
  - `default` — default value
- **`link_fields`** — convenience list of all Link fields with their target DocTypes
- **`is_submittable`** — 1 if the DocType supports submit/cancel workflow (docstatus)
- **`naming_rule`** — how documents are named (autoname, naming series, prompt, etc.)
- **`title_field`** — the field used as display title

## Best Practices

1. **Always call before `create_document`** — to know which fields are required (`reqd: 1`) and what types they expect.
2. **Check `fieldtype` for filters** — use appropriate filter operators for each field type.
3. **Check `options` for Select fields** — Select fields only accept values from their options list.
4. **Check Link field targets** — Link fields reference other DocTypes via their `options` value. Use `search_link` to find valid values.
5. **Look for Table fields** — these indicate child tables. The `options` value is the child DocType name.
6. **Check `is_submittable`** — if 1, documents go through Draft → Submitted → Cancelled workflow.

## Common Patterns

### Discover required fields before creating
```json
{ "doctype": "Sales Invoice" }
```
Then filter response fields where `reqd: 1` to know what's mandatory.

### Find child table structure
If `get_doctype_info("Sales Invoice")` shows a Table field with `options: "Sales Invoice Item"`, call `get_doctype_info("Sales Invoice Item")` to see the child table's fields.

### Check if DocType is submittable
Look at `is_submittable` in the response — if 1, use `submit_document` after creation.

## Edge Cases

- **Section Break, Column Break, Tab Break** fields appear in the list but are layout elements, not data fields — ignore them.
- **Hidden fields** (`hidden: 1`) exist but aren't shown in the UI — they may still be settable via API.
- **Read-only fields** (`read_only: 1`) cannot be set during creation — they're computed or system-managed.
- **Returns error if DocType doesn't exist** — `{"success": false, "error": "DocType 'X' not found"}`.
