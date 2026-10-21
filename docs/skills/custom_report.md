# Custom Report

## Overview

Builds a report the standard list does not give, such as "overdue invoices by sales person" or "items sold this month with their margin". This creates a `Report` document. Follow `get_skill("setup-change-protocol")` for the plan, the confirmation and the change log. This skill covers what goes into the record.

**Only a System Manager can do this.** Anyone else gets "Changing Report needs a System Manager". A Query Report or Script Report also needs the **Script Manager** role. If it is missing, the error names it. Tell the user which role and who can grant it.

**Talk to the user in business words.** Say "a report of overdue invoices", not `ref_doctype` or `report_type`.

## When to use

- "I need a report of X", "show me X grouped by Y", "can we save this list as a report?"

**Not for** one-off questions. Answer those with `run_database_query` or `generate_report`.

## Workflow

1. **Report Builder first.** It needs no code: columns, filters and grouping on one doctype. Use it whenever the answer comes from one doctype and its child table.
2. **Query Report next**, when the report must join several doctypes. The query is `SELECT` or `WITH` only. Anything that writes is refused.
3. **Script Report last**, only when scripts are on. Call `get_doctype_info` on `Report` and read `server_scripts_enabled`. If it is false, say in plain words that this site does not run scripts, and offer a Report Builder or Query Report instead, or to save the script report switched off (`disabled: 1`).
4. **State the scope in one plain sentence**: "This adds a new report on Sales Invoice. It only reads data; nothing else changes."
5. **List existing reports** on the doctype (`list_documents` on `Report` with `ref_doctype`) and offer to reuse one.
6. **Show the full query or code** in a fenced block and explain in plain words what each column means and which records are included.
7. **Create it, run it once** with `generate_report` or in Desk, and show the user the first rows before calling it done. Create a script report with `disabled: 1` and enable it only after the user confirms the output.
8. **Amounts.** Use company-currency `base_*` amounts when summing across currencies, and say whether item-level discounts are included.
9. **Link the result**: the new report and the doctype it reports on (`applies_to` is not set for reports, so link the report's own `url`).

## Reference

```json
{
  "doctype": "Report",
  "data": {
    "report_name": "Overdue Sales Invoices",
    "ref_doctype": "Sales Invoice",
    "report_type": "Query Report",
    "is_standard": "No",
    "query": "SELECT name AS \"Invoice:Link/Sales Invoice:140\", customer AS \"Customer:Link/Customer:160\", base_grand_total AS \"Amount:Currency:120\" FROM `tabSales Invoice` WHERE docstatus = 1 AND status = 'Overdue'"
  }
}
```

- Column format is `Label:Type/Options:Width`.
- Roles that can open the report are set in its `roles` table; by default only the roles that can read the doctype.

## Gotchas

- A Query Report ignores user permissions unless the query filters for them. Warn the user if the data is sensitive.
- Cancelled and draft documents are included unless the query filters `docstatus`.

## Anti-patterns

- A Script Report where a Report Builder would do.
- Showing the user the SQL but not what the columns mean.
- Summing `grand_total` across currencies.
