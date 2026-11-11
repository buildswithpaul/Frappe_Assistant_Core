# How to Use set_opening_invoices

## Overview

Makes an import session's file the user's opening receivables (Sales: what customers still owe) or
payables (Purchase: what is still owed to suppliers). They come in as opening Sales or Purchase
Invoices, made the way ERPNext's Opening Invoice Creation Tool makes them: one line of the
outstanding amount against the company's Temporary Opening account, no taxes, no stock.
It writes no business data.

## Before calling

1. `start_import_session` with the file (`file_id`; upload it in File Manager first).
2. Ask the user **which company**, whether the file is **receivables or payables** (one kind per
   session; a file with both is two sessions), and **the cut-off date** (the last day in the old
   system). Don't guess the date. In a migration plan, take the company and the date from
   `plan_migration`'s `opening_setup` (asked once there).

## Parameters

| Parameter | Required | Description |
|---|---|---|
| `session` | Yes | The import session id |
| `company` | Yes | The company the invoices belong to |
| `invoice_type` | Yes | `Sales` or `Purchase` |
| `cut_off` | Yes | Cut-off date, `YYYY-MM-DD` |
| `columns` | Yes | File column header -> one of `party`, `outstanding_amount`, `invoice_number`, `posting_date`, `due_date`, `item_name` |

`party` and `outstanding_amount` are required.

- `posting_date` is the invoice's own date (it keeps the ageing right); default the cut-off. A date
  after the cut-off is refused: what was owed at the cut-off was invoiced on or before it.
- `due_date` defaults to the invoice date.
- Sales: the invoice number becomes the invoice's name. Purchase: it becomes the supplier's bill
  number (`bill_no`); ERPNext names the invoice.

## Next

`dry_run_import(session)`. Every wrong column is listed at once: correct them all in one call.
Then fix what it finds, and `import_opening_invoices`.
