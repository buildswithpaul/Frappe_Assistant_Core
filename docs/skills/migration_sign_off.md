# Migration Sign-off

Use when the user asks what a data migration brought in, for a migration or sign-off report, whether
they can go live, or for a copy of the report to keep. Every time: run the report, tell the user,
and make the PDF (steps 1 to 3), without waiting to be asked for it.

## 1. Run the report

Call `generate_report` with `report_name: "Migration Sign-off"`, `filters` with `document: 1`, and
**no `import_session`**: a migration is every file the user imported (master data, opening stock,
opening invoices, opening balances), and sessions from other chats count too. Without it, the
report covers all of the user's sessions. Filters:

- `from_date` / `to_date`: the sessions started between these dates. Always give them, `to_date`
  today and `from_date` the start of the current fiscal year unless the user says otherwise: left out, `generate_report` fills in the newest fiscal year, which can be next year's and miss
  every session. They don't narrow sessions named in `import_session`.
- `migration_plan`: a migration plan's id, for a migration the user ran as a plan: the report
  covers its files only, whatever the dates, so earlier test runs of the same files stay out.
  Always pass it for a plan, rather than dates. The report's message starts with its scope:
  quote it, so the user sees what was counted.
- `import_session`: session ids, comma separated. Only when the user names the sessions themselves.
  Never just the ones in this chat.
- `user`: whose sessions; the user's own by default.
- `document`: always 1. The report's `message` is then the whole report written as a document, for
  the PDF in step 3.

**Which period is the migration?** Look at the **Sessions** section. If its sessions started on
different days (earlier test runs or attempts, say), ask the user from which date the migration
counts, then run the report again with that `from_date`, before telling the user anything else or
making the PDF. If the user already said, pass it the first time.

Every number in the report is counted by ERPNext from the files and from the books. Never add up,
round or change a number yourself: quote the report's values.

## 2. Tell the user

Start with the report's `report_summary` cards (rows in the files, imported, left out,
failed, not imported, ready to sign off). Then each `section` of the rows:

- **Records**: per DocType, the rows in the files, imported, left out, failed and not imported. They
  always add up to the rows in the files. Rows the user sent back corrected (the failed-rows file,
  a whole file sent again, a Google Sheet fetched again) are counted as rows of the first file:
  a row is counted once, and stays imported whichever file brought it in.
- **Why Not Imported**: for each reason, how many rows and which ones (row numbers in the file).
- **Opening Balances**: stock value, receivables and payables per company: in the files, the part not
  imported, the files' amount for the rows imported, in ERPNext, and the difference. A receivable or
  payable is compared on the invoices' totals, so a payment after go-live is not a difference.
- **Trial Balance**: the opening balances file's debits and credits, the accounts that differ from
  ERPNext at the cut-off, ERPNext's debit and credit, and what is left on Temporary Opening (zero once
  every opening balance is in).
- **Open Points**: what stands in the way of signing off. Go through them one by one. Failed rows can
  be fixed and imported again (`dry_run_import`, then the import).

The same report opens in Desk: **Migration Sign-off**, for the accountant to check or print.

## 3. The PDF, every time

The report is what the business signs, so make its PDF in the same reply: call `generate_document`
with:

- `title`: "Data migration sign-off report"; `filename`: "Migration sign-off" and today's date;
  `orientation`: "landscape".
- `content`: the report's `message`, exactly as it came (the report run with `document: 1`). It is
  already the whole report, every row and number, with the sign-off block. Don't rewrite, shorten
  or reformat it, and never rebuild it with run_python_code.

Share the `download_link` exactly as `generate_document` returns it.
