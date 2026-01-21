# run_database_query

Execute complex SQL queries with analysis capabilities. Restricted to SELECT statements for security.

## When to Use

- Complex queries with JOINs that can't be done with `list_documents`
- Direct database analysis with statistical insights
- Query optimization guidance
- Schema exploration

## Requirements

- **System Manager role required** for security

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| query | string | Yes | - | SQL query (SELECT only) |
| analysis_type | string | No | "basic" | Analysis level: "basic", "statistical", "detailed" |
| validate_query | boolean | No | true | Validate and get optimization suggestions |
| format_results | boolean | No | true | Format results for readability |
| include_schema_info | boolean | No | false | Include table schema information |
| limit | integer | No | 100 | Maximum rows to return (max: 1000) |

## Examples

### Simple Query

```json
{
  "query": "SELECT customer_name, grand_total, status FROM `tabSales Invoice` WHERE docstatus = 1"
}
```

### Query with JOINs

```json
{
  "query": "SELECT c.customer_name, SUM(si.grand_total) as total_revenue FROM `tabSales Invoice` si JOIN `tabCustomer` c ON si.customer = c.name WHERE si.docstatus = 1 GROUP BY c.customer_name ORDER BY total_revenue DESC",
  "analysis_type": "statistical"
}
```

### Detailed Analysis

```json
{
  "query": "SELECT * FROM `tabItem` WHERE is_stock_item = 1",
  "analysis_type": "detailed",
  "include_schema_info": true
}
```

## Analysis Types

| Type | Includes |
|------|----------|
| basic | Row count, column count, column names |
| statistical | Basic + mean/median/std for numeric columns, data types, missing values |
| detailed | Statistical + correlation matrix, unique value counts for categorical columns |

## Response Format

### Success

```json
{
  "success": true,
  "query_executed": "SELECT ...",
  "rows_returned": 50,
  "execution_time_ms": 45.2,
  "data": [...],
  "analysis": {
    "basic_info": {
      "total_rows": 50,
      "total_columns": 5,
      "column_names": ["customer_name", "grand_total", ...]
    },
    "statistical_summary": {
      "grand_total": {
        "count": 50,
        "mean": 15000.5,
        "std": 5000.2,
        "min": 500,
        "25%": 10000,
        "50%": 15000,
        "75%": 20000,
        "max": 50000
      }
    }
  },
  "optimization_suggestions": [
    "Consider selecting specific columns instead of using SELECT * for better performance"
  ]
}
```

### Security Violation

```json
{
  "success": false,
  "error": "Query contains forbidden keyword: DELETE. Only SELECT statements are allowed.",
  "security_violation": true
}
```

## Security Restrictions

Only SELECT statements are allowed. The following are blocked:
- INSERT, UPDATE, DELETE
- DROP, CREATE, ALTER, TRUNCATE
- EXEC, EXECUTE, CALL
- DECLARE, SET
- Multiple statements (;)

## Optimization Suggestions

The tool provides optimization guidance:
- `SELECT *` usage warnings
- Missing WHERE clauses in JOINs
- Missing LIMIT with ORDER BY
- Multiple JOIN performance warnings
- GROUP BY without HAVING suggestions

## Table Naming

Frappe tables use the `tab` prefix:
- Customer → `tabCustomer`
- Sales Invoice → `tabSales Invoice`
- Stock Entry → `tabStock Entry`

## Related Tools

- **list_documents** - Simpler document listing without SQL
- **analyze_business_data** - Pre-built analysis without SQL
- **run_python_code** - Custom analysis with pandas
