# How to Use plan_migration

Group the import sessions of one migration into a **migration plan**, ordered so every file comes
after the files whose records it links to. The plan is how a migration of several files is checked
together and imported after **one approval** (`run_migration_plan`), with no questions after it.

## When to use

- The user migrates several files (customers, items, prices, opening balances).
- Or the user wants to answer everything first and approve once.

For one file the user is happy to take step by step, the plain path (`start_import`) is fine.

## Inputs

| Input | Type | Required | Description |
|---|---|---|---|
| `sessions` | list of strings | Yes | The import session ids to add. Open every file's session first (`start_import_session`, once per file). |
| `plan` | string | No | An existing plan to add them to: it orders all its files again. Left out, a new plan is made. |
| `cut_off` | string | No | The cut-off date the user picked from `opening_setup`, `YYYY-MM-DD`. Pass it with `plan` (no new sessions) once they pick: the plan's check (`dry_run_import` with `plan`) then doesn't ask it again. |
| `leave_out` | list of strings | No | Session ids to take out of the plan (with `plan`, and `sessions` `[]`), once the user agrees. See "A file that can't be ready now". |
| `failure_rule` | `leave_out` or `stop` | No | What happens to rows that fail when their file comes up. `leave_out` (default) leaves them out with their reason; `stop` stops the plan before that file. The plan's check asks it if the user hasn't said. |

## Result

| Field | Description |
|---|---|
| `plan` | The plan id: the session id of its first file (`IMP-YYYY-NNNNN`), which keeps the plan. Pass this id, not another file's, to `dry_run_import` (as `plan`), `run_migration_plan` and `stop_migration_plan`. |
| `status` | `Planning` until every question is answered and every file is ready, then `Ready to Run`. |
| `files` | The files in import order: `session`, `file_name`, `doctype`, `position`, `reason` (which earlier files it needs) and the session's `status`. Show this to the user. |
| `problems` | Files that link to each other, so neither can go first. Import one with the linking columns left out, then the other. |
| `opening_setup` | For opening stock, invoices and balances: `company` (the site's only company) or `companies` with `suggested_company`; and `cut_off_choices` (dates from the file names, the last month end and the last fiscal year end, then `another_date`), or `cut_off` once the user picked it. |

## The company and the cut-off: once, at the start

When any file is opening stock, invoices or balances, ask now, before mapping, not file by file:

- **Company**: `company` given → use it, don't ask. `companies` → one single-choice card of them.
- **Cut-off**: one `ask_user` **single_select** card, its options `cut_off_choices` written as
  dates ("30 Sep 2026"), and "Another date". Never as text to type, never a year you guessed.
- Set every opening file up with that company and date (`set_opening_stock`,
  `set_opening_invoices`, `set_opening_balances`), and call `plan_migration` with `plan` and
  `cut_off`. Don't ask either again.

## A file that can't be ready now

The plan runs only when every file is ready. When one can't be made ready now (its opening setup
was refused, say: the company already has its opening entry), it holds the others back. Tell the
user which file and why, and ask whether to leave it out of the plan. On yes, call `plan_migration`
with `plan`, `sessions` `[]` and `leave_out` [its session], then check the plan again
(`dry_run_import` with `plan`). The file keeps its session: import it on its own once it can be,
or plan it again.

When the file left is the plan's first, the plan moves to the next file: use the reply's `plan`
from then on.

## Refusals

- A session already in another plan, or one already importing, imported or cancelled: nothing changes, `problems` says which.
- A plan that is running or finished: its files can't change.
- `leave_out` with every file of the plan (stop the plan instead, `stop_migration_plan`), or with a
  session that isn't in it.

## Next

Map every file (`get_import_schema`, `set_column_mapping`) yourself, then call `dry_run_import`
with the plan.
