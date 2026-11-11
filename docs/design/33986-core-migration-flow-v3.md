# Design: Guided data migration, core flow (#33988 to #33994), v3

Feature #33986 "FAC Chat: Guided data migration into ERPNext", v3.1.0
Author: Rachana · 5 October 2026 · Status: draft for approval

## 1. Overview

A user attaches an Excel or CSV export, and FACO guides them through moving it into ERPNext: pick the record type, map the columns, check every row without saving, fix problems, import, and retry what failed.

This plan is built on what Frappe and FAC already do:
- Frappe's **Data Import** record holds the file, the target doctype, the column mapping, the status and a log for every row, and does all the importing.
- FAC's existing document tools create, read and update that record.
- The user fixes data in their file and uploads it again.

We build only what neither Frappe nor FAC has: **checking every row before import**, and **starting an import from chat**. That's 2 new tools and a one-line change to chat. There is no new doctype and no new plugin.

Every fact below was checked in one of three ways:
- **Live test:** run on test.local with the existing FAC tools, then fully rolled back, and confirmed afterwards that nothing was left.
- **Code:** read in Frappe 15.107.3, ERPNext 15.108.0, or FAC on `test-develop`.
- **Docs:** docs.frappe.io.

## 2. What already exists (with evidence)

### 2.1 Frappe Data Import

