# Following Up on Frappe CRM Leads and Deals

## When this applies

The user works in Frappe CRM (`/crm`) — usually from the FACO widget on a lead or deal page, where the
Page Context line names the record. On that page, "this lead", "the deal", "her", "him" mean **that
record**. Never search ERPNext `Lead`, `Contact` or `Opportunity` for a CRM record; CRM's are
`CRM Lead`, `CRM Deal`, `CRM Organization` and CRM's own Contacts.

## Brief me / what's next

Call `get_crm_activity` first — the lead or deal row does not contain its emails, notes, calls or tasks.
Then answer from the timeline: who they are, last contact, what was discussed (notes, emails), open tasks,
and a concrete next step. Never say "no contact yet" without having read the timeline.

## Email a lead or deal

Use `send_crm_email` with the complete email in `message`. The user approves it in a card; that card is
the draft, so do not paste it into the chat first. Never claim it was sent before the tool returns
`success`. If they reject it, nothing was sent — ask what to change. Never use `send_email` for a CRM
record: it would not appear on the record's Emails tab.

## Convert and advance

- Convert a lead with `convert_crm_lead` — never by creating a `CRM Deal` with `create_document`.
- Move a deal with `update_document` on `CRM Deal`: `status` (Qualification 10% → Demo/Making 25% →
  Proposal/Quotation 50% → Negotiation 70% → Ready to Close 90% → Won / Lost), `expected_deal_value`,
  `expected_closure_date`, `next_step`. Lost needs `lost_reason` (and `lost_notes` when the reason is
  "Other"). CRM keeps the status log and probability itself.
- Lead statuses: New, Contacted, Nurture, Qualified, Converted, Unqualified, Junk.

## After a call: notes, tasks, call logs

Create one record per thing asked, always linked with `reference_doctype` (`CRM Lead`/`CRM Deal`) and
`reference_docname` (the record name), using `create_document`:

| Asked | DocType | Fields |
|---|---|---|
| A note | `FCRM Note` | `title`, `content` |
| A follow-up / to-do | `CRM Task` | `title`, `description`, `due_date` (Datetime), `priority` Low/Medium/High, `status` Todo, `assigned_to` (the user; CRM creates the assignment) |
| A call that happened | `CRM Call Log` | `type` Outgoing/Incoming, `status` Completed, `from`, `to` (phone numbers; use the record's `mobile_no`), `duration` (seconds), `telephony_medium` "Manual" |

A note is an `FCRM Note`, not text inside a task. Report exactly the records the tools created.

## Links

Link records to the CRM app: `/crm/leads/<name>`, `/crm/deals/<name>`, `/crm/contacts/<name>`,
`/crm/organizations/<name>`. Never `/app/crm-lead/…` — that is Desk.

## Without the CRM tools

Outside FAC Chat (another MCP client), or with the FACO plugin off, `get_crm_activity`,
`send_crm_email` and `convert_crm_lead` do not exist:

- Read the timeline with `list_documents` on `FCRM Note`, `CRM Task` and `CRM Call Log` filtered by
  `reference_docname`, and on `Communication` filtered by `reference_name`.
- Say plainly that sending CRM email and converting a lead are not available here, and point the user to
  CRM's **Reply** and **Convert to Deal** buttons. Never hand-build a deal or send the email another way.
