# Design: Guided data migration, core flow (#33988 to #33994), v2

Feature #33986 "FAC Chat: Guided data migration into ERPNext", v3.1.0
Author: Rachana · 5 October 2026 · Status: draft for approval

## 1. Overview

A user attaches an Excel or CSV export from their old system, and FACO guides them over several messages: pick the record type, map the columns, check every row without saving, fix the problems, create missing masters, import, and retry what failed. The plan reuses what Frappe and FAC already have. Frappe's Data Import does every real save, and FAC's existing upload, file reader, approvals and audit log stay as they are. We build only three things neither has: a **dry run**, a small **session record** that remembers the user's decisions, and **six tools** that connect the steps. The same tools work from FAC Chat, Claude and ChatGPT.

**What the plan guarantees.** Every row ends in exactly one state: imported, failed with a reason, or left out by the user. Nothing goes into ERPNext without one clear approval, and every import can be seen in Desk and undone.

## 2. What changed since the first draft

| First draft | This version | Why |
|---|---|---|
| 14 tools | 6 tools | Several steps merge into one tool, and existing tools cover the rest. |
| 3 new doctypes, with a copy of the file and a sheet cache | 1 doctype plus 1 child table, linking to the existing File and Data Imports | Store only what exists nowhere else. |
| An in-chat cleaning engine (dates, trimming, number formats) | Only three fixes in chat: map a value, leave rows out, create a missing master | Bigger corrections belong in the file, which the user fixes and uploads again. Data Import already trims values and reads dates and yes/no. |
| A separate bulk-create tool for masters | Masters go through Data Import too | One approval style, one log and one undo path for everything. |
| A separate file to download failed rows | Data Import's own "Export Errored Rows" and import log, linked from chat | These already exist in Desk (question 8). |
| 39 days | 26.5 days | |

## 3. Shared design (decided once)

### 3.1 What we reuse, and what for

| Already exists | Where | Used for |
|---|---|---|
| Uploaded file saved on the chat message | FAC Chat Message, `chat/api/chat/helpers.py` | The source file; no copy is made |
| Sheets, headers, row counts, 10 sample rows | `extract_file_content` | What the model sees of the file |
| Upload type and content checks | #33987, `chat/api/settings/uploads.py` | Accepting xlsx, xls and csv |
| File parser and column matching | Data Import's `ImportFile`, `build_fields_dict_for_column_matching` | The dry run and the real import read the file the same way |
| Import-permission and blocked-doctype checks | `DataImport.validate_doctype` | The permission check before any work |
| Background import, progress, log per row, resume without duplicates, retry of failed rows | Data Import, Data Import Log | Every real write |
| Errored rows and import log downloads | Data Import buttons in Desk | The failed-rows file the user fixes in Excel |
| Closest-match search for a missing value | The link search behind `search_documents` | Suggestions such as "Retail" → "Retail Customers" |
| Approval cards, choice cards, audit log | FAC approvals, `ask_user`, Assistant Audit Log | One approval per batch; who did what |
| Wrapping file content as untrusted | `wrap_untrusted` | Every tool result that contains cell values |

### 3.2 The FAC Import Session doctype

This is the only new record, needed because nothing in Frappe or FAC keeps a migration's decisions:
- the model forgets everything between turns;
- Claude and ChatGPT create no FAC chat messages;
- chat messages are deleted after retention and aren't saved at all for privacy-restricted users;
- a Data Import needs its target doctype on creation, and has no place for fixes or check results.

Module Assistant Core, named `IMP-{YYYY}-{#####}`, change tracking on. Only the tools change it; in Desk it is read-only.

