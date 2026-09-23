# Rich Components

## Overview

Rich components render as interactive UI elements in the chat. Use them **sparingly** — plain markdown is preferred for most responses. Rich components are useful when you need to draw attention to something important, display a KPI, guide the user through steps, or organize dense content.

All components use triple-backtick code fences with a component name and optional attributes.

## Callout

Highlighted notice box for important information.

```callout type="info" title="Payment Overdue"
Invoice INV-00042 is overdue by 15 days. Consider sending a reminder.
```

**Types:** `info`, `warning`, `tip`, `success`, `error`

- `title` is optional — omit for simple notices
- Content supports **markdown** (bold, links, lists)
- Use `warning` for things the user should act on, `error` for failures, `tip` for suggestions

A JSON body is also accepted (`type`, `title`/`heading`, `content`/`body`/`text`/`message`), so this renders the same box:

```callout
{"type": "warning", "title": "Data quality caveat", "content": "All 216 leads were bulk-imported."}
```

Prefer the attribute form — it keeps the body free for markdown. A JSON body whose keys are none of the above is shown as-is rather than silently emptied.

## Metric Card

Single KPI display with optional trend indicator.

```metric title="Monthly Revenue" value="₹14,25,000" change="+18%" trend="up"
```

**Attributes:**
- `title` — what is being measured
- `value` — the current value (include currency/unit)
- `change` — percentage change string (e.g., `"+18%"`, `"-5%"`)
- `trend` — `up`, `down`, or `flat`
- `description` — optional qualifier under the value (e.g., `"per night"`)

**Attributes go on the fence line, not in the body** — unlike `chart`, which takes a JSON body. A JSON body is also accepted as a fallback (`label`/`title`, `value`, `change`, `trend`, `suffix`/`description`), so this renders the same card:

```metric
{"label": "Monthly Revenue", "value": "₹14,25,000", "change": "+18%", "trend": "up"}
```

A JSON **array** renders one card per entry — the way to write a whole KPI row in a single fence:

```metric
[{"label": "Open tickets", "value": "15"}, {"label": "Resolved this week", "value": "42"}]
```

Prefer the attribute form. A metric fence with neither a title nor a value renders as a plain code block, not a card; entries in an array that have neither are skipped.

## Chart

Interactive chart for numerical comparisons and trends. Use for 2+ data points; prefer a markdown table for 2–3 raw values, prefer a chart when proportions, trends, or distributions matter.

**Supported types:** `bar`, `line`, `pie`, `scatter`.

### Schema

```chart
{"type": "bar", "title": "Monthly Revenue", "data": {"categories": ["Jan", "Feb", "Mar"], "series": [{"name": "Revenue", "values": [1000, 1500, 1200]}]}}
```

- `type` — one of `bar`, `line`, `pie`, `scatter`.
- `title` — optional heading shown above the chart.
- `data.categories` — array of x-axis labels (or slice labels for pie).
- `data.series` — array of series objects. Each has:
  - `name` — label shown in legend and tooltip (recommended — include units here, e.g. `"Revenue (₹)"`).
  - `values` — numeric array, same length as `categories`.

### Examples — one per type

**Bar**

```chart
{"type": "bar", "title": "Payment Status", "data": {"categories": ["Paid", "Overdue"], "series": [{"name": "Amount (₹)", "values": [164854, 184293]}]}}
```

**Line**

```chart
{"type": "line", "title": "Weekly Orders", "data": {"categories": ["W1", "W2", "W3", "W4"], "series": [{"name": "Orders", "values": [12, 19, 17, 24]}]}}
```

**Pie** — same `categories`/`series` shape; no pie-specific dialect.

```chart
{"type": "pie", "title": "Supplier Spend", "data": {"categories": ["Summit Traders", "Zuckerman Security", "MA Inc."], "series": [{"name": "Spend (₹)", "values": [158200, 110250, 80697]}]}}
```

