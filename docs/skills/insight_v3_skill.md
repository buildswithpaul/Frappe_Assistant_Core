---
name: insights-dashboard
description: >
  Use this skill whenever the user wants to create, build, set up, or fix a dashboard
  in Frappe Insights (also called "Insights", "Frappe Insights v3", or the analytics module).
  Trigger on phrases like: "create an Insights dashboard", "build a dashboard in Insights",
  "add a chart to a workbook", "create a workbook", "set up analytics in Insights",
  "Insights is showing errors", "column does not exist in chart", "dashboard not showing",
  "chart is empty in Insights". This skill contains critical pitfalls that WILL be hit
  without it — always load it before attempting any Insights dashboard work.
---

# Frappe Insights v3 — Dashboard Creation Skill

## Overview

Frappe Insights v3 uses a **Workbook-centric** architecture. Everything lives inside a Workbook:
queries, charts, and dashboards. There are several legacy doctypes that look similar but are
wrong — using them is the #1 source of errors. This skill documents the correct path and every
known pitfall.

---

## Critical: Right vs Wrong Doctypes

This is the most important thing to get right. There are legacy v1/v2 doctypes that still exist
in the database but are NOT used by the Insights v3 UI.

| Purpose | ✅ CORRECT (v3) | ❌ WRONG (legacy) |
|---|---|---|
| Workbook container | `Insights Workbook` | — |
| Query | `Insights Query v3` | `Insights Query` |
| Chart | `Insights Chart v3` | `Insights Chart` |
| Dashboard | `Insights Dashboard v3` | `Insights Dashboard` |

**Always use the v3 doctypes.** The legacy `Insights Dashboard` doctype will save without error
but will never appear in the Insights UI. The workbook will show "Dashboard not found".

---

## Architecture: How the Pieces Fit Together

```
Insights Workbook (e.g. name=496)
├── queries JSON field  ← manifest listing all Query v3 docs
├── charts JSON field   ← manifest listing all Chart v3 docs
├── dashboards JSON field ← manifest listing all Dashboard v3 docs
│
├── Insights Query v3 (workbook=496)   ← SQL that fetches data
├── Insights Chart v3 (workbook=496)   ← visual config referencing a query
└── Insights Dashboard v3 (workbook=496) ← grid layout referencing charts
```

The Workbook's `queries`, `charts`, and `dashboards` fields are **JSON manifests** that the UI
reads to populate the sidebar and tabs. If these are null or stale, the UI shows empty
placeholders even though the underlying documents exist in the DB.

---

## Step-by-Step Creation Process

### Step 1: Create the Workbook

```python
create_document(doctype="Insights Workbook", data={"title": "My Analytics"})
# Returns: name=497 (autoincrement integer)
```

Note the returned integer `name` — all child docs reference it as a string.

### Step 2: Create Queries (use native SQL — always)

**Always use native SQL queries.** The builder query type (`is_builder_query=1`) has a known bug:
column names become ambiguous after JOINs and the summarize operation fails with
"Column name does not exist in the table". Native SQL is reliable and matches how all
existing working workbooks (CRM, Helpdesk, Finance) are built.

```python
create_document(
  doctype="Insights Query v3",
  data={
    "title": "Issues by Project",
    "workbook": "496",          # string, even though it's an integer
    "is_native_query": 1,
    "is_builder_query": 0,
    "is_script_query": 0,
    "operations": json.dumps([{
      "data_source": "Site DB",
      "raw_sql": "SELECT rp.project_name, COUNT(ri.name) AS `Total Issues` FROM `tabRedmine Issue` ri INNER JOIN `tabRedmine Project` rp ON ri.redmine_project = rp.name GROUP BY rp.project_name ORDER BY `Total Issues` DESC LIMIT 50",
      "type": "sql"
    }])
  }
)
# Returns name like "1v34po75e2"
```

**SQL column naming rules:**
- Use backtick-quoted aliases for multi-word columns: `` COUNT(name) AS `Total Issues` ``
- The alias name must exactly match what you reference in the chart config
- Keep single-word columns lowercase with no spaces (e.g. `project_name`, `Status`, `Priority`)

### Step 3: Create Charts with Correct Config Schema

Chart config depends on chart type. Use the exact schema below — wrong keys cause silent
rendering failures or "column does not exist" errors.

