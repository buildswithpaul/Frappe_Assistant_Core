# Add a Custom Field

## Overview

Adds a field to an existing form, such as "add a vehicle number to Delivery Note" or "we need a PO reference on every invoice". This creates a `Custom Field` document, and Frappe adds the database column when it's saved. Follow `get_skill("setup-change-protocol")` for the plan, the confirmation and the change log. This skill covers what goes into the record.

**Only a System Manager can do this.** `Custom Field` is write-protected for every other role.

## When to use

- "Add a field for X on Y", "we need to capture X on every Y", "can Y have a place to enter X?"

**Not for** changing a standard field's label, default, mandatory flag or visibility. That's a `Property Setter`, which the user can set in **Customize Form**. Not for a whole new document type.

## Workflow

1. **Check the field doesn't already exist.** `get_doctype_info` on the target doctype and look for a field with the same meaning, not just the same label. ERPNext already covers a lot: **Delivery Note has `vehicle_no` ("Vehicle No"), `driver`, `transporter` and `lr_no` as standard fields.** If it exists, show the user where it is (it may be hidden in a collapsed section) instead of adding a second one.
2. **Pick the right doctype.** A value for the whole document goes on the parent (`Delivery Note`). A value per line goes on the item table (`Delivery Note Item`). Ask if it's ambiguous.
3. **Pick the fieldtype** from what the user will type:

   | They'll enter | `fieldtype` | `options` |
   |---|---|---|
   | Short text, a code, a number plate | `Data` | — |
   | A paragraph | `Small Text` | — |
   | A whole number / a decimal | `Int` / `Float` | — |
   | Money | `Currency` | — |
   | A date | `Date` | — |
   | Yes / no | `Check` | — |
   | One of a fixed list | `Select` | Values separated by `\n` |
   | Another record (a Customer, an Employee) | `Link` | The DocType name |
   | A file | `Attach` | — |

4. **Pick `insert_after`**: the `fieldname` of an existing field on that doctype, taken from `get_doctype_info`. It must exist, or the save fails.
5. **Plan, confirm and create** through the protocol.

## Reference

```json
{
  "doctype": "Custom Field",
  "data": {
    "dt": "Sales Invoice",
    "label": "Sales Channel",
    "fieldtype": "Select",
    "options": "Online\nRetail\nDistributor",
    "insert_after": "customer_group",
    "allow_on_submit": 0,
    "in_list_view": 0,
    "in_standard_filter": 1
  }
}
```

- **Leave `fieldname` out.** Frappe derives it from the label as `custom_<label>` (here, `custom_sales_channel`). The prefix keeps it from clashing with a field a future ERPNext release adds.
- `reqd: 1` makes it mandatory. `allow_on_submit: 1` lets users fill it in after the document is submitted. `in_standard_filter: 1` puts it in the list-view filter bar, and `in_list_view: 1` adds it as a list column.
- `depends_on: "eval:doc.customer_group == 'Export'"` shows the field only when that condition holds.

## Gotchas

- **Carrying the value forward.** When a Delivery Note is turned into a Sales Invoice, Frappe copies fields that have the **same fieldname** on both. To carry the value along, create the same label on the next doctype too. Same label, same `custom_` fieldname.
- **Mandatory on an existing form.** Existing drafts can't be saved until someone fills the new field. Submitted documents aren't affected. Warn the user before setting `reqd: 1`.
- **The fieldtype is mostly permanent.** Frappe only allows changes between compatible types, so `Data` → `Link` later is refused. Choose carefully now.
- **Submitted documents won't show a value.** The field is empty on everything created before it existed.
- **Undoing it deletes data.** Deleting the Custom Field drops the column and every value in it.
- The user may need to reload the form to see the new field.

## Anti-patterns

- Adding a duplicate of a standard field because you only searched by label.
- Setting `fieldname` by hand without the `custom_` prefix.
- Using `Data` for something that should link to an existing record, like a customer or an employee.
