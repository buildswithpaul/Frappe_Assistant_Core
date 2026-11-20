# How to Use set_column_mapping

## Overview

The `set_column_mapping` tool saves which column of the user's migration file goes to which ERPNext field, on the file's import session. The session keeps it across the conversation, so the mapping is still there on later turns. It is saved in Data Import's own format, so the import later uses it as it stands.

The session comes from `start_import_session`. Get the fields from `get_import_schema` first. Saving moves the session to **Mapped** and adds a "Map Columns" row to its step log.

Sessions a preset opened (start_import_session's `matched: true`) already have their mapping. Use this tool to change any column the user wants changed.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session` | string | **Yes** | The import session id |
| `mapping` | object | **Yes** | Column → field. Only the columns to set or change. |
| `doctype` | string | No | The target DocType. Needed the first time; changing it clears the mapping. |
| `import_type` | string | No | `Insert New Records` or `Update Existing Records`. Default: keep the session's. |
| `match_on` | array | For updates | The field(s) that find each row's record, e.g. `["tax_id"]`. |

In `mapping`:
- **A column** is its header exactly as in the file (`"Cust Name"`), or its 0-based position (`"3"`) when two columns share a header.
- **A field** is a fieldname (`"customer_name"`), a child table field as `"<table fieldname>.<fieldname>"` (`"barcodes.barcode"`), or `"Don't Import"` to skip the column. An exact label also works.

## Response Format

```json
{
  "success": true,
  "session": "IMP-2026-00012",
  "doctype": "Item",
  "status": "Mapped",
  "mapping": [
    {"column": "Code", "position": 0, "field": "item_code", "label": "Item Code"},
    {"column": "Group", "position": 1, "field": "item_group", "label": "Item Group"}
  ],
  "child_tables": {
    "Barcodes (barcodes)": [
      {"column": "EAN", "position": 3, "field": "barcodes.barcode", "label": "Barcode"}
    ]
  },
  "not_imported": ["Internal Ref"],
  "unmapped_columns": ["Old Code"],
  "missing_required": [],
  "required_when": [],
  "summary": "3 columns mapped, 1 not imported, 1 unmapped."
}
```

If anything is wrong, **nothing is saved**. `problems` says what to fix, for example `'item_nme' is not an importable field of Item. Did you mean 'item_name' (Item Name)?`, and `columns` lists the file's headers. Fix those entries and call again.

## Updating existing records

Start the session with `import_type: "Update Existing Records"` (or pass it here). Pass `match_on`:
the field(s) that find each row's record, mapped from the file's key column(s): `["tax_id"]`,
`["customer_name"]`, `["item_code", "price_list"]` for Item Price. A column mapped to the ID
(`name`) is the match on its own. The key columns are only used to find records; they are never
written. Child-table columns can't be updated from a file: map them to "Don't Import".

## The old system's ID column

Many exports carry the old system's own ID for each row: an Odoo `id` or `External ID`, a Zoho
`Customer ID`, a Tally ledger's name. Later files (orders, invoices, payments) refer to records by
that ID, and ERPNext names the record differently, so the ID has to be kept when the record is
created. When the file has such a column, pass it as `source_key_column` (its header or position)
with `source_system` (`odoo`, `zoho`, `tally`, `quickbooks`... the system's short name, in lower
case; ask the user when you can't tell). The call marks it; the result's `old_ids` says so.

- The key column is **not imported** unless you also map it to a field (an Item code is both).
  Never map it to the ID (`name`): the records would be named by their old codes (an Item Group
  `G01`), and the call refuses it for a DocType ERPNext names itself.
- Pass `{}` as `mapping` to set only the key column on a session that is already mapped. Pass the
  column again to change it; the system is kept when you leave it out.
- Don't guess a column from a name like `ref`: ask the user, and never mark one when no column
  holds an ID.
- Changing the target DocType drops the key column, like the rest of the mapping.
- A preset (`start_import_session` on a recognised export) marks its own key column: nothing to do.

### Where the old IDs are kept

In FAC's key map: it adds nothing to the record's form and works the same for the import. **Don't
ask the user where to keep them.** Say `old_ids.message` in one sentence and go on to the dry run.

- `old_ids.existing_fields` lists fields that already hold the file's IDs. Only when a **System
  Manager** wants them there, call again with `old_id_field` set to that fieldname (and `{}` as
  `mapping`). Anyone else gets a refusal, and the IDs stay in the key map.
- `old_ids.new_field` is the field to add when the user asks to **see** the old IDs on the form:
  create it with `create_document`, exactly that record, on its own (never in a list), then call
  again with `old_id_field: "fac_old_system_id"`. Don't offer it unasked.
- `old_id_field: "key_map"` moves them back from a field to the key map.
- The choice is one setting per DocType and source system for the whole site, and later files use
  it too.

## When the mapping can't change

While the session's import is running (**Importing**) the mapping is kept: wait for the import to finish, or continue it with `start_import`. A session that was cancelled keeps its mapping too: start a new session for the file. A file set up as opening stock, invoices or balances (`set_opening_stock`, `set_opening_invoices`, `set_opening_balances`) keeps its columns in that setup: change them with the same tool, never here, or the setup reads the wrong columns. The one thing this tool sets on such a file is a column of another system's IDs (a party's Tally Ledger ID): pass only `old_id_columns`, with `mapping` {}.

## Best Practices

1. **During an import of a file, don't show the mapping table:** the check's card is what the user sees. Show the table only when the user asks for it, or changes the mapping. Then show it as a table: *Your column → ERPNext field*. Show each child table in its own table under its title. Below, mark the **unmapped columns** and the **required fields with no column** clearly. An unmapped column is not imported, like one mapped to "Don't Import".
2. **Don't ask before the check.** Map what you're sure of yourself and go straight to `dry_run_import`: its `card` is the one question the user answers. Only a column you can't place at all goes on that card's question (or one question with it), offering the likely fields, **"Create a field '<column>' on <DocType>"** (a text field; one `create_document` call of Custom Field per field, all in ONE response as parallel tool calls so they are approved on one card, System Manager only, then map them) and "Don't import". Never put another system's columns in Notes. A column that only numbers the rows (S.No, Sr. No., #) needs no question.
   - **Insert or update** is not a question: with no records of the DocType yet, it's always new records.
   - **Use the site's own fields first.** `get_import_schema` lists custom fields too: a code column ("Customer": C000065) goes to a field like "Legacy Customer Code", a "Project ID" to "Legacy Project Reference", when the site has one.
   - **The file's own ID.** When the DocType is named by a series (PROJ-0001…) and the file has a column of IDs that are all different (Project ID), map it to the ID (`name`) on new records, so the records keep the client's IDs.
3. **Corrections are one call.** When the user says "that's the billing city, not the shipping city", send just that column with its new field. The other columns keep their mapping. Confirm the change in a sentence.
4. **A required field with no column** needs a decision: map a column to it, rely on its default if it has one, or the user adds the column to the file. An update (Update Existing Records) lists none: it changes only the fields mapped. For a DocType named by the user, `name` (ID) is listed until a column maps to it.
5. **`required_when`** lists fields with no column that a condition makes required (`when`), with `sample_rows`: how many of the file's first rows meet it, or `null` when that can't be worked out (a condition written for the browser). Tell the user: the import goes through without them, but Desk asks for them when the record is next saved.
6. **Changing the target DocType** clears the mapping, because the fields differ. Say so before you do it.
7. **A party (customer, supplier) by name, not by code.** When the file has both a party code column (e.g. "Customer": C000065) and a name column (e.g. "Customer name"), map the **name** column to the link and the code to "Don't Import" (or to the old ID): a missing party is created by the value it is linked by, and one named "C000065" is no use to anyone. Ask when unsure.
8. **A link column whose values the site doesn't have and can't create** (e.g. Department codes on a new site): offer "Don't import" for that column in the same question as the other unsure ones, rather than letting every row fail on it.

## Next

Once the user agrees the mapping, call `dry_run_import(session)` to check every row before anything is imported: **after `set_column_mapping`'s reply, never in the same response** (sent together, the check runs before the mapping is saved). A required Company with no column: a column of the old system's company or legal entity is mapped to Company by the tool itself; its codes are matched to a company on the card.

## In a migration plan

When the session is in a migration plan (its `migration_plan` is set), don't ask the user here:
`dry_run_import` with `plan` gathers every question of the plan into one list, and a file's columns no field was given are one question there (`kind` `columns`). Map the columns you are sure of; leave the unsure ones for that list.
