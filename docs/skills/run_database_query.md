# How to Use run_database_query

## Overview

The `run_database_query` tool executes read-only SQL queries against the Frappe/MariaDB database. It provides direct database access for complex queries that cannot be expressed through the document API. Requires **System Manager** role.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | **Yes** | — | SQL SELECT query |
| `limit` | integer | No | 100 | Max rows to return (max: 1000) |
| `analysis_type` | string | No | `"basic"` | `"basic"`, `"statistical"`, or `"detailed"` |
| `validate_query` | boolean | No | `true` | Validate and optimize query before execution |
| `format_results` | boolean | No | `true` | Format results for readability |
| `include_schema_info` | boolean | No | `false` | Include table schema in response |

## Response Format

```json
{
  "success": true,
  "result": {
    "success": true,
    "query_executed": "SELECT name, module FROM tabDocType LIMIT 5",
    "rows_returned": 5,
    "execution_time_ms": 0.14,
    "data": [
      { "name": "Customer", "module": "Selling" }
    ],
    "analysis": { ... }
  }
}
```

## Best Practices

1. **Always use `tab` prefix** — Frappe tables are prefixed with `tab`: `` `tabSales Invoice` ``, `` `tabCustomer` ``
2. **Use backtick quoting** — DocType names with spaces need backticks: `` `tabSales Invoice` ``
3. **SELECT only** — INSERT/UPDATE/DELETE are rejected
4. **Always include LIMIT** — prevents returning excessive data. The tool also enforces a max via the `limit` parameter.
5. **Use `analysis_type: "statistical"`** — for automatic mean/median/percentile calculations on numeric columns
6. **Set `include_schema_info: true`** — when you need to discover column names and types for a table
7. **Prefer `list_documents` for simple queries** — SQL is for complex JOINs, aggregations, and subqueries

## Common Patterns

### Aggregation with GROUP BY
```sql
SELECT customer, COUNT(*) as invoice_count, SUM(grand_total) as total_revenue
FROM `tabSales Invoice`
WHERE docstatus = 1 AND posting_date >= '2024-01-01'
GROUP BY customer
ORDER BY total_revenue DESC
LIMIT 20
```

### JOIN across DocTypes
```sql
SELECT si.name, si.customer, si.grand_total, sii.item_code, sii.qty
FROM `tabSales Invoice` si
JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
WHERE si.docstatus = 1
LIMIT 50
```

### Date-based analysis
```sql
SELECT DATE_FORMAT(posting_date, '%Y-%m') as month,
       COUNT(*) as count,
       SUM(grand_total) as total
FROM `tabSales Invoice`
WHERE docstatus = 1
GROUP BY month
ORDER BY month DESC
LIMIT 12
```

### Discover table columns
Use `include_schema_info: true` or:
```sql
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'tabSales Invoice'
ORDER BY ORDINAL_POSITION
```

## Table Naming Conventions

| Concept | Table Name |
|---------|------------|
| Parent DocType | `` `tabDocType Name` `` |
| Child table | `` `tabChild DocType Name` `` |
| Child → parent link | `parent` column |
| Child → parent type | `parenttype` column |
| Submission status | `docstatus` (0=Draft, 1=Submitted, 2=Cancelled) |

## Edge Cases

- **Long queries may timeout** — add appropriate WHERE clauses and LIMIT
- **Child table queries** — always JOIN through `parent` column
- **Amended documents** — filter by `docstatus != 2` to exclude cancelled
- **Permissions are NOT automatically applied** — results may include documents the user can't normally see
- **Results are not permission-filtered** — unlike `list_documents`, SQL bypasses Frappe's permission system
