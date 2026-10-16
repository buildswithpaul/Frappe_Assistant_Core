# How to Use send_crm_email

## Overview

Emails a Frappe CRM lead or deal exactly as CRM's own composer does
(`frappe.core.doctype.communication.email.make` on the record): the email lands on the record's Emails
tab, CRM updates the record's communication status, and it goes out from the user's own email account
(or the site's default). The user sees the email in an approval card first — To, Cc, Subject, the full
message and the sending account — and nothing is sent unless they choose Send.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doctype` | string | **Yes** | `CRM Lead` or `CRM Deal` |
| `name` | string | **Yes** | The record name |
| `subject` | string | **Yes** | Email subject |
| `message` | string | **Yes** | The complete email, HTML or plain text |
| `recipients` | array | No | Defaults to the record's email |
| `cc` | array | No | CC addresses |

## Response

`{"success": true, "communication", "recipients", "email_queued"}` or `{"success": false, "error"}`.

## Tips

- Read the record's history with `get_crm_activity` first, so the email follows up on what was actually said.
- Put the final email in `message` — the card is the draft. Do not also paste it into the chat.
- Never say it was sent until the tool returns `success: true`. If the user rejects the card, nothing was
  sent: ask what to change and call the tool again.
- Never use `send_email` for a CRM lead or deal — it would not appear on the record.
