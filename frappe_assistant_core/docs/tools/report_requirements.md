# report_requirements

Get report metadata including required filters, columns, and execution requirements before running a report.

## When to Use

- **Before** executing `generate_report` to understand requirements
- When `generate_report` returns filter errors
- To discover valid filter values for Link/Select fields
- Planning complex report execution
- Understanding report structure and capabilities

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| report_name | string | Yes | - | Exact name of the report (e.g., 'Sales Analytics') |
| include_metadata | boolean | No | false | Include technical metadata (creation date, SQL query) |
| include_columns | boolean | No | true | Include column structure information |
| include_filters | boolean | No | true | Include filter requirements and guidance |

## Examples

### Basic Requirements

```json
{
  "report_name": "Sales Analytics"
}
```

### With Full Metadata

```json
{
  "report_name": "Accounts Receivable Summary",
  "include_metadata": true,
  "include_columns": true,
  "include_filters": true
}
```

### Columns Only

```json
{
  "report_name": "Stock Ledger",
  "include_filters": false
}
```

## Response Format

### Success

```json
{
  "success": true,
  "report_name": "Sales Analytics",
  "report_type": "Script Report",
  "prepared_report": false,
  "disable_prepared_report": false,
  "prepared_report_info": {
    "requires_background_processing": false,
    "behavior": "Direct execution - returns results immediately."
  },
  "columns": [
    {"fieldname": "customer", "label": "Customer", "fieldtype": "Link"},
    {"fieldname": "total", "label": "Total", "fieldtype": "Currency"},
    {"fieldname": "qty", "label": "Quantity", "fieldtype": "Float"}
  ],
  "filters_definition": [
    {
      "fieldname": "doc_type",
      "label": "Document Type",
      "fieldtype": "Select",
      "options": ["Sales Invoice", "Sales Order", "Quotation", "Delivery Note"],
      "default": "Sales Invoice",
      "required": true
    },
    {
      "fieldname": "tree_type",
      "label": "Tree Type",
      "fieldtype": "Select",
      "options": ["Customer", "Item", "Territory", "Customer Group"],
      "default": "Customer",
      "required": true
    },
    {
      "fieldname": "value_quantity",
      "label": "Value or Quantity",
      "fieldtype": "Select",
      "options": ["Value", "Quantity"],
      "default": "Value",
      "required": true
    },
    {
      "fieldname": "company",
      "label": "Company",
      "fieldtype": "Link",
      "options": "Company",
      "required": false
    }
  ],
  "required_filter_names": ["doc_type", "tree_type", "value_quantity"],
  "optional_filter_names": ["company", "from_date", "to_date"],
  "filter_requirements": {
    "common_required_filters": [
      "doc_type (Document Type) - Select: Sales Invoice, Sales Order, Quotation, ... (4 options)",
      "tree_type (Tree Type) - Select: Customer, Item, Territory, ... (4 options)",
      "value_quantity (Value or Quantity) - Select: Value, Quantity"
    ],
    "common_optional_filters": [
      "company (Company) - Link to Company",
      "from_date (From Date) - Date",
      "to_date (To Date) - Date"
    ],
    "guidance": [
      "This report requires 3 mandatory filters. All required filters must be provided for successful execution.",
      "Additionally, 3 optional filters are available to refine results. These have default values if not specified."
    ]
  }
}
```

### Prepared Report

```json
{
  "success": true,
  "report_name": "Accounts Receivable Summary",
  "report_type": "Script Report",
  "prepared_report": true,
  "prepared_report_info": {
    "requires_background_processing": true,
    "typical_execution_time": "2 minutes for large datasets",
    "behavior": "First execution automatically waits for completion (up to 5 minutes). Subsequent calls with same filters retrieve cached results instantly.",
    "recommendation": "The tool will automatically wait for report completion. If timeout occurs, retry with the same filters to retrieve cached results."
  }
}
```

## Filter Field Types

| Type | Description | How to Use |
|------|-------------|------------|
| Link | Reference to another DocType | Exact document name required (e.g., "ABC Company") |
| Select | Dropdown with fixed options | Use exact option value from `options` array |
| Date | Date value | Format: "YYYY-MM-DD" |
| Check | Boolean checkbox | Use 1 or 0 |
| Data | Free text | Any string value |

## Common Report Patterns

### Financial Reports

Reports like P&L, Balance Sheet typically require:
- `company` - Exact company name
- `from_date` / `to_date` or `as_on_date` - Date range
- `periodicity` - Monthly, Quarterly, Yearly

### Sales/Purchase Reports

Reports like Sales Analytics typically require:
- `doc_type` - Source document type
- `tree_type` or `based_on` - Grouping dimension
- `value_quantity` - Metric type

### Inventory Reports

Reports like Stock Ledger typically require:
- `item_code` - Optional item filter
- `warehouse` - Optional warehouse filter
- `from_date` / `to_date` - Date range

## Using Filter Information

After getting requirements, build your `generate_report` call:

```json
// From report_requirements response:
// required_filter_names: ["doc_type", "tree_type", "value_quantity"]

// Use in generate_report:
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

## Including Metadata

When `include_metadata: true`, you get:

```json
{
  "metadata": {
    "basic_info": {
      "name": "Sales Analytics",
      "report_type": "Script Report",
      "module": "Selling",
      "is_standard": true,
      "ref_doctype": "Sales Invoice"
    },
    "system_info": {
      "creation": "2023-01-15 10:00:00",
      "modified": "2024-06-01 14:30:00",
      "owner": "Administrator"
    },
    "technical_config": {
      "has_javascript": true,
      "has_json_config": false
    }
  }
}
```

## Report Builder Limitation

Report Builder reports are not fully supported as they are simple DocType list views without custom business logic. Use `list_documents` tool instead for basic listing.

## Recommended Workflow

1. **Discover** reports using `report_list`
2. **Understand** requirements using this tool
3. **Identify** required filters and valid values
4. **Execute** with `generate_report` using correct filters

## Related Tools

- **report_list** - Discover available reports
- **generate_report** - Execute the report with filters
- **list_documents** - For simple DocType listing
- **run_python_code** - Custom analysis on report data
