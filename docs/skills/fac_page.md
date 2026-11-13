# FAC Page

## Overview

A `FAC Page` is a full screen with its own layout, such as a planner, a board or a tracker, stored as a record and opened at `/app/fac-pages/<name>`. Follow `get_skill("setup-change-protocol")` for the plan and the change log of a shared page. A personal page (left at "Only me") needs no plan: follow `get_skill("pages-in-chat")`. This skill covers what goes into the record.

**Personal or shared.** `visibility` is `"Only me"` (the default) or `"Shared"`.

- **Personal** ("Only me"): any Desk user can build one. It opens only for its owner, not even for System Managers, and it loads and runs as soon as it is saved, inside a walled-off frame: its script reads only what its owner may and asks them before anything else. So the owner's own creates and changes need no approval card. A shared page's script runs in Desk itself, because it was approved on the publish card. Its record name is the slug plus a six-character tag for the owner (`sales-summary-3fa9c1`), so use the `name` and `page_url` from the create result, never the slug alone. For a report or summary built in chat, follow `get_skill("pages-in-chat")`.
- **Shared**: opens for the roles you list, once published. Its name is the slug. Only a System Manager can share a page, publish it, give it roles or change a shared page. If the user is not a System Manager, say so and offer a personal page instead. People with those roles find it under **FAC Pages** in the Desk sidebar (`/app/fac-pages`), which lists every page they can open, even without FAC Chat; tell the user that when the page goes live.

Website users cannot build pages, and a page cannot be shared with Frappe's Share button.

## When to use

- The user wants a screen of their own: a planner, a board, a tracker, a page that reads and writes records in one place.

**Not for** cards, shortcuts and charts. Use a `Workspace` for those.

## Workflow for a shared page

1. **Plan it.** For a shared page, when you have the `propose_build_plan` tool, list the page with its `slug` as the `name`, mark it as going live, and send a `mockup_html` written with the `mockup-kit` classes. List what the page needs the way Frappe saves it: a new doctype as a `DocType` create, a role for the page as a `Role` create (it goes live), and giving that role to people as an update of each `User` by name, never `Has Role`. If a rule the page relies on is built switched off, list switching it on as its own update entry, marked as going live, so the user sees it coming. List how people reach the page too: the update of the Workspace that links it (step 5), unless the user says not to link it. A new doctype's `module`, and a new Workspace's, must be a module installed on this site: check with `list_documents` on `Module Def` (fields `name`, `app_name`) and pick from that list. Never assume a module such as HR or CRM exists; it is missing on a site without that app.
2. **Build it with `published: 0`.** An unpublished page is a draft: creating, changing or deleting it needs no card. Only System Managers can open a draft. It is shown in a sandboxed frame without its script, forms or network access, so the preview runs no code. Remote images, fonts and data from calls appear only once the page is published.
   To change an existing shared page or a Server Script, use `update_document` with `edits`. Keep each `find` short but unique, and copy it from the current code. Send the whole field only for a rewrite.
3. **Publish with one card.** Update it with `published: 1`. That is the go-live change, and publishing asks once, with the final code, even when it is on the plan: the code was written after the user approved the plan. Still list it on the plan so the user sees it coming. Any change to a published page asks again, and so does unpublishing it. When the user says to publish, publish and do nothing else. If something is still waiting, such as a rule still switched off or a check not yet run, raise it before publishing instead of doing it unasked.
4. **Check it** with the read tools (`list_documents`, `get_doctype_info`, `test_as_user`), not `run_database_query`, which asks on every call. Take a doctype's fields from `get_doctype_info`, never `run_python_code` or a read of `DocField`. In the full chat app the page opens beside the chat: look with `browser_take_screenshot` and read its `page_errors` and `page_text`. `browser_navigate_to` and `browser_capture_diagnostics` work only in the Desk widget, so don't call them in the chat app. In the Desk widget, open the `page_url` from the create or update result with `browser_navigate_to`, look with `browser_take_screenshot`, and run `browser_capture_diagnostics` on it for script errors and failed calls. Fix any script error before you say the page is done, and look again after every change to a published page. Then check access with `test_as_user`: `read` on every doctype the page reads, and `write` or `create` on those it changes, for a user who should see the page and one who should not. `read` on the `FAC Page` itself, with its slug as `name`, answers whether that user can open the page. Check the page's rules without saving anything, as `get_skill("server-script")` describes.
5. **Link it.** A shared page nobody can find is not done, so link it unless the user said not to. Update the Workspace its users open (ask which, or use the one for its module) with two changes in one `update_document` call:
   - a `shortcuts` row `{"type": "URL", "url": "/app/fac-pages/<slug>", "label": "<Page title>"}`. Pass it together with `{"name": "<an existing row's name>"}` for one existing shortcut, so the update appends; rows without a `name` replace every shortcut on the Workspace.
   - the whole `content` with a block added at the end: `{"id": "<new short id>", "type": "shortcut", "data": {"shortcut_name": "<the same label>", "col": 3}}`. The Workspace shows only the shortcuts that have a block.

   Read the Workspace first with `get_document` for its `shortcuts` and `content`. A Workspace you create needs a `module` (see step 1).

