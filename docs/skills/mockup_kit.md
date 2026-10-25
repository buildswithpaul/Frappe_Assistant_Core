# Mockup Kit

## Overview

Use this kit to write the `mockup_html` shown with a build plan. The mockup is plain HTML in a sandboxed preview that already carries the kit's styles. It cannot load anything from the network and cannot reach the page around it, so write static markup only.

The same classes work in a FAC Page's `html` (see the `fac-page` skill), so a mockup can become the page itself.

## Rules

- Write the inside of a page: no `<html>`, `<head>` or `<body>` tags.
- Use inline `<svg>` or `data:` URIs for images. Nothing external loads (no fonts, scripts, stylesheets or image URLs).
- Keep it under 200 KB, and show the screen as the user will see it, with sample data.

## Classes

| Class | Use |
|---|---|
| `mk-page` | outer wrapper, adds padding and spacing |
| `mk-card` | bordered panel |
| `mk-btn`, `mk-btn-primary` | buttons (primary is the filled one) |
| `mk-badge` | small status pill |
| `mk-table` | table with a muted header row |
| `mk-field` | a label above an input, select or textarea |
| `mk-tabs` | row of tabs; mark the current child with `active` |
| `mk-stat` | a small label over a large number |
| `mk-chart` | a chart container, full width and 320 px high; `fac.chart` adds it |

## Example

```html
<div class="mk-page">
  <div class="mk-tabs"><span class="active">Overview</span><span>Activity</span></div>
  <div class="mk-card">
    <div class="mk-stat"><span>Open orders</span><span>24</span></div>
  </div>
  <div class="mk-field"><label>Customer</label><input value="Acme Ltd"></div>
  <table class="mk-table">
    <tr><th>Order</th><th>Status</th></tr>
    <tr><td>SO-0001</td><td><span class="mk-badge">Draft</span></td></tr>
  </table>
  <button class="mk-btn mk-btn-primary">Save</button>
</div>
```

## Charts in a FAC Page

A mockup is static, so it cannot draw a chart; show a sample chart as an inline `<svg>` there. A published FAC Page's `script` can call `fac.chart(el, option)`, which draws an [ECharts](https://echarts.apache.org/en/option.html) `option` into `el` as SVG. It works the same in the chat's page panel and in Desk.

- Bar, line and pie charts, with the grid, tooltip, legend and title components. No other ECharts chart type or component is loaded.
- Series take the FAC palette unless the option sets its own `color`.
- It returns `{update(option), dispose()}`. `update` merges a new option in, as ECharts' `setOption` does.
- The container gets `mk-chart`. Set a different height in the page's `style` if 320 px does not suit.

```html
<div class="mk-page">
  <div class="mk-card"><div class="sales-chart"></div></div>
</div>
```

```js
frappe.db.get_list("Sales Invoice", {
  fields: ["customer", "grand_total"],
  filters: { docstatus: 1 },
  limit: 10,
}).then((rows) => {
  fac.chart(root_element.querySelector(".sales-chart"), {
    tooltip: {},
    xAxis: { type: "category", data: rows.map((r) => r.customer) },
    yAxis: { type: "value" },
    series: [{ type: "bar", data: rows.map((r) => r.grand_total) }],
  });
});
```

## Printing

The chat's page panel has a Download PDF button. It prints the page as it is drawn at that moment, charts included, in the kit's design:

- A4 portrait, or landscape when the page is wider than 900 px, with 12 mm margins. The suggested file name is the page title and today's date.
- Shadows are dropped and colours print as shown.
- A card, a table row and a chart are not split across sheets. A chart wider than the sheet is scaled down to fit.
