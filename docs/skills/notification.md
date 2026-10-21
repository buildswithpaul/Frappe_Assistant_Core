# Notification

## Overview

Sends an email, a system alert or a message when something happens to a document, such as "email the sales manager when an invoice above 100,000 is submitted" or "remind the owner a week before a contract ends". This creates a `Notification` document. Follow `get_skill("setup-change-protocol")` for the plan, the confirmation and the change log. This skill covers what goes into the record.

**Who can do this:** Frappe's normal permissions apply, so anyone allowed to create notifications can. If the write is refused, relay the error in plain words. Do not turn someone away because they are not a System Manager.

**Talk to the user in business words.** Say "when an invoice is submitted", not `event` or `condition`. Never show field names, flags or option keys in what you tell the user unless they ask (for example a server-scripts flag, `custom_` names or "Insert after"). Say "server scripts are switched off", "after the Customer field", "the Required By date". See `setup-change-protocol`.

## When to use

- "Email X when Y happens", "alert the manager if X", "remind someone N days before a date".

**Not for** approvals ("someone must approve first"). That is a `Workflow` (`get_skill("set-up-approval-workflow")`), which has its own notifications.

## Workflow

1. **Ask three plain questions** with `ask_user`: what happens (saved, submitted, a date approaching), who gets it (a role, the owner, a named person), and what it should say.
2. **State the scope in one plain sentence**: "This sends one email to the Sales Manager each time a Sales Invoice is submitted above 100,000. Nothing else changes."
3. **List existing notifications** on the doctype (`list_documents` on `Notification` with `document_type`). A second one on the same event sends a second email.
4. **Be honest about the condition, and say it in words.** Tell the user the rule as a sentence ("when the grand total is over 100,000"), never as the expression, in the plan, the questions and the change log, unless they ask to see it. A condition is a Python-style expression checked on the server when the event fires, so it also applies to imports and API writes. Use company-currency `base_*` amounts or percentages, not a foreign-currency amount against a company-currency limit, and say whether item-level discounts count.
5. **Check email is set up.** Look for an outgoing `Email Account`. If there is none, tell the user the notification will be saved but nothing will be sent until one exists.
6. **Show the plan in plain words**: when it fires, who gets it, the subject and message as they will read. Create it with `enabled: 0`, which sends nothing yet, and ask the user whether to go ahead. Only after they say yes, switch it on with `enabled: 1`, sending only to the user at first (change the recipients to the user alone until the test passes). Then straight away ask them to trigger it once on a test document, and confirm what arrived. Once they are happy, set the real recipients, and offer to switch it off again if it misbehaves.
7. **Link the result**: the new notification and the form where the event happens (the result's `applies_to.url` opens a new form of that document type).

## Reference

```json
{
  "doctype": "Notification",
  "data": {
    "name": "Large invoice submitted",
    "document_type": "Sales Invoice",
    "event": "Submit",
    "enabled": 0,
    "channel": "Email",
    "condition": "doc.base_grand_total > 100000",
    "recipients": [{"receiver_by_role": "Sales Manager"}],
    "subject": "Invoice {{ doc.name }} submitted",
    "message": "<p>{{ doc.customer }} was invoiced {{ doc.get_formatted('base_grand_total') }}.</p>"
  }
}
```

- `subject` and `message` accept Jinja, with `doc` as the document.
- `Days Before` / `Days After` events use a date field and run once a day, not at the moment of change.

## Gotchas

- **Name records by what they do, never by a value that may change (no limits, percentages or dates in names):** 'Discount limit on Sales Invoice submit', not 'Block discount above 15%'. Changing a value never needs a rename. The update tool cannot rename a record; if the user wants a different name, tell them to use Rename from the record's menu in Desk.
- **A broken condition is rejected when you save**, so a saved notification has a valid one. A condition that passes the save check can still fail on some documents (for example one with a missing value). That is logged in the Error Log, and for a save or submit event it blocks saving or submitting that document, so the person's own save fails. Test the condition on a test document straight after switching the notification on, sending only to the user.
- A notification sent to a role reaches every enabled user with that role. Say how many.

## Anti-patterns

- Sending to a whole role when one person was meant.
- Switching it on without the user's go-ahead, or sending to the real recipients before one test.
- Asking the user to trigger a notification that is still switched off. It sends nothing.
- Putting a secret, a password or a private figure in the message.
