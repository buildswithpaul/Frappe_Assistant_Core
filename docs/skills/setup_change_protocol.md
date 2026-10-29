# Setup Change Protocol

## Overview

The safety procedure for changing how a site is set up — creating a company, fiscal year, account, warehouse or tax template, adding a custom field, setting up an approval workflow, changing naming series or a Settings page. Setup mistakes are expensive: a wrong chart of accounts or tax setup made today is posted against by every transaction after it. So you **plan, confirm, dry-run, then write**, and you leave a record of what you changed and how to undo it.

Every other setup skill (`add-custom-field`, `server-script`, `client-script`, `print-format`, `custom-report`, `notification-setup`, `fac-page`, `set-up-approval-workflow`, `configure-naming-series`, `guided-setup`) follows this protocol.

## When to use

- Before any create or update of setup or configuration records, or of more than a handful of master records at once.
- When a health check finding is being fixed.

**Not for** ordinary day-to-day documents (one invoice, one customer) — the normal approval card covers those.

## Workflow

**Plain words, always.** Never show field names, flags or option keys (such as a server-scripts flag, `custom_` names, "Insert after" or a date field's code name) in text for the user unless they ask. Say "the Required By date", "after the Customer field", "server scripts are switched off". The same goes for conditions: write them as a sentence ("when the grand total is over 100,000"), never as an expression such as `eval:doc.base_grand_total > 100000`, in the plan, the questions and the change log. Show the expression only if the user asks for it.

1. **Check who you're working for.** `Custom Field`, `Property Setter`, `Workflow`, `Workflow State`, `Workflow Transition`, `Role`, `DocType`, `Server Script`, `Client Script` and a shared `FAC Page` (also `Custom DocPerm`, `User Permission` and similar permission records) are write-protected for everyone except a **System Manager**. Any Desk user may build a personal FAC Page that only they can open (`fac-page`). If the user isn't one, say so up front and stop. Don't attempt the write to find out. `Report`, `Print Format` and `Notification` are not on that list: normal permissions apply, so try the write and relay a refusal in plain words. Query and Script Reports need the Script Manager role.
2. **Read the current state** with `list_documents`, `get_document` and `get_doctype_info` (and `test_as_user` for who can reach what), not `run_database_query`, which asks for approval on every call. To see who holds a role, call `list_documents` on `User` with `filters: {"Has Role.role": "<role>"}`. Look at what already exists before planning — the field may already be there, the fiscal year may exist, the template may be disabled rather than missing. Never plan a duplicate.
3. **Write the plan as a table** and show it. Use plain business language in every cell ("Add a Sales Channel choice to Sales Invoice"), not field names or code; keep those inside the write itself and mention them only if the user asks:

   | # | Action | DocType | Record | Key values | Undo |
   |---|---|---|---|---|---|
   | 1 | Create | Workflow State | Pending Approval | style: Warning | Delete it |
   | 2 | Update | Stock Settings | Stock Settings | allow_negative_stock: 1 → 0 | Set it back to 1 |

   Order it by dependency — whatever a later row links to comes first. For every Update row, record the **current** value (read it now) so the undo is real.
4. **Name the hard-to-undo rows.** Call these out in a sentence under the table:
   - A new **Company** creates its chart of accounts, warehouses, cost centre and (with India Compliance) GST templates in one go. It can't be deleted once anything is posted against it.
   - The **chart of accounts template**, the **fiscal year dates** and the **stock valuation method** can't be changed once transactions exist. The same goes for an item's batch/serial tracking once it has stock transactions.
   - An activated **Workflow** immediately stamps a state on every existing document of that type and changes who can edit them.
   - Deleting a **Custom Field** removes it from the form but keeps its database column and values, so a later field with the same name picks the old values up.
5. **Confirm once, then wait.** `ask_user` with `confirm`, stating the count and scope: "Create these 4 records and change 1 setting?" Wait for the answer before any write, including a dry run. No answer is not a yes. The per-write approval cards still appear after that, and for a customisation (field, script, workflow, report, print format, notification) "Don't ask again" never applies, so expect a card for every write that has an effect unless it is on an approved build plan. Edits to a script that is switched off need no card; switching it on, or changing a live one, asks. This confirmation is for the plan as a whole; a build plan card replaces it (see below).
6. **Dry-run each create.** Call `create_document` with `validate_only: true`. It runs what a save runs before writing (link checks, the doctype's own `validate()` and any Before Insert, Before Validate or Before Save rule), then undoes it and saves nothing. It does *not* check mandatory fields or duplicate names, so the real insert can still fail. `update_document` has no dry run at all.
7. **Execute in order, one write at a time.** Stop at the first failure. Don't improvise a workaround write that isn't in the plan — report what failed and what's still pending, and re-plan with the user.
8. **Close with the change log**: the same table, now with a Result column and a link to every record. This is the user's undo list, so keep it accurate.

## Plan before a multi-record setup

When you have the `propose_build_plan` tool, call it before creating or changing two or more setup records.
A personal page (a FAC Page left at "Only me") is not a setup change: build it without a plan or a
confirmation, as `get_skill("pages-in-chat")` says.
List every change, mark the ones that go live, and wait for the approval. Writes the plan lists
then run without a card each, except publishing a FAC Page, switching a rule on or changing live code
(the code or audience of a published page, the code of a rule that is on, a report's or print format's
code, a workflow transition's condition, a notification recipient's condition, cc or bcc, or a field's
`eval:` condition on a form other people use); anything else still asks. The plan card then stands in for the confirmation in step 5. Give each entry the `name` Frappe will give the record (a Report's
`report_name`, a Workflow's `workflow_name`, a Role's `role_name`, a FAC Page's `slug`, the name you
set for a script),
or for a Custom Field, Property Setter or Custom DocPerm its `identity` fields. A record Frappe
names by hash or series cannot be listed, so its write still asks.

List each change the way Frappe saves it:

- **A new doctype** is a `DocType` create named after it, not an entry for the new doctype itself.
- **A role assignment** is an update of each `User` by name. `Has Role` is a child table, and a child
  row is always saved through its parent, so list the parent record.
- **Switching a rule on** (a script or Notification built switched off) is its own update entry marked
  `goes_live`, so the user sees it coming. Publishing a page or switching a rule on still
  asks once, with the final code, even when it is on the plan: the code was written after the plan
  was approved.
- **Mark `goes_live` honestly.** Mark a new Role, DocType, Custom Field, permission and anything else
  without an on/off switch as going live. A plan entry carries no field values, so FAC cannot prove such
  a record is dormant and shows it under Goes live to be safe. Only a Server Script, Client Script,
  Notification or FAC Page created switched off (or unpublished, or personal) can stay dormant, and an update of one
  that is on now goes live.

FAC checks the plan before the card shows. An entry it cannot match to a save comes back to you with
the reason: fix the entry and propose again. A dormant claim FAC cannot prove is shown as going live.

## Building and checking without probe scripts

1. **Look it up first.** Read how the thing works (`sandbox_reference` for script code, `get_doctype_info` for fields) instead of guessing or creating a throwaway record to find out.
2. **Build it switched off.** A script that is switched off changes nothing, and a switched-off Server Script needs no approval card.
3. **Switch it on with one card**, shown even when the plan lists it, then trigger it or open the page it changes. For a form or page, look with `browser_take_screenshot` / `browser_capture_diagnostics`. Trigger a rule with `create_document` and `validate_only: true`, never by creating real records and deleting them, and never as another user.
4. **If it fails, read `recent_errors`**, filtered by the record's name, then fix and trigger again.
5. **Check who can use it** with `test_as_user`.

## Gotchas

- **Name records by what they do, never by a value that may change (no limits, percentages or dates in names):** 'Discount limit on Sales Invoice submit', not 'Block discount above 15%'. Changing a value never needs a rename. The update tool cannot rename a record; if the user wants a different name, tell them to use Rename from the record's menu in Desk.
- **Single doctypes** (Stock Settings, Selling Settings, Accounts Settings…) are updated with `name` equal to the doctype name.
- **A setting change applies to future transactions only.** Turning off negative stock doesn't fix existing negative stock. Say so, so the user doesn't expect it to.
- **Check as you build.** Use the loop under "Building and checking without probe scripts" above; don't test on a copy or create a throwaway record to find out how something works.
- **"Publish it" means publish.** Anything else still waiting, such as a rule still switched off or a test, goes on the plan or is raised before publishing, not done unasked.
- **One plan, one purpose.** Don't fold an unrelated "while I'm here" fix into someone's plan. Offer it separately afterwards.

## Anti-patterns

- Writing first and explaining afterwards.
- Pasting a raw condition (`eval:doc...`) into the plan or the change log instead of saying it in words.
- A plan that says "configure GST" instead of listing the actual records.
- Treating a passed `validate_only` as proof the insert will succeed.
- Updating a record without noting its old value, so it can't be undone.
