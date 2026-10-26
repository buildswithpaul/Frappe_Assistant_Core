# FAC Page

## Overview

A `FAC Page` is a full screen with its own layout, such as a planner, a board or a tracker, stored as a record and opened at `/app/fac-pages/<name>`. Follow `get_skill("setup-change-protocol")` for the plan and the change log of a shared page. A personal page (left at "Only me") needs no plan: follow `get_skill("pages-in-chat")`. This skill covers what goes into the record.

**Personal or shared.** `visibility` is `"Only me"` (the default) or `"Shared"`.

- **Personal** ("Only me"): any Desk user can build one. It opens only for its owner, not even for System Managers, and it loads and runs as soon as it is saved, inside a sealed frame: its script reads only what its owner may and asks them before any change. So the owner's own creates and changes need no approval card. A shared page's script runs in Desk itself, because it was approved on the publish card. Its record name is the slug plus a six-character tag for the owner (`sales-summary-3fa9c1`), so use the `name` and `page_url` from the create result, never the slug alone. For a report or summary built in chat, follow `get_skill("pages-in-chat")`.
- **Shared**: opens for the roles you list, once published. Its name is the slug. Only a System Manager can share a page, publish it, give it roles or change a shared page. If the user is not a System Manager, say so and offer a personal page instead.

Website users cannot build pages, and a page cannot be shared with Frappe's Share button.

## When to use

- The user wants a screen of their own: a planner, a board, a tracker, a page that reads and writes records in one place.

**Not for** cards, shortcuts and charts. Use a `Workspace` for those.

## Workflow for a shared page

1. **Plan it.** For a shared page, when you have the `propose_build_plan` tool, list the page with its `slug` as the `name`, mark it as going live, and send a `mockup_html` written with the `mockup-kit` classes. List what the page needs the way Frappe saves it: a new doctype as a `DocType` create, a role for the page as a `Role` create (it goes live), and giving that role to people as an update of each `User` by name, never `Has Role`. If a rule the page relies on is built switched off, list switching it on as its own update entry, marked as going live, so the user sees it coming.
2. **Build it with `published: 0`.** An unpublished page is a draft: creating, changing or deleting it needs no card. Only System Managers can open a draft. It is shown in a sandboxed frame without its script, forms or network access, so the preview runs no code. Remote images, fonts and data from calls appear only once the page is published.
3. **Publish with one card.** Update it with `published: 1`. That is the go-live change, and publishing asks once, with the final code, even when it is on the plan: the code was written after the user approved the plan. Still list it on the plan so the user sees it coming. Any change to a published page asks again, and so does unpublishing it. When the user says to publish, publish and do nothing else. If something is still waiting, such as a rule still switched off or a check not yet run, raise it before publishing instead of doing it unasked.
4. **Check it** with the read tools (`list_documents`, `get_doctype_info`, `test_as_user`), not `run_database_query`, which asks on every call. Open the `page_url` from the create or update result with `browser_navigate_to` and look with `browser_take_screenshot`. Then check access with `test_as_user`: `read` on every doctype the page reads, and `write` or `create` on those it changes, for a user who should see the page and one who should not. `read` on the `FAC Page` itself, with its slug as `name`, answers whether that user can open the page. Check the page's rules without saving anything, as `get_skill("server-script")` describes.
5. **Link it.** To put it on a Workspace, add a shortcut of type `URL` to `/app/fac-pages/<slug>`.

To share a user's personal page, update it with `visibility: "Shared"`, the `roles` and `published: 1`. It keeps its name. That change opens the page to other people, so it asks for approval.

## Reference

```json
{
  "doctype": "FAC Page",
  "data": {
    "title": "Team Planner",
    "slug": "team-planner",
    "visibility": "Shared",
    "published": 0,
    "roles": [{"role": "Projects User"}],
    "html": "<div class=\"mk-page\"><div class=\"mk-card\"><table class=\"mk-table\" id=\"tasks\"></table></div></div>",
    "script": "const esc = frappe.utils.escape_html;\nfrappe.db.get_list('Task', {fields: ['name', 'subject', 'status'], limit: 20}).then((rows) => {\n  root_element.querySelector('#tasks').innerHTML = rows.map((r) => `<tr><td>${esc(r.subject)}</td><td>${esc(r.status)}</td></tr>`).join('');\n});",
    "style": "#tasks td { padding: 4px 8px; }"
  }
}
```

- **`slug`**: lower-case words joined by single hyphens, at most 80 characters. A shared page's name is its slug; a personal page's name adds the owner's tag. It must be unique among shared pages, and among each user's own pages. It cannot change after the page is saved.
- **`html`** is static markup. The `mockup-kit` classes (`mk-page`, `mk-card`, `mk-table` and the rest) work here as in a mockup. Put event handlers in the `script` (`root_element.querySelector(...).addEventListener(...)`), never inline. A personal page's html keeps only allowlisted tags and attributes, so its code lives only in `script`. It is served without inline handlers (`onclick`, `onerror` and the rest), `javascript:` and `data:` URLs (so no `data:` images), `<script>`, `<iframe>`, `<object>`, `<embed>`, `<base>` or SVG animation. Forms, inputs and buttons are kept. Inline `<svg>` shapes lose their drawing attributes there, so draw charts with `fac.chart` from the script.
- **`script`** runs after the html renders. `root_element` is the page's shadow root (on a personal page, the page's own element), so find elements with `root_element.querySelector`, not `document`. In Desk it has the normal `frappe` object; in the chat panel only a small part of it (see `pages-in-chat`). It runs as the viewer, so `frappe.call` and `frappe.db` read and write only what that user may.
- **`style`** applies to this page only, and stays inside the page's box: a `position: fixed` element is fixed to the page, not the screen. A personal page's style is served without `@import` or any at-rule other than `@media`, `@supports`, `@keyframes` and `@font-face`, and without any declaration whose `url(...)`, `image-set()` or similar is not a `/files/...` or `/assets/...` path on this site. A stylesheet that does not parse cleanly is served empty. Inline `style` attributes in its html follow the same rule.
- **`roles`** (shared pages only): users with any listed role can open the page. No roles means System Managers only. "All" or "Guest" opens it to every logged-in user, website users included, so pick roles on purpose.

## Gotchas

- Escape record values before putting them into html with `frappe.utils.escape_html`, which works in Desk and in the chat panel.
- A script must never turn page text into markup or code: no `innerHTML` of text read from the page (`el.innerHTML = el.dataset.tpl`, `el.textContent`), no `new Function` or `eval` of it. Build markup from record values escaped with `frappe.utils.escape_html`.
- The script runs again on every visit, so guard anything that outlives it. Keep a `setInterval` handle on `root_element` and clear it first, and call `frappe.realtime.off` before `frappe.realtime.on`, or the handlers pile up.
- A role on the page lets a user open it, not read the data. The script's calls still need that user's permission on each doctype, which is why step 4 checks them.

## Anti-patterns

- Publishing before the user has seen the plan or the draft.
- Opening a page to "All" because no role was chosen.
- Testing the page or its rules by creating real records and deleting them, or by acting as another user.
- Building a Workspace full of custom HTML blocks when the user asked for a screen of its own.
