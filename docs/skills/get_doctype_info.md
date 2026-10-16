# How to Use get_doctype_info

## Overview

The `get_doctype_info` tool retrieves metadata about a Frappe DocType — its fields, types, options, required flags, link fields, and permissions. This is essential for understanding a DocType's structure before creating or querying documents.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doctype` | string | One of `doctype` / `topic` | DocType name (e.g., `"Customer"`, `"Sales Invoice"`) |
| `topic` | string | One of `doctype` / `topic` | A subject to locate (e.g., `"bookings"`, `"complaints"`). Ignored when `doctype` is given |

Passing neither returns `{"success": false, "error": ...}`.

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
- **`child_tables`** — every child-table field (`Table` and `Table MultiSelect`) with the child DocType's own `fields`. A Table MultiSelect entry also has `link_field`: the child field a bare value fills when you pass its values to `create_document` / `update_document`.
- **`is_child_table`** / **`parent_doctypes`** — for a child DocType, `is_child_table` is true and `parent_doctypes` lists the `{doctype, fieldname}` tables it lives in that you can read. Write its rows through one of those parents.
- **`is_submittable`** — 1 if the DocType supports submit/cancel workflow (docstatus)
- **`naming_rule`** — how documents are named (autoname, naming series, prompt, etc.)
- **`title_field`** — the field used as display title

## Finding where a topic's data lives (`topic`)

When no report fits the question (a site's custom "Booking" DocType, say), ask once where the data lives instead of exploring with many `list_documents` / `get_document` calls:

```json
{ "topic": "bookings" }
```

```json
{
  "success": true,
  "doctypes": [
    {
      "doctype": "Booking",
      "module": "Custom",
      "custom": true,
      "is_submittable": false,
      "has_data": true,
      "date_fields": ["booking_date"],
      "amount_fields": ["total_amount"],
      "party_fields": ["client"],
      "custom_fields": []
    }
  ]
}
```

- Matches DocType name or module; singular and plural both match (`bookings` finds `Booking`). Best match first, custom DocTypes ahead of standard ones on a tie. At most 8 are returned.
- Only DocTypes you may read are listed. Child tables and Single DocTypes are never listed.
- `has_data` is a boolean: whether you can see at least one record. It is never a count.
- `date_fields`, `amount_fields` (Currency, Float, Int) and `party_fields` (Customer / Supplier / Party Type links and Dynamic Links) are the fields worth filtering, grouping or summing on. `custom_fields` are fields a site added with Custom Field.
- Fields you may not read (permission level) and sensitive fields are left out.
- Next step: call `get_doctype_info` with the `doctype` for its full field list, then `list_documents` or `generate_report`.

## Best Practices

1. **Always call before `create_document`** — to know which fields are required (`reqd: 1`) and what types they expect.
2. **Check `fieldtype` for filters** — use appropriate filter operators for each field type.
3. **Check `options` for Select fields** — Select fields only accept values from their options list.
4. **Check Link field targets** — Link fields reference other DocTypes via their `options` value. Use `search_documents` with `purpose: "link_value"` to find valid values.
5. **Look for Table and Table MultiSelect fields** — these are child tables. The `options` value is the child DocType name.
6. **Check `is_submittable`** — if 1, documents go through Draft → Submitted → Cancelled workflow.

## Common Patterns

### Discover required fields before creating
```json
{ "doctype": "Sales Invoice" }
```
Then filter response fields where `reqd: 1` to know what's mandatory.

### Find child table structure
`get_doctype_info("Sales Invoice")` already includes each child table's fields under `child_tables`, so a second call is rarely needed. Calling `get_doctype_info("Sales Invoice Item")` also works if you can read a parent that uses it. It returns `parent_doctypes`, which tells you where those rows are written.

### Check if DocType is submittable
Look at `is_submittable` in the response — if 1, use `document_action` after creation.

## Edge Cases

- **Section Break, Column Break, Tab Break** fields appear in the list but are layout elements, not data fields — ignore them.
- **Hidden fields** (`hidden: 1`) exist but aren't shown in the UI — they may still be settable via API.
- **Read-only fields** (`read_only: 1`) cannot be set during creation — they're computed or system-managed.
- **Returns error if DocType doesn't exist** — `{"success": false, "error": "DocType 'X' not found"}`.
