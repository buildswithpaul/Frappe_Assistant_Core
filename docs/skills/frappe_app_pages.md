# Working in Frappe Apps (Helpdesk, CRM, Insights)

## When this applies

The system prompt has a **Page Context** section when the user is chatting from the FACO
widget inside another Frappe app. Desk pages do not use it (you have browser tools there).

## Reading the page line

- **"The user is viewing <DocType> <name> in <App>…"** — that document is open. Read it with the tool the line names before answering "what is this?", "summarise this" or "what should I reply?".
- **"The user is on a <App> page."** — no single document is open, or the user cannot read it. Ask which record they mean, or find it with `list_documents` / `search_documents`. Never guess a record.

## What does not work outside Desk

You cannot read the screen, navigate, take screenshots or see filters the user changed. Do not
offer those. Links to Desk pages in your answer open in a new tab, so the user keeps their place.

## Helpdesk

- **HD Ticket** key fields: `subject`, `status` with `status_category` (Open / Paused / Resolved), `priority`, `ticket_type`, `agent_group` (team), `customer`, `contact`, `raised_by` (email), SLA `response_by` / `resolution_by` / `agreement_status`, `first_responded_on`, `resolution_date`, `feedback_rating`.
- The **conversation** is `Communication` rows with `reference_doctype = "HD Ticket"` and `reference_name = <ticket>` — list them oldest first to follow the thread; the customer's latest message is usually the last one with `sent_or_received = "Received"`.
- **Internal notes** are `HD Ticket Comment` (`reference_ticket`, `content` (HTML), `commented_by`). They are never shown to the customer — do not quote them in a reply draft.
- **History** (assignments, status changes) is `HD Ticket Activity` (`ticket`, `action`).
- "Summarise this ticket": subject, status, priority, customer, what the customer asked, what was answered, what is pending, SLA risk.
- "Draft a reply": draft only — sending a reply is the agent's action in Helpdesk.

## CRM

(From the Frappe CRM code; not verified on a live install — check field names with `get_doctype_info` if a call fails.)

- **CRM Lead**: `lead_name`, `first_name`, `last_name`, `organization`, `email`, `mobile_no`, `status`, `source`, `industry`, `lead_owner`, `converted`.
- **CRM Deal**: `organization`, `status`, `deal_value`, `expected_deal_value`, `expected_closure_date`, `probability`, `deal_owner`, `next_step`, `lost_reason`, `lead`.
- **Notes** are `FCRM Note`, **tasks** `CRM Task`, **calls** `CRM Call Log` — each linked by `reference_doctype` + `reference_docname`.

## Insights

- Use `get_insights_dashboard` / `get_insights_chart` (when the page line names them). `get_document` on a dashboard returns its layout JSON, not its numbers.
- Always say the numbers use the dashboard's default filters, and offer to apply the user's filters.

## Any other app

Say what you can see (the app, not the screen) and work from the records the user names.
