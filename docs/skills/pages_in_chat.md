# Pages in Chat

## Overview

When a user asks for a report, a summary or "a PDF of …" about their own data, build it as a personal `FAC Page`, not with `generate_document`. It opens beside the chat as soon as it is saved, the user can look at it while you change it, and they can download it as a PDF. Any Desk user can have one. This skill covers building and fixing the page with the user. The `fac-page` skill covers the record itself.

## When to use

- "Give me a report of …", "summarise … on one page", "make me a PDF of …", "show me … as a chart".
- "Create a PDF of how my sales did this month" is a page, not `generate_document`: the page reads the figures live and downloads as a PDF. Use `generate_document` only for a written document such as a proposal or a letter, or to print an existing document.

**No build plan and no confirmation.** A personal page is not a site change: only its owner opens it, and its script runs in a sealed frame that reads only what they may and asks them before any change. Don't call `propose_build_plan` or `ask_user` before creating or changing one. Just build it.

**Not for** a page other people should open. That is a shared page, which only a System Manager can set up (`get_skill("fac-page")`).

## Workflow

1. **Create it personal.** `create_document` on `FAC Page` with a `title`, a readable `slug` (`overdue-invoices`, not `page-1`), `html`, `script` and `style`. Leave `visibility` out, or set it to `"Only me"`. A personal page opens only for its owner, needs no approval card, and loads and runs as soon as it is saved. Leave out `published` and `roles`. Only a System Manager can set them.
2. **Fetch data live in the script.** Don't paste figures into the html. The script reads them each time the page opens, so the page stays current.
3. **It opens by itself.** In the chat app, the page opens beside the chat as soon as your create saves, unless the user already has another page open or is on a phone. Then it appears only as a chip in your reply, and you ask the user to open it from the chip. Don't paste the html into the chat.
4. **Test it before you say it's done.** After every save, look at the page with `browser_take_screenshot`; in the chat app it captures the page open beside the chat, after the user approves. Check that the figures are filled in, and read the result's `page_errors`: the script's errors and the calls that failed while the page ran. Fix what is wrong (an error, an empty table, a chart with no data, cut-off text) and look again. If no screenshot is possible (a phone, the Desk widget, or another page open), run the page's queries yourself with `list_documents` or `get_doctype_info` and tell the user what you checked. Never call a page done while it shows errors or empty figures you can't explain. The user judges the page by its figures; they never see or run its code.
5. **Change it on request.** Use `update_document` with the record `name` from the create result, which is the slug plus a short tag, not the slug alone. Send only the fields that change. The panel redraws, shows the new version number and runs it at once. Then test it again (step 4).
6. **For a PDF, point to Download PDF** in the panel header. It prints the page as it is shown, A4, in landscape when the page is wide. Don't offer to generate a PDF any other way.

## What a page can use

- **The `mockup-kit` classes** (`mk-page`, `mk-card`, `mk-table`, `mk-stat`, `mk-badge`, `mk-btn`, `mk-field`, `mk-tabs`, `mk-chart`).
- **`root_element`**, the page's own element. Find elements with `root_element.querySelector` or `root_element.getElementById`.
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

  The script runs as the user, so it reads only what they may. **Reads run at once:** `get_list`, `get_value`, `get_doc` and a `frappe.call` with `type: "GET"`. **Every change asks the user first**, in plain words in the panel: `insert`, `set_value`, `delete_doc` and a `frappe.call` with `type: "POST"`. A `frappe.call` that names no type is tried as a read, and asks only if its method refuses GET. So a page that only shows data never asks: read with `type: "GET"`, and give any API the page reads `methods=["GET"]`.

  Any other member, such as the rest of `frappe.utils`, `frappe.ui`, `frappe.realtime` or `frappe.set_route`, makes the panel say the page needs Desk and offer **Open in Desk**. Write your own small helpers for anything else.
- **A sealed frame.** The script can't fetch anything itself, open a window, submit a form, navigate or reach the chat around it. Its data comes only through `frappe`. Images and fonts load only from this site's `/files/` and `/assets/`.

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
- If the user moved from the Desk widget to the full chat while you worked, your screenshot can still go to the widget and fail. Test the page's queries with the read tools instead, and say so.
- To share the page, the user asks a System Manager. The panel's **Share…** button sends that request when the user is one. Sharing asks for approval.

## Anti-patterns

- Replying "done" without looking at the page.
- Calling a page done while `page_errors` lists errors or its figures are empty.
- Reading with `type: "POST"` calls, so the user is asked to allow a change every time the page opens.
- Pasting numbers into the html instead of fetching them.
- A slug like `report` or `page-2` that the user can't find again in **My pages**.
- Inline `onclick` or `onerror` handlers in the html. They are stripped, so the button does nothing.
- Reaching for Desk-only `frappe` members, so the page shows **Open in Desk** instead of the report.
