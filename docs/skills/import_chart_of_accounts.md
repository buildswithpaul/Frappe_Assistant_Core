# How to Use import_chart_of_accounts and replace_chart_of_accounts

Put the client's own chart of accounts on a company, so their opening balances and books use the accounts
they already know.

## When

The client has a chart of accounts of their own (an export from Tally, Zoho, QuickBooks, or a sheet) and the
company on this site has the standard one. Do this **before** the opening balances, so the trial balance
finds its accounts by the client's names and numbers.

## Steps

1. Open the file (`start_import_session`) and map its columns to Account fields with `set_column_mapping`
   (DocType Account): Account Name, Parent Account, and where the file has them Account Number, Root Type,
   Account Type, Is Group. A Tally export of groups and ledgers is one sheet with the group as the parent.
2. `dry_run_import(session, chart={"company": ...})`: the chart's check. It writes nothing and asks no approval. Show the tree's top levels, the counts, and what each
   account is proposed to be (root type, account type, and where that came from: the file's own column,
   Tally's primary groups, words in the name, or its parent).
   - `unclassified` lists **every** account no rule could place. Ask the user about all of them in one
     list, then pass the answers as `classifications` ({account name: {root_type, account_type}}): inside `chart` on the next check, and as a parameter of the import.
   - `problems` lists a cycle, an account under a ledger, an account twice. Nothing can be imported until
     the file is corrected.
   - `doubtful` lists accounts whose account type doesn't belong under their root type (a "Stock" account
     under Equity, an expense account under Income). ERPNext takes them and books to them as their type
     says, so show them all in one list and ask: correct the file, or go on as it is.
   - `add_creates_top_level` names the root types the company has no top-level account of (ERPNext's
     "India - Chart of Accounts" has no Equity): add and map make the file's top group of that type the
     company's new top-level account. Say so before the user picks.
   - `already_in_place`: the company has this chart already. Say so and stop; there is nothing to
     offer.
3. Say which modes the company allows (`modes`). **map** is the default when the company has transactions,
   **add** otherwise; **replace** is offered only for a company with no ledger entries, no submitted
   documents and nothing else pointing at its accounts, and `modes.replace_refused` says why otherwise.
4. Do what the user picks:
   - **map**: `import_chart_of_accounts(mode="map")`. The client's accounts that match the company's become
     those accounts; nothing is created. List what matched nothing (`unmatched`) and ask: add them
     (`add_unmatched`) or map them by hand.
   - **add**: `import_chart_of_accounts(mode="add")`. The accounts are created under the right parents,
     parents first. One the company has already is kept.
   - **replace**: tell the user it **deletes** the company's accounts and creates the client's, and how many
     of each: the check gives them in `modes.replace_figures`. It also removes the company's own **tax
     setup**, made for the chart that goes (`modes.replace_figures.tax_setup`: its sales, purchase and item
     tax templates, its rows in the tax withholding categories and in GST Settings; an Indian company gets
     all of them when it is created). Show those counts too. Pass `accounts_removed`, `accounts_created`
     and `tax_setup_removed` exactly, on the first call, so the user approves one card that shows them.
     A template something uses (an item, a customer, a tax rule) stops the replace, and nothing changes.
     It is refused, with the list, while any other record outside the chart points at the company's
     accounts (a draft document, a mode of payment, a warehouse, a customer's account): the user changes
     those, or picks add.
     A mode of payment on the company's default cash account is not refused: ERPNext sets one up for every
     new company, and the replace moves it to the new chart's cash ledger (`cash_mode_of_payment_account`).
     Afterwards set the default accounts listed in `defaults_left_empty` (Company settings), and, when
     `tax_setup_removed` is there, help the user set the tax setup up again on the new chart's own tax
     accounts (GST Settings accounts, tax templates, tax withholding accounts), asking which accounts.
     Replace once. If an answer seems lost, check the company's accounts before calling again: a call
     on a company that already has this chart answers `already_in_place` and changes nothing.
   - A chart made for ERPNext's own Chart of Accounts Importer may repeat a name under another number (a
     sub-account named like its parent): that is two accounts, not a problem. Its Parent Account Number
     column links each account to its parent; there is nothing to map for it.
5. The client's account names and numbers are kept as old IDs under `source_system`, so the opening trial
   balance later resolves its accounts by them without asking.

## Rules

- Never guess an account's root type: an account the rules can't place is asked about.
- Never replace on a company with transactions, whatever the user says: map or add.
- A chart is not designed in chat: restructuring an existing one is an accountant's job.
- When a chart tool refuses or fails, tell the user why and stop. Never create, move, rename or delete
  accounts, tax templates or settings by hand (create_document, update_document, delete_document) to get
  round it: an account put under the wrong root, or setup half removed, is worse than no import.
