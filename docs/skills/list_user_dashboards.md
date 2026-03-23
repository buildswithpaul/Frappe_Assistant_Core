# How to Use list_user_dashboards

## Overview

The `list_user_dashboards` tool lists all dashboards accessible to the current user, including owned and shared dashboards.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `dashboard_type` | string | No | `"all"` | `"insights"`, `"frappe_dashboard"`, or `"all"` |
| `include_shared` | boolean | No | `true` | Include dashboards shared with user |
| `user` | string | No | current user | Specific user to list for |

## Response Format

```json
{
  "success": true,
  "result": {
    "success": true,
    "dashboards": [
      {
        "name": "Selling",
        "dashboard_name": "Selling",
        "creation": "2020-07-20 20:17:16.688162",
        "modified": "2020-07-22 15:31:22.299903",
        "module": "Selling",
        "access_type": "owner",
        "dashboard_type": "frappe_dashboard"
      }
    ],
    "total_count": 10,
    "user": "Administrator",
    "dashboard_type_filter": "all",
    "includes_shared": true
  }
}
```

Each dashboard includes:
- `name` / `dashboard_name` — the dashboard identifier (use with `browser_navigate_to` to open it)
- `module` — which ERPNext module it belongs to (`"Custom"` for user-created ones)
- `access_type` — `"owner"` or `"shared"`
- `dashboard_type` — `"frappe_dashboard"` or `"insights"`

## Best Practices

1. **Check before creating** — avoid duplicate dashboards by listing existing ones first.
2. **Use `dashboard_type: "frappe_dashboard"`** — to filter to standard Frappe dashboards only.
3. **Use the `name` field** — when referencing a dashboard in other operations.
4. **Standard dashboards exist** — ERPNext ships with dashboards for Selling, Buying, Accounts, Stock, CRM, Manufacturing, etc.