#### Bar / Row chart config
```json
{
  "filters": {"filters": [], "logical_operator": "And"},
  "limit": 50,
  "order_by": [],
  "x_axis": {
    "dimension": {
      "column_name": "project_name",
      "data_type": "String",
      "dimension_name": "project_name",
      "label": "project_name",
      "value": "project_name"
    }
  },
  "y_axis": {
    "series": [{
      "measure": {
        "aggregation": "sum",
        "column_name": "Total Issues",
        "data_type": "Integer",
        "measure_name": "Total Issues"
      }
    }],
    "show_axis_label": true,
    "show_data_labels": true,
    "stack": false
  }
}
```

#### Donut / Pie chart config
```json
{
  "filters": {"filters": [], "logical_operator": "And"},
  "limit": 100,
  "order_by": [],
  "show_inline_labels": true,
  "label_column": {
    "column_name": "Status",
    "data_type": "String",
    "dimension_name": "Status",
    "label": "Status",
    "value": "Status"
  },
  "value_column": {
    "aggregation": "sum",
    "column_name": "Total Issues",
    "data_type": "Integer",
    "measure_name": "Total Issues"
  }
}
```

#### Number card config

**CRITICAL: `measure_name` is the label displayed on the card.** Do NOT use the auto-generated
format `"sum_of_ColumnName"` — it renders literally as the label. Always set it to a clean
human-readable string like `"Total Leads"` or `"Active Pipeline"`.

Use `"shorten_numbers": true` for large values (millions, lakhs) so they display as `₹99L`
instead of `99,34,480`.

```json
{
  "date_column": {},
  "filters": {"filters": [], "logical_operator": "And"},
  "limit": 100,
  "number_column_options": [],
  "number_columns": [{
    "aggregation": "sum",
    "column_name": "Total Leads",
    "data_type": "Integer",
    "measure_name": "Total Leads"
  }],
  "order_by": [],
  "shorten_numbers": true
}
```

#### Line chart config
```json
{
  "filters": {"filters": [], "logical_operator": "And"},
  "limit": 100,
  "order_by": [],
  "x_axis": {
    "dimension": {
      "column_name": "creation",
      "data_type": "Datetime",
      "dimension_name": "creation",
      "granularity": "month",
      "label": "creation",
      "value": "creation"
    }
  },
  "y_axis": {
    "series": [{
      "measure": {
        "aggregation": "count",
        "column_name": "name",
        "data_type": "Integer",
        "measure_name": "Count"
      }
    }],
    "show_area": false,
    "show_data_labels": true,
    "smooth": false,
    "stack": false
  }
}
```

#### Table chart config

**CRITICAL: An empty config `{}` causes "No data to display" even when the query has data.**
The Table chart requires explicit `rows`, `columns`, and `values` arrays. All columns from the
SQL that should appear as rows must be listed individually. Use `"columns": [{}]` as a
placeholder when you don't need pivot columns, and `"values"` with an empty entry when the
rows contain all needed data (no aggregation needed).

```json
{
  "columns": [{}],
  "filters": {"filters": [], "logical_operator": "And"},
  "limit": 50,
  "order_by": [],
  "rows": [
    {
      "column_name": "Industry",
      "data_type": "String",
      "dimension_name": "Industry",
      "label": "Industry",
      "value": "Industry"
    },
    {
      "column_name": "Opportunities",
      "data_type": "Integer",
      "dimension_name": "Opportunities",
      "label": "Opportunities",
      "value": "Opportunities"
    },
    {
      "column_name": "Value (K)",
      "data_type": "Integer",
      "dimension_name": "Value (K)",
      "label": "Value (K)",
      "value": "Value (K)"
    }
  ],
  "show_filter_row": true,
  "show_row_totals": false,
  "show_column_totals": false,
  "values": [
    {
      "aggregation": "",
      "column_name": "",
      "data_type": "Decimal",
      "measure_name": ""
    }
  ]
}
```

For pivot-style tables (rows × columns × aggregated value), populate `columns` with the
pivot dimension and `values` with the measure — same pattern as Project Projections example.

**Create the chart:**
```python
create_document(
  doctype="Insights Chart v3",
  data={
    "title": "Issues by Project",
    "workbook": "496",
    "query": "1v34po75e2",   # query name from Step 2
    "chart_type": "Bar",     # exact casing: Bar, Donut, Line, Number, Row, Table, Pie
    "is_public": 1,
    "config": json.dumps(bar_config_from_above)
  }
)
# Returns name like "28jo5dmvrg"
```

