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

## generate_report Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `report_name` | string | **Yes** | — | Exact report name |
| `filters` | object | No | `{}` | Filter key-value pairs |
| `format` | string | No | `"json"` | `"json"`, `"csv"`, or `"excel"` |

## Best Practices

1. **Always call `report_requirements` first** — missing mandatory filters often cause empty results or errors. The tool auto-defaults dates and company, but these defaults may not match what you need.
2. **Use exact values for Link filters** — company names, customer names, etc. must match exactly what's in the database.
3. **Use `report_list` to find reports** — don't guess report names. Common modules: Accounts, Selling, Buying, Stock, HR.
4. **Script Reports are most powerful** — they have custom business logic. Query Reports are simpler SQL-based reports.
5. **Use `format: "csv"` or `"excel"` for exports** — returns downloadable file links.

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
