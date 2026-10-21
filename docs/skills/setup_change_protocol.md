# Setup Change Protocol

## Overview

The safety procedure for changing how a site is set up — creating a company, fiscal year, account, warehouse or tax template, adding a custom field, setting up an approval workflow, changing naming series or a Settings page. Setup mistakes are expensive: a wrong chart of accounts or tax setup made today is posted against by every transaction after it. So you **plan, confirm, dry-run, then write**, and you leave a record of what you changed and how to undo it.

Every other setup skill (`add-custom-field`, `server-script`, `client-script`, `print-format`, `custom-report`, `notification-setup`, `set-up-approval-workflow`, `configure-naming-series`, `guided-setup`) follows this protocol.

## When to use

- Before any create or update of setup or configuration records, or of more than a handful of master records at once.
- When a health check finding is being fixed.

**Not for** ordinary day-to-day documents (one invoice, one customer) — the normal approval card covers those.

## Workflow

**Plain words, always.** Never show field names, flags or option keys (such as a server-scripts flag, `custom_` names, "Insert after" or a date field's code name) in text for the user unless they ask. Say "the Required By date", "after the Customer field", "server scripts are switched off". The same goes for conditions: write them as a sentence ("when the grand total is over 100,000"), never as an expression such as `eval:doc.base_grand_total > 100000`, in the plan, the questions and the change log. Show the expression only if the user asks for it.

1. **Check who you're working for.** `Custom Field`, `Property Setter`, `Workflow`, `Workflow State`, `Workflow Transition`, `Role`, `DocType`, `Server Script` and `Client Script` (also `Custom DocPerm`, `User Permission` and similar permission records) are write-protected for everyone except a **System Manager**. If the user isn't one, say so up front and stop. Don't attempt the write to find out. `Report`, `Print Format` and `Notification` are not on that list: normal permissions apply, so try the write and relay a refusal in plain words. Query and Script Reports need the Script Manager role.
2. **Read the current state.** Look at what already exists before planning — the field may already be there, the fiscal year may exist, the template may be disabled rather than missing. Never plan a duplicate.
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
5. **Confirm once, then wait.** `ask_user` with `confirm`, stating the count and scope: "Create these 4 records and change 1 setting?" Wait for the answer before any write, including a dry run. No answer is not a yes. The per-write approval cards still appear after that, and for a customisation (field, script, workflow, report, print format, notification) "Don't ask again" never applies, so expect a card for every write. This confirmation is for the plan as a whole.
6. **Dry-run each create.** Call `create_document` with `validate_only: true`. **It only runs the doctype's own `validate()`.** It does *not* check mandatory fields, whether linked records exist, or duplicate names, so the real insert can still fail. Check links yourself beforehand (`search_documents` with `purpose: "link_value"`). `update_document` has no dry run at all.
7. **Execute in order, one write at a time.** Stop at the first failure. Don't improvise a workaround write that isn't in the plan — report what failed and what's still pending, and re-plan with the user.
8. **Close with the change log**: the same table, now with a Result column and a link to every record. This is the user's undo list, so keep it accurate.

## Gotchas

- **Name records by what they do, never by a value that may change (no limits, percentages or dates in names):** 'Discount limit on Sales Invoice submit', not 'Block discount above 15%'. Changing a value never needs a rename. The update tool cannot rename a record; if the user wants a different name, tell them to use Rename from the record's menu in Desk.
- **Single doctypes** (Stock Settings, Selling Settings, Accounts Settings…) are updated with `name` equal to the doctype name.
- **A setting change applies to future transactions only.** Turning off negative stock doesn't fix existing negative stock. Say so, so the user doesn't expect it to.
- **Test on a copy first** when the user has a staging or test site and the change is on the hard-to-undo list. Recommend it; don't insist.
- **One plan, one purpose.** Don't fold an unrelated "while I'm here" fix into someone's plan. Offer it separately afterwards.

## Anti-patterns

- Writing first and explaining afterwards.
- Pasting a raw condition (`eval:doc...`) into the plan or the change log instead of saying it in words.
- A plan that says "configure GST" instead of listing the actual records.
- Treating a passed `validate_only` as proof the insert will succeed.
- Updating a record without noting its old value, so it can't be undone.
