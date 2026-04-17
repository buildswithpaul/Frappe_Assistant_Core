# How to Use analyze_business_data

## Overview

The `analyze_business_data` tool performs statistical analysis and data profiling on any DocType. Use it when standard reports don't cover your specific analysis needs.

**Use hierarchy:** First try `generate_report` for standard reports, then use this tool for custom analysis.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `doctype` | string | **Yes** | — | DocType to analyze |
| `analysis_type` | string | **Yes** | — | Type of analysis (see below) |
| `fields` | array | No | auto | Specific fields to focus on |
| `filters` | object | No | `{}` | Frappe filters to narrow data |
| `date_field` | string | No | `"creation"` | Date field for trend analysis |
| `limit` | integer | No | 1000 | Max records (max: 10000) |

## Analysis Types

| Type | What it does |
|------|-------------|
| `profile` | Data overview: field types, null counts, unique counts, basic stats for numeric fields |
| `statistics` | Business metrics: mean, median, std, quartiles for numeric fields |
| `trends` | Time-series patterns: daily/monthly growth rates using `date_field` |
| `quality` | Data health: duplicates, nulls, consistency score |
| `correlations` | Relationships between numeric fields |

## Response Format (profile example)

```json
{
  "success": true,
  "result": {
    "success": true,
    "doctype": "Customer",
    "analysis_type": "profile",
    "record_count": 3,
    "analysis_result": {
      "record_count": 3,
      "field_count": 16,
      "fields": {
        "customer_name": {
          "type": "str",
          "non_null_count": "3",
          "null_count": "0",
          "null_percentage": 0.0,
          "unique_count": 3
        },
        "is_internal_customer": {
          "type": "int64",
          "min": "0", "max": "0",
          "mean": 0.0, "median": 0.0, "std": 0.0
        }
      }
    }
  }
}
```

## Best Practices

1. **Check `report_list` first** — existing reports are faster and more comprehensive.
2. **Use `fields` to focus** — analyzing all fields is slow on wide DocTypes.
3. **Use `filters` to narrow** — e.g., `{"docstatus": 1}` for only submitted documents.
4. **Use `date_field`** — for trends, specify the business date: `"posting_date"`, `"transaction_date"`, etc.
5. **Increase `limit` for accuracy** — default 1000 may not be representative. Use up to 10000.
6. **For complex analysis, use `run_python_code`** — this tool handles standard patterns; custom analysis needs code.

## Common Patterns

### Profile a DocType
```json
{"doctype": "Sales Invoice", "analysis_type": "profile", "filters": {"docstatus": 1}}
```

### Revenue statistics
```json
{
  "doctype": "Sales Invoice",
  "analysis_type": "statistics",
  "fields": ["grand_total", "outstanding_amount"],
  "filters": {"docstatus": 1}
}
```

### Monthly trends
```json
{
  "doctype": "Sales Invoice",
  "analysis_type": "trends",
  "date_field": "posting_date",
  "filters": {"docstatus": 1},
  "limit": 5000
}
```
