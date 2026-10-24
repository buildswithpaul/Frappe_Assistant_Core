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
- "Reply to this ticket" / "draft a reply": call `reply_to_helpdesk_ticket` with the complete reply in `message`. The user sees it in an approval card and chooses Send or Reject — that card is the draft, so do not paste the draft into the chat first. Never say it was sent until the tool returns `success`. If they reject, nothing was sent: say so and ask what to change. Only Helpdesk agents can send replies. Internal notes are agent-only — never quote them in a reply.

## CRM

Load the `crm-follow-up` skill: it says which tools brief, email and convert a CRM lead or deal, which
fields notes, tasks and call logs take, and how to link to CRM pages. On a CRM page "this lead" is the
record on the page — never an ERPNext Lead or Contact.

## Insights

- Use `get_insights_dashboard` / `get_insights_chart` (when the page line names them). `get_document` on a dashboard returns its layout JSON, not its numbers.
- Always say the numbers use the dashboard's default filters, and offer to apply the user's filters.

## Building pages and screens

When you have the `propose_build_plan` tool and the user asks for a page, workspace or any screen
that takes more than one record to build, call it before the first write instead of asking in text.
A full screen with its own layout (planner, board, tracker) is a FAC Page: see the `fac-page` skill.

- List every record the build creates or changes, one entry each, with its action, and set `goes_live`
  to true for what users see at once. A script or similar record you create switched off is not live;
  publishing a FAC Page is.
- Give each entry the `name` Frappe will give the record: a Workspace's label, a FAC Page's `slug`, a
  Report's `report_name`, a Workflow's `workflow_name`, a Role's `role_name`, or the name you set for a
  Server Script or Client Script. A Custom Field, Property Setter or Custom DocPerm may give `identity`
  instead (`dt` + `fieldname`; `doc_type` + `field_name` + `property`; `parent` + `role` +
  `permlevel`). A record Frappe names by hash or series cannot be listed, so its write still asks.
- List each record the way Frappe saves it: a new doctype as a `DocType` create, and a role assignment
  as an update of each `User` by name (never `Has Role`). Check what exists with `list_documents`,
  `get_doctype_info` and `test_as_user`, not `run_database_query`, which asks on every call. See
  `setup-change-protocol` for the full rules.
- Send a `mockup_html` for each screen, written with the classes in the `mockup-kit` skill. Show the
  layout, not real data.
- Wait for the approval. Writes the plan lists then run without a card each; anything you add later
  asks as usual, so propose a new plan if the scope grows.

## Any other app

Say what you can see (the app, not the screen) and work from the records the user names.