**chart_type valid values:** `Bar`, `Row`, `Line`, `Donut`, `Pie`, `Number`, `Table`
(capital first letter, matches what the Insights UI sends)

### Step 4: Create the Dashboard (Insights Dashboard v3)

The items field is a **JSON string** (not a child table) containing a list of chart/text/filter
objects with grid layout coordinates.

```python
items = [
  # Optional: title text banner
  {
    "type": "text",
    "text": "<h2>My Dashboard Title</h2>",
    "layout": {"x": 0, "y": 0, "w": 20, "h": 1, "i": "title-001", "moved": False}
  },
  # Full-width bar chart
  {
    "type": "chart",
    "chart": "28jo5dmvrg",   # chart name from Step 3
    "layout": {"x": 0, "y": 1, "w": 20, "h": 10, "i": "chart-001", "moved": False}
  },
  # Two donuts side by side
  {
    "type": "chart",
    "chart": "2ak9k9mcnc",
    "layout": {"x": 0, "y": 11, "w": 10, "h": 8, "i": "chart-002", "moved": False}
  },
  {
    "type": "chart",
    "chart": "2t5ndovcs1",
    "layout": {"x": 10, "y": 11, "w": 10, "h": 8, "i": "chart-003", "moved": False}
  }
]

create_document(
  doctype="Insights Dashboard v3",
  data={
    "title": "My Dashboard",
    "workbook": "496",
    "is_public": 1,
    "items": json.dumps(items)
  }
)
# Returns name like "aj7tikqn6l"
```

**Grid layout rules:**
- Grid is 20 columns wide (`w=20` for full-width, `w=10` for half-width side-by-side)
- `i` must be a unique string per item across ALL items — use short readable IDs like `"chart-001"`
- `x + w` must not exceed 20 or items will overflow off-screen
- `y` values must be **exactly sequential with no gaps and no overlaps**: next item's `y` = previous item's `y + h`. Never reuse a y value for a different row unless items are intentionally side-by-side (same y, different x).

**CRITICAL — Side-by-side alignment:** When placing two charts next to each other (e.g., x=0,w=10 and x=10,w=10), both must share the **same `y` value** AND the **same `h` value**. If heights differ, the taller one will overlap items below it on the shorter side.

**CRITICAL — Mixed-height rows:** When a tall chart (e.g. Donut h=8) sits beside short charts (e.g. Number cards h=4) at the same y, any items placed in the gap on the short side (y+4 to y+8) must stay within x=0..9 and must end at y+8 to align with the tall chart before the next full-width row begins.

**RECOMMENDED — Prefer full-width sections to avoid alignment bugs entirely.** The safest
layout is every section on its own full-width row (w=20). Only use side-by-side (w=10 each)
when both charts have **identical h values** and there are no other items between them:

```
✅ CLEAN — each section is full-width:
  y=0  Header text         w=20 h=2
  y=2  Section label       w=20 h=1
  y=3  Number card left    w=10 h=4   ← same y, same h, side-by-side OK
       Number card right   w=10 h=4
  y=7  Next section label  w=20 h=1   ← y = 3+4 = 7, perfectly aligned
  y=8  Full-width chart    w=20 h=9

❌ RISKY — mixed heights on same row cause gaps and overlaps:
  y=3  Number cards (h=4) left side
       Donut chart (h=8)  right side  ← different h, causes left-side gap
  y=7  Section label appears in the gap — visually broken
```

**Always validate layout before creating the dashboard:**
```python
errors = []
for item in items:
    l = item["layout"]
    if l["x"] + l["w"] > 20:
        errors.append(f"OVERFLOW: x={l['x']} w={l['w']} sum={l['x']+l['w']}")
if errors:
    print("LAYOUT ERRORS:", errors)
else:
    print("Layout valid - no overflow")
```

---

## Adding Filters to a Dashboard

**ALWAYS add filters to every dashboard.** A dashboard without filters forces users to look at
all-time data with no way to slice by date, user, or any dimension. Filters are what make a
dashboard actually useful.

### How Filters Work in Insights v3

Filters are **dashboard-level items** placed in the `items` JSON — the same array as charts and
text blocks. There is no way to embed a filter inside an individual chart card. Instead, the
recommended pattern is to place filter widgets **directly above the chart(s) they control**,
linked only to those charts. This makes them feel per-chart even though they are technically
dashboard-level.

