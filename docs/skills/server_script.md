# Server Script

## Overview

Adds a rule that runs on the server when a document is saved, submitted, cancelled or deleted, such as "stop a sales invoice going out below cost" or "fill the sales person from the customer". This creates a `Server Script` document. Follow `get_skill("setup-change-protocol")` for the plan, the confirmation and the change log. This skill covers what goes into the record.

**Only a System Manager can do this**, and the user needs the Script Manager role too. If a role is missing, the error names it. Tell the user which role and who can grant it.

**Talk to the user in business words.** Say "this checks every Sales Invoice when it is submitted", not `before_submit` or `reference_doctype`. Field names belong in the record, not in the conversation, unless the user asks.

## When to use

- "Don't let X happen when Y is saved or submitted", "automatically fill X", "make sure X always matches Y".

**Not for** showing, hiding or requiring a field. Use the smallest mechanism that does the job (next section). Not for a scheduled job or an API the user did not ask about.

## Workflow

1. **Smallest mechanism first.** Work down this list and stop at the first that does the job:
   1. A field property: `reqd`, `read_only`, `hidden`, `default`, set through a `Property Setter`, or `mandatory_depends_on` / `depends_on` for "required when".
   2. A Client Script (`get_skill("client-script")`) for behaviour in the form.
   3. A Server Script, only when the rule must hold for everything that saves the document.
   4. A `Workflow` only when the user asked for an approval process (`get_skill("set-up-approval-workflow")`).
2. **State the scope in one plain sentence** before anything else: "This affects every Sales Invoice submit. Nothing else changes."
3. **Say where the rule is enforced.** A Server Script runs for the Desk form, imports, the API and FACO's own writes. `depends_on`, `mandatory_depends_on` and Client Scripts are checked in the Desk form only, so tell the user that a rule built from them does not stop an import or an API write. Never claim a protection the mechanism cannot enforce. A Custom Field of type Code, for example, stores text and runs nothing.
4. **Check scripts are allowed.** Call `get_doctype_info` on `Server Script` and read `server_scripts_enabled`. If it is false, tell the user in plain words that this site does not run scripts, so an active script would do nothing. Offer to save it switched off (`disabled: 1`) so a System Manager can switch the site setting on later. Do not try to create it active; the write is refused.
5. **List what already exists** on the same doctype and event: `list_documents` on `Server Script` with `reference_doctype` and `doctype_event`. Two scripts on one event run in an undefined order. If one overlaps, offer to change it instead of adding another.
6. **Show the full code** in a fenced block, then explain in plain words what it does and when it runs. The user must be able to approve it without reading Python.
7. **Create it with `disabled: 1`.** Ask the user to test it (say exactly what to do, for example "save a draft invoice below cost"), and only after they confirm, update it with `disabled: 0`.
8. **Link the result**: the new record and the form where the change shows. A create result carries `url` for the record and `applies_to.url` for the form. Give both as links, and say the user may need to reload the form.

## Reference

```json
{
  "doctype": "Server Script",
  "data": {
    "name": "Block sale below cost",
    "script_type": "DocType Event",
    "reference_doctype": "Sales Invoice",
    "doctype_event": "Before Submit",
    "disabled": 1,
    "script": "for row in doc.items:\n    if row.base_net_rate < row.valuation_rate:\n        frappe.throw(f\"Row {row.idx} is priced below cost\")"
  }
}
```

- `doc` is the document being saved. `frappe.throw` stops the save and shows the message to the user.
- **Amounts and discounts.** Compare percentages, or totals before the discount, or the company-currency `base_*` amounts (`base_net_rate`, `base_grand_total`). Never compare a foreign-currency `rate` or `grand_total` with a company-currency limit. Item-level discounts change the net rate, so handle them in the rule or say plainly that the rule ignores them.
- Server Scripts run in a restricted sandbox: no imports, limited functions.

## Gotchas

- **A script that fails breaks saving for everyone** on that doctype. That is why it starts switched off and is tested first.
- **Submitted documents.** A `Before Save` script does not run when a submitted document is updated after submit. Use `Before Submit` for "must hold at submit".
- **An update that flips `disabled` from 1 to 0 is refused when scripts are off**, the same as a create. Do not retry.
- The approval card appears for every customisation write, and "Don't ask again" never applies to one. That is intended; do not tell the user to switch it off.

## Anti-patterns

- Reaching for a script when a field property or Client Script would do.
- Creating the script active, or enabling it before the user has tested it.
- Describing a Client Script or `mandatory_depends_on` rule as if it protected imports and API writes.
- Pasting code without saying in plain words what it does.
