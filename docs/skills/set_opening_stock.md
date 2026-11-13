# How to Use set_opening_stock

## Overview

Opening stock is the stock on hand on the cut-off date, carried over from the old system. It goes into
ERPNext as a **Stock Reconciliation with purpose Opening Stock**, never a Stock Entry, so it posts against
the opening account and not an expense. Use this tool, not `set_column_mapping`, for a stock sheet.
It writes no business data.

## Before calling

1. `start_import_session` with the file (`file_id`).
2. Ask the user **which company** and **the cut-off date** (the last day in the old system). Don't guess the date.
   In a migration plan, take both from `plan_migration`'s `opening_setup` (asked once there).
3. Items and warehouses must exist first. If they don't, import them first.

## Parameters

| Parameter | Required | Description |
|---|---|---|
| `session` | Yes | The import session id |
| `company` | Yes | The company the stock belongs to (one company per session) |
| `posting_date` | Yes | Cut-off date, `YYYY-MM-DD`; must be in one of the company's fiscal years |
| `posting_time` | No | Default `23:59:59`, the end of the cut-off day |
| `difference_account` | No | Default: the company's Temporary Opening account. Must be a Balance Sheet account |
| `columns` | Yes | File column header → one of `item_code`, `warehouse`, `qty`, `valuation_rate`, `amount`, `uom`, `batch_no`, `serial_no`, `expiry_date` |

Item, warehouse and quantity are required, plus a rate or a value (`amount`; the rate is worked out from it).
Map `uom` when the file counts in another unit than the item's stock unit: it is converted.

## Who can use it

The user needs Create and Submit on Stock Reconciliation (usually a Stock Manager) and to own the session.

## Next

`dry_run_import(session)`: every row is checked, nothing is written. Then fix what it finds, and
`import_opening_stock`.
