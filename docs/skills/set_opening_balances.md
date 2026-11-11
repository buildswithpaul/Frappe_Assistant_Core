# How to Use set_opening_balances

## Overview

Makes an import session's file the old system's closing trial balance, brought in as ONE opening
Journal Entry (voucher type Opening Entry, "Is Opening" Yes) dated the cut-off. It writes no
business data.

Accounts of type Receivable, Payable or Stock are not put in the entry: the opening invoices and
the opening stock imports bring those in. Stock accounts only when the company has perpetual
inventory on: without it, opening stock posts no ledger entry, so Stock rows go in this entry like
any other. They still count in the file's balance check. Because
they are left out, the entry has one balancing line to the company's Temporary Opening account
(the account of type Temporary) for their net. When opening invoices, opening stock and these
balances are all imported, Temporary Opening nets to zero, unless rows were left out: their net
amount is not brought in, so Temporary Opening stays off zero by that amount.

## Before calling

1. `start_import_session` with the file (`file_id`; upload it in File Manager first).
2. Ask the user (in a migration plan, the company and the cut-off come from `plan_migration`'s
   `opening_setup`, asked once there):
   - **which company**;
   - **the cut-off date** (the last day in the old system). Don't guess it. It must fall in a
     fiscal year of the company;
   - **what to do with Profit and Loss rows** (income and expense accounts), see below;
   - **which columns** hold the account and the amounts: either `debit` and `credit`, or one
     signed `balance` column.
3. The company needs a Temporary Opening account, and no submitted Period Closing Voucher.

## Parameters

| Parameter | Required | Description |
|---|---|---|
| `session` | Yes | The import session id |
| `company` | Yes | The company the balances belong to |
| `cut_off` | Yes | Cut-off date, `YYYY-MM-DD` |
| `columns` | Yes | File column header -> one of `account`, `debit`, `credit`, `balance` |
| `profit_and_loss` | No | `stop` (default) or `retained_earnings` |
| `retained_earnings_account` | With `retained_earnings` | An Equity account of the company that is not a group |

`account` is required, with `balance` or with `debit` and `credit`. `balance` is signed: positive is
a debit, negative (or in brackets) is a credit. When a row has a debit or credit cell, those are
used; the balance cell is read only when both are blank. A row can't have both a debit and a credit.

The account in the file can be the exact account name, the name without the company abbreviation,
the account number, or the account name when only one ledger account of the company has it.

## Profit and Loss rows

ERPNext doesn't accept Profit and Loss accounts in an opening entry.

- `stop` (default): those rows are one group in the check, "Profit and Loss account". Tell the user
  why, and either leave them out or run `set_opening_balances` again with `retained_earnings`.
- `retained_earnings`: the net of all Profit and Loss rows is added as one line on the
  `retained_earnings_account`.

Ask the user which one before calling; ask for the retained-earnings account by name.

## Refused at setup

- a submitted Period Closing Voucher in the company;
- an opening Journal Entry already on that company and date;
- a company without a Temporary Opening account, or a cut-off in no fiscal year;
- a session that already made its opening entry, for another company or date: start a new session;
- a session that brought in opening stock or invoices: start a new session for the balances;
- a user without Create or Submit permission on Journal Entry;
- a session whose status doesn't allow setting up again (for example Completed or Importing);
- two columns mapped to the same field, or any other wrong column (all are listed at once).

## Chart of accounts

If the old system's chart is not in ERPNext yet, bring the accounts in first. Replacing the chart
of accounts is possible only before any transaction, with ERPNext's Chart of Accounts Importer.
This tool does not do that, and ERPNext refuses it once any GL Entry exists. It also can't create
single accounts during the import: an account that is not found is mapped to an existing one or
left out.

## Next

`dry_run_import(session)`. Every wrong column is listed at once: correct them all in one call.
Then fix what it finds, and `import_opening_balances`.
