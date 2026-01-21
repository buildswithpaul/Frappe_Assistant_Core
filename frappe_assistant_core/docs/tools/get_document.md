# get_document

Retrieve detailed information about a specific Frappe document by its name/ID.

## When to Use

- Getting complete details of a known record
- Viewing all fields including child tables
- Checking document status (draft, submitted, cancelled)
- Following up after list_documents to get full details

## Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| doctype | string | Yes | The DocType name (e.g., 'Customer', 'Sales Invoice') |
| name | string | Yes | The document name/ID (e.g., 'CUST-00001', 'SINV-00001') |

## Examples

### Get a Customer
```json
{
  "doctype": "Customer",
  "name": "ABC Corporation"
}
```

### Get a Sales Invoice
```json
{
  "doctype": "Sales Invoice",
  "name": "SINV-00001"
}
```

### Get an Item
```json
{
  "doctype": "Item",
  "name": "WIDGET-001"
}
```

### Get a User Profile
```json
{
  "doctype": "User",
  "name": "john@example.com"
}
```

## Response Format

### Success
```json
{
  "success": true,
  "doctype": "Customer",
  "name": "ABC Corporation",
  "data": {
    "name": "ABC Corporation",
    "customer_name": "ABC Corporation",
    "customer_type": "Company",
    "customer_group": "Commercial",
    "territory": "United States",
    "creation": "2024-01-15 10:30:00",
    "modified": "2024-06-01 14:20:00",
    "owner": "admin@example.com",
    "docstatus": 0
  },
  "message": "Customer 'ABC Corporation' retrieved successfully"
}
```

### With Child Tables
```json
{
  "success": true,
  "doctype": "Sales Invoice",
  "name": "SINV-00001",
  "data": {
    "name": "SINV-00001",
    "customer": "ABC Corporation",
    "posting_date": "2024-06-15",
    "grand_total": 1100,
    "docstatus": 1,
    "items": [
      {
        "item_code": "WIDGET-001",
        "item_name": "Standard Widget",
        "qty": 10,
        "rate": 100,
        "amount": 1000
      }
    ],
    "taxes": [
      {
        "charge_type": "On Net Total",
        "account_head": "VAT - C",
        "rate": 10,
        "tax_amount": 100
      }
    ]
  }
}
```

### Document Not Found
```json
{
  "success": false,
  "error": "Customer 'NonExistent Corp' not found",
  "doctype": "Customer",
  "name": "NonExistent Corp"
}
```

## Document Status (docstatus)

| Value | Meaning | Description |
|-------|---------|-------------|
| 0 | Draft | Document can be modified |
| 1 | Submitted | Document is finalized, cannot be modified |
| 2 | Cancelled | Document has been cancelled |

## Common Patterns

### 1. List then Get Details
```
list_documents (find matching records)
    ↓
get_document (get full details of specific record)
```

### 2. Create then Verify
```
create_document (create new record)
    ↓
get_document (verify creation with all fields)
```

### 3. Check Before Update
```
get_document (see current values)
    ↓
update_document (modify specific fields)
```

## Security Notes

- Permission is checked before retrieving
- Sensitive fields (passwords, API keys) are automatically redacted
- Administrator record can only be accessed by Administrator user
- For User DocType, non-admin users can only see their own profile

## Related Tools

- **list_documents** - Find records to get the document name
- **update_document** - Modify the document after viewing
- **delete_document** - Remove the document
- **get_doctype_info** - Understand the DocType structure
