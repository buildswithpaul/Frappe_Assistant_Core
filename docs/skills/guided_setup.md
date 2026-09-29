# Guided Setup

## Overview

Sets up an ERPNext site through a conversation about the business, not the ERP. You ask business questions ("do you hold stock?", "more than one branch?") and turn the answers into a setup plan: warehouses, cost centres, fiscal years, price lists, taxes, numbering, approvals and extra fields. Then you carry the plan out one area at a time, each through `get_skill("setup-change-protocol")`.

## When to use

- "Help me set up ERPNext", "we just installed this, what now?", "set up my company properly", "we're opening a new branch / warehouse".

**Not for** the first-run **setup wizard**. That has to be finished in the browser first, because it creates the first company, its chart of accounts and the first fiscal year. **Not for** importing customers, items or opening balances; point the user to ERPNext's **Data Import** and **Opening Invoice Creation Tool** in Desk.

## Workflow

1. **See where the site stands.** Run `get_skill("site-health-check")` first, or reuse its findings from this conversation. Don't set up what already exists.
2. **Ask about the business.** Use `ask_user`, two or three questions at a time, in plain words. Skip any question the health check already answered.
   - **Entities:** "Is this one legal business, or several with separate books?" Separate books means separate Companies. Branches of one business stay in **one** Company, with a Cost Centre per branch for branch-wise profit and, in India, an Address per branch GSTIN.
   - **Stock:** "Do you keep goods in stock?" If yes: "Where? One store or several?" and "Do you track batches or serial numbers?"
   - **Selling and buying:** "Do you sell at different prices to different customers?" (price lists) and "Which taxes do you charge?"
   - **Controls:** "Does anything need someone's approval before it goes out?" (a threshold and a role)
   - **Documents:** "How should invoice numbers look?" and "Is there anything you write on invoices or delivery notes that the form doesn't have?"
3. **Show the setup plan by area**, in business language, with what each area will create. Let the user reorder or drop areas.
4. **Work one area at a time.** Each area is its own protocol run (plan table → confirm → dry-run → write → change log). Hand off to the matching skill where there is one:
   - Approvals → `set-up-approval-workflow`
   - Numbering → `configure-naming-series`
   - Extra fields → `add-custom-field`
5. **Finish with a re-run** of the health check, and show before-and-after counts.

## Reference

ERPNext adds the company abbreviation to warehouse, cost centre and account names. With company `Acme Traders` and abbreviation `AT`:

```json
{"doctype": "Warehouse", "data": {"warehouse_name": "Chennai Store",
  "parent_warehouse": "All Warehouses - AT", "company": "Acme Traders", "is_group": 0}}
```
Saved as `Chennai Store - AT`. Group warehouses are for grouping only; stock sits in leaf warehouses.

```json
{"doctype": "Cost Center", "data": {"cost_center_name": "Chennai",
  "parent_cost_center": "Acme Traders - AT", "company": "Acme Traders", "is_group": 0}}
```
The root cost centre is named after the company (`Acme Traders - AT`); the default leaf is `Main - AT`.

```json
{"doctype": "Fiscal Year", "data": {"year": "2027-2028",
  "year_start_date": "2027-04-01", "year_end_date": "2028-03-31"}}
```
An empty `companies` table applies to every company.

```json
{"doctype": "Price List", "data": {"price_list_name": "Wholesale",
  "currency": "INR", "selling": 1, "enabled": 1}}
```

Tax templates **outside India** (`Sales Taxes and Charges Template`, and the Purchase equivalent):

```json
{"doctype": "Sales Taxes and Charges Template", "data": {"title": "VAT 5%",
  "company": "Acme Traders", "is_default": 1,
  "taxes": [{"charge_type": "On Net Total", "account_head": "VAT - AT",
             "rate": 5, "description": "VAT 5%"}]}}
```
`account_head` must be an existing leaf `Account` of that company, normally under Duties and Taxes. Create the account first if it's missing.

## Gotchas

- **India Compliance creates GST tax templates and GST accounts itself** when a company is saved. Never hand-build GST templates; send the user to **GST Settings** if they're missing.
- **A second company:** prefer `create_chart_of_accounts_based_on: "Existing Company"` with `existing_company` set, so it copies the first company's chart. A standard template's name depends on the country. If they want one, let them pick it in Desk, where the list is shown.
- **Decide the valuation method (FIFO or Moving Average) before the first stock transaction.** Once any stock transaction exists, ERPNext refuses to change it in Stock Settings (except for items that set their own).
- **Batch and serial-number tracking** is set per item, and can't be switched once the item has stock transactions.
- **Passwords and logos stay in Desk.** An Email Account's password, or a letterhead image, is something the user sets in the browser. Navigate them there with `browser_navigate_to`, and never ask for a password in chat.
- **Don't design a chart of accounts in chat.** Adding an account under the right parent is fine; restructuring the chart is a job for an accountant.

## Anti-patterns

- One giant plan covering every area. Nobody can review 60 rows.
- Asking ERP-shaped questions ("Which valuation method?") before business ones ("Do your prices for the same item change often?").
- Creating a Company per branch of one legal business.
