# How to Use convert_crm_lead

## Overview

Converts a Frappe CRM lead into a deal through CRM's own conversion — the same as the Convert to Deal
button: the lead is marked converted, a Contact and (if the lead names one) a CRM Organization are
created or reused, assignees carry over, and the deal shows the lead's history. Calling it again for the
same lead returns the deal it already made.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `lead` | string | **Yes** | The CRM Lead name |
| `deal_fields` | object | No | Extra deal fields, e.g. `{"expected_deal_value": 1800000, "expected_closure_date": "2026-11-30", "next_step": "Send proposal"}` |

## Response

`{"success": true, "deal", "link"}` — `link` is `/crm/deals/<deal>`.

## Tips

- Never convert by creating a `CRM Deal` with `create_document`: that leaves the lead unconverted, with no contact.
- A Lost lead cannot be converted; when the site requires forecasting, pass `expected_deal_value` and
  `expected_closure_date` in `deal_fields`.
