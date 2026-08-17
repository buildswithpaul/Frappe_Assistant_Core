# How to Use generate_report (with report_list and report_requirements)

## Overview

Frappe/ERPNext includes hundreds of built-in business reports. Three tools work together for report execution:

1. **`report_list`** — discover available reports by module
2. **`report_requirements`** — get mandatory filters and valid options for a specific report
3. **`generate_report`** — execute the report with filters

**Always follow this workflow: list → requirements → generate.**

## report_list Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `module` | string | No | Filter by module: `"Accounts"`, `"Selling"`, `"Stock"`, `"HR"`, `"CRM"` |
| `report_type` | string | No | `"Script Report"`, `"Query Report"`, or `"Report Builder"` |

Returns: `{ reports: [{ name, report_name, report_type, module, is_standard, disabled }], count }`.

## report_requirements Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `report_name` | string | **Yes** | — | Exact report name |
| `include_filters` | boolean | No | `true` | Include filter requirements |
| `include_columns` | boolean | No | `true` | Include column structure |
| `include_metadata` | boolean | No | `false` | Include technical metadata |

Returns filter definitions with field types, required flags, and valid options.

### Filter values are per-report, never per-fieldname

`generate_report` validates your filters against **the definitions this report declares** — the same ones `report_requirements` returns. Two reports can give the same filter name completely different meanings, so never carry a value over from one report to another.

`range` is the clearest example:

| Report | `range` fieldtype | Accepted values |
|--------|-------------------|-----------------|
| Accounts Receivable / Payable (+ Summary) | `Data` | ageing buckets, e.g. `"30, 60, 90, 120"` |
| Stock Ageing | `Data` | ageing buckets, e.g. `"30, 60, 90"` |
| Sales Analytics, Stock Analytics | `Select` | `Weekly`, `Monthly`, `Quarterly`, `Half-Yearly`, `Yearly` |
| Website Analytics | `Select` | `Daily`, `Weekly`, `Monthly` |
| Sales Pipeline Analytics | `Select` | `Monthly`, `Quarterly` |

For a value-constrained filter (`Select`, `Autocomplete`), `options` is always an explicit list of the accepted values — use one of them verbatim. For a `Link` filter, `options` is the target DocType and the value must be an existing record name.

**Every advertised `default` is guaranteed executable.** Passing the defaults `report_requirements` returns will never be rejected as an invalid value, and omitting a filter applies that same default.

When a value is rejected, `validation_errors` names the accepted values and `error_details` carries them as structured data:

```json
{
  "success": false,
  "validation_errors": ["Invalid range: 'Weekly'. Must be one of: Monthly, Quarterly"],
  "error_details": [
    {
      "fieldname": "range",
      "type": "invalid_option",
      "value": "Weekly",
      "accepted_values": ["Monthly", "Quarterly"]
    }
  ]
}
```

`type` is one of `invalid_option`, `unknown_record` (a Link value with no such record — `suggestions` offers candidates), or `invalid_date`.

## generate_report Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `report_name` | string | **Yes** | — | Exact report name |
| `filters` | object | No | `{}` | Filter key-value pairs |
| `format` | string | No | `"json"` | `"json"`, `"csv"`, or `"excel"` |

## Best Practices

1. **Always call `report_requirements` first** — missing mandatory filters often cause empty results or errors. The tool auto-defaults dates and company, but these defaults may not match what you need.
2. **Use exact values for Link filters** — company names, customer names, etc. must match exactly what's in the database.
3. **Take Select values from that report's own `options`** — the same filter name can accept different values in a different report.
4. **Use `report_list` to find reports** — don't guess report names. Common modules: Accounts, Selling, Buying, Stock, HR.
5. **Script Reports are most powerful** — they have custom business logic. Query Reports are simpler SQL-based reports.
6. **Use `format: "csv"` or `"excel"` for exports** — returns downloadable file links.

## Common Workflow

### Step 1: Find reports
```json
{ "module": "Accounts" }
```

### Step 2: Check requirements
```json
{ "report_name": "Accounts Receivable Summary" }
```

### Step 3: Execute with proper filters
```json
{
  "report_name": "Accounts Receivable Summary",
  "filters": {
    "company": "My Company Ltd",
    "report_date": "2024-12-31"
  }
}
```

## Common Reports by Module

| Module | Reports |
|--------|---------|
| Accounts | P&L Statement, Balance Sheet, Accounts Receivable Summary, General Ledger, Trial Balance |
| Selling | Sales Analytics, Sales Order Analysis, Customer Acquisition and Loyalty, Territory-wise Sales |
| Stock | Stock Balance, Stock Ledger, Stock Ageing, Warehouse-wise Stock Balance |
| HR | Employee Information, Attendance, Monthly Attendance Sheet |

## Edge Cases

- **Empty results** — usually means filters are wrong. Check `report_requirements` for correct filter names and valid values.
- **Date filters** — use `YYYY-MM-DD` format.
- **Company filter** — most reports require a company. Get exact company name from `list_documents` with `doctype: "Company"`.
- **Report Builder reports are NOT supported** — only Script Reports and Query Reports work.
- **Large reports** — may take longer; the tool handles polling automatically for prepared reports.