**Scatter**

```chart
{"type": "scatter", "title": "Price vs Quantity", "data": {"categories": [10, 20, 30, 40, 50], "series": [{"name": "Units Sold", "values": [120, 95, 140, 80, 160]}]}}
```

### Multi-series

Express multiple series as multiple entries in `series` — do not nest arrays inside a single series.

```chart
{"type": "bar", "title": "Revenue vs Cost", "data": {"categories": ["Q1", "Q2", "Q3", "Q4"], "series": [{"name": "Revenue", "values": [1200, 1500, 1400, 1700]}, {"name": "Cost", "values": [800, 900, 950, 1100]}]}}
```

### Rules

- `categories.length` **must equal** `series[i].values.length` for every series.
- `values` must be **numbers**, not strings. Do not include currency symbols or commas inside numbers — write `1200`, not `"₹1,200"`. Put units in `series.name`.
- Pie charts also use `categories` + `series[].values` — not a special single-array shape.
- A single series is fine; `series[0].name` still shows in tooltips.

### Common pitfalls

**❌ Do NOT use Chart.js style with `labels` and `datasets`** — the renderer does not accept this shape and will show "Missing or invalid categories".

```
{"type": "bar", "data": {"labels": ["A", "B"], "datasets": [{"label": "Values", "data": [10, 20], "backgroundColor": ["#5470c6", "#91cc75"]}]}}
```

**✅ Correct — use `categories` and `series`:**

```
{"type": "bar", "data": {"categories": ["A", "B"], "series": [{"name": "Values", "values": [10, 20]}]}}
```

Colors are chosen automatically — do not pass `backgroundColor` or `color` fields; they're ignored.

## Steps

Step-by-step guide with optional progress tracking.

```steps title="Invoice Processing"
## Step 1: Create Draft
Create the Sales Invoice from the Sales Order using the "Make" button.

## Step 2: Verify Line Items
Check that quantities and rates match the Delivery Note.

## Step 3: Submit
Submit the invoice to finalize it and create GL entries.
```

**Attributes:**
- `title` — heading for the step guide
- `current` (optional) — highlight the active step (e.g., `current="2"`)
- Each `##` heading becomes a step title; content below it becomes the step body

## Accordion

Collapsible sections for dense content that users can expand on demand.

```accordion
## Outstanding Invoices
You have 12 outstanding invoices totaling ₹4,50,000. The oldest is from January.

## Payment Terms
Standard payment terms are Net 30. Three customers have custom terms.

## Action Items
- Send reminders for invoices overdue > 30 days
- Review credit limits for accounts on hold
```

- Each `##` heading becomes a collapsible section title
- Content between headings becomes the section body
- First section is expanded by default

## Tabs

Tabbed view for comparing alternatives or organizing related content side by side.

```tabs
## This Month
Revenue: ₹14,25,000 | Orders: 47 | Average Order: ₹30,319

## Last Month
Revenue: ₹12,10,000 | Orders: 41 | Average Order: ₹29,512

## Year to Date
Revenue: ₹1,02,50,000 | Orders: 384 | Average Order: ₹26,692
```

- Each `##` heading becomes a tab name
- Content between headings becomes the tab body
- Useful for: period comparisons, plan options, module-by-module breakdowns

## When to Use Each Component

| Component | Best For | Example |
|-----------|----------|---------|
| `callout` | Warnings, tips, important notices | Payment overdue alert |
| `metric` | Single KPI with trend | Monthly revenue card |
| `chart` | Numerical comparisons / trends | Monthly revenue bar chart |
| `steps` | Sequential processes | Invoice creation workflow |
| `accordion` | Dense info users can expand | FAQ, detailed breakdowns |
| `tabs` | Side-by-side comparisons | This month vs last month |

**Default to plain markdown.** Use rich components only when they genuinely improve clarity — a bullet list is often better than an accordion, and bold text is often better than a callout.