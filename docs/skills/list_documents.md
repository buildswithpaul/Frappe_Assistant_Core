# How to Use list_documents

## Overview

The `list_documents` tool searches and lists Frappe documents with filtering, field selection, and ordering. It is the primary tool for data exploration and discovery.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `doctype` | string | **Yes** | — | Exact DocType name (e.g., `"Sales Invoice"`, `"Customer"`) |
| `filters` | object | No | `{}` | Key-value filter pairs |
| `fields` | array | No | standard fields | Specific field names to return |
| `limit` | integer | No | 20 | Max results (max: 1000) |
| `order_by` | string | No | `"creation desc"` | Sort expression |

**Note:** There is no `page` parameter. Use `limit` to control result size.

## Response Format

```json
{
  "success": true,
  "result": {
    "success": true,
    "doctype": "Customer",
    "data": [ { "name": "CUST-00001", "customer_name": "Acme Corp" } ],
    "count": 5,
    "total_count": 42,
    "has_more": true,
    "filters_applied": { "status": "Active" },
    "message": "Found 5 Customer records"
  }
}
```

Key response fields:
- `data` — array of document records
- `count` — number of records returned in this response
- `total_count` — total matching records in the database
- `has_more` — boolean indicating more records exist beyond the limit

## Filter Syntax

### Simple equality
```json
{"status": "Active", "customer_type": "Company"}
```

### Comparison operators
```json
{"creation": [">", "2024-01-01"], "grand_total": [">=", 1000]}
```

### IN operator
```json
{"status": ["in", ["Draft", "Submitted"]]}
```

### LIKE operator (text search)
```json
{"customer_name": ["like", "%tech%"]}
```

### NOT operator
```json
{"status": ["!=", "Cancelled"]}
```

### BETWEEN operator
```json
{"creation": ["between", ["2024-01-01", "2024-12-31"]]}
```

### IS SET / IS NOT SET
```json
{"phone": ["is", "set"]}
{"phone": ["is", "not set"]}
```

## Best Practices

1. **Always specify fields** — requesting only needed fields is faster and returns cleaner results. Leave empty to get standard fields (name + title field).
2. **Start with small limits** — use `limit: 5` for exploration, increase when you know what you need.
3. **Use filters liberally** — filtered queries are much faster than fetching all records.
4. **Check DocType name first** — if unsure of the exact name, use `search_doctype` or `get_doctype_info` first.
5. **Check `has_more`** — if true, there are more records matching your filters beyond the current limit.
6. **Use `order_by`** — common patterns: `"creation desc"` (newest first), `"modified desc"`, `"name asc"`, `"grand_total desc"`.

## Common Patterns

### Find recent submitted invoices
```json
{
  "doctype": "Sales Invoice",
  "filters": {"docstatus": 1},
  "fields": ["name", "customer", "grand_total", "posting_date"],
  "order_by": "posting_date desc",
  "limit": 10
}
```

### Search by text pattern
```json
{
  "doctype": "Customer",
  "filters": {"customer_name": ["like", "%acme%"]},
  "fields": ["name", "customer_name", "customer_group", "territory"]
}
```

### Count pattern (get total without heavy data)
```json
{
  "doctype": "ToDo",
  "filters": {"status": "Open", "allocated_to": "user@example.com"},
  "fields": ["name"],
  "limit": 1
}
```
Then check `total_count` in the response for the full count.

## Edge Cases

- **Virtual DocTypes** may not support all filter operators
- **Child tables** cannot be queried directly — query the parent DocType instead
- **Permission filters** are applied automatically — results only include documents the user can read
- **Link fields** store the `name` (ID), not the display value — use the ID in filters
- **Maximum limit is 1000** — for larger datasets, use `run_database_query` with SQL
