# How to Use import_opening_balances

## Overview

Creates and submits the checked opening Journal Entry (voucher type Opening Entry, dated the
cut-off) after the user approves: all or nothing. Use it only after `dry_run_import` said the sheet
is ready, and only when the user asks to import. Called again with the same values, it creates
nothing more and reports. Entries of more than 100 lines are still submitted in the same request.

## Parameters

Pass exactly what the last check reported, so the approval card shows it: `session`, `company`,
`cut_off`, `rows` (the check's `ready`), `total_debit` and `total_credit`, and what the entry does
with them: `balancing_amount` (the Temporary Opening line, positive a debit, negative a credit),
`covered_debit` and `covered_credit` (rows another opening import brings in), `excluded_debit` and
`excluded_credit` (rows left out), all from the check's `opening_balances`. A 0 may be left out. If
any differs from the last check, it refuses. Show the user the balancing line before they approve.

## What goes in the entry

- Each ready row that is not covered (below) becomes a line as the file has it. A row
  with a zero amount produces no line.
- Receivable, Payable and Stock rows ("covered") are left out of the entry: the opening invoices
  and opening stock imports bring those in, and posting them here as well would count them twice.
  Stock rows are covered only when the company has perpetual inventory on; without it, opening
  stock posts no ledger entry, so they are lines of this entry.
- One balancing line to the Temporary Opening account carries the net of the left-out rows. It
  exists only when the other lines don't net to zero.
- With `profit_and_loss = "retained_earnings"`, the Profit and Loss accounts are folded into one
  line on the retained-earnings account. They are not compared one by one in the report: `folded`
  lists them with the file's net, and the message says how many were folded.

## Order with opening stock and opening invoices

Any order. Temporary Opening holds the balance until all three are in, and nets to zero when they
are, unless rows were left out: their net amount is not brought in, so Temporary Opening does not
net to zero by that amount, and the report's message says so. If everything is in and it still
isn't zero, the report says how much is unaccounted for.

## The reply

- `status`: Completed, Failed, or Importing.
- `journal_entry`: the entry made. `lines`: its line count. `balancing`: the Temporary Opening line
  (account, debit, credit), if any.
- `accounts`: each account whose ERPNext balance at the cut-off differs from the file (account,
  `file_net`, `erpnext_net`, `difference`), at most 50; `differences_count` is the full number.
- `covered`: the Receivable, Payable and Stock accounts, with the file's net, ERPNext's net and
  `source` (the opening invoices or opening stock imports). Differences here are normal until those
  are imported.
- `temporary_opening`: the account and its balance. Say whether it is expected to be non-zero yet.
- `folded`: the Profit and Loss accounts folded into the retained-earnings line, each with the
  file's net (empty unless `retained_earnings` was chosen).
- `not_brought_in`: rows the user left out, with the reason, count and the file's debit and credit.
- `totals`: `file_debit`, `file_credit`, `erpnext_debit`, `erpnext_credit` over the accounts
  compared (not the covered ones or Temporary Opening).
- `message`: a sentence to relay.

## When it stops

- A file whose debits and credits don't balance never reaches "Ready to Import", so there is
  nothing to import: correct the file and check again.
- A Period Closing Voucher, or an existing opening entry at that date: it refuses and nothing is
  created.
- After a failed import, calling it again refuses: check the sheet again with `dry_run_import`,
  then import. A completed session just reports.
- If ERPNext refuses the entry, nothing is left, the session shows Failed, and the reason is in
  the reply.
- If the sheet changed after the check, it refuses: check again first.
- A session that already made its entry never makes a second one.

## Things to tell the user

- That the entry matches the file account by account (folded Profit and Loss accounts excepted),
  or which accounts differ.
- That the covered rows (Receivable and Payable, and Stock with perpetual inventory on) are not in it
  and why, and the Temporary Opening balance.
- The rows left out and their amounts.
- Foreign-currency accounts aren't brought in here.
- Replacing the chart of accounts is possible only before any transaction, with ERPNext's Chart of
  Accounts Importer; this tool doesn't do it.
