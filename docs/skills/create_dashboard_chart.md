# How to Use create_dashboard_chart and create_dashboard

## Overview

Two tools work together to create Frappe dashboards:

1. **`create_dashboard_chart`** — creates individual chart documents
2. **`create_dashboard`** — creates a dashboard that links existing charts together

**Always create charts first, then create the dashboard.**

## create_dashboard_chart Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `chart_name` | string | **Yes** | — | Name for the chart |
| `chart_type` | string | **Yes** | — | `"line"`, `"bar"`, `"pie"`, `"donut"`, `"percentage"`, `"heatmap"` |
| `doctype` | string | **Yes** | — | Data source DocType |
| `aggregate_function` | string | **Yes** | — | `"Count"`, `"Sum"`, `"Average"`, `"Group By"` |
| `based_on` | string | No | — | Field to group by (x-axis for bar/pie/donut) |
| `value_based_on` | string | No | — | Numeric field for Sum/Average |
| `time_series_based_on` | string | No | — | Date field for line/heatmap charts |
| `timespan` | string | No | `"Last Month"` | `"Last Year"`, `"Last Quarter"`, `"Last Month"`, `"Last Week"` |
| `time_interval` | string | No | `"Daily"` | `"Yearly"`, `"Quarterly"`, `"Monthly"`, `"Weekly"`, `"Daily"` |
| `filters` | object | No | `{}` | Data filters |
| `color` | string | No | — | Hex color code |

### Field Requirements by Chart Type

| Chart Type | Required Fields |
|------------|----------------|
| `line` | `time_series_based_on` (date field) |
| `bar` | `based_on` (category field) |
| `pie`/`donut` | `based_on` (category field) |
| `percentage` | — |
| `heatmap` | `time_series_based_on` (date field) |

### Aggregation Requirements

| Function | Needs `value_based_on`? |
|----------|------------------------|
| `Count` | No |
| `Sum` | Yes (numeric field like `grand_total`) |
| `Average` | Yes (numeric field) |
| `Group By` | No |

## create_dashboard Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `dashboard_name` | string | **Yes** | — | Dashboard title |
| `chart_names` | array | **Yes** | — | Array of existing chart names |
| `doctype` | string | No | — | Primary data source DocType |
| `template_type` | string | No | `"custom"` | `"sales"`, `"financial"`, `"inventory"`, `"hr"`, `"executive"`, `"custom"` |
| `share_with` | array | No | — | Users/roles to share with |
| `auto_refresh` | boolean | No | `true` | Enable auto refresh |
| `refresh_interval` | string | No | `"1_hour"` | Refresh frequency |

## Workflow Example

### Step 1: Create charts
```json
{
  "chart_name": "Monthly Revenue",
  "chart_type": "line",
  "doctype": "Sales Invoice",
  "aggregate_function": "Sum",
  "value_based_on": "grand_total",
  "time_series_based_on": "posting_date",
  "timespan": "Last Year",
  "time_interval": "Monthly",
  "filters": {"docstatus": 1}
}
```

### Step 2: Create dashboard linking charts
```json
{
  "dashboard_name": "Sales Overview",
  "chart_names": ["Monthly Revenue", "Top Customers", "Invoice Status"],
  "template_type": "sales"
}
```

## Best Practices

1. **Use `list_user_dashboards`** — check existing dashboards before creating new ones.
2. **Charts must exist first** — `create_dashboard` links to existing chart names.
3. **Match chart type to data** — line for trends, bar for comparisons, pie for proportions.
4. **Filter for submitted docs** — use `{"docstatus": 1}` to exclude drafts/cancelled.
