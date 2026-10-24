# FAC Page

## Overview

A `FAC Page` is a full screen with its own layout, such as a planner, a board or a tracker, stored as a record and opened at `/app/fac-pages/<slug>`. Follow `get_skill("setup-change-protocol")` for the plan and the change log. This skill covers what goes into the record.

**Only a System Manager can create or change one.** If the user is not a System Manager, say so and stop.

## When to use

- The user wants a screen of their own: a planner, a board, a tracker, a page that reads and writes records in one place.

**Not for** cards, shortcuts and charts. Use a `Workspace` for those.

## Workflow

1. **Plan it.** When you have the `propose_build_plan` tool, list the page with its `slug` as the `name`, mark it as going live, and send a `mockup_html` written with the `mockup-kit` classes.
2. **Build it with `published: 0`.** An unpublished page is a draft: creating, changing or deleting it needs no card. Only System Managers can open a draft, and it is shown without its script, so the preview runs no code.
3. **Publish with one card.** Update it with `published: 1`. That is the go-live change and asks for approval, unless the approved build plan marked the page as going live. Any change to a published page asks again, and so does unpublishing it.
4. **Check it.** Open the `page_url` from the create or update result with `browser_navigate_to` and look with `browser_take_screenshot`. Then check access with `test_as_user`: `read` on every doctype the page reads, and `write` or `create` on those it changes, for a user who should see the page and one who should not.
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
- A role on the page lets a user open it, not read the data. The script's calls still need that user's permission on each doctype, which is why step 4 checks them.

## Anti-patterns

- Publishing before the user has seen the plan or the draft.
- Opening a page to "All" because no role was chosen.
- Building a Workspace full of custom HTML blocks when the user asked for a screen of its own.
