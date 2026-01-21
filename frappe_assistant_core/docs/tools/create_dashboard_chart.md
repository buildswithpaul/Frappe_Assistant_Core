# create_dashboard_chart

Create Dashboard Chart documents for Frappe's dashboard system.

## When to Use

- Building charts that integrate with Frappe dashboards
- Creating reusable business metrics visualizations
- Setting up real-time data monitoring
- Creating charts that persist in the system

## Key Concept

This creates **Dashboard Chart** documents in Frappe, not image visualizations. These charts:
- Can be added to Frappe Dashboards
- Update automatically with data changes
- Are accessible to users with proper permissions
- Use Frappe's native charting

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| chart_name | string | Yes | - | Name for the dashboard chart |
| chart_type | string | Yes | - | Visual type: line, bar, pie, donut, percentage, heatmap |
| doctype | string | Yes | - | Source DocType for data |
| aggregate_function | string | Yes | "Count" | Count, Sum, Average, Group By |
| value_based_on | string | Conditional | - | Field for Sum/Average (required for those) |
| based_on | string | No | - | Field for grouping (x-axis for bar/pie) |
| time_series_based_on | string | Conditional | - | Date field (required for line/heatmap) |
| timespan | string | No | "Last Month" | Time range for data |
| time_interval | string | No | "Daily" | Time grouping: Yearly, Quarterly, Monthly, Weekly, Daily |
| filters | object | No | {} | Filters to apply to data |
| color | string | No | - | Chart color (hex code) |
| dashboard_name | string | No | - | Dashboard to add chart to |

## Chart Types and Requirements

| Chart Type | Required Fields | Use Case |
|------------|-----------------|----------|
| line | time_series_based_on | Trends over time |
| bar | based_on | Category comparisons |
| pie | based_on | Proportions |
| donut | based_on | Proportions (hollow center) |
| percentage | - | Progress indicators |
| heatmap | time_series_based_on | Data density patterns |

## Aggregation Functions

| Function | Requires value_based_on | Description |
|----------|-------------------------|-------------|
| Count | No | Count records |
| Sum | Yes | Total numeric values |
| Average | Yes | Mean of numeric values |
| Group By | Yes (for Sum/Average) | Group by categories |

## Examples

### Sales Count Over Time (Line)

```json
{
  "chart_name": "Daily Sales Count",
  "chart_type": "line",
  "doctype": "Sales Invoice",
  "aggregate_function": "Count",
  "time_series_based_on": "posting_date",
  "timespan": "Last Month",
  "time_interval": "Daily",
  "filters": {"docstatus": 1}
}
```

### Revenue by Customer (Bar)

```json
{
  "chart_name": "Top Customers by Revenue",
  "chart_type": "bar",
  "doctype": "Sales Invoice",
  "aggregate_function": "Sum",
  "value_based_on": "grand_total",
  "based_on": "customer",
  "filters": {"docstatus": 1}
}
```

### Invoice Status Distribution (Pie)

```json
{
  "chart_name": "Invoice Status",
  "chart_type": "pie",
  "doctype": "Sales Invoice",
  "aggregate_function": "Count",
  "based_on": "status"
}
```

### Monthly Revenue Trend (Line with Sum)

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

### Average Order Value by Category (Bar)

```json
{
  "chart_name": "Average Order by Category",
  "chart_type": "bar",
  "doctype": "Sales Invoice",
  "aggregate_function": "Average",
  "value_based_on": "grand_total",
  "based_on": "customer_group",
  "filters": {"docstatus": 1}
}
```

### Add Chart to Dashboard

```json
{
  "chart_name": "Open Tasks",
  "chart_type": "bar",
  "doctype": "Task",
  "aggregate_function": "Count",
  "based_on": "status",
  "filters": {"status": ["!=", "Completed"]},
  "dashboard_name": "My Dashboard"
}
```

## Response Format

```json
{
  "success": true,
  "chart_name": "Daily Sales Count",
  "chart_id": "Daily Sales Count",
  "chart_type": "line",
  "aggregate_function": "Count",
  "chart_url": "/app/dashboard-chart/Daily Sales Count",
  "added_to_dashboard": "Sales Dashboard",
  "data_points": 30,
  "chart_validated": true,
  "warnings": []
}
```

## Common Issues

### "Field not found"

The specified field doesn't exist in the DocType. Use `get_doctype_info` to verify field names.

### "Time series field required"

Line and heatmap charts need `time_series_based_on` with a Date/Datetime field.

### "value_based_on required"

Sum and Average aggregations need a numeric field specified in `value_based_on`.

## Auto-Detection

The tool can auto-detect fields:
- Date fields: posting_date, transaction_date, creation
- Grouping fields: status, type, category, customer

## Workflow

1. **Create charts** using this tool
2. **Create dashboard** using `create_dashboard` linking the charts
3. **View dashboard** at `/app/dashboard/{name}`

## Related Tools

- **create_dashboard** - Create dashboard linking multiple charts
- **list_user_dashboards** - List available dashboards
- **get_doctype_info** - Verify field names exist
- **create_visualization** - One-off image visualizations