Each filter item has a `links` object that maps **chart name → query column reference**. The
column reference format is: `` `<query_name>`.`<column_name>` `` (backtick-quoted, both parts).

### Filter Item Schema

```json
{
  "type": "filter",
  "filter_name": "From Date",
  "filter_type": "Date",
  "layout": {"x": 0, "y": 1, "w": 4, "h": 1, "i": "flt-001", "moved": false},
  "links": {
    "<chart_name>": "`<query_name>`.`<column_name>`"
  }
}
```

**filter_type valid values:** `Date`, `String`, `Integer`, `Decimal`

### Full Example: Date Range + String Filter

```python
items = [
  # Section heading
  {"type": "text", "text": "<b>Issues by Project</b>",
   "layout": {"x": 0, "y": 0, "w": 20, "h": 1, "i": "sec-001", "moved": False}},

  # Filter row — placed directly above the chart it controls
  {
    "type": "filter",
    "filter_name": "From Date",
    "filter_type": "Date",
    "layout": {"x": 0, "y": 1, "w": 4, "h": 1, "i": "flt-001", "moved": False},
    "links": {
      "28jo5dmvrg": "`1v34po75e2`.`creation`"
      #              ^chart name    ^query name  ^column name
    }
  },
  {
    "type": "filter",
    "filter_name": "To Date",
    "filter_type": "Date",
    "layout": {"x": 4, "y": 1, "w": 4, "h": 1, "i": "flt-002", "moved": False},
    "links": {
      "28jo5dmvrg": "`1v34po75e2`.`creation`"
    }
  },
  {
    "type": "filter",
    "filter_name": "Project",
    "filter_type": "String",
    "layout": {"x": 8, "y": 1, "w": 4, "h": 1, "i": "flt-003", "moved": False},
    "links": {
      "28jo5dmvrg": "`1v34po75e2`.`project_name`"
    }
  },

  # The chart itself
  {
    "type": "chart",
    "chart": "28jo5dmvrg",
    "layout": {"x": 0, "y": 2, "w": 20, "h": 10, "i": "chart-001", "moved": False}
  }
]
```

### Linking One Filter to Multiple Charts

A single filter can fan out to control multiple charts simultaneously — just add more entries
to the `links` object, one per chart:

```json
{
  "type": "filter",
  "filter_name": "From Date",
  "filter_type": "Date",
  "layout": {"x": 0, "y": 0, "w": 4, "h": 1, "i": "flt-global-from", "moved": false},
  "links": {
    "chart_name_1": "`query_name_1`.`creation`",
    "chart_name_2": "`query_name_2`.`creation`",
    "chart_name_3": "`query_name_3`.`timestamp`"
  }
}
```

### ⚠️ Critical Filter Pitfalls

**PITFALL 1 — Never link a filter to a KPI / Number card query.**
Number card queries return a single aggregated scalar (e.g. `COUNT(*) AS Total`). They have
no `user`, `date`, or dimension columns to filter on. Linking a `User` or `Date` filter to a
Number card query will cause the error:
> *"Column 'user' is not found in table. Existing columns: 'Total Calls'."*

**Fix:** In the filter's `links` object, only include charts whose underlying queries actually
SELECT the column being filtered. Omit all Number card charts from filter links entirely.

**PITFALL 2 — Column name in links must match the SQL alias exactly.**
If the SQL uses `DATE(timestamp) AS date`, the filter link must reference `` `query`.`date` ``,
not `` `query`.`timestamp` ``.

**PITFALL 3 — `i` values must be unique across ALL items** (charts, text, filters).
Reusing an `i` value causes the grid to collapse items on top of each other silently.

### Recommended Filter Layout Pattern

Always place filters in a dedicated row immediately above the section they control, with a
section heading text item above the filter row:

```
y=0  Section heading text (full width, h=1)
y=1  Filter row: [From Date][To Date][Dimension filter]  (h=1 each)
y=2  Chart(s) the filters apply to
```

This gives the dashboard a clear visual hierarchy and makes it obvious which filters affect
which charts.

### Step 5: Update the Workbook Manifests

This is the step most likely to be forgotten — without it the sidebar is empty.

