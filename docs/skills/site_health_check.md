# Site Health Check

## Overview

A read-only audit of an ERPNext site's setup. You check the configuration that makes transactions fail or post wrongly — missing default accounts, no fiscal year, negative stock, a stopped scheduler — and report it as one prioritised table. **You change nothing during the check.** Fixes happen afterwards, one at a time, through `get_skill("setup-change-protocol")`.

## When to use

- "Check my setup", "is my ERPNext configured correctly?", "health check", "audit my site", "what's missing before go-live?"
- A partner or a previous admin handed the site over and the user wants to know its state.

**Not for** one specific error ("why won't this invoice submit?") — investigate that directly. Not for server performance tuning.

## Workflow

1. **Scope.** `list_documents` on `Company` (fields `name`, `country`, `default_currency`, `abbr`). More than one company → `ask_user` (`single_select`, with an "All companies" option).
2. **Detect what the business uses**, so you skip what doesn't apply and say so:
   - Stock: any `Item` with `is_stock_item = 1` and `disabled = 0`.
   - Selling / buying: any `Sales Invoice` / `Purchase Invoice`, or the user said they sell or buy.
   - India Compliance: `get_doctype_info` on `GST Settings` succeeds (the app is installed) and the company's `country` is `India`.
3. **Run the checks below** for the sections that apply. If you hand a section to a helper, name this skill (`site-health-check`) and the section in the task, so it applies these severity rules rather than a summary of them. Batch reads: one `get_document` per company, one `list_documents` per check — never one call per record.
4. **Report** (see Reporting). Then stop — don't start fixing.
5. **Offer the next step** in one sentence: fix the critical findings (through `setup-change-protocol`), or run this check on a schedule as an agent.

## Checks

Severity: **Critical** = transactions will fail or post wrongly. **Warning** = works today, will bite later. **Note** = housekeeping.

### A. Company defaults — `get_document("Company", <name>)`

| Field empty | Severity | Why |
|---|---|---|
| `default_receivable_account`, `default_payable_account` | Critical | Invoices fail unless every party has its own account |
| `round_off_account`, `round_off_cost_center` | Critical | Any invoice with rounding fails to post |
| `default_income_account`, `default_expense_account` | Warning | Every item then needs its own account |
| `cost_center` | Warning | Every transaction needs one typed in |
| `exchange_gain_loss_account` | Warning, only if a non-`default_currency` Customer, Supplier or Price List exists | Exchange differences on foreign-currency payments have no account to post to |
| `enable_perpetual_inventory = 1` with `stock_adjustment_account` or `stock_received_but_not_billed` empty | Critical | Stock transactions fail to post |
| `tax_id` (or, with India Compliance, `gstin` / `gst_category`) | Critical for India, Note elsewhere | GST invoices and returns need it |
| `default_letter_head` (and no `Letter Head` with `is_default = 1`) | Note | Printed documents have no header |

Then read every account the company names in one `list_documents` on `Account` (`filters: {"name": ["in", [...]]}`, fields `name`, `is_group`, `disabled`, `company`). An account that is a group, disabled, or belongs to another company is **Critical** — it's set, but it can't be posted to.

### B. Fiscal year — `list_documents` on `Fiscal Year`, `disabled = 0`

Fields `name`, `year_start_date`, `year_end_date`; `get_document` each one to see its `companies` table.

- No fiscal year covers today for this company → **Critical** ("Fiscal Year not found" on every transaction).
- Today is within 45 days of the year's end and the next year doesn't exist → **Warning**.

### C. Taxes

- No `Sales Taxes and Charges Template` with `company` = this company and `disabled = 0` → **Warning** (if they sell). Same for `Purchase Taxes and Charges Template` (if they buy).
- None of them `is_default = 1` → **Note**.
- **India Compliance installed:** it creates the GST templates itself when a company is saved. If they're missing, say so and point to GST Settings — **never hand-build GST templates**.

### D. Stock — only if stock is in use

`get_document("Stock Settings", "Stock Settings")`:
- `allow_negative_stock = 1` → **Warning**. It's the most common root cause of wrong stock valuation.
- `valuation_method` empty → **Note**; `default_warehouse` empty → **Note**.

Then:
- `Bin` with `actual_qty < 0` → **Critical**: give the count and the ten worst (`item_code`, `warehouse`, `actual_qty`).
- No `Warehouse` with `company` = this company, `is_group = 0`, `disabled = 0` → **Critical**.
- Perpetual inventory on, and a leaf warehouse has no `account` while the company has no `default_inventory_account` → **Critical**.
- `Item` with `is_stock_item = 1`, `disabled = 0`, `valuation_rate <= 0` → **Note** with the count: opening stock or a material receipt without a rate will fail or post at zero.

### E. Selling and buying defaults

`get_document` on `Selling Settings` and `Buying Settings`. An empty `customer_group`, `territory`, `selling_price_list`, `supplier_group` or `buying_price_list` → **Note** (every new record needs it typed). A default price list whose `Price List` has `enabled = 0` → **Warning**.

### F. System — System Manager only; skip quietly otherwise

- `get_document("System Health Report", "System Health Report")` if that doctype exists. It computes live and takes a few seconds. `scheduler_status` is `Inactive` or `Process Not Found` → **Critical** (emails, auto-repeat and scheduled jobs stop); `Dormant` → **Note** (Frappe pauses the scheduler on an idle site, and it resumes on activity). Rows in `failing_scheduled_jobs` → **Warning**. `failed_emails > 0` → **Warning**. `onsite_backups = 0` → **Warning**.
- No `Email Account` with `enable_outgoing = 1` and `default_outgoing = 1` → **Warning**: invoices and notifications can't be emailed.

### G. Stale drafts

Count `docstatus = 0` with `posting_date` more than 30 days ago on `Sales Invoice`, `Purchase Invoice`, `Delivery Note`, `Purchase Receipt` and `Journal Entry` → **Note** per doctype with a count. Forgotten drafts are the usual reason "the report doesn't match".

## Reporting

1. One line: "**2 critical**, 3 warnings and 4 notes across 6 areas."
2. One table sorted by severity: Severity | Area | Finding | Why it matters | Link. Link each record: `[Company A](/app/company/Company%20A)`.
3. One line listing the areas you skipped and why ("Stock — no stock items").

Write findings in business language ("invoices with rounding will fail to post"), not field names. Put the field name in the link or leave it out.

## Gotchas

- **A Single doctype's name is its doctype name**: `get_document("Stock Settings", "Stock Settings")`.
- **A Fiscal Year with an empty `companies` table applies to every company.** Don't report it missing for a company it doesn't list.
- **A field that is set can still be broken.** Always run the Account follow-up in section A — a disabled or group account passes an "is it filled?" check.
- **Don't inflate severity.** Critical means a transaction fails or posts wrong today. A missing letter head is not critical.
- **An empty or refused read is not a finding.** If a read returns a permission error, or nothing at all from a doctype you may not be able to see (Email Account, GST Settings), say "I couldn't check X". Never report it as missing.

## Anti-patterns

- Fixing things mid-check. The user asked what's wrong; show them the whole picture first.
- Dumping raw documents or every negative-stock row. Counts plus the worst ten.
- Checking stock or GST for a business that has neither.
