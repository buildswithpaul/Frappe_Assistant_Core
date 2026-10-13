# How to Use get_insights_chart

## Overview

Reads one Frappe Insights v3 chart in more depth than `get_insights_dashboard` returns — for
follow-ups ("break that down", "show me all the rows") or for charts listed in `more_charts`.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | **Yes** | Insights Chart v3 name |
| `dashboard` | string | No | The dashboard the chart is on — applies that dashboard's filters |
| `filters` | array | No | Overrides by the dashboard's filter names (needs `dashboard`) |
| `max_rows` | integer | No | 1–500, default 200 |

## Response

`{"success", "chart": {title, type, columns, rows, truncated, source, config_summary?, note?, error?}, "filters", "unknown_filters"}`

Read `source`, `truncated` and the filters exactly as described for `get_insights_dashboard`:
quote `chart` numbers, aggregate `raw` rows yourself and say so, never treat truncated rows as
totals, and say which filters applied.

## Tips

- Pass `dashboard` whenever the user is looking at the chart on a dashboard, so the numbers match what they see on first load.
- Without `dashboard`, no dashboard filters apply; say the numbers are unfiltered.
