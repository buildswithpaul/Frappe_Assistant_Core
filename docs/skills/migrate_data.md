# Migrate Data

Use when the user wants to bring data from another system into ERPNext: "migrate my data", "import
my customers", "bring my data from Tally", "load my item master", "move our opening balances", or
attaches a spreadsheet and says to import it. Follow this workflow every time, however the request
is worded. Each tool has its own skill page with the details; this page is the order and the rules
that hold across them.

## Two ways through a migration

- **Several files, or the user wants to approve once**: make a **migration plan** (below). Every
  question is asked up front, in one list; then one approval, and the whole migration runs with no
  further questions.
- **One file, taken step by step**: the workflow after it, one file at a time.

When unsure, ask the user which they prefer. A plan is the better default for two files or more.

## A migration plan: ask everything once, then run

| # | Step | Tool | Done when |
|---|---|---|---|
| 1 | **Sessions**: open one per file | `start_import_session`, once per file | Every file has a `session_id` |
| 2 | **Plan**: group and order them | `plan_migration` with all the sessions | The user has seen the files in order, each with its reason; with opening files, the cut-off picked on one card from `opening_setup` |
| 3 | **Map** every file | `get_import_schema`, `set_column_mapping`. Opening files only with their own tool (`set_opening_stock`, `set_opening_invoices`, `set_opening_balances`), never `get_import_schema`: they need no Import permission. A column of an earlier file's old IDs in an opening file: `set_column_mapping` with only `old_id_columns` and `mapping` {} | Every file is mapped. Map yourself where you are sure; ask only where you aren't |
| 4 | **Questions**: all of them at once | `dry_run_import` with `plan` | Show every question together, grouped by file, the suggested answer first; send all the answers in one call. Repeat until ready is true |
| 5 | **Approve once** | `run_migration_plan` with the files, rows and masters it will do | The user approved |
| 6 | **Follow it** | `dry_run_import` with `plan` alone (it only reports, no approval card; never `run_migration_plan` again) | The plan is Completed, Partially Completed, Stopped or Failed |
| 7 | **Sign-off** | `get_skill("migration-sign-off")` with the plan's sessions | The user has the report |

What the plan does for you:

- **Order**: masters before the records that link to them, from the DocTypes' links; opening
  stock, invoices and balances last.
- **References between files**: a file's check counts the records earlier files of the plan will
  create, so an Items file isn't failed for Item Groups the Item Groups file brings. A link to a
  record a *later* file creates is reported as an order problem.
- **Missing masters**: the create fix plans them; the plan creates them when it runs, before any
  file, and each is listed on the session that needed it. Don't call `create_document` in a plan.
- **The failure rule**: asked once. When a file comes up, it is checked again; rows that would
  fail then (their parent row failed in an earlier file, say) are left out with their reason
  (leave_out), or the plan stops before that file (stop).

