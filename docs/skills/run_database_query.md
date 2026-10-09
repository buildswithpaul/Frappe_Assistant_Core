# How to Use run_database_query

## Overview

The `run_database_query` tool executes read-only SQL queries against the Frappe/MariaDB database. It provides direct database access for complex queries that cannot be expressed through the document API.

Only **System Managers** see this tool. If it is not in your tool list, the user is not a System Manager: use `list_documents`, or `run_python_code` with `frappe.get_list` / `tools.get_documents` (both support `group_by` and aggregate fields).

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | **Yes** | — | SQL SELECT query |
| `limit` | integer | No | 100 | Rows to return when the query has no `LIMIT` of its own (max: 1000) |
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

### Row cap

No query returns more than **1000 rows**, whatever its `LIMIT`:

- A trailing `LIMIT` above 1000 is clamped to 1000. `LIMIT 5000` returns 1000 rows.
- A query with no `LIMIT` gets `LIMIT <limit>` (default 100), so `credit_limit` or any other column name containing "limit" does not disable the cap.
- A trailing `-- comment` does not stop the cap from applying.

When rows were cut, the response says so:

- `truncated`: `true` when the query matched more rows than were returned.
- `row_cap`: the number of rows the cap allows for this query (1000, or the query's own `LIMIT` if it is smaller).
- `message`: present only when `truncated` is `true`. It asks you to aggregate in SQL or narrow the `WHERE` clause.

## Restrictions

These queries are rejected before they run:

- Anything other than a single `SELECT` statement
- Frappe's internal tables — names starting with `__` (`__Auth`, `__global_search`, …). Query DocType tables (`tab…`) instead. A column alias such as `AS __total` is fine.
- Executable comments (`/*! … */`, `/*M! … */`)
- `INTO` anywhere in the query (`SELECT … INTO @var`, `INTO OUTFILE`, `INTO DUMPFILE`)
- `SET`, `CALL`, and `:=` assignment — a query cannot change session state or run a procedure
- Row locks: `FOR UPDATE`, `FOR SHARE`, `LOCK IN SHARE MODE`, and `LOCK` / `UNLOCK TABLE(S)`
- `GRANT` and `REVOKE`
- `LOAD DATA`, `LOAD XML` and `LOAD_FILE(…)`

Column names that merely contain these words (`granted_on`, `set_name`) are fine; only the whole word is refused. A `CHARACTER SET` clause is refused because it contains the word `SET`; use `CAST(x AS CHAR)` instead.

`query_executed` in the response echoes the SQL as you sent it, not the statement that ran after the row cap was applied.

## Best Practices

1. **Always use `tab` prefix** — Frappe tables are prefixed with `tab`: `` `tabSales Invoice` ``, `` `tabCustomer` ``
2. **Use backtick quoting** — DocType names with spaces need backticks: `` `tabSales Invoice` ``
3. **SELECT only** — INSERT/UPDATE/DELETE are rejected
4. **Always include LIMIT** — prevents returning excessive data. Results are capped at 1000 rows even when the query names a larger `LIMIT`; check `truncated` before treating the rows as complete.
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
- **Results are not permission-filtered** — unlike `list_documents` and `run_python_code`, SQL ignores User Permissions, so a System Manager restricted to one company still sees every company's rows. When the answer should reflect what the user may see ("my company's sales", "my team's leads"), use `run_python_code` or `list_documents` instead.
