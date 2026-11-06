# How to Use run_migration_plan

The **one approval** of a migration plan. It creates the records the plan planned, then imports
every file in order in the background. Nothing asks the user again.

## When to use

Only when `dry_run_import` with `plan` says `ready: true` (the plan is `Ready to Run`) and the user approves.

## Inputs

| Input | Type | Required | Description |
|---|---|---|---|
| `plan` | string | Yes | The plan id. |
| `files` | integer | Yes | How many files the plan imports. |
| `rows` | integer | Yes | Rows ready to import, all files together (the sum of each file's `ready`). |
| `masters` | integer | Yes | Missing records the plan creates first. |
| `cut_off` | string | Yes | The cut-off date of its opening files, `""` when it has none. |
| `decisions` | list of strings | Yes | Every decision of the plan, one line each: the records it creates, each fix ("Customer Group 'Retal' → 'Retail'"), rows left out, a file name whose date isn't the cut-off, and the failure rule. |

Pass the plan check's last `approval` (`dry_run_import` with `plan`) exactly. The approval card shows it, so the user reads
every decision and the cut-off date before anything is imported. If it isn't what the plan would
do now, nothing runs and the reply's `approval` is what to pass.

## What happens

1. The planned records (Customer Groups, Item Groups, UOMs...) are created and listed on the session that needed them.
2. Each file, in the plan's order, is checked again just before its import. A file whose parent rows failed in an earlier file, or whose records changed meanwhile, has rows that would fail now: with the failure rule `leave_out` they are left out with their reason; with `stop` the plan stops before that file.
3. The file is imported as `start_import` (or its opening import tool) would import it; a tree file a level at a time.
4. The next file starts when that one ends.

## Following it

Call `dry_run_import` with `plan` alone (no `answers`): while it runs or once it's done it only
reports `status` (`Running`, `Completed`, `Partially Completed`, `Stopped`, `Failed`) and each
file's `status`, `created` and `left_out`, and asks no approval.

Don't call `run_migration_plan` again to follow it. It would start nothing, but every call of it
puts a new Approve/Reject card in front of the user, which stays there as if the plan were
waiting on them.

When it ends, report what came in, and offer the sign-off report for the plan's sessions
(`get_skill("migration-sign-off")`, with `migration_plan` = the plan: its files only, so earlier
test runs of the same files stay out).

## Stopping

- `stop_migration_plan` stops it once the file importing now is done. What's imported stays.
