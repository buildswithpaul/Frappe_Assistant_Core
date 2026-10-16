# How to Use reply_to_helpdesk_ticket

## Overview

Sends a reply to the customer on a Helpdesk ticket through Helpdesk's own reply flow — the same
thing that happens when an agent clicks Reply in Helpdesk. The reply is added to the ticket thread,
emailed to the person who raised the ticket from the support account, and counts towards first
response and SLA.

Before it runs, the user sees the reply in an approval card (To, Cc, Subject, the full message) and
chooses Send or Reject. Nothing is sent unless they approve.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ticket` | string | **Yes** | HD Ticket name |
| `message` | string | **Yes** | The complete reply, as HTML |
| `cc` | array | No | CC email addresses |

The recipient is always the ticket's `raised_by`; there is no `to` parameter.

## Response

`{"success": true, "ticket", "communication", "email_queued"}` or `{"success": false, "error"}`.

`email_queued: false` means Helpdesk is set not to email agent replies: the reply is on the ticket
but the customer was not emailed. Say so.

## Tips

- Read the ticket and its thread first (`get_document` / `list_documents` on `Communication`) so the
  reply answers the customer's latest message.
- Put the complete, final reply in `message` — the card shows exactly that. Do not also paste the
  draft into the chat.
- Never say the reply was sent until the tool returns `success: true`.
- If the user rejects the card, nothing was sent. Say so and ask what to change, then call the tool
  again with the revised reply.
- Only Helpdesk agents can reply. If the tool says so, tell the user instead of retrying.
- Never quote internal notes (`HD Ticket Comment`) in a reply — the customer must not see them.