| What | Supported? | Evidence |
|---|---|---|
| Insert new records, or update existing ones by ID | Yes | Docs: docs.frappe.io/erpnext/data-import |
| Import from CSV, .xlsx, .xls, or a public Google Sheet | Yes | Docs; code `importer.py:603-614` |
| Reading only one sheet of a workbook (the active sheet for xlsx, the first for xls) | Yes, one sheet only | Code `utils/xlsxutils.py:103-126` |
| Automatic column matching by label or fieldname, plus a manual map stored in `template_options` | Yes | Docs ("map columns"); live test: "Cust Name" mapped to `customer_name` through `template_options` |
| Child tables (extra rows under the parent) | Yes | Docs |
| Preview checks across the whole file: links that don't exist, invalid options, unreadable dates | Yes | Live test: caught missing Customer Group "Retail", missing Territory, invalid Customer Type |
| These preview problems block the whole import until fixed | Yes | Docs ("You must resolve all the warnings before you can import"); code `importer.py:82-90` |
| Preview checks for empty required fields, duplicates, ERPNext/India Compliance rules | **No** | Live test: an empty customer name and a duplicate "Acme Traders" were not flagged; docs mention no dry run |
| "Don't Send Emails", "Submit After Import" | Yes | Docs |
| Runs in the background, saves each row separately, partial success | Yes | Code `data_import.py:107-128`, `importer.py:186-194` |
| A log row for every record: success, created name, error | Yes | Docs ("Import Log"); code Data Import Log |
| Continue after an interruption without duplicates; Retry re-runs only failed rows | Yes | Code `importer.py:93-133` |
| Export Errored Rows, Download Import Log | Yes, in Desk | Code `data_import.js:86`, `data_import.py:205-216` |
| Who can import | System Manager only by default | Code `data_import.json` permissions |
| Row limit | None, but docs advise "a few thousand records at a time", and `bench data-import` over about 5,000 | Docs |
| File size limit | 25 MB on this site (System Settings empty, so Frappe's default) | Live: `get_max_file_size()` = 26,214,400 |
| A tool to migrate from Tally, or the old Data Migration Tool | Removed before v15 | Docs and GitHub (erpnext PR #45100; Frappe v14 migration notes) |

### 2.2 FAC

| What | Supported? | Evidence |
|---|---|---|
| Upload .csv, .xlsx, .xls in chat, up to 50 MB, with content checks | Yes, on the #33987 branch (`test-develop` allows only .csv) | Code `chat/api/settings/uploads.py`; git |
| The file is saved as a private File on the chat message | Yes | Code `chat/api/chat/helpers.py:79-117` |
| The model gets sheets, columns, row count and 10 sample rows, wrapped as untrusted | Yes | Code `helpers.py:120-179`, `messages.py:261-266` |
| The model gets the file's URL | **No**, only its name | Code `helpers.py:157-165` |
| `extract_file_content`: all sheets, columns, row count, 10 rows; a file URL from Claude or ChatGPT | Yes | Code `extract_file_content.py:813-887` |
| `create_document` creates a Data Import with file, doctype, import type, mapping, emails off | Yes (System Manager) | **Live test** |
| `get_document` reads back status, row count and mapping | Yes | **Live test** |
| `update_document` changes the mapping | Yes | **Live test**. Changing the file resets the mapping (`data_import.py:44-52`). |
| `list_documents` reads Data Import Log rows and their total count | Yes | **Live test** |
| A tool can see Frappe's preview warnings | **No.** They're only stored during an import. | **Live test** (`template_warnings` empty after save) |
| A tool can start a Data Import | **No.** Browser tools can't click buttons. | Code `document_action.py:29`, `widget_browser_tools.js:24-28` |
| A tool can check rows before import | **No.** `validate_only` runs only `validate()` on one record. | Code `create_document.py:188-200` |
| Closest existing names for a missing value | Partly: `search_documents` link search, which matches by "contains", not by spelling similarity | Code `desk/search.py:120-183` |
| Choice cards (single or multiple choice, confirm, text) and approval cards showing the tool's arguments | Yes | Code `QuestionCard.vue`, `ApprovalCard.vue` |
| A per-user "always allow" setting for a tool | Yes | Code `chat/api/tools.py:105-160` |
| The task rail (a step list beside the chat) | Yes, driven by AR | Code `relay.py:979-991`, `ContextRail.vue` |
| Every tool call logged: who, when, arguments, result | Yes | Code `utils/audit_trail.py` |
| A tool's own checks running inside a doctype's save logic, reachable through create/update tools | Yes (precedent: FAC Skill) | Code `fac_skill.py:35-171` |
| Pushing progress from a background job into the chat | **No** | Code: the chat doesn't listen for `data_import_progress` |
| A skill for import or migration | **No.** `guided_setup.md:11` sends users to Desk's Data Import. | Code `data/system_skills.json` |

### 2.3 The gaps (everything else exists)

1. **Checking every row before import.** Required fields, duplicates and ERPNext's own rules are only found while importing. This is the gap the feature exists for.
2. **Preview warnings aren't reachable from a tool.** Frappe computes them, but no FAC tool can read them.
3. **Starting an import from chat.** It can only be done in Desk today.
4. **The file URL isn't given to the model.**

## 3. Design decisions

### 3.1 The Data Import record is the session (no new doctype)

What a session must remember, and where it already lives:

| Needed | Where it lives | Evidence |
|---|---|---|
| The file | Data Import `import_file`, and the File on the chat message | Live test |
| Target doctype, import type | Data Import | Live test |
| Column mapping | Data Import `template_options` | Live test |
| Row count | Data Import `payload_count` | Live test |
| Status and progress | Data Import `status` plus Data Import Log counts | Live test |
| What was created, for undo (#34002) | Data Import Log `docname` | Code |
| Masters created in chat | Assistant Audit Log (tool, doctype, name, user) | Code |
| Visible in Desk | Data Import, with its file and log | Docs |
| Coming back days later | `list_documents` on Data Import for this user, status Pending or Partial Success | Live test |
| Works in Claude and ChatGPT | Same generic tools | Code |

**What we drop from the roadmap to make this possible:** fixes stored in chat as rules. Following the manager's direction, data problems are fixed in the file and the file is uploaded again. Section 4 lists every difference from the tickets.

**If in-chat fixes are wanted later:** add a few custom fields to Data Import, as FAC already does on File and User (`fixtures/custom_field.json`). That's still no new doctype.

### 3.2 Fix in the file, upload again

- FACO explains each problem in plain words and tells the user exactly what to change, for example: "rows 12, 40, 77: change *Retail* to *Retail Customers*".
- The only fix FACO makes itself is **creating a missing master**, with the existing `create_document`.
- After a new upload, FACO updates the same Data Import with the new file. Because changing the file resets the mapping (`data_import.py:44-52`), FACO then saves the mapping again in a second update.

### 3.3 Two new tools, in the existing core plugin

- **`check_import`** (read-only) fills gaps 1 and 2.
- **`start_import`** (write, one approval card) fills gap 3.
- Both go into the existing **core** plugin. No new plugin and no enable patch are needed, and admins can still turn either tool off in FAC Tool Configuration.

### 3.4 How the check works

1. **Preview.** It runs Frappe's own preview and parser (`ImportFile`, the same code Data Import uses). It returns the column-to-field matches, the importable fields not yet mapped (short: fieldname, label, required), and the preview problems as groups.
2. **Full check (the dry run).**
   - Each row is inserted exactly as Data Import would insert it (`in_import` on, emails muted), the result is recorded, and the transaction is fully rolled back.
   - **A full rollback per row, not a savepoint.** A savepoint keeps database locks until the whole run ends, which blocks other users. It also keeps Frappe's queue of jobs waiting to run after a save. A full rollback avoids both.
   - **A guard.** Any save a record tries to make on its own fails that row instead. ERPNext's Call Log hook, reached through Customer contacts, does this. Jobs queued straight away are dropped, and search indexing is off.
   - **Doctypes skipped with a warning:** Company, User, DocType, Custom Field, Property Setter, Customize Form, Accounting Dimension, File, Location, and submittable doctypes with "submit after import".
   - **Duplicates inside the file** are checked separately, because each row is rolled back on its own.
   - **Files over 500 rows** run in the background (`frappe.enqueue`). The result is saved as a private File attached to the Data Import, the way `generate_document` saves files.
3. **Failures after an import.** It reads Data Import Log and returns the same groups.

Each group has a cause, a count and up to 3 example rows. Cell values are wrapped as untrusted. The model never sees all the rows.

### 3.5 Permissions

- **Reused, nothing new:**
  - Data Import's own checks run on every save: the doctype isn't blocked, Allow Import is on, and the user has import permission (`data_import.py:59-75`).
  - Frappe's document permissions apply through the existing tools.
- **The two new tools also check:**
  - read permission on the Data Import;
  - **create** permission on the target (Insert) or **write** (Update);
  - the row limit (#34003).
- **Who can migrate:** only System Managers, unless Data Import permissions are changed (question 2).

### 3.6 Progress and approvals

- **Progress:** FACO reads it when the user asks, using `get_document` (status) and `list_documents` (log count). There's no way to push it into the chat without new frontend code (question 5).
- **Approval cards per migration:**
  - one to create the Data Import (`create_document`);
  - one per mapping change (`update_document`). FACO collects the decisions and saves them together.
  - one for any missing masters (`create_document`, one card per record) (question 7);
  - one to start the import (`start_import`).

## 4. Per ticket

### #33988 Start an import session

**What the user sees.** They say "import this". FACO lists the sheets, columns and row counts, asks which record type, and creates the Data Import. Days later, FACO finds it and carries on.

| Criterion | How it's met |
|---|---|
| Shows sheets, columns, row counts | Existing: the attachment summary, or `extract_file_content` from Claude and ChatGPT |
| Mapping and results are still there later | Existing: the Data Import record, found with `list_documents`. A check result is saved as a File on it. |
| Desk shows the file, target, step and imports | Existing: the Data Import form and log |
| Permission refused before any work | Existing: Data Import refuses the save without import permission. The new tools check create/write. |

**Build.** The file URL in the attachment summary (`helpers.py`, one line).

**Differences from the ticket.**
- No FAC Import Session doctype and no `start_import_session` tool. Data Import plus `create_document` do the job.
- Only one sheet per import: the user saves the sheet they want as its own file (verified limit, `xlsxutils.py`).

### #33989 Suggest the target DocType and column mapping

**What the user sees.** "These look like **Customers**." Then a table of *your column → ERPNext field*, with unmapped columns and missing required fields marked, and a choice card when FACO isn't sure.

| Criterion | How it's met |
|---|---|
| Proposes the doctype and says why | The model, from headers and samples (existing) |
| Column → field table, gaps marked | **New:** `check_import(mode="preview")` returns Frappe's own matches, the unmapped importable fields and the missing required ones |
| Maps by meaning ("Cust Name", "GSTIN No.") | The model proposes; it's saved in `template_options` with `update_document` (live-tested) |
| Choice card when unsure | Existing `ask_user` |
| Corrections update the mapping | Existing `update_document` |
| Child tables shown separately | Frappe's matcher already labels child fields as "Field (Table)" |

**Differences from the ticket.** No `get_import_schema` or `set_column_mapping`. The preview returns the short field list, Frappe checks fieldnames when it parses, and `update_document` saves.

### #33990 Check every row before import (dry run)

**What the user sees.** "4,812 rows ready, 188 would fail", in groups with counts and up to 3 examples. Duplicates are a group of their own. Large files run in the background.

**Build.** `check_import(mode="full")`, as in 3.4. This is the main new work.

**Differences from the ticket.**
- **No transformation step.** That's the title's "clean and reshape" (question 1).
- **A re-check runs the whole file again**, not only the rows that failed. That's simpler, and the result is the same.

### #33991 Explain errors and fix them together

**What the user sees.** "**43 rows**: Customer Group *Retail* doesn't exist. Existing groups containing 'Retail': *Retail Customers*. Create it, or change those rows in your file?"

| Criterion | How it's met |
|---|---|
| Plain cause and at least one fix per group | Groups from `check_import`; the model explains |
| Missing link: map, create or leave out | **Create:** existing `create_document`. **Map** and **leave out:** the user edits the file (FACO names the rows and the value). Closest names come from existing `search_documents`. |
| Fix becomes a rule; rows re-checked | Changed: the fix is made in the file, then the user uploads it and FACO checks again |
| Left-out rows listed in the final report | The user deletes them from the file, and FACO lists the rows it advised removing |
| "Ready" with the final count | `check_import` reports no blocking groups |

**Differences from the ticket.**
- No transformation rules. "Map" and "leave out" happen in the file.
- Closest matches use the existing "contains" search, not spelling similarity.

### #33992 Create missing masters

**What the user sees.** A plan table of the missing masters (with parents for groups and territories), then the masters are created.

**Reuse.** The setup-change-protocol skill (plan table, one confirmation, change log) and `create_document`.

**Difference from the ticket.** That's one approval card per record, not one for the whole batch. One card for a batch needs a small bulk tool, about 1 day (question 7). Undo can find created masters in Assistant Audit Log.

### #33993 Import through Data Import with one approval

**What the user sees.** One approval card: *Customer · 4,812 rows · new records*. Progress when they ask. At the end: created, failed and skipped counts, and the import in Desk.

**Build.**
- **`start_import(data_import, doctype, row_count, import_type)`** does what Desk's Start Import button does (`form_start_import`).
- The card repeats the doctype, row count and type. The tool refuses if they don't match the Data Import, so an approval given for an older version can't run.
- It refuses if the last full check found blocking problems (question 4).

**Reuse.**
- Data Import runs it, logs every row, mutes emails, and allows partial success.
- Counts come from `list_documents` on the log.
- **"Continue" after an interruption** calls `start_import` again, and Frappe skips rows already done.

**Risk.** Data Import writes its log before saving each record, so a crash at exactly that moment can log a record that wasn't saved. On "continue", the tool checks that the last logged record exists.

### #33994 Fix failed rows and re-import only those

**What the user sees.** "22 rows failed: 15 missing a Tax Category, 7 duplicate emails." After fixing (for example creating the Tax Category), "try again" re-runs only those 22. Rows that need file changes are downloaded from Desk, fixed and uploaded, then checked first.

**Reuse.**
- Frappe's Retry (`start_import` on the same Data Import) re-runs only the failed rows.
- "Export Errored Rows" and "Download Import Log" in Desk. FACO links to the Data Import.

**Build.** `check_import(mode="failures")` groups the log the same way as the check.

**Difference from the ticket.** The download is Desk's two files (the rows, and the reasons), not one file with a reason column (question 8).

## 5. Tools

| Tool | New or existing | Used for | Type |
|---|---|---|---|
| extract_file_content | Existing | Sheets, headers, samples (Claude and ChatGPT) | Read-only |
| create_document | Existing | Create the Data Import; create missing masters | Write |
| update_document | Existing | Save the mapping; attach a corrected file | Write |
| get_document | Existing | Status, row count, mapping | Read-only |
| list_documents | Existing | Find open imports; log counts | Read-only |
| search_documents (link search) | Existing | Existing names for a missing value | Read-only |
| **check_import(data_import, mode)** | **New** | mode = preview / full / failures; a job id and its progress for big files | Read-only |
| **start_import(data_import, doctype, row_count, import_type)** | **New** | Start, continue or retry the import | Write (approval card) |

## 6. Files to create and change

Paths are under `frappe_assistant_core/`.

| File | Create / change | Tickets |
|---|---|---|
| `plugins/core/tools/check_import.py` | Create | 33989, 33990, 33991, 33994 |
| `plugins/core/tools/start_import.py` | Create | 33993, 33994 |
| `plugins/core/import_check.py` (preview, full check with guard, grouping) | Create | 33990 |
| `plugins/core/plugin.py` (add the two tools) | Change | 33989, 33993 |
| `utils/tool_category_detector.py` (read-only / write lists) | Change | 33989, 33993 |
| `chat/api/chat/helpers.py` (file URL in the summary) | Change | 33988 |
| `tests/test_check_import.py`, `tests/test_start_import.py` | Create | All |

No new doctype, plugin, patch or setting. The skill that guides FACO through these steps is #34004.

## 7. Impact on existing behaviour

- **The attachment summary** gains one line, the file URL.
- **The core plugin** gains two tools.
- **Data Import records** are created from chat. They're ordinary Data Imports with emails muted.
- **Background load:** large checks run on a `long` worker, sometimes for tens of minutes. Imports use Data Import's own job.
- **What a check leaves behind:** Error Log rows, some cache entries, gaps in autoincrement names. No business records.
- **Unchanged:** every existing tool, uploads, Frappe's Data Import code.

## 8. My ideas: agree or disagree

1. **Optional target with an early permission check: agree, and it comes for free.** Data Import's own save refuses a target without import permission, and `start_import` checks create or write.
2. **Check file read and Data Import create: agree, and it's already done.** `create_document` checks Data Import create, and Frappe checks the file when parsing it.
3. **Loading a session: no new tool.** FACO finds the user's open Data Imports with `list_documents`. Data Import has no field for the chat id; a custom field could add one later if needed.
4. **Where the tools live: disagree with a new plugin.** For two tools, the core plugin is enough, and admins can still turn tools off individually.
5. **Status list: not needed.** Data Import's own status (Pending, Success, Partial Success, Error, Timed Out) plus "last check passed" cover the steps.
6. **Merge the shared pieces first: agree.** For the accounting teammate that's `check_import` and its group format, then `start_import`.

## 9. What the accounting teammate needs, and when

| They need | Ready |
|---|---|
| `check_import` (preview mode) and the group format | End of week 1 |
| `check_import` (full mode), including the decision on submittable documents | Week 2 |
| `start_import` | Week 3 |

**For them to decide:**
- **Submittable documents.** Their tickets import submittable documents, which the check skips when "submit after import" is on. Should their check insert only, or also submit inside the rolled-back transaction?
- **Opening stock.** Their area has its own Frappe tools (Stock Reconciliation, Opening Invoice Creation Tool, Chart of Accounts Importer). Data Import may not be the right path there.

## 10. Open questions for my manager

1. **#33990 title vs description.** Confirm the ticket is the dry run, and that data correction happens in the file, not as rules in chat.
2. **Who can migrate.** Data Import is System Manager only by default.
3. **File size.** Chat allows 50 MB, but Frappe refuses files over its own maximum (25 MB on this site). Raise Frappe's limit, or document 25 MB?
4. **Must a full check pass before import?** Or can the user import anyway, accepting partial success?
5. **Progress.** Is "FACO reports when asked" enough? A live progress bar in chat is about 1.5 days.
6. **Doctypes the check skips.** Is "skip with a warning" acceptable?
7. **Masters: one card per record (existing), or one card per batch** (a bulk tool, about 1 day)?
8. **Failed rows: Desk's two downloads, or one file with reasons** (half a day)?
9. **Row limit.** Frappe's docs advise "a few thousand records at a time". Default the limit to 5,000? A 50,000-row check can take over an hour.
10. **Session doctype dropped.** Is replacing the FAC Import Session doctype with the Data Import record acceptable for #33988?
11. **#33987 merge.** It's on its own branch, not yet in `test-develop`. Please confirm it merges first.

## 11. Build order and estimate

Order: #33988 (file URL) → #33989 (preview mode) → #33990 (full check) → #33991 (grouping and explanations) → #33993 (start_import) → #33994 (failures mode) → #33992 (skill guidance only, unless question 7 asks for a bulk tool).

| Ticket | Build (days) | Testing (days) | Main items |
|---|---|---|---|
| #33988 | 0.25 | 0.25 | File URL in the summary |
| #33989 | 1.5 | 1 | Preview mode: matches, unmapped and required fields, preview groups |
| #33990 | 4.5 | 2.5 | Full check: per-row rollback, guard, skip list, duplicates, background run and result file |
| #33991 | 1 | 0.5 | Group causes and examples; closest names through existing search |
| #33992 | 0 | 0.5 | Uses `create_document` and setup-change-protocol (1 day more if a bulk tool is wanted) |
| #33993 | 1 | 1 | `start_import`: approval checks, resume check |
| #33994 | 0.75 | 0.5 | Failures mode over Data Import Log |
| **Total** | **9** | **6.25** | **About 15 days (3 weeks)** |

Testing covers:
- unit tests for both tools;
- a guard test for each skipped doctype;
- a live run with a 50-row file, a 5,000-row file and the 9 MB / 200k-row file;
- one interrupted import followed by "continue";
- one run from Claude using a file URL;
- a Desk check of each Data Import and its log.
