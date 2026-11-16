# Design: Guided data migration, core flow (#33988 to #33994)

Feature #33986 "FAC Chat: Guided data migration into ERPNext", v3.1.0
Author: Rachana · 1 October 2026 · Status: draft for approval

## 1. Overview

A user attaches an Excel or CSV export from their old system, and FACO takes them through the migration over several messages: pick the record type, map columns, clean values, test every row without saving, fix errors together, create missing masters, import, and retry failures. All real work runs in server code. The model sees only headers, a few sample rows, grouped summaries and counts. AR rebuilds the agent on every turn, so everything is stored on a new **FAC Import Session** record. The import itself goes through Frappe's own Data Import, so every import can be seen in Desk with its log.

Base branch: #33987 is on `feature/33987-accept-spreadsheet-exports-in-chat` and has not been merged into `test-develop` yet. This design builds on that branch.

## 2. Shared design (decided once)

### 2.1 The FAC Import Session doctype

Module Assistant Core, named `IMP-{YYYY}-{#####}`, change tracking on. Only the tools change the step-related fields; in Desk they are read-only.

| Field | Type | Why |
|---|---|---|
| status | Select | The current step (see 2.6). |
| user | Link: User | The owner. Permission rules use it, as on FAC Chat Message. |
| chat_session_id | Data, indexed | The conversation it belongs to, so FACO can find it without remembering an id. |
| parent_session | Link: FAC Import Session | Groups several file sessions for the migration order (#33995). Empty for now. |
| source_file | Link: File | The file the user uploaded. |
| working_copy | Attach (private) | The chosen sheet saved once as UTF-8 CSV, all values as text. Later steps read this fast copy, and it survives chat retention deleting the upload. |
| sheet | Data | The chosen sheet (empty for CSV). |
| sheets | JSON | Each sheet's name, headers, row count and up to 10 sample rows. |
| target_doctype | Link: DocType | What the rows become. |
| import_type | Select: Insert New Records / Update Existing Records | Same values as Data Import, so they copy straight across. |
| match_key | Data | The field used to find existing records: duplicate checks now, updates by a key other than name later (#34005). |
| template_options | JSON | The column map in Data Import's own shape: `column_to_field_map` keyed by 0-based column position as a string, with values like `fieldname`, `table_field.fieldname` or `Don't Import`. |
| transformation_rules | JSON | The ordered cleaning rules (#33990, #33991). |
| excluded_rows | JSON | Rows the user chose to leave out, each with a reason (#33991). |
| validation_summary | JSON | The latest dry-run result as groups and counts. This is what the model sees. |
| validation_results | Attach (private) | The full result for every row, kept as a file so the session record stays small at 50,000 rows. |
| validated_fingerprint | Data | A hash of the mapping and rules the last dry run used. If they have changed since, the session can't go to import. |
| progress | JSON | The running job's phase, current row, total, job id and update time. |
| data_imports | Table | Each Data Import created: name, purpose (Import / Retry), status and counts. Undo (#34002) reads this. |
| created_records | Table | Masters created by #33992: doctype, name, parent. Undo removes these. |

### 2.2 What the server does and what the model sees

The engine is a set of plain Python modules under the new plugin. The tools are thin wrappers around it.

| The engine (server) | The model |
|---|---|
| Reads every row, applies the rules, runs the dry run and import, stores the results per row | Headers, up to 10 sample rows, each column's distinct-value counts and top values |
| Works out closest matches from existing ERPNext names | Up to 5 ranked matches per group, which it must choose from (it never makes up names) |
| Writes the cleaned file and the failed-rows file | Groups with a cause, count and up to 3 example rows |
| Checks every fieldname and value the model proposes | Clear errors, such as "`customer_grp` is not a field of Customer; did you mean `customer_group`?" |

Any file content in a tool result (headers, samples, examples) is wrapped with `wrap_untrusted`. Tools don't do this today; only the chat path does, so these tools will be the first. The row limit is a new setting, **Import row limit** (default 50,000) on Assistant Core Settings, checked when the session starts.

### 2.3 Permission helper

One helper, `check_import_access(session_or_doctype, action)`, runs before any work. Every tool calls it. On failure it raises a PermissionError with a plain message, which BaseTool logs as "Permission Denied".

| Check | When |
|---|---|
| The user can read the source file under Frappe's own File permission | At start |
| The user can create a Data Import (#33993 needs it) | At start |
| The row count is within the import row limit | At start |
| The target allows import: Allow Import is on, it isn't blocked by Data Import, and it isn't a child table or a Single. The user has **import** permission plus **create** (Insert) or **write** (Update). | As soon as the target is known |
| The user can create each master doctype in the plan | #33992 |
| The user owns the session (System Manager sees all). Enforced with a permission query and a has_permission hook, as for FAC Chat Message. | Every tool |

Data Import is System Manager only by default, so without a change only System Managers can migrate (question 2).

### 2.4 Background jobs and progress

- **What runs in the background:** reading a file over 5 MB, a dry run or re-check over 500 rows, building the import file, and the import itself.
- **How jobs run:** our jobs use the `long` queue with job id `fac_import::<session>::<phase>`, and a second start while one is running is refused. Data Import's own job runs on the `default` queue with a 10,000-second timeout. On a bench in developer mode (like this one) it runs inline instead.
- **How progress is recorded:** jobs save progress on the session every 100 rows. The dry run is the exception, because it must never commit. It writes progress to the Redis cache and saves to the session only once it has finished.
- **How progress reaches the chat:** FAC has no way to post into a chat from a background job. The chat screen only shows AR's events for the current turn. So in v3.1.0, FACO reports progress when the user asks ("how's it going?") or on their next message, by reading `get_import_session`. A live progress bar in the chat screen is possible (question 4). Jobs of 500 rows or fewer run inside the tool call, so small files finish in one turn.

### 2.5 Where the tools live

They go in a new **`data_migration`** plugin (`plugins/data_migration/`), with the engine in `plugins/data_migration/engine/`. One catch: on sites that still carry the old enabled-plugins list, a new plugin starts **off** (`utils/migration_hooks.py:864`). A v3.1 patch will turn it on. Every new tool is added to the read-only or write list in `utils/tool_category_detector.py`, and that gives AR its readOnlyHint and destructiveHint. Write tools ask for approval by default.

### 2.6 Status flow

**Draft** (file read, no target yet) → **Mapped** (target and mapping saved) → **Validated** (dry run done, failures remain) or **Ready** (dry run done, nothing blocking) → **Importing** → **Completed**, **Partially Imported** or **Failed** → **Undone** (#34002). **Cancelled** is available from any step before Importing.

- Changing the mapping, the rules or the match key sends the session back to **Mapped**. A fix applied through `apply_fix` re-checks the affected rows at once, so it stays in Validated or moves to Ready.
- A running job doesn't get a status of its own. It shows in `progress`, so the status always says where the user is, not what the server is doing.
- A retry (#33994) goes from Partially Imported back to Importing.

## 3. Per ticket

### #33988 Start an import session for an uploaded file

**What the user sees.** They say "import this". FACO lists the sheets, columns and row counts and asks which sheet and what it holds. Days later, in the same chat, FACO carries on from where they stopped.

**How it works.**
- FACO isn't given the file's URL today: the attachment summary has only its name (`chat/api/chat/helpers.py:161-165`). So `file_url` is optional. When it is left out, the tool picks the latest spreadsheet attached to this conversation's messages. The summary also gets the URL added.
- The session saves `chat_session_id` from `frappe.local.ar_session_id`. That is the `X-AR-Session-Id` header, which the browser tools already use.
- Starting twice for the same file in the same chat returns the existing session.
- Files up to 5 MB are read inside the call. `extract_file_content` already parses the file in send-message, so its sheet summary is cached for 10 minutes against the file's content hash, and the tool doesn't read the file a second time.
- Larger files go to a background job, and FACO says "reading your file". For speed, the headers and an approximate row count come from openpyxl in read-only mode.
- Once a sheet is chosen, a job saves it as the working copy. All values are kept as text, so leading zeros, phone numbers and GSTINs survive. pandas, as used by `extract_file_content`, would turn them into numbers.

**New tools.**
- `start_import_session(file_url=None, sheet=None, doctype=None, import_type="Insert New Records")`. Returns the session id, status, sheets (headers, row counts, samples) and any permission problem. Write.
- `get_import_session(session=None)`. Returns the step, mapping, rules, last summary and progress. With no id, it returns this chat's open session. If there is none, or more than one, it lists the user's open sessions to choose from. Read-only.

**Files.** The plugin, the two tools, `engine/access.py`, `engine/reader.py`, the doctype and its two child tables, the plugin patch, `hooks.py`, `tool_category_detector.py`, `helpers.py`, the row-limit setting, tests.

**Risks.**
- Chat already extracts the whole file in send-message. With a 50 MB workbook that can pass the 120 s timeout before our tool even runs, which is #33987's open risk. I suggest chat give only headers and row counts for spreadsheets over 5 MB (half a day, question 3).
- Older AR versions and other MCP clients don't send the chat id. There, `get_import_session` falls back to listing open sessions.

### #33989 Suggest the target DocType and column mapping

**What the user sees.** "These look like **Customers**: there are name, group, territory and GSTIN columns." Then a table of *your column → ERPNext field*, with unmapped columns and required fields that have no source marked. A choice card appears when FACO isn't sure.

**How it works.**
- `get_import_schema` returns only fields Data Import can accept, using the same rules as Data Import's column matching (`importer.py:1073-1213`):
  - fieldname, label, type, required, unique
  - options or the link target, and the parent field for tree doctypes
  - child tables, with their importable fields
  - the naming rule
  - the suggested match key
  - the doctypes this one links to (for #33995)
- This is about 2-4 KB for Customer. `get_doctype_info` returns every field including layout breaks, and drops `unique` and naming.
- The model suggests the mapping from header meanings and samples ("Cust Name", "Party", "GSTIN No."). The engine then checks it.
- `set_column_mapping` rejects unknown fields, mapping two columns to one field, and child fields for the wrong table. It suggests the closest fieldname. It stores the result in `template_options` and returns the list of required fields that still have no column. Child-table columns are shown as their own section.

**New tools.**
- `get_import_schema(doctype)`. Read-only.
- `set_column_mapping(session, doctype, mapping, import_type=None, match_key=None)`. `mapping` is a list of {column, field}. Returns the mapping as stored, the unmapped columns and the required fields with no source. Write. It changes only the session.

**Files.** The two tools, `engine/schema.py`, `engine/mapping.py`, tests.

**Risks.**
- The mapping is by column position. The working copy and the file sent to Data Import must keep the same column order. The engine writes both, so it can guarantee this.
- Whether the model understands headers well depends on the samples. Low confidence must always lead to a choice card, and that is a skill rule (#34004).

### #33990 Clean and reshape values, and dry run

Part A covers the title (cleaning) and part B the description (dry run). The mismatch is question 1.

**What the user sees.** (A) "Dates look like 31/12/2024; I'll read them as day/month/year." "Map *Retail* to *Retail Customers*?" (B) "4,812 ready, 188 would fail", with failures grouped and up to 3 example rows each. Over 500 rows it runs in the background.

**A. How cleaning works.**
- Rules are an ordered list on the session. Each rule has a column, a type, its settings and an origin (the user, or a fix group).
- Rule types:
  - trim
  - change case
  - date format (source format to ISO)
  - number (strip thousands separators and currency signs)
  - yes/no to 1/0
  - value map (e.g. "Retail" → "Retail Customers")
  - fill blanks with a default
  - leave out rows (stored in `excluded_rows`)
- The engine applies the rules in order when it reads rows, the same way for the dry run and the import file. Trim is on by default.
- Column profiles (blanks, distinct values, a guessed date format using Frappe's own `guess_date_format`) let FACO suggest rules without seeing every row.

**B. How the dry run works.**
- The engine maps each row with Frappe's own `ImportFile` class, the same parser Data Import uses: Select, Link and date checks, coercion and child-row grouping.
- It then calls `doc.insert()` with the same flags as a real import: `in_import` on and emails muted. These flags change validation (Select checks and defaults are skipped), so they must match.
- `Importer.import_data` can't be reused, because it commits after every row and does a full rollback on failure (`importer.py:186-194`).
- Each row runs in its own transaction, which is then fully rolled back. I recommend this over the ticket's savepoint:
  - InnoDB keeps the locks taken after a savepoint until the whole transaction ends. One long transaction would hold the naming-series row and tree locks, and block other users creating Customers for the whole run.
  - Rolling back to a savepoint doesn't clear Frappe's after-commit queue (webhooks, queued jobs, realtime events). A full rollback does.
- A sandbox guards each row:
  - `frappe.db.commit` raises an error, so a hidden commit fails that row as "can't be tested safely" instead of saving it. ERPNext's Call Log hook, reached through Customer and Supplier contacts, commits. So do Custom Field and Company.
  - Jobs queued straight away are dropped.
  - Global search indexing is off.
  - The real `commit` is put back only after the final rollback.
- **Doctypes skipped with a warning:** DocType, Custom Field, Property Setter, Customize Form, Company, Accounting Dimension, User, File, Location, the core doctypes Data Import blocks, and any submittable doctype when "submit after import" is on. Each of these commits, runs schema changes, sends mail or writes files. A row that hits the guard on any other doctype is reported in its own group.
- **Duplicates have their own group:**
  - Within the file: the same match-key value twice. A per-row rollback can't see earlier rows, so this is checked separately.
  - Against ERPNext: the match key already exists, or the insert raises a duplicate error.
  - The match-key check matters because Customers named by series never raise a duplicate error.
- If a link points to a record created earlier in the same file (such as a parent group), the dry run counts it as present, as a real import would.
- **Re-check:** only rows that failed, or whose columns changed rules, are run again. The result is merged into the per-row file.
- **What still escapes the rollback:** Error Log rows, some Redis cache entries and gaps in autoincrement names. None of these is business data.

**New tools.**
- `set_transformation_rules(session, rules, replace=False)`. Write.
- `profile_columns(session, columns=None)`. Read-only.
- `run_dry_run(session, only_failed=False)`. Returns counts and groups, or a job id. Read-only, because nothing is saved.

**Files.** The three tools, `engine/rules.py`, `engine/dry_run.py` (the sandbox), `engine/grouping.py`, `engine/jobs.py`, tests.

**Risks.**
- **Speed.** An insert takes roughly 20-100 ms, so 50,000 rows take 15-80 minutes and hold one long worker for that time.
- **Mail and Notifications.** With import and mute both on, Frappe skips Notifications completely (`document.py:1026-1031`), and we rely on that.
- **Custom hooks.** A site's own app may have after-insert hooks that call outside services. The commit guard doesn't catch those (question 6).

### #33991 Explain errors in plain language and fix them together

**What the user sees.** "**43 rows**: Customer Group *Retail* doesn't exist. Closest: *Retail Customers*, *Retail*. Map to one, create it, or leave these rows out?" After each choice: "Fixed. 145 rows still need attention."

**How it works.**
- Groups are keyed by cause, field and value. The causes are:
  - missing required value
  - link not found
  - invalid option
  - invalid date or number
  - duplicate in file
  - duplicate in ERPNext
  - other validation error (the controller's message)
  - can't be tested safely
- Each group carries a plain-language cause and the fixes available for it.
- Closest matches are ranked by the engine from existing names, within the user's permissions. The model can only pick from that list, and the engine rejects anything else.
- A fix becomes one of three things:
  - a value-map rule (map to existing, or set a value)
  - an entry in the master plan (create it)
  - an excluded row with a reason (leave out)
- After each fix, the affected rows are re-checked straight away and the new counts come back.
- When no groups are left, the status becomes Ready and FACO gives the final count, with the excluded rows listed.

**New tools.**
- `get_validation_results(session, group=None)`. Returns the groups, or one group's details with up to 3 examples and its closest matches. Read-only.
- `apply_fix(session, group, fix, value=None, reason=None)`. `fix` is one of map_to_existing, set_value, create_master, leave_out. Returns new counts. Write. It changes only the session.

**Files.** The two tools, `engine/matching.py`, additions to `engine/grouping.py`, tests.

**Risks.**
- Controller messages are free text. Grouping them by message after removing names and numbers will sometimes split one cause into several groups.

### #33992 Create missing masters in one approved batch

**What the user sees.** One plan table (6 Customer Groups, 3 Territories, 12 UOMs), with the parent shown for tree masters and changeable. They approve once and get a change log back.

**How it works.**
- This follows the setup-change-protocol: a plan table in dependency order, one confirmation, and a change log at the end.
- One bulk tool call means one approval card. I suggest the card replaces the protocol's separate confirm step (question 7).
- The parent defaults to the tree's root group, or the group the user picks.
- The tool checks create permission for every doctype first. It then inserts parents before children in one transaction, all or nothing, and records each master in `created_records`. That table is both the change log and the undo list.

**New tool.**
- `create_masters(session, records)`. `records` is a list of {doctype, name, parent, values}. Returns the created names, or the first failure with nothing created. Write.

**Files.** The tool, `engine/masters.py`, tests.

**Risks.**
- The approval card shows all the tool's arguments. With 30 records it gets long. The plan table in chat stays the readable version.

### #33993 Import through Frappe's Data Import with one approval

**What the user sees.** One approval card: *Customer · 4,812 rows · 4,812 new, 0 updates*. Then progress on request, ending with "4,790 created, 22 failed, 188 left out", and the record under Data Import in Desk.

**How it works.**
- The tool only runs when the session is **Ready** and the fingerprint matches the last dry run.
- The card's arguments repeat the doctype, row count and import type. The tool refuses if they no longer match the session, so an approval given for an older version can't run.
- A background job then:
  1. writes the cleaned single-sheet CSV with the rules applied and excluded rows removed (Data Import reads only the first sheet of a workbook), and keeps a map from cleaned rows back to source rows;
  2. creates the Data Import with reference_doctype, import_type, `mute_emails=1` and template_options, then attaches the CSV as a private File;
  3. checks write permission and calls `start_import()`, as `form_start_import` does.
- Counts come from `get_import_status`. Created, failed and left-out are reported separately. The importer commits each document, so partial success is normal and is reported that way.
- **Resume ("continue"):** if the job stopped (timed out or crashed), the tool starts the same Data Import again. The importer skips every row already in its log, which avoids duplicates. One catch: the importer writes its log (a non-transactional MyISAM table) *before* it commits the document. A crash at exactly that moment leaves a "success" log for a document that doesn't exist. On resume, the engine checks the last logged document exists and reports it if not.

**New tool.**
- `start_import(session, doctype, row_count, import_type, resume=False)`. Returns the Data Import name and job status. Write.

Progress comes from `get_import_session`, which reads `get_import_status`.

**Files.** The tool, `engine/import_runner.py`, tests.

**Risks.**
- The Data Import job runs on the shared `default` queue. A long import can delay other default jobs, such as email. This site runs 1 background worker.
- Data Import checks import permission only when it is saved, not when it is started, so our helper checks it again at start.

### #33994 Fix failed rows and re-import only those

**What the user sees.** "22 rows failed: 15 missing a Tax Category, 7 duplicate emails." The user fixes them as in #33991 and says "try those again". Rows that can't be fixed in chat come back as a file to download, with a reason on each row. A corrected file uploaded later goes through the dry run first.

**How it works.**
- Failures are read from Data Import Log (`row_indexes`, `messages`, `exception`), mapped back to source rows, and grouped by the #33991 engine.
- Data Import's own `get_import_logs` stops at 5,000 rows, so the engine queries the log directly.
- **Retry:** instead of re-running the original Data Import (which would ignore the new fixes), the engine writes a new file with only the failed rows and their fixes applied. It creates a new Data Import with purpose **Retry** on the same session. Successful rows are never touched.
- **Download:** the failed-rows file follows `download_errored_template` (original headers and original row values) with a **Reason** column added. It is saved as a private File on the session, and FACO gives a download link, as `generate_document` does.
- **Corrected file:** a file uploaded later replaces the working copy on the same session. The session goes back to Mapped, so a dry run is needed before import.

**New tools.**
- `get_import_failures(session)`. Read-only.
- `retry_failed_rows(session, row_count)`. Write, with one approval card.
- `export_failed_rows(session)`. Returns a file_url. Write, because it creates a File.

**Files.** The three tools, `engine/retry.py`, tests.

**Risks.**
- A Data Import's logs are deleted when the Data Import is deleted (`on_trash`). The engine copies each import's created docnames into a private file on the session when it finishes, so undo (#34002) doesn't depend on Data Import Logs that might be gone.

## 4. All tools

| Tool | Ticket | Arguments | Returns | Type |
|---|---|---|---|---|
| start_import_session | 33988 | file_url?, sheet?, doctype?, import_type? | session, sheets, headers, counts, samples | Write |
| get_import_session | 33988 | session? | step, mapping, rules, summary, progress | Read-only |
| get_import_schema | 33989 | doctype | importable fields, child tables, naming, match key, links | Read-only |
| set_column_mapping | 33989 | session, doctype, mapping, import_type?, match_key? | stored mapping, gaps | Write |
| set_transformation_rules | 33990 | session, rules, replace? | stored rules | Write |
| profile_columns | 33990 | session, columns? | per-column profile | Read-only |
| run_dry_run | 33990 | session, only_failed? | counts and groups, or job id | Read-only |
| get_validation_results | 33991 | session, group? | groups or group detail, closest matches | Read-only |
| apply_fix | 33991 | session, group, fix, value?, reason? | new counts | Write |
| create_masters | 33992 | session, records | created list or first failure | Write |
| start_import | 33993 | session, doctype, row_count, import_type, resume? | Data Import, job status | Write |
| get_import_failures | 33994 | session | failure groups | Read-only |
| retry_failed_rows | 33994 | session, row_count | new Data Import, job status | Write |
| export_failed_rows | 33994 | session | file_url | Write |

Write tools that change only the session (set_column_mapping, set_transformation_rules, apply_fix) could skip the approval prompt. Otherwise a long chat would ask the user to approve every mapping tweak (question 5).

## 5. Files to create and change

Paths are under `frappe_assistant_core/`.

| File | Create / change | Tickets |
|---|---|---|
| `plugins/data_migration/plugin.py`, `__init__.py` | Create | 33988 (tools added by each ticket) |
| `plugins/data_migration/tools/<tool>.py` (14 tools) | Create | One per ticket, as in section 4 |
| `plugins/data_migration/engine/access.py` | Create | 33988, extended in 33989 and 33992 |
| `engine/reader.py` (sheets, working copy, cache) | Create | 33988 |
| `engine/schema.py`, `engine/mapping.py` | Create | 33989 |
| `engine/rules.py`, `engine/dry_run.py`, `engine/grouping.py`, `engine/jobs.py` | Create | 33990 |
| `engine/matching.py` | Create | 33991 |
| `engine/masters.py` | Create | 33992 |
| `engine/import_runner.py` | Create | 33993 |
| `engine/retry.py` | Create | 33994 |
| `assistant_core/doctype/fac_import_session/` | Create | 33988 (fields used by later tickets added now) |
| `assistant_core/doctype/fac_import_session_data_import/` (child) | Create | 33988, used in 33993 and 33994 |
| `assistant_core/doctype/fac_import_session_record/` (child) | Create | 33988, used in 33992 |
| `patches/v3_1/enable_data_migration_plugin.py`, `patches.txt` | Create, change | 33988 |
| `tests/test_data_migration_*.py` | Create | Every ticket |
| `hooks.py` (permission query, has_permission) | Change | 33988 |
| `chat/utils/permissions.py` (owner rule for sessions) | Change | 33988 |
| `utils/tool_category_detector.py` | Change | Every ticket |
| `chat/api/chat/helpers.py` (file URL in summary, extraction cache, header-only summary for large spreadsheets) | Change | 33988 |
| `plugins/data_science/tools/extract_file_content.py` (read the cache; no change in behaviour) | Change | 33988 |
| `assistant_core/doctype/assistant_core_settings/` (Import row limit) | Change | 33988 |

## 6. Impact on existing behaviour

- **The attachment summary FACO receives** gains the file URL. Spreadsheets over 5 MB get headers and row counts instead of a full extraction, if question 3 is approved.
- **A Data Migration plugin** appears in FAC Admin, turned on by the patch, with 14 new tools.
- **Data Import records** are created by FACO, always with emails muted. They look and behave like ones made in Desk.
- **Background load:**
  - Dry runs take `long` workers, possibly for tens of minutes.
  - Imports take `default` workers.
  - Sites with one worker will notice. Each session can run only one job at a time.
- **What dry runs leave behind:** Error Log rows, some Redis cache entries and gaps in autoincrement names. No business records.
- **Unchanged:** existing tools, chat uploads, Data Import itself and `extract_file_content`'s results.

## 7. My ideas: agree or disagree

1. **Optional target with an early permission check: agree, with two changes.** Name the argument `doctype`, because the audit log fills its Target DocType column only from an argument with that name (`utils/audit_trail.py:103-107`). Also check **import** permission and Allow Import, not only create: Data Import checks both, and checking create alone would let a session reach #33993 and fail there.
2. **The helper also checks file read and Data Import create: agree.** Use Frappe's own File permission rather than `extract_file_content`'s stricter rule, which refuses non-System Managers a private file that isn't attached to anything. Data Import is System Manager only by default (question 2).
3. **Loading a session: both, as one design.** Save the chat id on the session and add `get_import_session`, which uses it by default. A tool alone relies on the model remembering an id through a long chat. A link alone needs something to load the session, and doing that in send-message would add work to every turn.
4. **Where the tools live: a new plugin.** `data_science` also holds `run_python_code` and `run_database_query`, which admins often turn off for safety, and migration would go with them. The new plugin still reuses its file reader.
5. **Status list: agree, with two changes.** Add **Cancelled**. Treat running jobs as progress rather than a status, so there is no "Validating" or "Reading" state to get stuck in. The difference between Validated (failures remain) and Ready (nothing blocking) is what the import gate checks.
6. **Merge the session and schema first: agree, and add two more.** The teammate also needs the rules engine and the dry-run sandbox. Opening stock and opening balances must be tested the same way, and the sandbox's skip list affects them most (section 8).

**One further change to the ticket notes:** roll back after each row, not to a savepoint (section 3, #33990). It gives the same result, without holding locks across the run or leaking after-commit jobs.


## 9.questions

1. **#33990's title and description don't match.** The title is about cleaning values; the description is about the dry run. Both are designed here. I propose splitting cleaning into its own ticket (3.5 days) and keeping #33990 for the dry run (7.5 days).
2. **Who may migrate?** Data Import is System Manager only by default. Should we keep that, or grant it to Assistant Admin?
3. **Large files in chat.** For spreadsheets over 5 MB, chat would give headers and row counts instead of extracting the whole file, which can take longer than the 120 s request timeout at 50 MB. Can this go into #33988 (half a day)? Also, what is AR's time limit for one tool call? That sets how much runs inside a call.
4. **Progress in chat.** Plan: FACO reports when asked. A live progress bar in the chat screen adds about 1.5 days. An automatic "your import is done" message would need work in AR.
5. **Approvals for session-only tools.** Mapping, rules and fixes change only the session. They could skip the approval prompt, so a long chat doesn't ask for approval on every tweak. The Import and Retry calls always ask.
6. **Doctypes the dry run skips.** Is "skip with a warning" acceptable for the doctypes listed in #33990? A site's own after-insert hooks that call outside services can't be caught. Should admins be able to turn the dry run off per doctype?
7. **One approval for masters.** Can the bulk tool's approval card replace the setup-change-protocol's separate confirmation? Otherwise the user confirms twice.
8. **The 50,000-row limit.** A dry run of 50,000 rows can take over an hour. Keep the limit, or lower it to 20,000 for v3.1.0?


