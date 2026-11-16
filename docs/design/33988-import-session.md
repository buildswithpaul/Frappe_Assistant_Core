# Design: FAC Import Session (#33988)

Feature #33986 "FAC Chat: Guided data migration into ERPNext", v3.1.0
Author: Rachana · 1 October 2026 · Status: draft for approval

## 1. What we're building

This ticket adds a new doctype, **FAC Import Session**, that holds one migration's state on the server: file, sheet, target doctype, mapping, cleaning rules, last validation result, linked Data Imports and current step. Two new tools let FACO open a session for an uploaded file and load it again on a later turn. AR rebuilds the agent on every turn, so this record is the migration's only memory, and tickets #33989 to #34002 all read and write it.

## 2. How it will work

1. The user attaches `old_customers.xlsx` and says "import this".
2. FACO calls `start_import_session`. The tool checks permissions, reads the file once, and saves a session linked to this conversation. It returns the sheets, columns, row counts and sample rows, and FACO asks which sheet to use and what it contains.
3. The user says "the Customers sheet, they're customers". FACO calls the tool again with that sheet and `doctype="Customer"`. The same session comes back, and the target permission check now runs. If it fails, FACO says so and stops.
4. Later tickets save the mapping, rules, fixes, validation and imports onto the session.
5. Days later the user returns to the same conversation. FACO calls `get_import_session`, finds the open session for this conversation, and carries on from the current step.
6. In Desk, the session shows its file, target, status and the Data Imports it created.

## 3. The FAC Import Session doctype

Sessions are named `IMP-{YYYY}-{#####}`, the same style as FAC Chat Message. The doctype is in the Assistant Core module, with change tracking on. Status and the JSON fields are read-only in Desk; only the tools change them.

