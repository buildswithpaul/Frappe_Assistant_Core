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
```json
{
  "date_column": {},
  "filters": {"filters": [], "logical_operator": "And"},
  "limit": 100,
  "number_column_options": [],
  "number_columns": [{
    "aggregation": "count",
    "column_name": "name",
    "data_type": "Integer",
    "measure_name": "Total Count"
  }],
  "order_by": []
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
- Grid is 20 columns wide (use `w=20` for full-width)
- `i` must be a unique string per item — use a short readable ID like `"chart-001"`
- `x + w` must not exceed 20 (items wrap otherwise)
- `y` values should be sequential (no gaps); items stack vertically

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
