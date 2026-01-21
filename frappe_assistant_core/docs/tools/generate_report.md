# generate_report

Execute pre-built Frappe business reports with filtering and formatting.

## When to Use

- **Always try first** for business data needs
- Sales analytics and revenue reporting
- Financial statements and P&L reports
- Customer and supplier insights
- Inventory and stock reports
- Territory and performance analysis

## Priority Order

1. **Use `generate_report`** for standard business reports
2. Fall back to `analyze_business_data` for custom analysis
3. Use `run_python_code` only for complex custom requirements

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| report_name | string | Yes | - | Exact report name (case-sensitive) |
| filters | object | No | {} | Report-specific filters |
| format | string | No | "json" | Output: "json", "csv", "excel" |

## Examples

### Sales Analytics

```json
{
  "report_name": "Sales Analytics",
  "filters": {
    "doc_type": "Sales Invoice",
    "tree_type": "Customer",
    "value_quantity": "Value",
    "from_date": "2024-01-01",
    "to_date": "2024-12-31"
  }
}
```

### Accounts Receivable Summary

```json
{
  "report_name": "Accounts Receivable Summary",
  "filters": {
    "company": "Your Company Name",
    "report_date": "2024-06-30"
  }
}
```

### Profit and Loss Statement

```json
{
  "report_name": "Profit and Loss Statement",
  "filters": {
    "company": "Your Company Name",
    "from_fiscal_year": "2024",
    "to_fiscal_year": "2024",
    "periodicity": "Monthly"
  }
}
```

### Stock Balance

```json
{
  "report_name": "Stock Balance",
  "filters": {
    "company": "Your Company Name"
  }
}
```

### Balance Sheet

```json
{
  "report_name": "Balance Sheet",
  "filters": {
    "company": "Your Company Name",
    "from_fiscal_year": "2024",
    "to_fiscal_year": "2024"
  }
}
```

## Response Format

```json
{
  "success": true,
  "report_name": "Sales Analytics",
  "columns": [
    {"fieldname": "customer", "label": "Customer", "fieldtype": "Link"},
    {"fieldname": "total", "label": "Total", "fieldtype": "Currency"}
  ],
  "data": [
    {"customer": "ABC Corp", "total": 150000},
    {"customer": "XYZ Ltd", "total": 125000}
  ],
  "total_rows": 2,
  "report_type": "Script Report",
  "filters_used": {...}
}
```

## Report Types

| Type | Description | Capability |
|------|-------------|------------|
| Script Report | Python-based | Complex calculations, aggregations |
| Query Report | SQL-based | Flexible data retrieval |
| Report Builder | Simple views | **NOT SUPPORTED** - use `list_documents` |

## Filter Validation

Filter values are validated before execution:

- **Link fields** (company, customer, item) - Must be exact names
- **Select fields** (tree_type, doc_type) - Must use exact enum values
- **Date fields** - Format: "YYYY-MM-DD"

### Invalid Filter Error

```json
{
  "success": false,
  "error": "Invalid filter value for 'company': 'ABC'. Did you mean 'ABC Corporation'?",
  "suggestions": ["ABC Corporation", "ABC Industries"]
}
```

## Prepared Reports

Large reports (Stock Balance, Sales Analytics with large datasets) are "Prepared Reports":
- Automatically waits for completion (up to 5 minutes)
- Cached results return immediately on retry
- If timeout, retry with same filters to get cached results

## Common Reports

### Sales & Revenue
- Sales Analytics
- Quotation Trends and Analytics
- Sales Order Analysis
- Sales Person Target Variance

### Accounts
- Accounts Receivable Summary
- Accounts Payable Summary
- Profit and Loss Statement
- Balance Sheet
- Trial Balance
- General Ledger

### Stock & Inventory
- Stock Balance
- Stock Ledger
- Item-wise Stock Movement
- Warehouse Wise Stock Balance

### Buying
- Purchase Analytics
- Supplier Quotation Comparison
- Purchase Order Analysis

## Recommended Workflow

1. **Discover** reports: `report_list`
2. **Get requirements**: `report_requirements`
3. **Execute**: `generate_report`
4. **Analyze results**: `run_python_code` if needed

## Filter Discovery

Before executing, use `report_requirements` to find:
- Required filters
- Valid filter values
- Filter types

```json
{"report_name": "Sales Analytics"}
```

## Related Tools

- **report_list** - Discover available reports
- **report_requirements** - Get filter requirements
- **analyze_business_data** - Custom analysis (fallback)
- **run_python_code** - Complex data processing