| Field | Type | Why |
|---|---|---|
| status | Select | The current step (3.7). |
| user | Link: User | The owner. Permission rules use it, as on FAC Chat Message. |
| chat_session_id | Data, indexed | The FAC Chat conversation, so FACO finds the session without an id. Empty for Claude and ChatGPT. |
| parent_session | Link: FAC Import Session | Groups several files for the migration order (#33995). Empty for now. |
| source_file | Link: File | The existing uploaded File. Not copied. |
| sheet | Data | The chosen sheet (empty for CSV). |
| headers | JSON | The chosen sheet's column names, so a mapping can be checked without re-reading the file. |
| target_doctype | Link: DocType | What the rows become. |
| import_type | Select: Insert New Records / Update Existing Records | Same values as Data Import. |
| mapping | JSON | The column map in Data Import's own `template_options.column_to_field_map` shape, so it copies straight across. |
| fixes | JSON | The user's three kinds of fix: value maps, left-out rows with reasons, and masters to create with their parent. |
| prepared_file | Attach (private) | The chosen sheet as one CSV, with the fixes applied and the left-out rows removed. The dry run and the import both use this same file, so what was checked is exactly what gets imported. |
| check_summary | JSON | The last dry run as groups and counts. This is what the model sees. |
| check_results | Attach (private) | The result for every row, so a re-check runs only the rows that failed. |
| checked_hash | Data | A fingerprint of the mapping and fixes the last check used. If they change, the import is blocked until a new check runs. |
| progress | JSON | The running job's phase, current row, total and job id. |
| runs | Table | Each Data Import created: name, purpose (Masters / Data / Retry), doctype. Undo (#34002) reads the created records from their logs. |

### 3.3 What the server does and what the model sees

| The server | The model |
|---|---|
| Reads every row, runs the dry run, applies the fixes, writes the prepared file, starts Data Import | Headers, up to 10 sample rows, the importable fields |
| Groups failures by cause, field and value | Each group's cause, count and up to 3 example rows |
| Ranks closest matches from existing ERPNext names | Up to 5 matches per group to choose from; it never makes up names |
| Checks every fieldname and value the model sends | A clear error it can act on, such as "`customer_grp` is not a field of Customer; did you mean `customer_group`?" |

Cell values in tool results are wrapped with `wrap_untrusted`. Tools don't do this today, so these are the first.

### 3.4 Permission checks

A single helper, `check_import_access`, runs before any work and reuses Frappe's own checks. On failure it raises a PermissionError with a plain message, which BaseTool already logs as "Permission Denied".

| Check | How (reused) | When |
|---|---|---|
| The user can read the file | Frappe's File permission | At start |
| The user can create a Data Import | Frappe permission on Data Import | At start |
| The target can be imported: not blocked, Allow Import on, user has import permission | `DataImport.validate_doctype` on an unsaved Data Import | As soon as the target is known |
| The user can create (Insert) or write (Update) the target, and create each master | Frappe permissions | When the target is known, and for masters |
| The row count is within the limit (#34003, default 50,000) | A new setting on Assistant Core Settings | At start |
| The user owns the session (System Manager sees all) | Permission query and has_permission hook, as for FAC Chat Message | Every tool |

Data Import is System Manager only by default, so without a change only System Managers can migrate (question 2).

### 3.5 Background jobs and progress

- **What runs in the background:** a dry run or re-check over 500 rows (`frappe.enqueue`, `long` queue, job id `fac_import::<session>::check`), and the import itself (Data Import's own job). Up to 500 rows runs inside the tool call.
- **How progress is recorded:** the dry run never commits, so it writes progress to the Redis cache and saves its result to the session only when it ends. Import progress comes from Data Import's `get_import_status`.
- **How progress reaches the user:** FAC can't post into a chat from a background job. FACO reports progress when the user asks, by calling `get_import_session`. A live progress bar is possible later (question 5).

### 3.6 Where the tools live

The tools go in a new **`data_migration`** plugin, so admins can turn migration on or off on its own. `data_science` also holds `run_python_code` and `run_database_query`, which admins often turn off, and migration would go with them.
- **Turning it on:** on sites that still carry the old enabled-plugins list, a new plugin starts off (`utils/migration_hooks.py:864`), so a small v3.1 patch turns it on.
- **Approval types:** each tool goes on the read-only or write list in `utils/tool_category_detector.py`. That's what FAC Chat, Claude and ChatGPT use to decide when to ask for approval.

### 3.7 Status flow

**Draft** (file read) → **Mapped** (target and mapping saved) → **Checked** (dry run done, failures remain) or **Ready** (nothing blocking) → **Importing** → **Completed**, **Partially Imported** or **Failed** → **Undone** (#34002). **Cancelled** is available any time before Importing.

- Changing the mapping sends the session back to Mapped.
- A fix re-checks the affected rows straight away, so the session stays Checked or becomes Ready.
- A running job shows in `progress`, not as a status.
- A retry goes from Partially Imported back to Importing.

## 4. Per ticket

### #33988 Start an import session for an uploaded file

**What the user sees.** They say "import this". FACO shows the sheets, columns and row counts, and asks which sheet and what it holds. Days later, in the same chat, FACO carries on from the same step.

**Reuse.**
- The file on FAC Chat Message.
- `extract_file_content`'s per-sheet columns, row count and samples.
- Frappe's permission checks, through the helper in 3.4.
- Data Import in Desk for each run, plus the session record itself, covers criterion 3.

**Build.**
- The doctype and its child table.
- The permission helper.
- Two tools.
- The file URL in the attachment summary. FACO gets only the file's name today (`chat/api/chat/helpers.py:161-165`).
- **A fast header read for big spreadsheets.** It reads only the headers, the first 10 rows and the row count, using openpyxl in read-only mode, instead of loading every row with pandas. This keeps chat and the tool fast for any file size, the 9 MB / 200k-row file included, which took about 32 s before.

**Tools.**
- `start_import_session(file_url=None, sheet=None, doctype=None, import_type="Insert New Records")`
  - Without `file_url`, it takes the latest spreadsheet attached to this chat. Claude and ChatGPT pass the URL of a file already in Frappe.
  - Starting again for the same file and chat returns the same session.
  - Returns the session id, status and sheets (headers, row counts, samples). Write (it changes only the session).
- `get_import_session(session=None)`
  - Returns the step, mapping, fixes, check summary and progress.
  - With no id, it returns this chat's open session. If there is none, or more than one, it lists the user's open sessions.
  - Read-only.

**Risks.**
- **Only one sheet at a time.** Data Import reads only the first sheet of a workbook. The prepared file (3.2) solves this by writing the chosen sheet out as its own CSV.
- **No chat id from Claude or ChatGPT.** There, FACO uses the session id or the list of open sessions.

### #33989 Suggest the target DocType and column mapping

**What the user sees.** "These look like **Customers**: there are name, group, territory and GSTIN columns." Then a table of *your column → ERPNext field*, with unmapped columns and required fields that have no source marked. A choice card appears when FACO isn't sure.

**Reuse.**
- Data Import's own field matching, which already knows which fields can be imported, including child-table fields and "Label (Table)" headers.
- `ask_user` for choice cards.

**Build.**
- **`get_import_schema`.** It returns a short list of the importable fields, built by Data Import's own function. We don't use `get_doctype_info`: it returns about 157,000 characters for Delivery Note, and a live test missed `po_no` because of the cut-off.
- **The mapping part of `update_import_session`.** It checks every fieldname against that list, then saves the mapping and returns what's still missing.

**Tools.**
- `get_import_schema(doctype)`. Returns for each field: fieldname, label, type, whether it's required, and its options or link target. Also returns the child tables and the doctypes this one links to (used by #33995). Read-only.
- `update_import_session(session, mapping=None, doctype=None, import_type=None, fixes=None)`
  - `mapping` is a list of {column, field}.
  - Rejects unknown fields, two columns on one field, and child fields for the wrong table, each with the closest fieldname.
  - Returns the stored mapping, the unmapped columns and the required fields with no source.
  - Write (session only).

**Risks.**
- **Header understanding depends on the samples.** When FACO isn't confident it must ask with a choice card. That's a rule for the skill (#34004).

### #33990 Check every row before import (dry run)

The title says "clean and reshape", but the description and every criterion describe the dry run. Cleaning is limited to the three fixes in #33991 (question 1).

**What the user sees.** "4,812 rows ready, 188 would fail", with the failures in groups, each with a count and up to 3 example rows. Duplicates have their own group. Over 500 rows, it runs in the background.

**Why we build it.** Frappe's preview checks only three things: an option outside the list, a link that doesn't exist, and a date it can't read. Required fields, duplicates and controller rules (for example India Compliance's GSTIN and GST category checks) fail only during the real import. That gap is what this feature exists to close.

**Reuse.**
- Data Import's `ImportFile` reads the prepared file and builds each document exactly as the import will. Its warnings already cover options, links and dates across the whole file.
- `doc.insert()` runs every ERPNext rule.
- Data Import's own flags (`in_import` on, emails muted) make validation behave exactly like a real import.

**Build: the check loop.**
- **Per row:** insert the row, record the result, then fully roll back. A full rollback, rather than the savepoint in the ticket, releases database locks after every row, so other users aren't blocked. It also clears Frappe's queue of things waiting to run after a save (webhooks, background jobs).
- **A guard:** while the check runs, a save the record tries to make on its own makes that row fail ("can't be tested safely") instead of saving. ERPNext's Call Log hook does this, reached through Customer and Supplier contacts. Jobs queued straight away are dropped, and global search indexing is off.
- **Doctypes skipped with a warning:** Company, User, DocType, Custom Field, Property Setter, Customize Form, Accounting Dimension, File, Location, the doctypes Data Import blocks, and submittable doctypes when "submit after import" is on. Each of these saves on its own, changes the database structure, sends mail or writes files.
- **Duplicates:** inside the file, by the naming field or unique fields, checked separately because each row is rolled back on its own. Against ERPNext, by the same fields or from the insert's duplicate error.
- **Rows that depend on earlier rows** in the same file, such as a parent group, count as present, as they would in a real import.
- **Re-check:** only the rows that failed, or that a fix touched, run again.

**Tool.**
- `check_import(session, only_failed=False)`. Returns the counts and groups, each group with up to 3 examples and its closest matches. For files over 500 rows it returns a job id. Read-only: nothing is saved in ERPNext.

**Risks.**
- **Speed.** 20-100 ms per row, so 50,000 rows take 15-80 minutes in the background.
- **Custom apps.** A site's own app might call an outside service on save. The guard can't stop that (question 7).
- **Small leftovers.** Error Log rows, some cache entries and gaps in autoincrement names survive the rollback. None of these is business data.

### #33991 Explain errors in plain language and fix them together

**What the user sees.** "**43 rows**: Customer Group *Retail* doesn't exist. Closest: *Retail Customers*, *Retail*. Map to one, create it, or leave these rows out?" After each choice: "Fixed. 145 rows still need attention."

**Reuse.**
- The existing link search for closest matches.
- `ask_user` for the choice.
- Anything bigger than these three fixes goes back to the file. FACO tells the user what to change in Excel, and they upload it again.

**Build.**
- **Grouping** by cause, field and value. The causes:
  - missing required value;
  - link not found;
  - invalid option;
  - bad date or number;
  - duplicate in the file;
  - duplicate in ERPNext;
  - other rule (the controller's message);
  - can't be tested safely.
- **The fixes part of `update_import_session`.** Each fix becomes a value map, a left-out row with a reason, or a master to create. The prepared file is rebuilt, the affected rows are re-checked straight away, and the new counts come back.
- **Ready.** When no groups are left, the session becomes Ready and FACO gives the final count, with the left-out rows listed.

**Tools.** `update_import_session` (fixes) and `check_import`, both described above.

**Risks.**
- **Error messages are free text.** "Other rule" groups by message after names and numbers are removed, so one cause can sometimes show as several groups.

### #33992 Create missing masters in one approved batch

**What the user sees.** One plan table (for example 6 Customer Groups, 3 Territories, 12 UOMs), with the parent shown for tree masters and changeable. One approval, then a change log.

**Reuse.**
- **Data Import does the creating.** For each master doctype, the engine writes a small file, ordered so parents come before children, and imports it. The masters then have a log in Desk and are undone the same way as the main import.
- **The setup-change-protocol's plan table and change log.** The approval card is the one confirmation; there is no separate confirm step.

**Build.** The `masters` mode of `run_import`.

**Tool.**
- `run_import(session, what="masters")`. One call means one approval card. Returns each master Data Import and its counts. Write.

**Risks.**
- **Masters that need more than a name and parent.** FACO asks for the missing values before planning them.
- **Masters can partly fail too.** That is reported, and the main import waits until the masters it needs exist.

### #33993 Import through Frappe's Data Import with one approval

**What the user sees.** One approval card: *Customer · 4,812 rows · new records*. Progress when they ask. At the end: "4,790 created, 22 failed, 5 left out", and the import is under Data Import in Desk with its file and log.

**Reuse.** All of Data Import:
- the background job and progress;
- `mute_emails`;
- the log for every row;
- partial success;
- resuming without duplicates, because a re-run skips rows already in the log.

**Build.** The `data` mode of `run_import`:
- **It only runs when** the session is Ready and the fingerprint matches the last check.
- **The card repeats** the doctype, row count and import type. The tool refuses if they no longer match the session, so an approval given for an older version can't run.
- **It creates the Data Import** with the prepared file, `template_options` and `mute_emails=1`, then starts it the way `form_start_import` does.
- **Continue after an interruption:** the same Data Import is started again.

**Tool.**
- `run_import(session, what="data", doctype, row_count, import_type)`. Returns the Data Import name and job status. Write.

**Risks.**
- **One missing record after a crash.** Data Import writes its log before it saves each document, so a crash at exactly that moment can log a document that wasn't saved. On continue, the engine checks that the last logged document exists.
- **Shared queue.** The import runs on the shared `default` queue, so a long one can delay other jobs such as email. This bench has 1 worker.

### #33994 Fix failed rows and re-import only those

**What the user sees.** "22 rows failed: 15 missing a Tax Category, 7 duplicate emails." The user fixes them and says "try those again". Only those rows run, and the successes aren't touched. Rows that can't be fixed in chat are downloaded, fixed in Excel and uploaded again, and that file goes through the check first.

**Reuse.**
- Data Import Log for the failures.
- Data Import's own retry, which re-runs only failed rows.
- "Export Errored Rows" and "Download Import Log" in Desk. FACO gives the link.

**Build.**
- **Reading failures:** the log is read directly, because Frappe's `get_import_logs` stops at 5,000 rows. Failures are grouped as in #33991.
- **The `retry` mode of `run_import`:**
  - If the user only created missing masters, the same Data Import is started again, using Frappe's own retry.
  - If they added value maps or left rows out, a new prepared file of only the failed rows becomes a new Data Import, linked to the same session.
- **A corrected file uploaded later** replaces the source file on the session. The session goes back to Mapped, so it must be checked before import.

**Tools.**
- `get_import_session` returns the failure groups after an import. Read-only.
- `run_import(session, what="retry", row_count)`. Write.

**Risks.**
- **One file with reasons.** The ticket asks for a single download with a reason on every row. Desk gives two files: the errored rows, and the log with reasons (question 8).
- **Logs disappear with the Data Import.** They are deleted if the Data Import is deleted, so on completion the engine saves the created record names on the session for undo.

## 5. All tools

| Tool | Tickets | Arguments | Returns | Type |
|---|---|---|---|---|
| start_import_session | 33988 | file_url?, sheet?, doctype?, import_type? | session, sheets, headers, counts, samples | Write (session only) |
| get_import_session | 33988, 33994 | session? | step, mapping, fixes, check summary, failures, progress | Read-only |
| get_import_schema | 33989 | doctype | importable fields, child tables, links | Read-only |
| update_import_session | 33989, 33991 | session, mapping?, doctype?, import_type?, fixes? | stored mapping, gaps, new counts | Write (session only) |
| check_import | 33990, 33991 | session, only_failed? | counts and groups, or job id | Read-only |
| run_import | 33992, 33993, 33994 | session, what (masters / data / retry), doctype, row_count, import_type | Data Imports, job status | Write (approval card) |

The two "session only" write tools change nothing in ERPNext. Whether they should skip the approval prompt is question 6.

## 6. Files to create and change

Paths are under `frappe_assistant_core/`.

| File | Create / change | Tickets |
|---|---|---|
| `plugins/data_migration/plugin.py`, `__init__.py` | Create | 33988 |
| `plugins/data_migration/tools/` (6 tools) | Create | As in section 5 |
| `plugins/data_migration/engine/access.py` (permission helper) | Create | 33988 |
| `engine/reader.py` (fast header read, prepared file) | Create | 33988, 33989, 33991 |
| `engine/schema.py`, `engine/mapping.py` | Create | 33989 |
| `engine/check.py` (dry-run loop and guard), `engine/grouping.py` | Create | 33990, 33991 |
| `engine/runner.py` (masters, data, retry) | Create | 33992, 33993, 33994 |
| `assistant_core/doctype/fac_import_session/` | Create | 33988 |
| `assistant_core/doctype/fac_import_session_run/` (child table) | Create | 33988, used in 33992 to 33994 |
| `patches/v3_1/enable_data_migration_plugin.py`, `patches.txt` | Create, change | 33988 |
| `tests/test_data_migration_*.py` | Create | Every ticket |
| `hooks.py` (permission query, has_permission) | Change | 33988 |
| `chat/utils/permissions.py` (session owner rule) | Change | 33988 |
| `utils/tool_category_detector.py` | Change | Every ticket |
| `chat/api/chat/helpers.py` (file URL in summary) | Change | 33988 |
| `plugins/data_science/tools/extract_file_content.py` (fast header read for big spreadsheets; same output shape) | Change | 33988 |
| `assistant_core/doctype/assistant_core_settings/` (import row limit) | Change | 33988 |

## 7. Impact on existing behaviour

- **The attachment summary** gains the file URL. Big spreadsheets are summarised faster, in the same shape.
- **A Data Migration plugin** appears in FAC Admin, turned on by the patch, with 6 new tools.
- **Data Import records** are created by FACO, always with emails muted. They look and behave like ones made in Desk, including the masters.
- **Background load:** checks use `long` workers, sometimes for tens of minutes. Imports use `default` workers. Each session runs one job at a time.
- **What a check leaves behind:** Error Log rows, some cache entries and gaps in autoincrement names. No business records.
- **Unchanged:** existing tools, uploads, Frappe's Data Import code, and `extract_file_content`'s results.

## 8. My ideas: agree or disagree

1. **Optional target with an early permission check: agree, with two changes.**
   - Name the argument `doctype`, because the audit log fills its Target DocType column only from that name (`utils/audit_trail.py:103-107`).
   - Reuse Data Import's own `validate_doctype`, which also checks import permission and Allow Import, so a session can't reach the import and fail there.
2. **The helper also checks file read and Data Import create: agree.** Use Frappe's File permission, not `extract_file_content`'s stricter rule, which refuses non-System Managers a private file that isn't attached to anything.
3. **Loading a session: both.**
   - Save the chat id on the session, and add `get_import_session`, which uses it by default.
   - For Claude and ChatGPT, which send no chat id, it lists the user's open sessions.
4. **Where the tools live: a new plugin**, for the reasons in 3.6.
5. **Status list: agree, with two changes.**
   - Add **Cancelled**.
   - Show running jobs as progress, not as a status.
   - "Checked" (failures remain) and "Ready" (nothing blocking) are what the import gate checks.
6. **Merge the session and schema first: agree, plus one more.** Also merge the check engine's result format early, because the accounting tickets report errors the same way (section 9).

**One change to the ticket notes:** roll back fully after each row, not to a savepoint (#33990).

## 9. What the accounting teammate needs from me, and when

| They need | Why | Ready |
|---|---|---|
| The session doctype, with `parent_session` | Their files are sessions too | End of week 1 |
| `check_import_access` and `get_import_schema` | Permissions and field lists for Stock Reconciliation, Journal Entry and invoices | End of week 2 |
| `check_import` and its group format | Their dry runs and error groups match ours | Week 3 |
| `run_import` | The same import path | Week 4 |

**For them to decide:**
- **Submittable documents.** All three of their tickets import submittable documents, and the check skips "submit after import". They need to decide whether their check inserts only, or also submits inside the rolled-back transaction.
- **Opening stock.** It should come in through Stock Reconciliation, not Item's opening-stock field, which submits a Stock Entry inside Item's own save.

## 10. Open questions for my manager

1. **#33990's title and description don't match.** Please confirm the ticket is the dry run, and that cleaning means only the three fixes in #33991, with everything else fixed in the file and uploaded again.
2. **Who may migrate?** Data Import is System Manager only by default. Keep that, or grant it to Assistant Admin?
3. **The file size limit.** Chat allows 50 MB, but Frappe refuses files over its own maximum, 25 MB by default (System Settings), so a 30 MB upload fails on a default site. Raise Frappe's limit, or document 25 MB?
4. **AR's time limit for one tool call.** It decides how much can run inside a call. The plan assumes at least 60 s.
5. **Progress in chat.** FACO reports when asked. A live progress bar adds about 1.5 days. An automatic "your import is done" message would need work in AR.
6. **Approvals for session-only tools.** `start_import_session` and `update_import_session` change nothing in ERPNext. Can they skip the approval prompt, so users aren't asked on every mapping tweak? `run_import` always asks.
7. **Doctypes the check skips.** Is "skip with a warning" acceptable for the doctypes listed in #33990?
8. **The failed-rows download.** Are Desk's two existing downloads (errored rows, and the log with reasons) enough, or should FACO build one file with a reason column (half a day)?
9. **Masters through Data Import** instead of the bulk-create tool the ticket describes. It gives one approval card, a log and the same undo. Is that OK?
10. **The 50,000-row limit.** A check of 50,000 rows can take over an hour. Keep it, or use 20,000 for v3.1.0?
11. **Accepting #33988 on part of criterion 2.** Its criterion 2 names mapping, fixes and check results, which arrive with #33989 to #33991. Can #33988 be accepted when whatever is on the session comes back on a later turn?
12. **Merging #33987.** It is on its own branch, not yet in `test-develop`. Please confirm it merges before #33988 starts.

## 11. Build order and estimate

Order: #33988 → #33989 → #33990 → #33991 → #33992 → #33993 → #33994. The doctype goes in during week 1 so the accounting tickets can start. The migrate-data skill (#34004) follows, and it is what guides FACO through these six tools.

| Ticket | Build (days) | Testing (days) | Main build items |
|---|---|---|---|
| #33988 Session | 3 | 1.5 | Doctype and child table, permission helper, 2 tools, fast header read, file URL, plugin patch |
| #33989 Mapping | 2.5 | 1.5 | Import schema, mapping checks, prepared file |
| #33990 Dry run | 5 | 2.5 | Check loop, guard, skip list, duplicates, background and progress |
| #33991 Fix together | 2 | 1 | Grouping, closest matches, the three fixes, re-check |
| #33992 Masters | 1 | 0.5 | Master files ordered by parent, via Data Import |
| #33993 Import | 2 | 1.5 | Data Import creation and start, approval check, resume check |
| #33994 Retry | 1.5 | 1 | Failure grouping from the log, retry run |
| **Total** | **17** | **9.5** | **26.5 days (about 5.5 weeks)** |

Testing covers:
- unit tests for every engine module;
- a guard test for each skipped doctype, plus a Customer with a matching Call Log;
- manual runs in FAC Chat with a 50-row file, a 5,000-row file and the 9 MB / 200k-row file, across several turns and one interrupted import;
- one run from Claude, using a file URL;
- a Desk check of every Data Import and its log.

Add 1.5 days if question 5 asks for a live progress bar, and half a day if question 8 asks for a single failed-rows file.
