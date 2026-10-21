# Print Format

## Overview

Creates how a document looks when printed or saved as a PDF, such as "an invoice with our bank details at the bottom" or "a delivery note without prices". This creates a `Print Format` document. Follow `get_skill("setup-change-protocol")` for the plan, the confirmation and the change log. This skill covers what goes into the record.

**Who can do this:** Frappe's normal permissions apply, so anyone allowed to create print formats can. If the write is refused, relay the error in plain words. Do not turn someone away because they are not a System Manager.

**Talk to the user in business words.** Say "the invoice print", not `doc_type` or `custom_format`. Never show field names, flags or option keys in what you tell the user unless they ask (for example a server-scripts flag, `custom_` names or "Insert after"). Say "server scripts are switched off", "after the Customer field", "the Required By date". See `setup-change-protocol`.

## When to use

- "Change how the invoice prints", "add our logo / terms / bank details", "a version without prices".

**Not for** a small change a **Letter Head** or the doctype's **Print Settings** already covers. Check those first: a letter head carries the logo and address on every document.

## Workflow

1. **Smallest mechanism first.** Letter Head or Print Settings, then a Print Format built in the print designer, then a Jinja Print Format with custom HTML. Take the first that does the job.
2. **State the scope in one plain sentence**: "This adds a second print layout for Sales Invoice. The existing layout stays and nothing else changes."
3. **List existing formats** for the doctype: `list_documents` on `Print Format` with `doc_type`. Offer to copy and adjust one rather than start again. Never change the standard format, create a new one.
4. **Show the plan** in plain words: what appears, in what order, what is left out. For custom HTML, show the full code in a fenced block and say what it does.
5. **Create it** with `disabled: 0` and `standard: "No"`. It does not become the default unless the user asks. Setting the default is a separate change to the doctype's default print format, so name it in the plan.
6. **Link the result**: the new record and the document type it belongs to (the result's `applies_to.url` opens a new form of that document type). Tell the user to open any document and choose the format in the print menu.

## Reference

```json
{
  "doctype": "Print Format",
  "data": {
    "name": "Sales Invoice - Bank Details",
    "doc_type": "Sales Invoice",
    "print_format_type": "Jinja",
    "custom_format": 1,
    "standard": "No",
    "html": "<h2>{{ doc.name }}</h2>"
  }
}
```

- **Amounts and discounts.** Show amounts in the document's own currency, and label company-currency `base_*` totals (`base_grand_total`) if you print both. Use percentage fields or pre-discount totals where the point is the discount itself. Item-level discounts change each line's net rate, so print them or say plainly that the format ignores them.
- Use `{{ doc.get_formatted("grand_total") }}` for money and dates so the user's formatting applies.

## Gotchas

- **Name records by what they do, never by a value that may change (no limits, percentages or dates in names):** 'Discount limit on Sales Invoice submit', not 'Block discount above 15%'. Changing a value never needs a rename. The update tool cannot rename a record; if the user wants a different name, tell them to use Rename from the record's menu in Desk.
- **Test with a real document.** Print preview with a submitted invoice shows what a draft does not: taxes and totals.
- A format that errors prints a blank page or an error for that document type until it is fixed or removed.

## Anti-patterns

- Editing a standard print format in place.
- Making the new format the default without being asked.
- Hard-coding a company name, address or bank account that belongs on the Letter Head or Company record.
