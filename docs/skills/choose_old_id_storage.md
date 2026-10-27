# How to Use choose_old_id_storage

Where to keep the old system's IDs of a migration file, so later files (orders, invoices, payments,
or the same file again next week) can refer to the records by those IDs.

## When

A file has a column that holds the old system's own ID for each row, and you marked it with
`set_column_mapping` (`source_key_column`, `source_system`), or a preset did. The dry run is
refused until the user's answer is recorded: ask before it.

## The question, in order

Call `choose_old_id_storage(session)`. Read `offer`:

1. **`existing_field`**: a field of the record already holds these IDs (a custom field the client
   made, or a standard one such as an Item's code or a customer's tax ID). Ask `question` with
   `ask_user` ("These IDs are already kept in Customer > Tax ID (38 of 40 match). Use this
   field?"). On yes: `choose_old_id_storage(session, use="field", fieldname=...)`.
2. **`new_field`**: nothing holds them. Ask `question` ("Keep the old IDs in a new field Old System ID
   on Customer? If you'd rather not add a field, I'll keep them in FAC's key map instead."). On
   yes: create the field with `create_document`, **exactly the input in `new_field.record`**, on its
   own, never in a list (it is a customisation: it gets its own approval card). Then
   `choose_old_id_storage(session, use="field", fieldname="fac_old_system_id")`.
3. **The user doesn't want a field** (or says so in answer to either question):
   `choose_old_id_storage(session, use="key_map")`. The IDs are then kept in FAC's own key map
   and nothing is added to the DocType. Say so in one sentence and don't ask again.
4. `offer` is `null` and `storage` is set: it was answered before, for this DocType and source
   system. Don't ask again; go on to the dry run.

## Rules

- Never pick for the user, and never choose `field` for a field the result didn't list: the tool
  refuses a field that doesn't hold this file's IDs.
- A field is read-only for people: the IDs are written by the import, never typed.
- Records keep their old ID after an import creates them, including retries and each level of a
  tree file. Undoing an import removes the key-map rows it wrote; a field value goes with its record.
- The answer is kept for the site, so the next session of the same DocType and system doesn't ask.

## Next

`dry_run_import(session)`.
