# Set Up an Approval Workflow

## Overview

Turns a plain-language approval rule into a Frappe `Workflow`, for example "purchase orders above ₹50,000 need the purchase manager's approval" or "every leave application goes to HR". A workflow replaces a document's Submit button with actions (Approve, Reject…). Each action is allowed for a role, can be limited by a condition, and moves the document into a state. Follow `get_skill("setup-change-protocol")` for the plan, the confirmation and the change log.

**Only a System Manager can do this.** `Workflow`, `Workflow State` and `Workflow Transition` are write-protected for every other role.

## When to use

- "Approval needed above X", "X must be approved by Y before it's submitted", "add an approval step to Z".

**Not for** a one-off approval ("ask my manager about this PO"). Not for notifications only; that's a `Notification`.

## Workflow

1. **Pin down the rule.** Use `ask_user` if the request doesn't answer these:
   - Which doctype?
   - What threshold, and in which currency?
   - Who submits it (a role), and who approves it (a role)?
   - What happens on rejection: does it go back for editing, or is that the end?
2. **Check the roles exist and have users.** Each role must exist as a `Role`, and at least one enabled `User` must hold it (a `User` with a `Has Role` row for that role). A transition allowed for a role nobody holds leaves documents stuck with nobody able to move them.
3. **Check for an existing workflow** on the doctype (`list_documents` on `Workflow`, `document_type` = the doctype). **Only one workflow per doctype can be active.** Activating yours deactivates the other one, so tell the user.
4. **Make sure the states and actions exist.** Frappe ships the states `Pending`, `Approved` and `Rejected` and the actions `Approve`, `Reject` and `Review`. Anything else, such as a `Draft` or `Cancelled` state or a `Send for Approval` action, has to be created first (`Workflow State` with `workflow_state_name`; `Workflow Action Master` with `workflow_action_name`). Those go at the top of the plan.
5. **Plan, confirm and create** through the protocol. Create the workflow with `is_active: 1`, because **the doctype default is 0 and an inactive workflow does nothing.**

## Reference: "Purchase Orders above ₹50,000 need a Purchase Manager's approval"

```json
{
  "doctype": "Workflow",
  "data": {
    "workflow_name": "Purchase Order Approval",
    "document_type": "Purchase Order",
    "is_active": 1,
    "workflow_state_field": "workflow_state",
    "states": [
      {"state": "Draft",     "doc_status": "0", "allow_edit": "Purchase User"},
      {"state": "Pending",   "doc_status": "0", "allow_edit": "Purchase Manager"},
      {"state": "Approved",  "doc_status": "1", "allow_edit": "Purchase Manager"},
      {"state": "Rejected",  "doc_status": "0", "allow_edit": "Purchase User"},
      {"state": "Cancelled", "doc_status": "2", "allow_edit": "Purchase Manager"}
    ],
    "transitions": [
      {"state": "Draft", "action": "Submit", "next_state": "Approved",
       "allowed": "Purchase User", "condition": "doc.base_grand_total <= 50000"},
      {"state": "Draft", "action": "Send for Approval", "next_state": "Pending",
       "allowed": "Purchase User", "condition": "doc.base_grand_total > 50000"},
      {"state": "Pending", "action": "Approve", "next_state": "Approved",
       "allowed": "Purchase Manager", "allow_self_approval": 0},
      {"state": "Pending", "action": "Reject", "next_state": "Rejected",
       "allowed": "Purchase Manager"},
      {"state": "Rejected", "action": "Send for Approval", "next_state": "Pending",
       "allowed": "Purchase User"},
      {"state": "Approved", "action": "Cancel", "next_state": "Cancelled",
       "allowed": "Purchase Manager"}
    ]
  }
}
```

Before this is created, `Draft` and `Cancelled` (Workflow State) and `Submit`, `Send for Approval` and `Cancel` (Workflow Action Master) must already exist.

- **`doc_status`** is what the state does to the document: `0` Draft, `1` Submitted, `2` Cancelled. Moving into a `1` state submits it, so the Approve action is the submit.
- **`allow_edit`** is the role that can edit the document while it sits in that state.
- **`condition`** is a Python expression over `doc`. Every transition out of a state that has a condition needs a partner that covers the other side (`<=` and `>`). Otherwise some documents have no action available.

## Gotchas

- **Self-approval is on by default.** `allow_self_approval` defaults to `1`, so a Purchase Manager who creates a PO can approve their own. Set it to `0` on the approval transition, or the control means nothing.
- **Use `base_grand_total` for a money threshold.** `grand_total` is in the document's own currency, so a USD order of 1,000 compares 1,000 to 50,000. `base_grand_total` is in the company currency.
- **Existing documents are stamped when the workflow is saved.** Frappe gives every existing document with no state the **first** state in the table that has its `doc_status`. The order of `states` decides that: already-submitted POs become `Approved` here.
- **The standard Submit button disappears.** Users act through the workflow's action buttons. Warn them before it goes live.
- **Nobody holds the role → documents are stuck.** Re-check step 2 before activating.
- `workflow_state_field` is created as a field on the doctype automatically if it doesn't exist. Don't create it yourself.

## Anti-patterns

- Creating the workflow before the states and actions it links to exist.
- One transition with a condition and no partner for the other side of the threshold.
- Leaving the workflow inactive and telling the user it's set up.
