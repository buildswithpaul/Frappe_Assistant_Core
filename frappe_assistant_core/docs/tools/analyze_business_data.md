# analyze_business_data

One-click business intelligence tool for professional analytics without coding.

## When to Use

- Data profiling and quality assessment
- Statistical analysis on business data
- Trend analysis over time
- Finding correlations between fields
- When standard reports don't provide the analysis needed

## Use Hierarchy

1. **First**: Try `generate_report` for standard business reports
2. **Then**: Use this tool when reports don't provide specific analysis needed

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| doctype | string | Yes | - | DocType to analyze (e.g., 'Sales Invoice') |
| analysis_type | string | Yes | - | Type of analysis (see below) |
| fields | array | No | Auto-detect | Specific fields to analyze |
| filters | object | No | {} | Frappe filters to narrow data |
| date_field | string | No | "creation" | Date field for trend analysis |
| limit | integer | No | 1000 | Max records to analyze (max: 10000) |

## Analysis Types

| Type | Description | Output |
|------|-------------|--------|
| profile | Complete data overview | Nulls, types, unique counts, field statistics |
| statistics | Business metrics | Mean, median, std, quartiles, skewness |
| trends | Time-series patterns | Daily/monthly growth, seasonal trends |
| quality | Data health score | Duplicates, nulls, consistency issues |
| correlations | Field relationships | Which metrics affect each other |

## Examples

### Data Profile

```json
{
  "doctype": "Sales Invoice",
  "analysis_type": "profile"
}
```

### Statistical Analysis

```json
{
  "doctype": "Sales Invoice",
  "analysis_type": "statistics",
  "filters": {"docstatus": 1},
  "fields": ["grand_total", "outstanding_amount", "discount_amount"]
}
```

### Trend Analysis

```json
{
  "doctype": "Sales Invoice",
  "analysis_type": "trends",
  "date_field": "posting_date",
  "filters": {"docstatus": 1}
}
```

### Data Quality Check

```json
{
  "doctype": "Customer",
  "analysis_type": "quality",
  "limit": 5000
}
```

### Correlation Analysis

```json
{
  "doctype": "Item",
  "analysis_type": "correlations",
  "fields": ["valuation_rate", "standard_rate", "safety_stock"]
}
```

## Response Format

### Profile Analysis

```json
{
  "success": true,
  "doctype": "Sales Invoice",
  "analysis_type": "profile",
  "record_count": 500,
  "analysis_result": {
    "record_count": 500,
    "field_count": 15,
    "memory_usage": 125000,
    "fields": {
      "grand_total": {
        "type": "float64",
        "non_null_count": 500,
        "null_count": 0,
        "null_percentage": 0,
        "unique_count": 450,
        "min": 100,
        "max": 50000,
        "mean": 15000,
        "median": 12000,
        "std": 8000
      }
    }
  }
}
```

### Trends Analysis

```json
{
  "success": true,
  "analysis_result": {
    "daily_trend": {
      "data_points": 30,
      "average_per_day": 15.5,
      "max_day": 45,
      "min_day": 2,
      "trend_direction": "increasing"
    },
    "monthly_trend": {
      "data_points": 6,
      "average_per_month": 450.2,
      "max_month": 600,
      "min_month": 300
    },
    "date_range": {
      "start_date": "2024-01-01",
      "end_date": "2024-06-30",
      "total_days": 180
    }
  }
}
```

### Quality Analysis

```json
{
  "success": true,
  "analysis_result": {
    "total_records": 1000,
    "overall_score": 85.5,
    "summary": {
      "total_issues": 3,
      "fields_with_issues": 2,
      "quality_score": 85.5
    },
    "issues": {
      "email_id": ["High null percentage: 25.0%"],
      "mobile_no": ["High null percentage: 15.0%"]
    }
  }
}
```

### Correlation Analysis

```json
{
  "success": true,
  "analysis_result": {
    "numeric_fields": ["grand_total", "outstanding_amount", "paid_amount"],
    "correlation_matrix": {...},
    "strong_correlations": [
      {
        "field1": "grand_total",
        "field2": "paid_amount",
        "correlation": 0.85,
        "strength": "strong positive"
      }
    ],
    "analysis_summary": {
      "total_correlations_analyzed": 3,
      "strongest_correlation": 0.85
    }
  }
}
```

## Common Use Cases

| Use Case | Analysis Type | Example |
|----------|--------------|---------|
| Data quality audit | quality | Check customer data completeness |
| Sales trends | trends | Monthly revenue patterns |
| Field relationships | correlations | Price vs margin relationship |
| Data exploration | profile | Understand new DocType structure |
| Metric benchmarks | statistics | Average order values |

## Dependencies

Requires pandas and numpy to be installed.

## Related Tools

- **generate_report** - Standard business reports (try first)
- **run_python_code** - Custom analysis with full code control
- **run_database_query** - Direct SQL queries
- **report_list** - Discover available reports
