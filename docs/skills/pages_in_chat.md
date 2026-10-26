# Pages in Chat

## Overview

When a user asks for a report, a summary or "a PDF of …" about their own data, build it as a personal `FAC Page`, not with `generate_document`. It opens beside the chat as soon as it is saved, the user can look at it while you change it, and they can download it as a PDF. Any Desk user can have one. This skill covers building and fixing the page with the user. The `fac-page` skill covers the record itself.

## When to use

- "Give me a report of …", "summarise … on one page", "make me a PDF of …", "show me … as a chart".
- "Create a PDF of how my sales did this month" is a page, not `generate_document`: the page reads the figures live and downloads as a PDF. Use `generate_document` only for a written document such as a proposal or a letter, or to print an existing document.

**No build plan and no confirmation.** A personal page is not a site change: only its owner opens it, and they run its code with **Run new version**. Don't call `propose_build_plan` or `ask_user` before creating or changing one. Just build it.

**Not for** a page other people should open. That is a shared page, which only a System Manager can set up (`get_skill("fac-page")`).

## Workflow

1. **Create it personal.** `create_document` on `FAC Page` with a `title`, a readable `slug` (`overdue-invoices`, not `page-1`), `html`, `script` and `style`. Leave `visibility` out, or set it to `"Only me"`. A personal page opens only for its owner, needs no approval card, and its html and style show once saved. Its script waits for the user (step 4). Leave out `published` and `roles`. Only a System Manager can set them.
2. **Fetch data live in the script.** Don't paste figures into the html. The script reads them each time the page opens, so the page stays current.
3. **It opens by itself.** In the chat app, the page opens beside the chat as soon as your create saves, unless the user already has another page open. Then it appears only as a chip in your reply, and you ask the user to open it from the chip. Don't paste the html into the chat.
4. **Ask the user to run your code.** The first time a page has a script, and every time you change the script, the panel and the Desk page show the html and style but don't run the script. They show **Run new version** and **View changes** until the user has seen the code and clicked **Run new version**. Tell the user to click it. Until they do, Download PDF and your screenshots show the page without the new code, and the screenshot result says so in its `note`. So you can't look at what the new code does until they click. Changes to the html or style alone show at once.
5. **Look before you reply.** After every create or change, call `browser_take_screenshot`. In the chat app it captures the page open beside the chat, after the user approves. Fix what looks off (cut-off text, an empty table, a chart with no data) and look again before you answer. If the screenshot is declined or unavailable, or another page is open, say plainly that you couldn't look at the page.
6. **Change it on request.** Use `update_document` with the record `name` from the create result, which is the slug plus a short tag, not the slug alone. Send only the fields that change. The panel redraws and shows the new version number. If you changed the `script`, ask the user to click **Run new version** (step 4). Then look again (step 5).
7. **For a PDF, point to Download PDF** in the panel header. It prints the page as it is shown, A4, in landscape when the page is wide. Don't offer to generate a PDF any other way.

## What a page can use

- **The `mockup-kit` classes** (`mk-page`, `mk-card`, `mk-table`, `mk-stat`, `mk-badge`, `mk-btn`, `mk-field`, `mk-tabs`, `mk-chart`).
- **`root_element`**, the page's shadow root. Find elements with `root_element.querySelector`.
- **Event handlers in the script only**: `root_element.querySelector("#refresh").addEventListener("click", load)`. Inline handlers (`onclick="..."`) and `javascript:` links are stripped from a personal page's html.
- **`fac.chart(el, option)`** draws an ECharts bar, line or pie chart as SVG (see `mockup-kit`).
- **`__(text)`** for translatable text.
- **`frappe`**: in the chat panel, only these members:
  - `frappe.call`;
  - `frappe.db.get_list`, `get_value`, `get_doc`, `insert`, `set_value` and `delete_doc`;
  - `frappe.session.user`;
  - `frappe.datetime.get_today` and `str_to_user`;
  - `frappe.utils.escape_html`, the same as in Desk;
  - `frappe.format`.

  The script runs as the user, so it reads and writes only what they may. Any other member, such as the rest of `frappe.utils`, `frappe.ui`, `frappe.realtime` or `frappe.set_route`, makes the panel say the page needs Desk and offer **Open in Desk**. Write your own small helpers for anything else.

```js
const esc = frappe.utils.escape_html;
frappe.db.get_list("Sales Invoice", {
  fields: ["name", "customer", "outstanding_amount"],
  filters: { docstatus: 1, outstanding_amount: [">", 0] },
  limit: 50,
}).then((rows) => {
  root_element.querySelector("#rows").innerHTML = rows
    .map((r) => `<tr><td>${esc(r.name)}</td><td>${esc(r.customer)}</td><td>${esc(frappe.format(r.outstanding_amount, { fieldtype: "Currency" }))}</td></tr>`)
    .join("");
});
```

## Gotchas

- `frappe.db.get_list` returns 20 rows unless you pass `limit`.
- A failed call leaves part of the page empty, and the panel says part of the page didn't load. Check the doctype and fields with `get_doctype_info` first.
- The Desk widget has no panel beside the chat. Its chip opens the page in Desk, and the screenshot captures whatever the Desk tab shows, so ask the user to open the page from the chip before you look.
- To share the page, the user asks a System Manager. The panel's **Share…** button sends that request when the user is one. Sharing asks for approval.

## Anti-patterns

- Replying "done" without looking at the page.
- Judging new code from a screenshot taken before the user clicked **Run new version**.
- Pasting numbers into the html instead of fetching them.
- A slug like `report` or `page-2` that the user can't find again in **My pages**.
- Inline `onclick` or `onerror` handlers in the html. They are stripped, so the button does nothing.
- Reaching for Desk-only `frappe` members, so the page shows **Open in Desk** instead of the report.