To share a user's personal page, update it with `visibility: "Shared"`, the `roles` and `published: 1`. It keeps its name. That change opens the page to other people, so it asks for approval.

## Pages people type into

When a page's teams write their own part of it, such as each business unit's risks and priorities for a fortnightly review, keep what they write in doctypes the page's build plan creates, and keep each unit's part to its own team.

1. **Shape.**
   - A **period** doctype, one record per period, named by it (`autoname: field:period`), for company-wide fields and targets.
   - A **unit update** doctype, one record per unit and period, with `period` (Link to the period doctype), `business_unit` (Link to a small **Business Unit** doctype, or to Cost Center or Department if the site already uses one for its units; check with `list_documents`) and a child table for each repeating item, such as risks with a `severity` Select (`HIGH`, `MED`, `LOW`) and a description. Name it `autoname: format:{period}-{business_unit}` so a unit has one update per period, and make `period` and `business_unit` `reqd` and `set_only_once`, so nobody can move a record to another unit or period by changing them.
   - Turn on **Track Changes** for both, so the record shows who changed what.
2. **Who edits which unit.**
   - Give the Business Unit doctype an `editor_role` field (Link to Role), one role per unit such as "Decathlon BU Editor", and give each team its role on the plan, as an update of each `User`.
   - Give the unit update doctype `read` for everyone who opens the page, and `write` and `create` for the editor roles. Give the Business Unit doctype `read` for everyone who opens the page too: the page reads each unit's `editor_role`, and without it a viewer's sections never draw.
   - Add this **Before Save Server Script** on the unit update doctype and list it on the plan. It refuses a save by anyone outside the unit's team; change the doctype names if yours differ. Server Scripts cannot call `str.format`, so keep the message as it is:

     ```python
     role = frappe.db.get_value("Business Unit", doc.business_unit, "editor_role")
     is_manager = frappe.db.exists("Has Role", {"parent": frappe.session.user, "parenttype": "User", "role": "System Manager"})
     has_role = role and frappe.db.exists("Has Role", {"parent": frappe.session.user, "parenttype": "User", "role": role})
     if not (is_manager or has_role):
         frappe.throw(_("Only this business unit's team can change its update."))
     ```

   - On the page, pass `canEdit: await fac.hasRole(unit.editor_role)` to `fac.editList` and `fac.editText` (`get_skill("mockup-kit")`), so Edit shows only to the team. The Server Script still decides every save.
   - Never use **User Permissions on Cost Center** (or on the unit) for this: they also hide the other units' records, which everyone reads in the meeting, and they narrow every cost-center report for that user.
3. **Report figures.** Each viewer sees only the reports their roles allow (`get_skill("page-reports")`). List on the plan the report roles each team needs, such as Accounts User for P&L.
4. **History.** Never overwrite a past period: the page's period picker reads that period's records.
5. **Carry-over.** Offer a "Copy open items from last period" button that creates this period's update from the last one's rows. Run it only when the user clicks it.
6. **Record and reuse.** Set the page's `doctypes` to every doctype it reads or writes. Before changing a page, read its `doctypes` and reuse them; never create a second set for the same purpose. Deleting the page leaves them and their records.
7. **Check it.** With `test_as_user`, check that every viewer can `read` both units' updates and the Business Unit doctype, and that each editor role can `write` the unit update doctype. `test_as_user` cannot see the Server Script, so it reports `write` allowed on another unit's update too. To check the unit rule, ask a member of unit A to try saving B's section and confirm they see the script's message; don't change permissions because `test_as_user` says allowed.

## Reference

```json
{
  "doctype": "FAC Page",
  "data": {
    "title": "Team Planner",
    "description": "Who is on which project this week",
    "slug": "team-planner",
    "visibility": "Shared",
    "published": 0,
    "roles": [{"role": "Projects User"}],
    "doctypes": [{"doctype_link": "Task"}],
    "html": "<div class=\"mk-page\"><div class=\"mk-card\"><table class=\"mk-table\" id=\"tasks\"></table></div></div>",
    "script": "const esc = frappe.utils.escape_html;\nfrappe.db.get_list('Task', {fields: ['name', 'subject', 'status'], limit: 20}).then((rows) => {\n  root_element.querySelector('#tasks').innerHTML = rows.map((r) => `<tr><td>${esc(r.subject)}</td><td>${esc(r.status)}</td></tr>`).join('');\n});",
    "style": "#tasks td { padding: 4px 8px; }"
  }
}
```

