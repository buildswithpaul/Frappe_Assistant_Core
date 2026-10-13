# How to Use get_insights_dashboard

## Overview

Reads a Frappe Insights v3 dashboard as the user sees it on first load: its filters and, for
each chart, the chart's numbers with the dashboard's **default** filters. Use it when the user
is on a dashboard ("what does this show?", "what stands out?") or after finding one with
`list_insights_dashboards`.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | **Yes** | Insights Dashboard v3 name (from the page line or the list) |
| `filters` | array | No | Overrides by the dashboard's own filter names: `[{"filter": "Status", "operator": "=", "value": "Open"}]` |
| `max_rows_per_chart` | integer | No | 1–200, default 50 |

Operators follow Insights: `=`, `!=`, `>`, `>=`, `<`, `<=`, `in`, `not_in`, `between`, `within`, `contains`, `not_contains`, `starts_with`, `ends_with`, `is_set`, `is_not_set`.

## Response

- `filters`: each filter's `operator`, `value` and `source` — `default`, `override` or `none` (not applied).
- `charts`: up to 12, each with `title`, `type`, `columns`, `rows`, `truncated`, `columns_truncated`, `source`, `applied_filters`, `config_summary`, and `error` when it could not be read.
- `more_charts`: charts beyond the first 12 — read them with `get_insights_chart`.
- `unknown_filters`: override names the dashboard does not have.
- `notes`: the dashboard's text blocks, as plain text.

## Reading the numbers correctly

- **Always say which filters the numbers use, chart by chart.** A dashboard filter reaches only the charts it is linked to: a chart's `applied_filters` lists the ones that reached it, and an empty list means its numbers are unfiltered. The user may have changed filters on screen; you cannot see that. Say "with the dashboard's default filters (Status = Open)" and offer to apply theirs.
- **`source: "chart"`** — the chart's own numbers. Quote them, and use `config_summary` to say what they measure (a pivot table's columns are dimension values, so its cells do not name their measure). Charts often measure different things — never add or compare values across charts unless their measures match.
- **`source: "raw"`** — the chart's source rows, not its aggregation (its author changed it since it last ran). Aggregate them as `config_summary` describes (dimension, measure, aggregation) and say you did.
- **`truncated: true`** — you have the first rows only (a chart reads no more rows than it draws, its own row limit). Never present sums or counts over truncated rows as totals; say they are partial or read the chart with `get_insights_chart` and a higher `max_rows`.
- **`columns_truncated: true`** — the chart has more than 40 columns and you have the first 40; say so before drawing conclusions about the missing ones.
- A chart with `error` — mention it briefly ("one chart could not be read") and continue with the rest.
- `unknown_filters` not empty — tell the user which filter names do not exist on this dashboard and list the real ones from `filters`.

## Example

User on a dashboard asks "what stands out?" → call with `name` from the page line → report the
two or three biggest movements or outliers across charts, each with its chart title and the
filters used.
