# create_dashboard

Create Frappe dashboards by linking existing charts into organized views.

## When to Use

- Organizing multiple related charts into a single view
- Creating business monitoring dashboards
- Building executive summary pages
- Sharing dashboard views with users/roles

## Important Workflow

Charts must exist **before** creating the dashboard:

1. **First**: Create charts using `create_dashboard_chart`
2. **Then**: Create dashboard linking those charts with this tool

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| dashboard_name | string | Yes | - | Dashboard title |
| chart_names | array | Yes | - | Array of existing Dashboard Chart names |
| doctype | string | No | - | Primary data source (optional) |
| filters | object | No | {} | Global dashboard filters |
| share_with | array | No | [] | Users/roles to share with |
| auto_refresh | boolean | No | true | Enable auto refresh |
| refresh_interval | string | No | "1_hour" | Refresh interval |
| template_type | string | No | "custom" | Dashboard template type |
| mobile_optimized | boolean | No | true | Mobile responsive layout |

### Refresh Intervals

- `5_minutes`
- `15_minutes`
- `30_minutes`
- `1_hour`
- `24_hours`

### Template Types

- `sales` - Sales metrics
- `financial` - Financial KPIs
- `inventory` - Stock management
- `hr` - HR metrics
- `executive` - Executive summary
- `custom` - Custom layout

## Examples

### Basic Dashboard

```json
{
  "dashboard_name": "Sales Overview",
  "chart_names": [
    "Daily Sales Count",
    "Revenue by Customer",
    "Invoice Status"
  ]
}
```

### Dashboard with Sharing

```json
{
  "dashboard_name": "Executive Dashboard",
  "chart_names": [
    "Monthly Revenue",
    "Top Customers",
    "Outstanding Payments"
  ],
  "share_with": ["Sales Manager", "accounts@company.com"],
  "auto_refresh": true,
  "refresh_interval": "30_minutes"
}
```

### Department Dashboard

```json
{
  "dashboard_name": "HR Metrics",
  "chart_names": [
    "Employee Count by Department",
    "Leave Status",
    "Attendance Overview"
  ],
  "template_type": "hr",
  "share_with": ["HR Manager"]
}
```

## Response Format

```json
{
  "success": true,
  "dashboard_type": "frappe_dashboard",
  "dashboard_name": "Sales Overview",
  "dashboard_id": "Sales Overview",
  "dashboard_url": "/app/dashboard/Sales Overview",
  "charts_linked": 3,
  "mobile_optimized": true,
  "auto_refresh": true,
  "charts": ["Daily Sales Count", "Revenue by Customer", "Invoice Status"],
  "permissions": ["Sales Manager"]
}
```

## Chart Missing Error

If charts don't exist:

```json
{
  "success": false,
  "error": "Charts not found: Monthly Revenue, Top Customers. Use create_dashboard_chart to create them first."
}
```

## Complete Workflow Example

### Step 1: Create Charts

```json
// Chart 1
{
  "chart_name": "Monthly Revenue",
  "chart_type": "line",
  "doctype": "Sales Invoice",
  "aggregate_function": "Sum",
  "value_based_on": "grand_total",
  "time_series_based_on": "posting_date",
  "timespan": "Last Year",
  "time_interval": "Monthly"
}

// Chart 2
{
  "chart_name": "Customer Distribution",
  "chart_type": "pie",
  "doctype": "Sales Invoice",
  "aggregate_function": "Count",
  "based_on": "customer_group"
}

// Chart 3
{
  "chart_name": "Outstanding Amount",
  "chart_type": "bar",
  "doctype": "Sales Invoice",
  "aggregate_function": "Sum",
  "value_based_on": "outstanding_amount",
  "based_on": "customer",
  "filters": {"outstanding_amount": [">", 0]}
}
```

### Step 2: Create Dashboard

```json
{
  "dashboard_name": "Sales Dashboard",
  "chart_names": [
    "Monthly Revenue",
    "Customer Distribution",
    "Outstanding Amount"
  ],
  "share_with": ["Sales User", "Sales Manager"],
  "auto_refresh": true,
  "refresh_interval": "15_minutes"
}
```

## Sharing Permissions

The `share_with` parameter accepts:
- **User emails**: Direct user access
- **Role names**: All users with that role get access

## Accessing Dashboards

After creation:
- URL: `/app/dashboard/{dashboard_name}`
- Menu: Setup > Dashboard > {dashboard_name}

## Related Tools

- **create_dashboard_chart** - Create charts first
- **list_user_dashboards** - View accessible dashboards
- **get_document** - Check dashboard details
