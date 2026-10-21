# Client Script

## Overview

Adds behaviour to a form in the browser, such as "when the customer changes, fill the region", "hide this field unless the order is an export" or "show a warning when the discount is high". This creates a `Client Script` document. Follow `get_skill("setup-change-protocol")` for the plan, the confirmation and the change log. This skill covers what goes into the record.

**Only a System Manager can do this.** Anyone else gets "Changing Client Script needs a System Manager". Tell the user who can do it.

**Talk to the user in business words.** Say "when someone picks a customer on a Sales Invoice", not `frappe.ui.form.on` or `refresh`. Never show field names, flags or option keys in what you tell the user unless they ask (for example a server-scripts flag, `custom_` names or "Insert after"). Say "server scripts are switched off", "after the Customer field", "the Required By date". See `setup-change-protocol`.

## When to use

- "When X is chosen, fill / show / hide Y", "warn the user if X", "add a button on the form".

**Not for** a rule that must hold for imports, the API or FACO's own writes. That needs a Server Script (`get_skill("server-script")`).

## Workflow

1. **Smallest mechanism first.** A field property (`reqd`, `read_only`, `hidden`, `default`) through a `Property Setter`, or `depends_on` / `mandatory_depends_on` on the field, comes before a Client Script. A Client Script comes before a Server Script. A `Workflow` only when the user asked for an approval process.
2. **State the scope in one plain sentence**: "This affects the Sales Invoice form for everyone who opens it. Nothing else changes."
3. **Say where it is enforced.** `depends_on`, `mandatory_depends_on` and Client Scripts are checked in the Desk form only. They do not run on import, through the API or on FACO's own writes. Tell the user this before they rely on it, and offer a Server Script if the rule must always hold. Never claim a protection the mechanism cannot enforce.
4. **List what already exists**: `list_documents` on `Client Script` with `dt` set to the doctype. Two scripts on the same form event can fight. Offer to change an existing one instead of adding another.
5. **Show the full code** in a fenced block, then explain in plain words what it does and when it runs.
6. **Create it with `enabled: 0`**, which does nothing yet. Show what it will do and ask the user whether to go ahead. Only after they say yes, update it with `enabled: 1`. Then straight away ask them to try it on a draft or test document (say exactly what to do), and offer to switch it off again if it misbehaves.
7. **Link the result**: the new record and the form where the change shows (`applies_to.url` on the create result). Say the user needs to reload the form.

## Reference

```json
{
  "doctype": "Client Script",
  "data": {
    "name": "Sales Invoice - discount warning",
    "dt": "Sales Invoice",
    "view": "Form",
    "enabled": 0,
    "script": "frappe.ui.form.on('Sales Invoice', {\n  additional_discount_percentage(frm) {\n    if (frm.doc.additional_discount_percentage > 20) {\n      frappe.msgprint('Discount is above 20%');\n    }\n  }\n});"
  }
}
```

- **Always give the record a `name`** (as above). A Client Script is named by hand, and a dry run (`validate_only`) does not catch a missing name, so the real create fails.
- **Amounts and discounts.** Use percentage fields or totals before the discount, and the company-currency `base_*` amounts, not a foreign-currency amount compared with a company-currency limit. Handle item-level discounts or say plainly that the rule ignores them.
- The script runs in the user's browser and sees only what is on the form.

## Gotchas

- **Name records by what they do, never by a value that may change (no limits, percentages or dates in names):** 'Discount limit on Sales Invoice submit', not 'Block discount above 15%'. Changing a value never needs a rename. The update tool cannot rename a record; if the user wants a different name, tell them to use Rename from the record's menu in Desk.
- **A broken script breaks the form** for everyone until it is switched off. That is why it starts switched off and is switched on only with the user's go-ahead.
- A Client Script on a child table row needs the child doctype's own handler, not the parent's.
- The approval card appears for every customisation write, and "Don't ask again" never applies to one. That is intended.

## Anti-patterns

- A Client Script for a rule that imports and the API must also respect.
- Switching it on without the user's go-ahead.
- Asking the user to try a script that is still switched off. It does nothing, so the test shows nothing.
- A script that sets a value the user cannot then change, with no explanation.
