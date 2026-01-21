# create_document

Create new Frappe documents with validation, child table support, and optional submission.

## When to Use

- Creating new records (customers, items, invoices, orders)
- Inserting data with child tables (line items, taxes)
- Validating data before saving (dry-run mode)

## Recommended Workflow

1. **First**: Use `get_doctype_info` to understand the DocType structure
2. **Identify**: Required fields and child table formats
3. **Optionally**: Use `validate_only: true` to test before creating
4. **Create**: Submit the document with proper field values

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| doctype | string | Yes | - | The DocType name (e.g., 'Customer', 'Sales Invoice') |
| data | object | Yes | - | Document field data as key-value pairs |
| submit | boolean | No | false | Submit after creation (for submittable DocTypes) |
| validate_only | boolean | No | false | Only validate without saving |

## Examples

### Create a Customer
```json
{
  "doctype": "Customer",
  "data": {
    "customer_name": "ABC Corporation",
    "customer_type": "Company",
    "customer_group": "Commercial",
    "territory": "United States"
  }
}
```

### Create an Item
```json
{
  "doctype": "Item",
  "data": {
    "item_code": "WIDGET-001",
    "item_name": "Standard Widget",
    "item_group": "Products",
    "stock_uom": "Nos",
    "is_stock_item": 1
  }
}
```

### Create a Sales Order with Line Items
```json
{
  "doctype": "Sales Order",
  "data": {
    "customer": "ABC Corporation",
    "delivery_date": "2024-12-31",
    "items": [
      {
        "item_code": "WIDGET-001",
        "qty": 10,
        "rate": 100
      },
      {
        "item_code": "WIDGET-002",
        "qty": 5,
        "rate": 200
      }
    ]
  }
}
```

### Create and Submit a Sales Invoice
```json
{
  "doctype": "Sales Invoice",
  "data": {
    "customer": "ABC Corporation",
    "posting_date": "2024-06-15",
    "due_date": "2024-07-15",
    "items": [
      {
        "item_code": "WIDGET-001",
        "qty": 10,
        "rate": 100
      }
    ]
  },
  "submit": true
}
```

### Validate Before Creating
```json
{
  "doctype": "Purchase Order",
  "data": {
    "supplier": "XYZ Suppliers",
    "items": [
      {"item_code": "RAW-001", "qty": 100, "rate": 50}
    ]
  },
  "validate_only": true
}
```

## Child Tables

Child tables (like line items) must be provided as arrays of objects:

```json
{
  "items": [
    {"item_code": "ITEM-001", "qty": 10, "rate": 100},
    {"item_code": "ITEM-002", "qty": 5, "rate": 200}
  ],
  "taxes": [
    {"charge_type": "On Net Total", "account_head": "VAT - C", "rate": 10}
  ]
}
```

### Common Child Table Fields

| DocType | Child Table | Common Fields |
|---------|-------------|---------------|
| Sales Order | items | item_code, qty, rate, delivery_date |
| Sales Invoice | items | item_code, qty, rate |
| Purchase Order | items | item_code, qty, rate, schedule_date |
| Journal Entry | accounts | account, debit_in_account_currency, credit_in_account_currency |

## Response Format

### Success
```json
{
  "success": true,
  "name": "CUST-00001",
  "doctype": "Customer",
  "docstatus": 0,
  "owner": "user@example.com",
  "creation": "2024-06-15 10:30:00",
  "submitted": false,
  "can_submit": true,
  "message": "Customer 'CUST-00001' created successfully as draft",
  "next_steps": [
    "Document is in draft state",
    "You can update this document using update_document tool",
    "Submit permission: Available"
  ]
}
```

### Validation Only
```json
{
  "success": true,
  "validation_passed": true,
  "doctype": "Sales Order",
  "message": "Sales Order data validation passed successfully",
  "fields_validated": ["customer", "delivery_date", "items"],
  "child_tables": ["items", "taxes"],
  "next_step": "Use create_document with validate_only=false to actually create the document"
}
```

## Error Handling

### Missing Required Fields
```json
{
  "success": false,
  "error": "Missing required fields: customer_name, customer_group",
  "required_fields": ["customer_name", "customer_type", "customer_group"],
  "provided_fields": ["customer_type"],
  "suggestion": "Use get_doctype_info tool with doctype='Customer' to see all required fields"
}
```

### Referenced Record Not Found
```json
{
  "success": false,
  "error": "Customer 'NonExistent Corp' does not exist",
  "error_type": "validation_error",
  "guidance": "Referenced record does not exist in the system.",
  "suggestion": "1. Verify that referenced records exist\n2. Use search_documents to find correct names"
}
```

## Security Notes

- Permission is checked before creating
- Sensitive fields cannot be set by non-admin users
- Submit permission is verified separately
- Documents are created with the current user as owner

## Related Tools

- **get_doctype_info** - Understand DocType structure and required fields
- **get_document** - Retrieve the created document
- **update_document** - Modify the document after creation
- **submit_document** - Submit a draft document
- **list_documents** - Find existing records to reference
