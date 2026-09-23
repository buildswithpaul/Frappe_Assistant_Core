# Document Authoring (PDF Generation)

## Overview

When the user asks for a **report**, **analysis**, **summary**, **proposal**, or any *downloadable* file, call the `generate_document` tool. You write a single markdown document — the tool converts it to a styled PDF and returns a download link to share with the user.

This skill teaches you how to produce PDFs that look *designed*, not just dumped. The same rich-block dialect you use in chat (charts, callouts, metric cards) **also works inside `generate_document` content** — plus three PDF-specific blocks (`cover`, `pagebreak`) for structuring longer documents.

**Default to plain markdown.** Reach for rich blocks only when they earn their place — a section heading and a clean table beats a callout-and-chart sandwich nine times out of ten.

## When to use this tool

Use `generate_document` when the user:
- Asks for a file ("can you give me a PDF of…", "send me a report", "export this as a document")
- Wants something to share, print, or archive (proposals, audit summaries, monthly reports)
- Requests a deliverable distinct from the chat reply itself

**Don't** use it for:
- Quick answers — reply in chat
- Live dashboards — those are the chat surface's job
- Anything under ~one screenful of content — a markdown reply is friendlier

## The two response patterns

### Pattern A — Chat reply with attached file

The PDF is the deliverable; the chat message is a short cover note.

> Here's the Q1 sales report with the full breakdown by region:
>
> [Q1_Sales_Report.pdf](/private/files/Q1_Sales_Report.pdf)
>
> Top line: revenue up 18%, but DSO has crept up — worth a quick review with finance.

### Pattern B — File-only, no chat duplication

When the user explicitly asked for "just the PDF", paste the download link verbatim and stop. Don't restate the document body in chat.

**Always copy the `download_link` field from the tool result exactly as returned.** No `sandbox:` prefix, no `https://` rewrite — Frappe relative URLs like `/private/files/Report.pdf` work as-is.

## Document structure — when to use what

```
┌─────────────────────────┐
│  Cover page (optional)  │   For reports >5 pages or anything formal
├─────────────────────────┤
│  Executive summary      │   1–2 paragraphs. What is this and why does it matter?
├─────────────────────────┤
│  KPI strip (metrics)    │   3–5 metric cards side by side for headline numbers
├─────────────────────────┤
│  Charts                 │   Trend / comparison visualisations
├─────────────────────────┤
│  Detailed sections      │   Headings, tables, prose
├─────────────────────────┤
│  Conclusion / actions   │   What the reader should do next
└─────────────────────────┘
```

Match the structure to the depth of content. A 2-page summary doesn't need a cover page. A 20-page audit absolutely does.

## Rich blocks supported in PDFs

All five fenced blocks below work *inside the markdown you pass to `generate_document.content`*. They render as inline SVG and styled HTML — no external dependencies, no broken images.

### Chart

Identical schema to the chat-side `chart` block. Use `categories` + `series`, not Chart.js `labels`/`datasets`.

```chart
{"type": "bar", "title": "Monthly Revenue", "data": {"categories": ["Jan", "Feb", "Mar"], "series": [{"name": "Revenue (₹)", "values": [1200000, 1480000, 1425000]}]}}
```

**Supported types:** `bar`, `line`, `pie`, `scatter`.

**Tips that matter on paper:**
- Keep series count ≤ 3 — more than that and the legend gets noisy in print.
- Pie charts: ≤ 6 slices. Roll the long tail into "Others".
- Don't put a chart inside a tight section just because you can — give it air.

### Callout

For warnings, tips, key takeaways. Use sparingly — one or two per document.

```callout type="warning" title="Collections lagging"
DSO has crept up from 32 to **41 days**. Worth a review with the finance team this week.
```

**Types:** `info`, `tip`, `success`, `warning`, `error`.

### Metric card

For headline KPIs. Group 3–5 cards in a row above a chart — that's a "dashboard strip".

```metric title="Revenue" value="₹14,25,000" change="+18%" trend="up"
```

```metric title="Orders" value="247" change="+12%" trend="up"
```

```metric title="Avg Order" value="₹5,769" change="-4%" trend="down"
```

Place several metric blocks on consecutive lines — they render side-by-side. `trend` controls the arrow colour (`up` green, `down` red, `flat` grey).

### Cover page

A full-bleed branded page with title, subtitle, author, and date. Use for formal deliverables.

