# report_list

Discover and search available Frappe business reports across all modules.

## When to Use

- Finding reports for business questions before custom analysis
- Discovering available analytics and reporting options
- Exploring reports by module (Selling, Accounts, Stock, HR)
- Understanding what report types are available

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| module | string | No | All modules | Filter by module (e.g., 'Accounts', 'Selling', 'Stock') |
| report_type | string | No | All types | Filter by type: 'Report Builder', 'Query Report', 'Script Report' |

## Report Types

| Type | Description | Capability |
|------|-------------|------------|
| Script Report | Most powerful, custom Python logic | Complex analytics, custom calculations |
| Query Report | SQL-based custom queries | Flexible data retrieval |
| Report Builder | Simple list views | Basic filtering and display |

## Examples

### List All Reports

```json
{}
```

### Reports by Module

```json
{
  "module": "Selling"
}
```

```json
{
  "module": "Accounts"
}
```

```json
{
  "module": "Stock"
}
```

### Reports by Type

```json
{
  "report_type": "Script Report"
}
```

### Combined Filter

```json
{
  "module": "Accounts",
  "report_type": "Script Report"
}
```

## Common Modules

| Module | Report Examples |
|--------|-----------------|
| Selling | Sales Analytics, Quotation Trends, Territory Analysis |
| Accounts | P&L Statement, Balance Sheet, Accounts Receivable |
| Stock | Stock Ledger, Item-wise Stock Movement, Warehouse Wise Stock |
| Buying | Purchase Analytics, Supplier Quotation Comparison |
| HR | Attendance, Leave Balance, Monthly Salary |
| CRM | Lead Details, Opportunity Summary |

## Response Format

### Success

```json
{
  "success": true,
  "reports": [
    {
      "name": "Sales Analytics",
      "report_name": "Sales Analytics",
      "report_type": "Script Report",
      "module": "Selling",
      "ref_doctype": "Sales Invoice",
      "is_standard": "Yes",
      "description": "Sales analytics by customer, item, territory"
    },
    {
      "name": "Profit and Loss Statement",
      "report_name": "Profit and Loss Statement",
      "report_type": "Script Report",
      "module": "Accounts",
      "ref_doctype": "GL Entry",
      "is_standard": "Yes",
      "description": "Financial P&L report"
    }
  ],
  "count": 2,
  "module_filter": "Selling",
  "report_type_filter": null
}
```

### No Reports Found

```json
{
  "success": true,
  "reports": [],
  "count": 0,
  "module_filter": "NonExistent",
  "report_type_filter": null
}
```

## Popular Reports by Use Case

| Use Case | Recommended Reports |
|----------|---------------------|
| Revenue Analysis | Sales Analytics, Sales Invoice Trends |
| Customer Analysis | Customer Ledger, Accounts Receivable Summary |
| Inventory | Stock Balance, Stock Ledger, Item-wise Stock Movement |
| Financial | P&L Statement, Balance Sheet, Trial Balance |
| Purchasing | Purchase Analytics, Supplier Quotation Comparison |
| HR | Attendance, Leave Balance, Monthly Salary Register |

## Recommended Workflow

1. **Discover** reports using this tool
2. **Understand** requirements using `report_requirements`
3. **Execute** the report using `generate_report`
4. **Analyze** results using `run_python_code` if needed

## Permission Filtering

- Reports are filtered based on user permissions
- Only reports the user can access are returned
- Module-level permissions may apply

## Related Tools

- **report_requirements** - Get filter requirements before execution
- **generate_report** - Execute a discovered report
- **run_python_code** - Custom analysis on report data
