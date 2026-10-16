# How to Use get_crm_activity

## Overview

Reads a Frappe CRM lead's or deal's whole history through CRM's own timeline — the same data as the
record's Activity, Emails, Notes, Calls and Tasks tabs. The lead or deal record itself does not contain
any of this, so read it before summarising a record or deciding what to do next.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doctype` | string | **Yes** | `CRM Lead` or `CRM Deal` |
| `name` | string | **Yes** | The record name, e.g. `CRM-LEAD-2026-00009` |
| `limit` | integer | No | Items per list, 1–100, default 30 |

## Response

`{"success", "record": {doctype, name, title, status, owner, link}, "emails", "notes", "calls", "tasks",
"comments", "changes"}`, each list newest first. HTML is stripped and long text cut at 1,000 characters.
A deal includes the history of the lead it came from.

## Tips

- On a CRM page, call this for the record the Page Context names — "this lead", "her", "the deal".
- Link records with `record.link` (`/crm/leads/…`, `/crm/deals/…`), never `/app/crm-…`.
- Last contact = newest email or call; open work = tasks not Done/Canceled.
