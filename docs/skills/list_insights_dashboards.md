# How to Use list_insights_dashboards

## Overview

Lists the Frappe Insights v3 dashboards the user can open, newest first. Use it when a data
question ("how are sales trending?") is probably answered by an Insights dashboard and you do
not know which one. Then read the best match with `get_insights_dashboard`.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `search` | string | No | Words to find in dashboard titles |
| `limit` | integer | No | 1–50, default 20 |

## Response

`{"success": true, "dashboards": [{"name", "title", "workbook", "chart_count", "modified"}]}`

Only dashboards the user may open are listed — Insights' own sharing rules decide.

## Tips

- Search with the business word the user used ("sales", "tickets"), then try a broader word if nothing matches.
- If several dashboards fit, name them and ask which one, rather than reading all of them.
- `{"success": false, "error": "You don't have access to Frappe Insights."}` means the user has no Insights role; say so plainly.
