# How to Use import_opening_invoices

## Overview

Creates and submits the checked opening invoices after the user approves, one invoice per row, each
all or nothing. Use it only after `dry_run_import` said the sheet is ready, and only when the user
asks to import. Called again with the same values, it creates nothing more and reports.

## Parameters

Pass exactly what the last check reported under `opening_invoices`, so the approval card shows it:
`session`, `company`, `invoice_type`, `rows` (the check's `ready`) and `total_amount`.

## The reply

- `status`: Completed, Partially Completed (some rows refused), Failed, or Importing.
- `invoice_type`, `doctype`, `invoices`: what was made and how many invoices are submitted.
- `totals`: per party type, `file` (the whole file's total, every invoice row, read from the file
  now), `imported` (the file's amount for the rows imported), `erpnext` (the total of the invoices
  made), `difference` (`erpnext` against `imported`), `not_imported` (`file` less `imported`: rows
  left out, refused or not imported yet) and `outstanding_now` (what is still owed today). Show this.
  A payment after go-live lowers only `outstanding_now`: it is not a difference.
- `differences`: each row whose invoice's total differs from the file (row, invoice, party, file and
  ERPNext amounts). At most 50 are listed; `differences_count` is the full number.
- `no_longer_submitted` (with `no_longer_submitted_count`): invoices made earlier that have since
  been cancelled or deleted. Tell the user.
- `failed`: rows ERPNext refused, grouped by its message, with their amount.
- `left_out`: rows the user left out, with the reason.
- `message`: a sentence to relay.
- `progress`: only while Importing.

## Large imports

More than 100 invoices run in a background job and the call returns Importing at once. Call again
with the same values to follow `progress`: nothing is created twice. If the background import
stopped (the reply says so, with the reason), what it made is in; check the file again with
`dry_run_import` to import the rest (rows already in show as already imported), then call this again
with that check's values.

## When it stops

- Rows ERPNext refuses are reported and the others still go in. Fix them (in the file, or with
  `dry_run_import`'s fixes), check again, then import again with the new check's values.
- If the sheet changed after the check, it refuses: check again first.

## Things to tell the user

- The totals, and that every invoice matches, or which rows differ.
- Credit notes, advances and foreign-currency parties aren't brought in here.
- Opening invoices post against the Temporary Opening account; the offsetting opening balances are
  posted separately.
