# FAC Page

## Overview

A `FAC Page` is a full screen with its own layout, such as a planner, a board or a tracker, stored as a record and opened at `/app/fac-pages/<slug>`. Follow `get_skill("setup-change-protocol")` for the plan and the change log. This skill covers what goes into the record.

**Only a System Manager can create or change one.** If the user is not a System Manager, say so and stop.

## When to use

- The user wants a screen of their own: a planner, a board, a tracker, a page that reads and writes records in one place.

**Not for** cards, shortcuts and charts. Use a `Workspace` for those.

## Workflow

1. **Plan it.** When you have the `propose_build_plan` tool, list the page with its `slug` as the `name`, mark it as going live, and send a `mockup_html` written with the `mockup-kit` classes. List what the page needs the way Frappe saves it: a new doctype as a `DocType` create, a role for the page as a `Role` create (it goes live), and giving that role to people as an update of each `User` by name, never `Has Role`. If a rule the page relies on is built switched off, list switching it on as its own update entry, marked as going live, so the user sees it coming.
2. **Build it with `published: 0`.** An unpublished page is a draft: creating, changing or deleting it needs no card. Only System Managers can open a draft. It is shown in a sandboxed frame without its script, forms or network access, so the preview runs no code. Remote images, fonts and data from calls appear only once the page is published.
3. **Publish with one card.** Update it with `published: 1`. That is the go-live change, and publishing asks once, with the final code, even when it is on the plan: the code was written after the user approved the plan. Still list it on the plan so the user sees it coming. Any change to a published page asks again, and so does unpublishing it. When the user says to publish, publish and do nothing else. If something is still waiting, such as a rule still switched off or a check not yet run, raise it before publishing instead of doing it unasked.
4. **Check it** with the read tools (`list_documents`, `get_doctype_info`, `test_as_user`), not `run_database_query`, which asks on every call. Open the `page_url` from the create or update result with `browser_navigate_to` and look with `browser_take_screenshot`. Then check access with `test_as_user`: `read` on every doctype the page reads, and `write` or `create` on those it changes, for a user who should see the page and one who should not. `read` on the `FAC Page` itself, with its slug as `name`, answers whether that user can open the page. Check the page's rules without saving anything, as `get_skill("server-script")` describes.
5. **Link it.** To put it on a Workspace, add a shortcut of type `URL` to `/app/fac-pages/<slug>`.

## Reference

```json
{
  "doctype": "FAC Page",
  "data": {
    "title": "Team Planner",
    "slug": "team-planner",
    "published": 0,
    "roles": [{"role": "Projects User"}],
    "html": "<div class=\"mk-page\"><div class=\"mk-card\"><table class=\"mk-table\" id=\"tasks\"></table></div></div>",
    "script": "frappe.db.get_list('Task', {fields: ['name', 'subject', 'status'], limit: 20}).then((rows) => {\n  root_element.querySelector('#tasks').innerHTML = rows.map((r) => `<tr><td>${frappe.utils.escape_html(r.subject)}</td><td>${frappe.utils.escape_html(r.status)}</td></tr>`).join('');\n});",
    "style": "#tasks td { padding: 4px 8px; }"
  }
}
```

- **`slug`** is the record's name and the end of the URL: lower-case words joined by single hyphens, at most 80 characters. It cannot change after the page is saved.
- **`html`** is static markup. The `mockup-kit` classes (`mk-page`, `mk-card`, `mk-table` and the rest) work here as in a mockup.
- **`script`** runs after the html renders. `root_element` is the page's shadow root, so find elements with `root_element.querySelector`, not `document`. It has the normal `frappe` object and runs as the viewer, so `frappe.call` and `frappe.db` read and write only what that user may.
- **`style`** applies to this page only.
- **`roles`**: users with any listed role can open the page. No roles means System Managers only. "All" or "Guest" opens it to every logged-in user, website users included, so pick roles on purpose.

## Gotchas

- Escape record values before putting them into html (`frappe.utils.escape_html`).
- The script runs again on every visit, so guard anything that outlives it. Keep a `setInterval` handle on `root_element` and clear it first, and call `frappe.realtime.off` before `frappe.realtime.on`, or the handlers pile up.
- A role on the page lets a user open it, not read the data. The script's calls still need that user's permission on each doctype, which is why step 4 checks them.

## Anti-patterns

- Publishing before the user has seen the plan or the draft.
- Opening a page to "All" because no role was chosen.
- Testing the page or its rules by creating real records and deleting them, or by acting as another user.
- Building a Workspace full of custom HTML blocks when the user asked for a screen of its own.