While the plan runs, don't ask the user anything about it. If they want to stop: `stop_migration_plan`
(what's imported stays).

## The workflow, one file at a time

Every file goes through the same steps, in this order. Never skip one, and never import before the
check says the file is ready.

| # | Step | Tool | Done when |
|---|---|---|---|
| 1 | **Session**: open one for the file | `start_import_session` | You have the `session_id`, sheet, columns and row count |
| 2 | **Mapping**: file columns to ERPNext fields | `get_import_schema`, then `set_column_mapping` | The user agreed the mapping table |
| 3 | **Cleaning**: value fixes the user picks (map a value, leave rows out) | `dry_run_import` once to find the groups, then again with `fixes` | Every group has a decision |
| 4 | **Dry run**: check every row, nothing written | `dry_run_import` | `status` is `Ready to Import` |
| 5 | **Fixes**: create the missing masters, then check again | `create_document` with `documents` and `import_session`, then `dry_run_import` | No group is left |
| 6 | **Import**: with one approval, only when the user asks | `start_import` | The session has left Importing |
| 7 | **Failed rows**: explain, try again, or give them as a file | `dry_run_import`, then `start_import`; or `dry_run_import` with `failed_rows_file` | Every row is imported or left out with a reason |
| 8 | **Report**: what the migration brought in | `get_skill("migration-sign-off")` | The user has the report and its PDF |

**Step 1 is one `start_import_session` call per file**, for a spreadsheet or a Tally XML file. It
recognises exports from Tally, Zoho Books, Busy, Marg and QuickBooks, cleans them (title rows,
totals, `8,45,000 Dr` amounts) and opens the sessions with the mapping already made (`matched:
true`), so step 2 is only checking that mapping with the user. Any other file opens one session
the normal way, in the same call.

Steps 3 to 5 repeat until nothing fails: explain each group in its own words, offer only its
`fixes`, apply the user's choices in one call, and give the new count.

**Opening balances use their own setup tool in step 2** instead of `set_column_mapping`. They also
have their own import tool in step 6 instead of `start_import`:

| File | Step 2 | Step 6 |
|---|---|---|
| Stock on hand at the cut-off | `set_opening_stock` | `import_opening_stock` |
| Unpaid customer invoices / supplier bills | `set_opening_invoices` | `import_opening_invoices` |
| Closing trial balance | `set_opening_balances` | `import_opening_balances` |

Ask for the **company** and the **cut-off date** (the last day in the old system) once, and use the
same date for all three. Never guess either of them. In a migration plan, `plan_migration`'s
`opening_setup` gives them: the site's only company is used without asking, and the cut-off is
one single-choice card of its `cut_off_choices`.

## The order across files

Records must exist before the records that link to them. In a migration plan, `plan_migration`
orders the files this way for you. Without one, show this order as the plan, and work through it
one file at a time:

1. **Chart of accounts.** The accounts must be right before any transaction is posted. Replacing
   the chart is possible only on a company with no transactions yet, with ERPNext's **Chart of
   Accounts Importer** in Desk. No import tool does that. Adding missing accounts to an existing
   chart is a normal import of `Account`.
2. **Setup masters**: Payment Terms, Customer Groups, Supplier Groups, Item Groups, Territories,
   Warehouses, UOMs, Price Lists.
3. **Parties and items**: Customers, Suppliers, Items.
4. **What links to them**: Item Prices, Addresses, Contacts.
5. **Opening stock** (needs items and warehouses).
6. **Opening receivables and payables** (needs customers and suppliers).
7. **Opening trial balance** (needs the accounts). Steps 5 to 7 can come in any order among
   themselves: Temporary Opening holds the difference until all three are in.
8. **The sign-off report.**

If a file needs records from a later file (for example, Customers whose group is in the Customer
Group file), import the other file first. Use step 5 only for a few missing masters the file
doesn't bring itself.

## When an import tool fails

When an import tool fails or isn't available, tell the user it failed and what the error was, in
the tool's own words. Then stop. This holds for every one of them: `start_import_session`,
`get_import_schema`, `set_column_mapping`, `dry_run_import`, `start_import`,
the plan tools (`plan_migration`, `run_migration_plan`) and the opening tools
(`set_opening_stock`, `set_opening_invoices`, `set_opening_balances`, `import_opening_stock`,
`import_opening_invoices`, `import_opening_balances`).

Never import the file's records another way: not with `create_document` or `update_document`, not
one record at a time, and not as a `documents` list. That way skips the check and the muted emails,
and it changes values the user never chose. The user decides what comes next: try again,
correct the file, or ask their administrator. The one exception is step 5: the missing masters the
check listed, created with `create_document`, `documents` and `import_session`.

## Keep the migration in this conversation

Never hand a migration, or any step of it, to a helper task (delegating it), in Auto mode too:
the helpers don't have the import tools, and the user's answers and approvals belong here. Run every
import tool yourself, in this conversation, one step after another.

## What goes wrong without this skill

- **Steps out of order.** Importing before the dry run, or starting a new session for failed rows.
  A new session imports the done rows again. Retry failed rows, continue an interrupted import, or
  bring in a corrected file, always in the **same session**.
- **Opening stock through Stock Entry or Data Import.** Opening stock is always a **Stock
  Reconciliation with purpose Opening Stock**, made by `set_opening_stock` and
  `import_opening_stock`. A Stock Entry posts it to an expense account and the books are wrong.
- **Transactions before the chart of accounts.** Once any GL Entry exists, the chart can't be
  replaced. Check the accounts before opening invoices, stock or balances.
- **Sending emails.** The dry run and `start_import` run with emails muted, so imported records
  send no welcome mails or notifications. Never create a file's records one by one with
  `create_document` or `update_document` instead: emails are not muted there, and a migration of
  500 customers must not email 500 customers.
- **Reading the whole file.** Never read a migration file in full, page through its rows, or paste
  rows into the chat or a tool call. Not with `extract_file_content`, `run_python_code` or
  `get_document` either. The import tools read the file on the site and give you a summary:
  columns, row count, up to 10 sample rows, and grouped failures with row numbers. Work from those.
- **Dropping a column.** A column goes to "Don't Import" only when the user says so. A column you
  can't place is a question for the user, with the field you think fits (State → Territory).
- **Guessing.** Never invent a value, a mapping or a name. When you aren't sure what a column
  means, ask with a choice card (`ask_user`). A fix maps only to a name the tool listed in
  `closest`, or one the user gave. A value from the user's file is never replaced by a different
  value (for example "Retail" with "Commercial") unless the user chose that in a fix group. Close
  matches are offered, never applied unasked. When a group's map fix has `likely`, recommend it;
  never offer to create the misspelt value without saying it looks like a misspelling.
- **Explaining only in your thinking.** The user doesn't see it. What the files hold, the plan, the
  questions and what you suggest go in your message's text, before any card that asks about them.
- **Adding up numbers yourself.** Row counts, totals and differences come from the tools. Quote
  them as they are.

## Files the tools can take

`.csv`, `.xlsx` or `.xls`, with a row of column headings (a title row above them is fine) and
**one kind of record per file**. A
workbook with several sheets is one session per sheet.

- **A Google Sheets link**: pass it to `start_import_session` as `google_sheets_url`; one tab per
  session. When the user fixes the sheet, pass the link to `dry_run_import` again.
- **A `.zip`**: ask the user to unzip it and attach the files.
- **A Tally XML export** (`.xml`): `start_import_session` reads it and opens a session per target
  (Customers, Suppliers, Accounts from a ledger list).
- **A file larger than Max Rows per Import**: refused with the limit. Ask the user to split it.

## When the user asks to undo an import

An import is not undone. The user checked it and approved it on the approval card, and it ran as
their import. When they ask to take one back ("undo that import", "that was the wrong file"), say
that FAC doesn't undo imports, and never delete the imported records yourself: not by creation
time, owner or a name pattern, and not one by one with `delete_document`. To correct records,
update them from a corrected file (see the next section); to remove some, the user deletes them
in Desk.

## Updating records that already exist

When the user wants to change records already in ERPNext from a file ("update my customers' credit
days", "fix the item groups"), it is the same workflow with the session started as **Update
Existing Records**. In step 2, `set_column_mapping` also takes the field(s) that find each row's
record (its match key, for example the Tax ID). The dry run then shows what will change: show those
samples (record, field, old value, new value) and the counts before asking to import. Never update
records one by one with `update_document` instead.

## Off-topic questions during a migration

The user may ask something unrelated in the middle of a migration ("what were our sales last
month?"). Answer it fully, as you would any question. Then offer to carry on, saying where the
migration stands, for example: "Shall we carry on with the customer file? The check found 3 groups
still to decide." Don't refuse the question, and don't drop the migration.

The session keeps every step, so a migration can also continue in a later chat. To find where it
stands, read the user's sessions with `list_documents` on `FAC Import Session` (its `status`), and
open one with `get_document`. Carry on from its status. Never start the file again. A file in a
migration plan names it in `migration_plan`: the plan's id, the session of its first file, whose
`plan_settings` hold the plan's status. `dry_run_import` with `plan` carries on from there: while
it's Planning it lists the open questions, and once it runs or has ended it reports how far it got.

## Talking to the user

- Plain business words: "412 customers use a group that doesn't exist", not the ERPNext error.
- One decision at a time, grouped, never row by row. In a migration plan, all the decisions come
  together, still grouped: one list, so the user answers once.
- Say what each step will do before an approval card, and what it did afterwards, with the counts.
- After each file, say what's next in the order above.

## When the file has the old system's IDs

If a file carries the old system's own ID for each row (an Odoo id, a Zoho Customer ID, a Tally
ledger's name), mark it when you map (`set_column_mapping`, with source_key_column and
source_system; a preset does it itself). The IDs are kept in FAC's key map without asking. Later
files that refer to the records by those IDs can then be translated instead of corrected by hand.
