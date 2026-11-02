# Start Import

## Overview

The `start_import` tool imports an import session's file into ERPNext through **Frappe's own Data Import**, after **one approval**. It is the last step of a migration: only for a file `dry_run_import` said is ready, and only when the user asks to import.

What goes in is exactly what was checked: the session's sheet, with the value maps applied and the rows left out skipped. The import shows in Desk under **Data Import** with its file and log, like any import made by hand. Emails are muted while it runs.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session` | string | **Yes** | The import session id |
| `doctype` | string | **Yes** | The DocType imported, as the last check said |
| `rows` | integer | **Yes** | Rows to import: the last check's `ready` |
| `import_type` | string | **Yes** | `Insert New Records` or `Update Existing Records`, as the last check said |
| `validated_fingerprint` | string | **Yes** | The last check's `validated_fingerprint`, from `dry_run_import`'s reply: 12 characters, copied as given (the session's whole `validated_fingerprint` works too) |
| `file_name` | string | **Yes** | The session's `file_name`: the file imported |
| `submit_after_import` | boolean | **Yes** | The session's `submit_after_import`: whether the records are submitted |

For an update, `rows` is the check's `ready` (records that change). The update changes exactly the records the check matched, never a new match, and the result says "Updated N … records". Rows that change nothing were skipped at the check.

The approval card shows `doctype`, `rows`, `import_type`, `validated_fingerprint`, `file_name` and `submit_after_import`, so the user sees what goes in. They must match the last check and the session, or nothing is imported. The fingerprint names the check the user saw: if the file was mapped or checked again since (in another tab, say), the import is refused. Show the user the new check's result and ask again.

## Workflow

1. **Say what will happen:** "Import 250 Customer rows as new records? 2 rows are left out." Then call the tool; the user approves the card.
2. **Follow it.** The reply has `data_import` and `state`:
   - `started` (or `continued`): running in the background. **Don't poll it.** In FAC Chat the progress shows by itself, live, under your message and on the side panel's Import card (rows done of the total, created, failed), with no call of yours. Say once that it is running and that you'll report when it ends or when asked: "Importing 250 Customer rows; the progress shows below." When the user asks how far it is, read it once: `list_documents` on **Data Import Log** with filters `{"data_import": "<name>", "success": 1}` gives in its `total_count` how many are in, out of the reply's `total`.
   - `finished`: done (on sites that import at once, the reply is the result).
3. **Report the end** once the session has left **Importing**: read it with `get_document` (doctype `FAC Import Session`). The Data Import's own `status` is no guide: it says *Partial Success* from the first record on. The session's `status` is Completed, Partially Completed or Failed, and its last step's message has the counts, for example:

   "Imported 245 Customer records into ERPNext. 3 failed (rows 17, 40, 88: Email is invalid). 2 rows left out (Closed shop: rows 5-6). Data Import DI-0042."

   Tell the user that, with the link `/app/data-import/<name>`. A partial success is normal: each record is saved on its own, and only the failed ones are not.

4. **If rows failed**, explain each group of `failed_rows` with its `explanation` (one line per reason, never every row; at most 30 causes are listed, and `failed_groups_not_shown` says how many more the failed-rows file holds), then offer what `next` says: fix the cause and try those rows again, or download them as a file. See **When rows failed**.

## Response

```json
{
  "success": true,
  "session": "IMP-2026-00012",
  "state": "finished",
  "data_import": "DI-0042",
  "desk_url": "/app/data-import/DI-0042",
  "total": 250,
  "created": 245,
  "failed": 3,
  "skipped": 2,
  "failed_rows": [
    {
      "reason": "Email is invalid",
      "error": "InvalidEmailAddressError",
      "count": 3,
      "rows": [17, 40, 88],
      "explanation": "3 rows rejected by ERPNext: Email is invalid"
    }
  ],
  "left_out": [{"reason": "Closed shop", "count": 2, "rows": "5-6"}],
  "next": "Explain each reason and fix what can be fixed in chat ...",
  "message": "Imported 245 Customer records into ERPNext. 3 failed (...). 2 rows left out (...). Data Import DI-0042."
}
```

When the session has more than one Data Import (rows tried again, or a corrected file), the reply also has `runs` (each Data Import with its `created` and `failed`) and `created_in_all`, and `message` ends "In all, 248 records imported over 2 Data Imports."

Row numbers are the user's own spreadsheet rows (row 1 is the header; when the headings were below a title row, rows count from the heading row).

## When it stops

If the import was interrupted (the Data Import's status is **Timed Out**, or its count stops moving for minutes after a restart), the session stays **Importing**. When the user asks to continue, call `start_import` again **with the same values**. The same Data Import runs again and skips every record already imported, so nothing is duplicated. `state` is `continued` (or `running` if it was in fact still running: then just keep following it; or `finished` if it had ended, with its result).

If ERPNext now refuses some rows (`state` `refused`, a record they link to deleted since the check, say), the message says which. Nothing more is imported until that is fixed; then continue.

## When rows failed

A session that is **Partially Completed** or **Failed** isn't imported again as it is. When the user has fixed the causes and asks to try those rows again:

1. Call `dry_run_import`: it checks **only the rows not imported yet** (`imported` counts the rest).
2. Call `start_import` with that check's `ready`. A **new Data Import** gets just those rows, with every fix made since, and the session's report covers every run. The records already in are never touched.

Rows that can't be fixed in chat go to the user as a file (`dry_run_import` with `failed_rows_file`), and their corrected file comes back through `dry_run_import` as `file_id` (or `file_url`), checked before it is imported.

## When it can't start

- **Not checked, or changed since the check:** call `dry_run_import` first. Only a file that passed is imported.
- **ERPNext would now refuse some rows** (a record they link to was deleted since the check, say): check the file again.
- **The values passed don't match the last check:** pass the check's own.
- **The user can't use Data Import** (System Managers only, unless given the permission), or can't import that DocType: say so and stop.
- **The scheduler is off:** imports run in the background, so a System Manager must turn it on.
- **Developer mode:** on a site in developer mode (and under tests) the import runs inside the call, as
  Frappe's Data Import does there: the reply comes when the import has ended, and a large file can hit
  the request timeout. Use a small file there, or a site out of developer mode.
- **Rows failed and weren't checked again:** call `dry_run_import` first (see **When rows failed**).
- **Already imported:** every row of the file is imported (or left out); its Data Imports are named in the error.

## Anti-patterns

- Calling `create_document` per row instead of importing.
- Importing without the user asking, or before the dry run said the file is ready.
- Starting a new session to finish an interrupted import, or to try failed rows again: that would import the done rows again. Continue it, or check and import what is left, in the same session.
- Re-importing the whole file after a partial success.

## In a migration plan

When the session is in a migration plan (its `migration_plan` is set), don't ask the user here:
`dry_run_import` with `plan` gathers every question of the plan into one list. Don't call `start_import` for it: `run_migration_plan` imports every file of the plan. While the plan is open or running, `start_import` (and the opening import tools) refuse its files.
