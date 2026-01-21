# metadata_list_doctypes

List all available DocTypes in the Frappe system.

## When to Use

- Discovering what DocTypes are available
- Exploring DocTypes in a specific module
- Finding custom DocTypes
- Understanding the system structure

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| module | string | No | All | Filter by module name |
| custom_only | boolean | No | false | Show only custom DocTypes |

## Examples

### List All DocTypes

```json
{}
```

### Filter by Module

```json
{
  "module": "Accounts"
}
```

```json
{
  "module": "Selling"
}
```

```json
{
  "module": "Stock"
}
```

### List Custom DocTypes Only

```json
{
  "custom_only": true
}
```

### Combined Filter

```json
{
  "module": "Custom",
  "custom_only": true
}
```

## Response Format

```json
{
  "success": true,
  "doctypes": [
    {
      "name": "Sales Invoice",
      "module": "Accounts",
      "is_submittable": 1,
      "is_tree": 0,
      "istable": 0,
      "custom": 0,
      "description": "Sales Invoice for billing customers"
    },
    {
      "name": "Customer",
      "module": "Selling",
      "is_submittable": 0,
      "is_tree": 0,
      "istable": 0,
      "custom": 0,
      "description": "Customer master"
    }
  ],
  "count": 2,
  "filters_applied": {
    "module": "Accounts",
    "custom_only": false
  }
}
```

## Common Modules

| Module | Description | Example DocTypes |
|--------|-------------|------------------|
| Accounts | Financial documents | Sales Invoice, Purchase Invoice, Journal Entry |
| Selling | Sales operations | Customer, Quotation, Sales Order |
| Buying | Purchasing | Supplier, Purchase Order, Purchase Receipt |
| Stock | Inventory | Item, Stock Entry, Warehouse |
| HR | Human Resources | Employee, Leave Application, Salary Slip |
| CRM | Customer Relations | Lead, Opportunity, Campaign |
| Projects | Project management | Project, Task, Timesheet |
| Setup | Configuration | Company, Currency, Print Format |

## DocType Properties

| Property | Description |
|----------|-------------|
| is_submittable | Has Draft → Submitted workflow |
| is_tree | Hierarchical structure |
| istable | Child table DocType |
| custom | Custom created (not standard) |

## Permission Filtering

Results are automatically filtered to only show DocTypes the current user has read permission for.

## Use Cases

### Exploring Before Development

```json
{"module": "Custom"}
```

### Finding Transactional Documents

Look for `is_submittable: 1`:
- Sales Invoice
- Purchase Order
- Stock Entry

### Finding Master Data

Look for `is_submittable: 0` and `istable: 0`:
- Customer
- Item
- Supplier

## Related Tools

- **get_doctype_info** - Get detailed info for specific DocType
- **metadata_permissions** - Check permissions
- **list_documents** - List records in a DocType