```cover title="Q1 FY26 Sales Report" subtitle="Performance summary and outlook" author="Finance Team" date="May 2026"
Optional supporting paragraph rendered below the title — keep it to one sentence.
```

A cover page automatically inserts a page break after itself, so the next content starts on page 2.

### Page break

Force a new page where you need one — typically between major sections of a long document.

```pagebreak
```

(The block body is ignored; an empty fence works.)

## Markdown features that PDF renders well

- **Headings** (`#`, `##`, `###`) — used for table-of-contents-like structure. H1 in body content gets a coloured underline; H2 gets a thin grey rule; H3 is bold-only.
- **Tables** — full borders, alternating row stripes, **header row repeats on page breaks** automatically.
- **Lists** — both ordered and unordered.
- **Code blocks** — light grey background, monospace, page-break-protected.
- **Blockquotes** — italic, left-border, light grey background. Great for pull quotes.
- **Bold / italic / inline code / horizontal rule** — all styled.

## Worked example — a clean monthly report

```
# Q1 FY26 — Sales Performance

```cover title="Q1 FY26 Sales Report" subtitle="Revenue, regions, and outlook" author="Finance Team" date="May 2026"
```

## Executive Summary

Revenue grew **18% year over year** to ₹14.25 lakh, driven by stronger
performance in the North and East regions. Collections, however, slowed
from a 32-day to 41-day DSO — addressed in the action items below.

## Headline Numbers

```metric title="Revenue" value="₹14,25,000" change="+18%" trend="up"
```

```metric title="Orders" value="247" change="+12%" trend="up"
```

```metric title="DSO" value="41 days" change="+9d" trend="down"
```

## Revenue Trend

```chart
{"type": "bar", "title": "Monthly Revenue (₹ Lakhs)", "data": {"categories": ["Jan", "Feb", "Mar"], "series": [{"name": "Actual", "values": [12.0, 14.8, 14.25]}, {"name": "Target", "values": [12, 13, 14]}]}}
```

```callout type="warning" title="Collections need attention"
Three customers account for **62% of overdue invoices**. Recommend a
direct outreach this week, ahead of quarter-end close.
```

```pagebreak
```

## Regional Breakdown

| Region | Revenue    | Orders | YoY    |
|--------|------------|--------|--------|
| North  | ₹5,20,000  | 89     | +24%   |
| South  | ₹4,80,000  | 72     | +11%   |
| East   | ₹2,40,000  | 51     | +33%   |
| West   | ₹1,85,000  | 35     | -2%    |

## Recommended Actions

1. **Collections push** — direct outreach to top-3 overdue accounts.
2. **West region review** — only region declining; merits a separate analysis.
3. **East region investment** — strongest growth rate; consider capacity bump.
```

## Common mistakes — don't do these

- **Don't restate the entire PDF body in your chat reply.** That defeats the point of the file. A short cover note ("Here's the report — top line: revenue up 18%, DSO concern flagged") is enough.
- **Don't add `sandbox:` to the download link.** The link comes back as a working relative URL. Use it verbatim.
- **Don't generate a PDF for a 2-line answer.** Reply in chat.
- **Don't nest rich blocks** (e.g., a chart inside a callout). Each fence stands alone.
- **Don't pass Chart.js `labels`/`datasets` shape.** Use `categories` + `series`. Same constraint as the chat-side chart block.
- **Don't forget `trend` on metric cards** when you have a `change` value — the arrow + colour is the whole point of the card.
- **Don't put currency symbols inside the chart `values` array.** `1200`, not `"₹1,200"`. Put the unit in `series[i].name`.

## Parameter reference

| Parameter      | Required | Example              | Notes                                              |
|----------------|----------|----------------------|----------------------------------------------------|
| `content`      | yes      | (markdown string)    | Full document body. Rich fences allowed.           |
| `filename`     | yes      | `"Q1_Sales_Report"`  | No extension — `.pdf` added automatically.         |
| `title`        | no       | `"Q1 Sales Report"`  | Styled header at top of doc (skip if using `cover`)|
| `orientation`  | no       | `"landscape"`        | Default `portrait`. Use landscape for wide tables. |
| `page_size`    | no       | `"Letter"`           | Default `A4`.                                      |

## Final guidance

A great PDF tells a story in three beats: **what** (the headline numbers), **why** (the trend or context), **what now** (the recommended actions). Use cover pages, charts, and callouts to *serve* that story — never as decoration. If you can't justify why a chart is there, leave it out.