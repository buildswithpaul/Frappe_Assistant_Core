# Pages in Chat

## Overview

When a user asks for a report, a summary or "a PDF of …", build it as a personal `FAC Page`. It opens beside the chat as soon as it is saved, the user can look at it while you change it, and they can download it as a PDF. Any Desk user can have one. This skill covers building and fixing the page with the user. The `fac-page` skill covers the record itself.

## When to use

- "Give me a report of …", "summarise … on one page", "make me a PDF of …", "show me … as a chart".

**Not for** a page other people should open. That is a shared page, which only a System Manager can set up (`get_skill("fac-page")`).

## Workflow

1. **Create it personal.** `create_document` on `FAC Page` with a `title`, a readable `slug` (`overdue-invoices`, not `page-1`), `html`, `script` and `style`. Leave `visibility` out, or set it to `"Only me"`. A personal page opens only for its owner, needs no approval card and is live once saved. Leave out `published` and `roles`. Only a System Manager can set them.
2. **Fetch data live in the script.** Don't paste figures into the html. The script reads them each time the page opens, so the page stays current.
3. **Point to the chip.** The page appears as a chip in your reply, and the chip opens it beside the chat. Tell the user to open it. Don't paste the html into the chat.
4. **Look before you reply.** After every create or change, call `browser_take_screenshot`. In the chat app it captures the page open beside the chat, after the user approves. Fix what looks off (cut-off text, an empty table, a chart with no data) and look again before you answer. If the screenshot is declined or unavailable, or no page is open, say plainly that you couldn't look at the page.
5. **Change it on request.** Use `update_document` with the record `name` from the create result, which is the slug plus a short tag, not the slug alone. Send only the fields that change. The panel redraws and shows the new version number. Then look again (step 4).
6. **For a PDF, point to Download PDF** in the panel header. It prints the page as it is shown, A4, in landscape when the page is wide. Don't offer to generate a PDF any other way.

## What a page can use

- **The `mockup-kit` classes** (`mk-page`, `mk-card`, `mk-table`, `mk-stat`, `mk-badge`, `mk-btn`, `mk-field`, `mk-tabs`, `mk-chart`).
- **`root_element`**, the page's shadow root. Find elements with `root_element.querySelector`.
- **`fac.chart(el, option)`** draws an ECharts bar, line or pie chart as SVG (see `mockup-kit`).
- **`__(text)`** for translatable text.
- **`frappe`**: in the chat panel, only these members:
  - `frappe.call`;
  - `frappe.db.get_list`, `get_value`, `get_doc`, `insert`, `set_value` and `delete_doc`;
  - `frappe.session.user`;
  - `frappe.datetime.get_today` and `str_to_user`;
  - `frappe.format`.

  The script runs as the user, so it reads and writes only what they may. Any other member, such as `frappe.utils`, `frappe.ui`, `frappe.realtime` or `frappe.set_route`, makes the panel say the page needs Desk and offer **Open in Desk**. Write your own small helpers instead, for example to escape text.

```js
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
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
- In the Desk widget the chip opens the page in Desk, and the screenshot there captures the Desk tab.
- To share the page, the user asks a System Manager. The panel's **Share…** button sends that request when the user is one. Sharing asks for approval.

## Anti-patterns

- Replying "done" without looking at the page.
- Pasting numbers into the html instead of fetching them.
- A slug like `report` or `page-2` that the user can't find again in **My pages**.
- Reaching for Desk-only `frappe` members, so the page shows **Open in Desk** instead of the report.
