# Pages from Reports

## Overview

When a FAC Page shows figures a report already computes, such as profit and loss, receivables, a stock balance or a custom Script or Query Report, read the report with `fac.report` and draw its own figures. Don't rebuild them from raw records: the page would disagree with the report the user opens in Desk. This skill covers reading a report in a page's script. `pages-in-chat` and `fac-page` cover building the page itself.

## When to use

- "A page with this year's P&L by month", "income, expense and net profit cards", "overdue receivables by customer", "show our custom margin report as a chart".
- A page whose figures come from a financial statement or any report the site has.

**Not for** a list of records you filter yourself, such as open orders: read those with `frappe.db.get_list`.

## Workflow

1. **Find the report.** Search with `report_search` or `report_list`, then read its filters with `report_requirements`. Run it once with `generate_report` and the filters the page will use, so you see the real columns before writing the script.
2. **Read it with `fac.report(name, filters)`.** It returns a promise of:
   - `status`: `"ok"`, `"no_access"` (the viewer may not run this report), `"preparing"` (a Prepared Report with no result for these filters) or `"error"` (the server refused the run, such as a `company` or cost center the viewer may not read, or a missing mandatory filter);
   - `columns`: the report's columns, each with `fieldname`, `label` and `fieldtype`;
   - `rows`: the data rows as objects keyed by fieldname. Blank separator rows and the total row are left out. A financial statement's summary lines, such as "Total Income (Credit)" and "Profit for the year", have their quotes removed and carry `total_line: true`;
   - `total`: the report's total row as an object keyed by fieldname, or `null`;
   - `summary`: the report's summary cards, each with `label`, `value`, `datatype` and `currency`;
   - `chart`: the report's own chart data, or `null`;
   - `message`: the server's reason when `status` is `"error"`, or the report's own message.
3. **Show every status.** Branch on `status` for each card or table that reads a report:
   - `no_access`: show "You don't have access to this report" in that card. Never draw 0, an empty table or a broken card.
   - `preparing`: show "This report is prepared in the background and can't be shown on this page yet." A Prepared Report's result belongs to the person who generated it and matches only the exact filters they used, so opening it in Desk rarely makes the page's copy appear. For a page, prefer a report that runs directly.
   - `error`: show the `message` in that card, escaped. If it names a missing filter, fix the page's filters.
   - `ok`: draw the figures.
4. **Use the report's own figures.** Never recompute a total the report already gives.
   - **Profit and Loss Statement, Balance Sheet, Cash Flow:** use `summary` for the headline cards ("Total Income", "Total Expense", "Net Profit" on P&L), or the `total_line` row such as "Profit for the year". With `periodicity` set, each period is a column whose `fieldname` is the period, such as `nov_2026`; read the period columns from `columns`, never build their names. Each period column holds that period's own figure, as Desk shows it by default (`accumulated_values` 0): never subtract one period column from another. Pass `accumulated_values: 1` only when the user asks for running totals, and then each column is the total so far. Account rows carry `indent` and `parent_account` for the tree.
   - **Accounts Receivable and Payable:** `total.outstanding` is the total outstanding, and `range1` to `range5` (with `range0` for not yet due) are the ageing buckets. Rows are per voucher; group them by `party` in the script for a per-customer table. Leave the `group_by_party` filter off: with it on, the report adds per-party subtotal rows (marked `bold`) to `rows`, and grouping them again counts every amount twice.
5. **Filter it like the user would in Desk.** The filters management pages need most:
   - `company`;
   - `filter_based_on`: `"Date Range"` with `period_start_date` and `period_end_date`, or `"Fiscal Year"` with `from_fiscal_year` and `to_fiscal_year`;
   - `periodicity`: `"Monthly"`, `"Quarterly"`, `"Half-Yearly"` or `"Yearly"`;
   - `cost_center` as a list of names, and any accounting dimension the site has;
   - for receivables, `report_date` and `ageing_based_on`.
   A filter on the page (a period or company picker) calls `fac.report` again and redraws.
6. **Format** each figure with `frappe.format(value, { fieldtype: column.fieldtype }, …)` and escape the result, as `pages-in-chat` says. For a summary card, use its `datatype` as the fieldtype.
7. **Charts:** draw with `fac.chart` from `rows`, or from the period columns.
8. **Test it** as `pages-in-chat` (or `fac-page` for a shared page) says, and compare a figure on the page with the same report in Desk for the same filters.

```js
const esc = frappe.utils.escape_html;
const money = (v) => esc(frappe.format(v, { fieldtype: "Currency" }));
const card = (label, text) => `<div class="mk-stat"><span>${esc(label)}</span><span>${text}</span></div>`;

fac.report("Profit and Loss Statement", {
  company: "Acme Ltd",
  filter_based_on: "Date Range",
  period_start_date: "2026-04-01",
  period_end_date: "2026-11-30",
  periodicity: "Monthly",
}).then((r) => {
  const el = root_element.querySelector("#pl-cards");
  if (r.status === "no_access") return (el.textContent = __("You don't have access to this report"));
  if (r.status === "preparing") return (el.textContent = __("This report is prepared in the background and can't be shown on this page yet."));
  if (r.status === "error") return (el.textContent = r.message || __("This report could not be run."));
  el.innerHTML = r.summary.map((s) => card(s.label, money(s.value))).join("");
});
```

## Who sees the figures

A page reads every report as the person viewing it, so each viewer sees only the reports their roles allow; nothing on a page widens that. On a shared page, list on the build plan the report roles the page's viewers need (for example Accounts User for P&L), and check them with `test_as_user`. A viewer without them sees the `no_access` message, not the figures.

## Calling a report without fac.report

`fac.report` is the way to read a report. If you must call `frappe.desk.query_report.run` yourself, call `frappe_assistant_core.api.fac_page.report_access` with `{ reports: [name] }` first and skip the run when it answers `false`: on a shared page in Desk, a refused run opens Desk's "Not permitted" dialog and takes the user off the page. Pass `silent: true` so Desk doesn't open its message dialog over the page when the server refuses a filter. Then handle the shapes `fac.report` handles for you: a `prepared_report: true` answer with no `doc` and no rows, a total row that is an array aligned with `columns`, and quoted summary lines.

## Anti-patterns

- Pasting figures into the html instead of reading the report.
- Recomputing a P&L or an ageing from GL entries or invoices when the report gives it.
- Drawing 0 or an empty table for `no_access`, `preparing` or `error`.
- Building period fieldnames such as `nov_2026` yourself instead of reading them from `columns`.
- Calling `query_report.run` on a shared page without checking `report_access` first.
