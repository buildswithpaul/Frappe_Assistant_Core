# Configure Naming Series

## Overview

Changes how documents are numbered, for example "invoices should be INV/2026-27/0001" or "each branch needs its own invoice numbers". A doctype with a `naming_series` field takes its choices from that field's options. You change them with two `Property Setter` records, which is what **Document Naming Settings** does itself. Follow `get_skill("setup-change-protocol")` for the plan, the confirmation and the change log.

**Only a System Manager can do this.** `Property Setter` is write-protected for every other role.

## When to use

- "Change the invoice numbering", "add a series for branch X", "numbers should include the financial year", "start invoice numbers from 1001".

**Not for** renaming existing documents. A submitted document's name is permanent, and a new series only applies to documents created after it.

## Workflow

1. **Read the current series.** `get_doctype_info` on the doctype and read the `naming_series` field's `options`; the first line is the default. Also `list_documents` on `Document Naming Rule` with `document_type` = the doctype and `disabled = 0`. **A matching naming rule runs before the naming series and overrides it**, so if one exists, the series you change won't be used for the documents it matches.
2. **Write the new series** in the syntax below. Check the prefix isn't already used by another doctype (`list_documents` on `Property Setter`, `field_name = "naming_series"`, `property = "options"`, then read each `value`). Two doctypes sharing a prefix share one counter.
3. **Plan, confirm and create** the two Property Setters through the protocol.
4. **Starting number.** The counter can't be set through the tools. Navigate the user to it with `browser_navigate_to` (`/app/document-naming-settings`) and tell them to use the **Update Series Counter** section. There they enter the **Prefix** with its date parts already filled in (e.g. `INV-2026-2027-`), set **Current Value** to the last number used (1000 to start at 1001), and click **Update Series Number**.

## Reference

**Syntax.** Parts are separated by `.`:

| Part | Becomes |
|---|---|
| `INV-` | Literal text |
| `.FY.` | Fiscal year name, e.g. `2026-2027` (ERPNext) |
| `.YYYY.` `.YY.` `.MM.` `.DD.` | Date parts. **ERPNext takes them from the document's posting/transaction date, not today** |
| `.ABBR.` | The company's abbreviation (ERPNext) |
| `.{branch}.` | Any field value on the document |
| `.####` | The counter, as many digits as `#`s. Added as `.#####` if you leave it out |

`INV-.FY.-.####` → `INV-2026-2027-0001`. `.ABBR.-SINV-.YY.-.#####` → `ACME-SINV-26-00001`.

**The two records** (both `doctype_or_field: "DocField"`, `field_name: "naming_series"`, `property_type: "Text"`):

```json
{"doctype": "Property Setter", "data": {
  "doctype_or_field": "DocField", "doc_type": "Sales Invoice", "field_name": "naming_series",
  "property": "options", "property_type": "Text",
  "value": "INV-.FY.-.####\nACC-SINV-.YYYY.-"}}
```

```json
{"doctype": "Property Setter", "data": {
  "doctype_or_field": "DocField", "doc_type": "Sales Invoice", "field_name": "naming_series",
  "property": "default", "property_type": "Text",
  "value": "INV-.FY.-.####"}}
```

- `options` is **every** series the user can choose, one per line. **Keep the existing ones** unless they're sure no one needs them. Removing a series doesn't rename anything, but users can no longer choose it.
- `default` must be one of the `options` lines, exactly.
- Creating a Property Setter replaces any existing one for the same doctype, field and property, so you don't need to find and update the old one first.

## Gotchas

- **Per-branch or per-company numbering** is a separate series for each, plus a **Document Naming Rule**, or users picking the series on the form. With several companies, `.ABBR.` in one series often does the job with no rule at all.
- **A mid-year change** starts the new prefix at 1 unless the counter is set (step 4). A gap or restart in invoice numbers can matter for tax compliance; ask before doing it mid-year.
- **Fiscal-year series roll over by themselves.** `.FY.` changes the prefix each year, and the new prefix gets a fresh counter.
- **Amendments** keep the original name with a `-1` suffix. That's normal, not a series problem.

## Anti-patterns

- Replacing `options` with only the new series and breaking users who rely on the old one.
- Changing the series while a Document Naming Rule silently overrides it.
- Promising to set the starting number yourself.