- **`description`**: one line saying what the page shows. It appears under the title in the Pages list in Desk, so set it on every page.
- **`slug`**: lower-case words joined by single hyphens, at most 80 characters. A shared page's name is its slug; a personal page's name adds the owner's tag. It must be unique among shared pages, and among each user's own pages. It cannot change after the page is saved.
- **`html`** is static markup. The `mockup-kit` classes (`mk-page`, `mk-card`, `mk-table` and the rest) work here as in a mockup. Put event handlers in the `script` (`root_element.querySelector(...).addEventListener(...)`), never inline. A personal page's html keeps only allowlisted tags and attributes, so its code lives only in `script`. It is served without inline handlers (`onclick`, `onerror` and the rest), `javascript:` and `data:` URLs (so no `data:` images), `<script>`, `<iframe>`, `<object>`, `<embed>`, `<base>` or SVG animation. Forms, inputs and buttons are kept. Inline `<svg>` shapes lose their drawing attributes there, so draw charts with `fac.chart` from the script. For figures a report already computes, such as P&L or receivables, read the report with `fac.report` (`get_skill("page-reports")`). For anything people type into the page, use `fac.editList`, `fac.editText` and `fac.periodPicker`, never `frappe.ui` dialogs, so the page also works beside the chat (`get_skill("mockup-kit")`).
- **`script`** runs after the html renders. `root_element` is the page's shadow root (on a personal page, the page's own element), so find elements with `root_element.querySelector`, not `document`. In Desk it has the normal `frappe` object; in the chat panel only a small part of it (see `pages-in-chat`). It runs as the viewer, so `frappe.call` and `frappe.db` read and write only what that user may.
- **`style`** applies to this page only, and stays inside the page's box: a `position: fixed` element is fixed to the page, not the screen. A personal page's style is served without `@import` or any at-rule other than `@media`, `@supports`, `@keyframes` and `@font-face`, and without any declaration whose `url(...)`, `image-set()` or similar is not a `/files/...` or `/assets/...` path on this site. A stylesheet that does not parse cleanly is served empty. Inline `style` attributes in its html follow the same rule.
- **`doctypes`**: every doctype the page reads or writes, as `{"doctype_link": ...}` rows. Read it before changing the page and reuse those doctypes. It grants nothing, and deleting the page leaves them.
- **`roles`** (shared pages only): users with any listed role can open the page. No roles means System Managers only. "All" or "Guest" opens it to every logged-in user, website users included, so pick roles on purpose.

## Gotchas

- Escape record values before putting them into html with `frappe.utils.escape_html`, which works in Desk and in the chat panel.
- Use `frappe.format(value, df, options, doc)` for numbers, amounts, dates and durations only (`Currency`, `Float`, `Int`, `Percent`, `Date`, `Datetime`, `Time`, `Duration`). For these it returns plain text in Desk and in the chat panel alike, with the site's number, currency and date settings, so escape it too. For an amount in a record's own currency, set `options` to the record's currency field (`"currency"`) and pass the record as `doc`; a currency code in `options` is ignored. For text and link values, use the record's own value escaped with `frappe.utils.escape_html`, never `frappe.format`. See `pages-in-chat`.
- A script must never turn page text into markup or code: no `innerHTML` of text read from the page (`el.innerHTML = el.dataset.tpl`, `el.textContent`), no `new Function` or `eval` of it. Build markup from record values escaped with `frappe.utils.escape_html`.
- The script runs again on every visit, so guard anything that outlives it. Keep a `setInterval` handle on `root_element` and clear it first, and call `frappe.realtime.off` before `frappe.realtime.on`, or the handlers pile up.
- A page that calls an API you wrote must ask for what that API allows: keep each call within the limits of that API (a date range, a row count), or change the API's limit to fit what the page asks. Check the API's own checks when you write the page script.
- A role on the page lets a user open it, not read the data. The script's calls still need that user's permission on each doctype, which is why step 4 checks them.

## Anti-patterns

- Publishing before the user has seen the plan or the draft.
- Opening a page to "All" because no role was chosen.
- Testing the page or its rules by creating real records and deleting them, or by acting as another user.
- Building a Workspace full of custom HTML blocks when the user asked for a screen of its own.
