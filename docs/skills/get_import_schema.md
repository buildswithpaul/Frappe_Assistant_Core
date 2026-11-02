# How to Use get_import_schema

## Overview

The `get_import_schema` tool lists the fields a data import can fill on a DocType. Use it when a user wants to move a file from their old system into ERPNext: it tells you what each column can map to. Save the mapping with `set_column_mapping`.

Use this, not `get_doctype_info`, for imports. `get_doctype_info` returns a DocType's entire metadata, which for a large DocType (Delivery Note, Sales Invoice) is too long to read in full, so fields get missed. This returns only importable fields: no layout, hidden or read-only fields.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doctype` | string | **Yes** | The DocType the file's rows become, e.g. `"Customer"`, `"Item"` |

## Response Format

```json
{
  "success": true,
  "doctype": "Item",
  "naming": {"rule": "from the item_code field", "id_field": "name", "id_note": "Map a column to 'name' to update existing records."},
  "fields": [
    {"fieldname": "item_code", "label": "Item Code", "type": "Data", "required": true},
    {"fieldname": "item_group", "label": "Item Group", "type": "Link", "link": "Item Group", "required": true},
    {"fieldname": "stock_uom", "label": "Default Unit of Measure", "type": "Link", "link": "UOM", "required": true}
  ],
  "child_tables": [
    {
      "fieldname": "barcodes", "label": "Barcodes", "doctype": "Item Barcode",
      "fields": [
        {"fieldname": "barcode", "label": "Barcode", "type": "Data", "required": true},
        {"fieldname": "barcode_type", "label": "Barcode Type", "type": "Select", "options": ["EAN", "UPC-A", "..."]}
      ]
    }
  ],
  "map_as": "Map a column to a field by its fieldname, to a child table field as '<table fieldname>.<fieldname>', or to \"Don't Import\"."
}
```

- **`required`** with a **`default`**: ERPNext fills it in if no column maps to it, so it isn't missing (e.g. Customer's `customer_type` defaults to `Company`).
- **`required_when`**: required only when a condition holds, e.g. Bank Account's `account` when `is_company_account` is ticked. The import doesn't check it, but Desk does: a record imported without it can't be saved in Desk until it's filled. `set_column_mapping` says which of these the file's rows need.
- **Named by the user** (`naming.rule` says "typed by the user"): an insert needs a column mapped to `name` (ID).
- **`link`**: the value must be an existing record of that DocType (e.g. an Item Group that exists).
- **`options`**: a Select field accepts only these values. Very long lists are cut to 25, with `options_total`.
- **`note`**: what to know about the field. A field Frappe types "Read Only" is listed as `Data` with a note: it is importable, and the note says what becomes of the value (e.g. Customer's `mobile_no`: "On a new Customer, ERPNext creates the primary contact from this.").
- **`child_tables`**: rows inside the record, such as an Item's barcodes. Map their columns as `barcodes.barcode`. A table with a `note` (Frappe 16's `contacts` and `addresses` on Customer and Supplier) holds other records the import creates and links to the record.

## When it fails

It fails up front, with the reason in `error`, when the import can't happen. It uses the same check as `start_import_session`. Tell the user and stop:
- the user lacks **Create** or **Import** permission on the DocType
- the DocType is a child table (import it through its parent), a single settings record, or has Allow Import turned off
- the DocType doesn't exist

## Best Practices

1. **Work out the DocType from the file first.** Look at the headers and sample rows of the attached file. Tell the user what you think it is and why, e.g. "These look like **Customers**: there's a name, a GSTIN and a customer group." Then call this tool.
2. **Match columns by meaning, not exact label.** "Cust Name" → `customer_name`, "Party" → the customer or supplier name, "GSTIN No." → the GSTIN field. Use labels, types and options to decide. A column with no field of the same name may still have one (State or Region → `territory`). Never set a column to "Don't Import" on your own: ask the user about a column you can't place.
3. **Check the child tables.** A column like "Barcode" on an item list belongs in `barcodes`, not on the Item itself.
4. **Map a customer's or supplier's phone and email** by default; leave them out only when the user says so. When the schema has a `contacts` table (Frappe 16), map a Mobile / Phone / Contact No column to `contacts.mobile_no` and an Email column to `contacts.email_id`, and address columns to the `addresses` table: each row then gets its own linked Contact and Address. Otherwise map them to `mobile_no` and `email_id`: on a new Customer or Supplier, ERPNext creates the primary contact from them.
   - **Say which record each column goes to** (#34414): a customer or supplier sheet becomes up to three records, the party, its Contact (phone, email, the contact's name) and its Address. Show the mapping in those three groups, so the user sees that the phone goes to the Contact, not the Customer.
   - The check saves each row as all of them together: if the Contact or the Address fails (an email ERPNext can't read, an address without a city), the whole row fails and nothing of it is imported. A row with no phone and no email makes no Contact. The Contact is the party's primary one, so its phone and email show on the Customer.
   - **No `addresses` table** (Frappe 15): the party has no address fields, so address columns can't come in with it. Say so, and leave them for an Address import linked to the parties, after them.
   - Deleting an imported customer or supplier also deletes the Contact and Address made with it (ERPNext does it): when an import is undone, don't delete them separately.
5. **Some data is its own DocType in ERPNext.** Without those tables, addresses, and contacts beyond the first, are separate **Address** and **Contact** records, not fields on Customer. Say so, and import them as a separate step.

## Related

- `set_column_mapping` saves the mapping on the import session and shows what's still missing.
