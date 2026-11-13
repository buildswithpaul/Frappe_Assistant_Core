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

A mockup is static, so it cannot draw a chart; show a sample chart as an inline `<svg>` there. A FAC Page's `script` (personal, or shared and published) can call `fac.chart(el, option)`, which draws an [ECharts](https://echarts.apache.org/en/option.html) `option` into `el` as SVG. It works the same in the chat's page panel and in Desk.

- Bar, line and pie charts, with the grid, tooltip, legend and title components. No other ECharts chart type or component is loaded, and `fac.chart` throws for any other series type.
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

For figures a report already computes, read the report with `fac.report(name, filters)` and chart its rows or period columns instead of recomputing them (`get_skill("page-reports")`).

## Pages people type into

A page can let people type into records with the page tools. They work in Desk, beside the chat and on a personal page, so use them for anything people edit on a page, never `frappe.ui` dialogs, `frappe.prompt` or a hand-built form. The records belong in a doctype (`get_skill("fac-page")`); the tools only show and save them.

| Class | What |
|---|---|
| `mk-section` | one block of the page, such as one business unit; give it `data-title` |
| `mk-section-head` | the section's title row: title on the left, meta and actions on the right |
| `mk-section-meta` | small muted text, such as `fac.updated(doc)` |
| `mk-list` | a plain list of rows (`fac.editList` uses it) |
| `mk-text` | text that keeps its line breaks (`fac.editText` uses it) |
| `mk-edit` | marks a control that changes data; Present mode hides it |
| `mk-sev-high`, `mk-sev-med`, `mk-sev-low` | add to `mk-badge` for a HIGH, MED or LOW severity |
| `mk-status-done`, `mk-status-pending` | an 8px dot for "filled in" or "still to do"; put a word or `aria-label` beside it |

- **`fac.canWrite(doctype, name)`** resolves `true` when the viewer may change the record. It only decides whether to show edit controls; the server checks every save.
- **`fac.updated(doc)`** returns "Updated by … · date" from the record's `modified_by` and `modified`.
- **`fac.editList(el, { doctype, name, table, columns, canEdit, emptyText })`** shows the record's child table `table` as a list and, for someone who may change the record, an Edit button to edit, add and remove rows. Each column is `{ fieldname, label, fieldtype }` with `fieldtype` `"Data"`, `"Small Text"` or `"Select"` (give `options`), and `badge: true` to show the value as a severity badge. Save reads the record again and keeps every field and row change it does not show, then saves it. If the server refuses, the rows stay as typed with the reason below them. Leave `canEdit` out to ask `fac.canWrite`. It resolves `{ reload() }`.
- **`fac.editText(el, { doctype, name, fieldname, multiline, canEdit, emptyText })`** does the same for one text field.
- **`fac.periodPicker(el, { options, value, onChange, label })`** draws a period select. `options` are strings or `{ value, label }`. A change calls `onChange(value)`; the returned `set(value)` moves it without calling back, and `value()` reads it.

On a personal page each save asks the user first, listing the fields and rows it changes.

```html
<div class="mk-page">
  <div id="period"></div>
  <section class="mk-card mk-section" data-title="Decathlon">
    <div class="mk-section-head"><h3>Decathlon</h3><span class="mk-section-meta" id="updated"></span></div>
    <div id="risks"></div>
    <div id="notes"></div>
  </section>
</div>
```

```js
const show = async (period) => {
  const [row] = await frappe.db.get_list("BU Update", { filters: { period, business_unit: "Decathlon" }, fields: ["name"], limit: 1 });
  if (!row) return (root_element.querySelector("#risks").textContent = __("Not filled in yet"));
  const doc = await frappe.db.get_doc("BU Update", row.name);
  root_element.querySelector("#updated").textContent = fac.updated(doc);
  await fac.editList(root_element.querySelector("#risks"), {
    doctype: "BU Update", name: row.name, table: "risks",
    columns: [
      { fieldname: "severity", label: __("Severity"), fieldtype: "Select", options: ["HIGH", "MED", "LOW"], badge: true },
      { fieldname: "description", label: __("Risk"), fieldtype: "Small Text" },
    ],
  });
  await fac.editText(root_element.querySelector("#notes"), { doctype: "BU Update", name: row.name, fieldname: "notes", multiline: true });
};
fac.periodPicker(root_element.querySelector("#period"), { options: ["NOV-26 F1", "OCT-26 F2"], value: "NOV-26 F1", onChange: show });
show("NOV-26 F1");
```

## Printing

The chat's page panel has a Download PDF button. It prints the page as it is drawn at that moment, charts included, in the kit's design:

- A4 portrait, or landscape when the page is wider than 900 px, with 12 mm margins. The suggested file name is the page title and today's date.
- Shadows are dropped and colours print as shown.
- A card, a table row and a chart are not split across sheets. A chart wider than the sheet is scaled down to fit.