| Field | Type | Why |
|---|---|---|
| status | Select | Current step (see idea 5). |
| user | Link: User | Owner. Permission rules use it, as on FAC Chat Message. |
| chat_session_id | Data, indexed | The conversation it started in, so FACO can find it without the id. Empty for other MCP clients. |
| source_file | Link: File | The uploaded file. |
| sheet | Data | The chosen sheet. Empty for a CSV. |
| sheets | JSON | Each sheet's name, headers, row count and 10 sample rows, read once so later turns don't re-read the file. |
| target_doctype | Link: DocType | What we're importing into. |
| import_type | Select: Insert New Records / Update Existing Records | Same values as Data Import, so #33993 copies them across. |
| template_options | JSON | The mapping, in Data Import's own shape (see below), so #33993 can copy it straight in. |
| transformation_rules | JSON | Cleaning rules from #33990. Empty for now. |
| validation_summary | JSON | Last dry-run result from #33990. Empty for now. |
| data_imports | Table (data_import link, purpose Import / Retry) | Each Data Import the session creates (#33993, #33994), shown as links in Desk. Undo (#34002) works from these. |

The mapping is an object with one key, `column_to_field_map`:
- Its keys are column positions as strings ("0", "1", ...), not header names. Frappe looks columns up by position.
- Its values are a fieldname, `child_table.fieldname`, or `Don't Import`.

Later tickets can add fields when they need them (for example, row fixes in #33991 or created masters in #33992). Adding a field doesn't affect existing sessions.

## 4. Tools

Both tools go in a new `data_migration` plugin (idea 4). Each sets `requires_permission = "FAC Import Session"`, so users who can't read sessions don't see them.

**`start_import_session(file_url, sheet=None, doctype=None, import_type="Insert New Records")`**
- Returns the session id, status and file name, plus each sheet's name, columns, row count and sample rows.
- If this conversation already has an open session for the same file, it returns that session and fills in the new sheet or doctype instead of creating a duplicate.
- It counts as a write tool because it creates a record, like `generate_document` does.

**`get_import_session(session=None)`**
- Returns everything on the session.
- Without an id, it returns the current conversation's open session.
- If there is none, or more than one, it lists the user's open sessions to choose from.
- It is read-only.

The argument is named `doctype` rather than `target_doctype`, for two reasons. It matches `create_document` and #33989's `get_import_schema(doctype)`. And the audit log only fills its Target DocType column from an argument called `doctype`.

**Reading the file:**
- **How:** in the same request, using `extract_file_content` the way chat already does, once per session. The result goes into `sheets`.
- **Why there's no background job here:** the user needs the sheet list on the same turn, and most exports are small. The 9 MB / 200k-row file (about 32 s) also fits Frappe's default 120 s production timeout.
- **Where background jobs belong:** #33990, whose dry run reads every row, and #33993, where Data Import already runs in the background.
- **When to revisit:** if AR's tool timeout is shorter (question 3).

## 5. Permission checks

One shared helper, `check_import_access`, holds all the checks:
- **Who calls it:** `start_import_session` now, and later #33989 and #33993.
- **When it runs:** before the file is read or anything is saved.
- **On failure:** it raises a PermissionError with a plain message. BaseTool logs it as "Permission Denied" in the Assistant Audit Log, and FACO tells the user.

| Check | When |
|---|---|
| The user can read the file under Frappe's own File rule: public, their own upload, shared with them, or attached to a document they can read. A chat upload is attached to the sender's message, so only the sender passes. | Every start |
| The user can create a Data Import (#33993 imports through it). | Every start |
| The target can be imported into: Allow Import is on, and it isn't a child table, a Single, or a doctype Data Import blocks. The user also needs **create** (Insert) or **write** (Update) on it, plus **import** permission. | Once the doctype is known: at start, or when #33989 sets it |
| The user owns the session (System Manager sees all). A permission query and has_permission hook enforce this, as for FAC Chat Message. | Every get, and every later tool |

Who can do what with the doctype:
- **System Manager:** everything.
- **All:** create, read and write their own sessions. They can't delete, so undo history isn't lost.

## 6. Files to create and change

Paths are under `frappe_assistant_core/`.

**Create:**
- `plugins/data_migration/plugin.py`: the new plugin and its tool list.
- `plugins/data_migration/tools/start_import_session.py` and `get_import_session.py`: the two tools.
- `plugins/data_migration/permissions.py`: the shared checks, reused by later tickets.
- `assistant_core/doctype/fac_import_session/`: the doctype and its owner-only permission functions.
- `assistant_core/doctype/fac_import_session_data_import/`: child table of linked Data Imports.
- `docs/skills/import_session.md`, plus an entry in `data/system_skills.json`: tells FACO when to start a session and when to load one, as other tools have.
- `tests/test_fac_import_session.py`: tests.

**Change:**
- `hooks.py`: register the permission query and has_permission hook.
- `utils/tool_category_detector.py`: mark `start_import_session` as write and `get_import_session` as read-only, so chat's approval defaults are right.
- `chat/api/chat/helpers.py`: add the file URL to the attachment summary FACO receives. Today FACO only gets the file name, so it has nothing to pass to `start_import_session`.

## 7. Impact and risks

**What changes for existing users** (very little):
- FACO's hidden attachment summary gains one line, the file URL.
- A "Data Migration" plugin appears in FAC Admin. It turns itself on, except on older sites that still carry the old plugin-list setting, where an admin must turn it on.
- Two new tools appear in the tool list.
- Data Import, uploads and `extract_file_content` are unchanged.

**Risks:**
- **Large files are read twice.** If a file is attached and "import this" is said in the same message, chat reads it for the summary and the tool reads it again. For the 9 MB file that's about a minute before FACO replies. A short cache keyed on the file's content would remove the second read (about half a day).
- **Data Import reads only the first (or active) sheet of a workbook.** If the user picks another sheet, #33993 must write it out as its own file. That fits with #33990, which already writes a cleaned file, but #33993 must plan for it.
- **The mapping is by column position.** The file handed to Data Import must keep the original column order. The header list stored on the session lets us check that.
- **Data Import is System Manager-only by default.** So this check limits migration to System Managers unless an admin grants access to other roles (question 1).
- **The source file may be deleted while the session still needs it.** Chat retention deletes the files of archived chats older than 180 days, which leaves the session pointing at a deleted file. Each Data Import keeps its own file (#33993), so retry and undo still work.
- **Some callers don't send the conversation id.** Older AR versions and other MCP clients leave it out, so `get_import_session` lists open sessions instead of finding the right one.
- **The file reader is stricter than Frappe.** `extract_file_content` refuses non-System Managers a private file that isn't attached to anything. Chat uploads are attached, so chat is fine. A Desk upload by an ordinary user would be refused.

## 8. Your ideas: agree or disagree

1. **Permission timing: agree, with two changes.** I'd name the argument `doctype`. I'd also check **import** permission and Allow Import as well as create, because Data Import checks both. Checking create alone would let a session reach #33993 and fail there.
2. **File read + Data Import create: agree.** I'd use Frappe's standard File rule rather than writing our own. Note this means System Manager only by default (question 1).
3. **Finding the session: both, as one design.** Store the conversation id on the session, and add `get_import_session`, which uses it by default.
   - Tools already receive the id in the `X-AR-Session-Id` header; the browser tools use it today.
   - A tool alone would rely on the model remembering the id through a long chat.
   - A link alone needs something to load the session. Doing that in send-message would add work to every chat turn.
4. **Where the tools live: a new `data_migration` plugin.**
   - `data_science` also holds `run_python_code` and `run_database_query`. Admins often turn it off for safety, and that would take migration with it.
   - `faco` follows the chat toggle, which would hide the tools from Claude Desktop users.
   - About eight tools are coming, so they warrant their own group. They can still reuse the `data_science` file reader.
5. **Status values: agree, plus two.**
   - **The list:** Draft → Mapped → Validated → Importing → Completed / Partially Imported / Failed → Undone, plus Cancelled.
   - **Partially Imported** matches Data Import's "Partial Success" and is where the retry in #33994 starts.
   - **Cancelled** lets a user drop a session so FACO won't resume it.
   - **Rules:** Validated means the last dry run had no blocking errors. Changing the mapping or rules clears the validation and goes back to Mapped. Undo is allowed from Completed or Partially Imported.

## 9. Open questions for my manager

1. **Who may migrate?** Should Data Import stay System Manager-only (the default and safest), or be granted to another role such as Assistant Admin?
2. **Should `start_import_session` ask for approval?** As a write tool, it asks the user to approve it by default. It could be treated as read-only, since it only creates a tracking record. Tools that change ERPNext data would keep asking either way.
3. **How long can one tool call take in AR?** If the limit is under about 60 s, this ticket needs a background read with a "your file is ready" follow-up, adding 1.5 to 2 days.
4. **Can #33988 be accepted on part of criterion 2?** It names mapping, fixes and validation, which only exist after #33989 to #33991. I propose accepting #33988 when whatever is stored on a session comes back on a later turn. The full check would be repeated in those tickets.
5. **Is a dead file link after 180 days acceptable?** The alternative is for each session to keep its own copy of the file.

## 10. Rough estimate

| Work | Days |
|---|---|
| Doctype, child table, permission hooks | 0.5 |
| Shared permission check | 0.5 |
| `start_import_session` (CSV, xlsx, xls; reuse reader; no duplicates) | 1 |
| `get_import_session` | 0.5 |
| Plugin, tool types, skill doc, attachment-summary line | 0.5 |
| **Build** | **3** |
| Unit tests: each permission case, file types, missing conversation id, starting twice | 1 |
| Manual run in FAC Chat (small file and the 9 MB file, over several turns) and Desk check | 1 |
| **Testing** | **2** |

That's about 5 days, plus 1.5 to 2 days if question 3 means a background read.
