# Print Format

## Overview

Creates how a document looks when printed or saved as a PDF, such as "an invoice with our bank details at the bottom" or "a delivery note without prices". This creates a `Print Format` document. Follow `get_skill("setup-change-protocol")` for the plan, the confirmation and the change log. This skill covers what goes into the record.

**Only a System Manager can do this.** Anyone else gets "Changing Print Format needs a System Manager".

**Talk to the user in business words.** Say "the invoice print", not `doc_type` or `custom_format`.

## When to use

- "Change how the invoice prints", "add our logo / terms / bank details", "a version without prices".

**Not for** a small change a **Letter Head** or the doctype's **Print Settings** already covers. Check those first: a letter head carries the logo and address on every document.

## Workflow

1. **Smallest mechanism first.** Letter Head or Print Settings, then a Print Format built in the print designer, then a Jinja Print Format with custom HTML. Take the first that does the job.
2. **State the scope in one plain sentence**: "This adds a second print layout for Sales Invoice. The existing layout stays and nothing else changes."
3. **List existing formats** for the doctype: `list_documents` on `Print Format` with `doc_type`. Offer to copy and adjust one rather than start again. Never change the standard format, create a new one.
4. **Show the plan** in plain words: what appears, in what order, what is left out. For custom HTML, show the full code in a fenced block and say what it does.
5. **Create it** with `disabled: 0` and `standard: "No"`. It does not become the default unless the user asks. Setting the default is a separate change to the doctype's default print format, so name it in the plan.
6. **Link the result**: the new record and the document type it belongs to (`applies_to.url` opens a new form of it). Tell the user to open any document and choose the format in the print menu.

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

- Show amounts in the document's own currency. A total in company currency is a different field (`base_grand_total`), so label it if you print both.
- Use `{{ doc.get_formatted("grand_total") }}` for money and dates so the user's formatting applies.

## Gotchas

- **Test with a real document.** Print preview with a submitted invoice shows what a draft does not: taxes and totals.
- A format that errors prints a blank page or an error for that document type until it is fixed or removed.

## Anti-patterns

- Editing a standard print format in place.
- Making the new format the default without being asked.
- Hard-coding a company name, address or bank account that belongs on the Letter Head or Company record.
