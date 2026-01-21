# list_user_dashboards

List all dashboards accessible to the current user.

## When to Use

- Discovering available dashboards before navigation
- Finding dashboards shared with you
- Listing dashboards by type (Insights vs Frappe)
- Auditing dashboard access

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| user | string | No | Current user | Specific user to list dashboards for |
| dashboard_type | string | No | "all" | Filter: "insights", "frappe_dashboard", "all" |
| include_shared | boolean | No | true | Include dashboards shared with user |

## Examples

### List All Dashboards

```json
{}
```

### List Frappe Dashboards Only

```json
{
  "dashboard_type": "frappe_dashboard"
}
```

### List User's Own Dashboards

```json
{
  "include_shared": false
}
```

### List Specific User's Dashboards

```json
{
  "user": "manager@company.com"
}
```

## Response Format

```json
{
  "success": true,
  "dashboards": [
    {
      "name": "Sales Dashboard",
      "dashboard_name": "Sales Dashboard",
      "creation": "2024-06-01 10:00:00",
      "modified": "2024-06-15 14:30:00",
      "module": "Custom",
      "access_type": "owner",
      "dashboard_type": "frappe_dashboard"
    },
    {
      "name": "Executive View",
      "dashboard_name": "Executive View",
      "creation": "2024-05-20 09:00:00",
      "modified": "2024-06-10 11:00:00",
      "module": "Insights",
      "access_type": "shared",
      "dashboard_type": "insights"
    }
  ],
  "total_count": 2,
  "user": "user@company.com",
  "dashboard_type_filter": "all",
  "includes_shared": true
}
```

## Access Types

| Type | Description |
|------|-------------|
| owner | User created the dashboard |
| shared | Dashboard was shared with user |

## Dashboard Types

| Type | Description |
|------|-------------|
| frappe_dashboard | Standard Frappe Dashboard |
| insights | Insights app dashboard |

## Navigating to Dashboard

After finding dashboards:
- Frappe Dashboard: `/app/dashboard/{name}`
- Insights Dashboard: Insights app interface

## Common Use Cases

### Before Creating New Dashboard

Check if similar dashboard exists:

```json
{
  "dashboard_type": "frappe_dashboard"
}
```

### Finding Shared Reports

See what's been shared with you:

```json
{
  "include_shared": true
}
```

## Related Tools

- **create_dashboard** - Create new dashboards
- **create_dashboard_chart** - Create charts for dashboards
- **get_document** - Get dashboard details