```python
update_document(
  doctype="Insights Workbook",
  name="496",
  data={
    "queries": json.dumps([
      {"is_builder_query": 0, "is_native_query": 1, "is_script_query": 0,
       "name": "1v34po75e2", "title": "Issues by Project"},
      # ... one entry per query
    ]),
    "charts": json.dumps([
      {"chart_type": "Bar", "name": "28jo5dmvrg",
       "query": "1v34po75e2", "title": "Issues by Project"},
      # ... one entry per chart
    ]),
    "dashboards": json.dumps([
      {"name": "aj7tikqn6l", "title": "My Dashboard"}
    ])
  }
)
```

---

## URL Patterns

| Resource | URL |
|---|---|
| Workbook | `/insights/workbook/{workbook_id}` |
| Chart in workbook | `/insights/workbook/{workbook_id}/chart/{chart_name}` |
| Dashboard in workbook | `/insights/workbook/{workbook_id}/dashboard/{dashboard_name}` |

---

## Common Errors and Fixes

### "Column 'X' is not found in table. Existing columns: 'Total'"
**Cause:** A filter's `links` object points to a Number card chart. Number card queries return
only the aggregated scalar column — they have no dimension columns like `user`, `date`, etc.
**Fix:** Remove the Number card chart name from the filter's `links` object. Only link filters
to charts whose SQL actually SELECTs the column being filtered.

### Filter has no effect on a chart
**Cause 1:** The chart is missing from the filter's `links` object.
**Fix:** Add `"<chart_name>": "\`<query_name>\`.\`<column_name>\`"` to the filter's `links`.
**Cause 2:** The column name in the link doesn't match the actual SQL alias.
**Fix:** Check the SQL — if it uses `DATE(timestamp) AS date`, the link must use `` `query`.`date` ``.

### "Column name does not exist in the table"
**Cause:** Using `is_builder_query=1` with a JOIN + summarize pipeline.
**Fix:** Convert the query to native SQL (`is_native_query=1`, `is_builder_query=0`).

### Dashboard tab shows "Dashboard doesn't exist"
**Cause 1:** Dashboard was created in `Insights Dashboard` (legacy) instead of `Insights Dashboard v3`.
**Fix:** Delete the old one, create in `Insights Dashboard v3` with `workbook` field set.
**Cause 2:** Workbook `dashboards` manifest not updated.
**Fix:** Update the workbook's `dashboards` JSON field.

### Charts show as empty placeholders in workbook sidebar
**Cause:** Workbook `charts` manifest is null or stale.
**Fix:** Update the workbook's `charts` JSON field with all chart names.

### Chart renders but shows no data
**Cause:** Chart config `column_name` values don't match the actual column aliases in the SQL.
**Fix:** Check the SQL aliases carefully. If SQL has `` COUNT(name) AS `Total Issues` ``,
the config must use `"column_name": "Total Issues"` (no backticks, exact match).

### Chart config silently broken
**Cause:** Wrong config schema for the chart type (e.g. using `x_axis`/`y_axis` keys for a
Donut chart which needs `label_column`/`value_column`).
**Fix:** Use the exact schema from Step 3 above for each chart type.

---

## Checklist Before Finishing

- [ ] All queries use `is_native_query=1`, not builder
- [ ] SQL column aliases exactly match chart config `column_name` values
- [ ] All charts use correct doctype `Insights Chart v3`
- [ ] Dashboard uses correct doctype `Insights Dashboard v3` with `workbook` field
- [ ] Dashboard `items` JSON has unique `i` values per item and `x+w ≤ 20`
- [ ] **Filters added** — every dashboard must have at least date range filters
- [ ] **Filter links are correct** — `links` uses format `` `query_name`.`column_name` ``
- [ ] **No filter linked to a Number card** — Number card queries have no dimension columns to filter
- [ ] Workbook `queries`, `charts`, `dashboards` JSON manifests all updated
- [ ] Hard refresh the browser after all changes (`Cmd+Shift+R`)

---

## Reference: Inspect an Existing Working Dashboard

Before building anything new, it's useful to inspect a working workbook to verify
the exact format in your environment:

```sql
-- See all Insights Dashboard v3 items for a workbook
SELECT name, title, workbook, items
FROM `tabInsights Dashboard v3`
WHERE workbook = '495'  -- use a known working workbook

-- See all charts for a workbook
SELECT name, title, chart_type, query, config
FROM `tabInsights Chart v3`
WHERE workbook = '495'

-- Verify query type flags
SELECT name, title, is_native_query, is_builder_query, operations
FROM `tabInsights Query v3`
WHERE workbook = '495'
```