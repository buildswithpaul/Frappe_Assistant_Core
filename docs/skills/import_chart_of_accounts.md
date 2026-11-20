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
   Account Type, Is Group, and on ERPNext v16 Account Category. With headings like these, map them yourself
   without asking the user to confirm, and go straight to the check: the check's card is the one question.
   Root Type is read from its column by the check (mapping it is fine, it is read either way). Don't open
   the session again. A Tally export of groups and ledgers is one
   sheet with the group as the parent.
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
   - `names_from_another_company`: the file's names carry another ERPNext company's account numbers
     and/or abbreviation ("141600 - State Bank of India - CCBF", or "2210100 - Current Assets"). ERPNext
     adds this company's own to every account, so kept as they are they would be doubled. Ask it on the **same
     one card** of step 3 (its `clean_names` question; `names_question` gives
     the message, the `examples` (show 2-3 as "in the file → cleaned") and the two `choices`, **Remove
     them** first (suggested; the number taken off becomes the account number) and **Keep the names as
     they are**. Pass the answer as `clean_names` inside `chart` on the next check and to the import or
     replace. Don't ask it again later: an import without the answer is refused and points back here.
   - **Account Category** (ERPNext v16 only; the check has `by_category` then). It is the line of the
     Schedule III / IFRS Balance Sheet and P&L each account goes on; ERPNext reads it from ledgers only.
     Every ledger gets one: the file's own column, then ERPNext's own account of that name, words in the
     name ("Fixed Deposit" is an investment even if the file types it Fixed Asset), the group above, the
     account type. Show `by_category` as a short table. `categories_to_check` lists the ledgers that only
     got their root type's usual category: show them in one list and ask the user to confirm or name the
     right one, passed as `classifications` ({account name: {account_category}}). `categories_not_found`
     lists categories in the file the site doesn't have.
   - `already_in_place`: the company has this chart already. Say so and stop; there is nothing to
     offer.
3. **Ask once, on ONE card** (`ask_user`, one `single_select` per entry of `questions`, the `suggested`
   answer first). Don't ask the company or the mode before the check, and ask nothing again after the card.
   The card's title is `card_title`; each choice shows its `effect`.
   - `mode`: replace / add / map with what each does. A company with no transactions is suggested
     **replace** (the file's chart and nothing else); add's effect says how many of the company's own
     accounts it keeps beside the file's, with look-alikes ("Bank Accounts" and "Bank Account"). With
     transactions, **map** is suggested and replace isn't offered (`modes.replace_refused` says why).
   - `doubtful`, `clean_names`, `categories`: the file's mismatched types, the other company's numbers and
     abbreviation, the categories to check; each with examples and its suggested answer.
   Show it as the reply's `next` says: ONE ask_user card, the `headline` as its description, each question
   its own single_select with the suggested choice selected; never the lists written out in a message. A
   file not mapped yet is mapped by the check from its headings (`mapped_by_headings`): don't map it again.
   Each mode choice names its `tool` and `arguments`: **replace is `replace_chart_of_accounts`**, never a
   mode of `import_chart_of_accounts`.
   The user's answer on that card is their decision: call the tool straight away with the figures the
   check gave (replace: `accounts_removed`, `accounts_created`, `tax_setup_removed`).
4. Do what the user picked:
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
     Afterwards show the reply's `card` (the defaults, built from `defaults_proposed`) as ONE ask_user card,
     never one question per default: each question's suggested account is selected, the other accounts
     below, and "Leave empty"; only accounts ERPNext accepts in that field are listed. Set the user's picks
     (each option's `set`) on the Company with `update_document`, all in one call. A default no account
     fits is named in the card's `left_empty` and stays empty; don't search the accounts for one. An option
     with `change_type`: the right account has another type in the file (the client's "Sundry Creditors"
     typed Current Liability); its label says so. If picked, `update_document` that Account's
     `account_type` first, then set the default. And, when
     `tax_setup_removed` is there, help the user set the tax setup up again on the new chart's own tax
     accounts (GST Settings accounts, tax templates, tax withholding accounts), asking which accounts.
     Replace once. If an answer seems lost, check the company's accounts before calling again: a call
     on a company that already has this chart answers `already_in_place` and changes nothing.
   - A chart made for ERPNext's own Chart of Accounts Importer may repeat a name under another number (a
     sub-account named like its parent): that is two accounts, not a problem. Its Parent Account Number
     column links each account to its parent; there is nothing to map for it.
5. A company whose chart came in **before** categories were set (or by hand) has accounts with no Account
   Category: `import_chart_of_accounts(mode="categories", company=...)` sets the empty ones by the same rules,
   no session needed; categories already set are kept. Show `by_category` and `categories_to_check` after.
6. The client's account names and numbers are kept as old IDs under `source_system`, so the opening trial
   balance later resolves its accounts by them without asking.

## Rules

- The company is the user's choice. If they didn't name it, run the check without `company` (never a
  placeholder): with one company on the site the check uses it (say which); with several, the card's first
  question is `company`. Never guess or pick one yourself.

- Never guess an account's root type: an account the rules can't place is asked about.
- Never remove or keep another company's numbers and abbreviation in the names without asking the user.
- Never replace on a company with transactions, whatever the user says: map or add.
- A chart is not designed in chat: restructuring an existing one is an accountant's job.
- When a chart tool refuses or fails, tell the user why and stop. Never create, move, rename or delete
  accounts, tax templates or settings by hand (create_document, update_document, delete_document) to get
  round it: an account put under the wrong root, or setup half removed, is worse than no import.
- A big chart takes a minute or two to add or replace. When a call answers `still_running`, the same
  step is still running from your earlier call: nothing failed and nothing was started again. Don't tell
  the user it failed, and don't run another chart tool on that company: wait a minute and call the same
  tool once more with the same arguments; once the earlier run has finished, that call says what it did.
- The reply gives `created_count` and only a few `created` names: say the count. Never try to read
  back a full list of accounts.
- When the chart is in, say so and ask what the user wants next. Don't start opening balances or any other
  step on your own: a "go ahead" after the chart is not a request for the next step.
- An add that answers `already_on_company` with nothing `created` found the file's accounts in place: an
  earlier call added them. Say the chart is in place (how many accounts), not that nothing was added.
- When the file has a "Root Type" column, it is read even if you don't pass `root_type_column`; pass it
  anyway when the heading differs (e.g. "Account Root").
