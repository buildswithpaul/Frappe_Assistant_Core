# update_document

Modify an existing Frappe document by updating specific field values.

## When to Use

- Changing field values on existing records
- Updating status or workflow state
- Modifying child table entries
- Correcting data errors

## Important Notes

- **Always fetch the document first** using `get_document` to understand current values
- Only draft documents (docstatus=0) can be modified
- Submitted documents must be amended, not updated

## Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| doctype | string | Yes | The DocType name |
| name | string | Yes | The document name/ID to update |
| data | object | Yes | Fields to update as key-value pairs |

## Examples

### Update Customer Details
```json
{
  "doctype": "Customer",
  "name": "ABC Corporation",
  "data": {
    "customer_group": "Premium",
    "territory": "Europe"
  }
}
```

### Update Item Price
```json
{
  "doctype": "Item",
  "name": "WIDGET-001",
  "data": {
    "standard_rate": 150,
    "description": "Updated standard widget with new features"
  }
}
```

### Update Sales Order Delivery Date
```json
{
  "doctype": "Sales Order",
  "name": "SO-00001",
  "data": {
    "delivery_date": "2024-12-31"
  }
}
```

### Update with Child Table Replacement
```json
{
  "doctype": "Sales Order",
  "name": "SO-00001",
  "data": {
    "items": [
      {"item_code": "WIDGET-001", "qty": 20, "rate": 100},
      {"item_code": "WIDGET-002", "qty": 10, "rate": 200}
    ]
  }
}
```

## Response Format

### Success
```json
{
  "success": true,
  "name": "ABC Corporation",
  "doctype": "Customer",
  "modified": "2024-06-15 14:30:00",
  "message": "Customer 'ABC Corporation' updated successfully",
  "updated_fields": ["customer_group", "territory"]
}
```

### Cannot Update Submitted Document
```json
{
  "success": false,
  "error": "Cannot update submitted document. Use amend workflow instead.",
  "doctype": "Sales Invoice",
  "name": "SINV-00001",
  "docstatus": 1
}
```

## Child Table Updates

When updating child tables, you have two approaches:

### 1. Replace Entire Table
Provide the complete new list - existing rows are replaced:
```json
{
  "data": {
    "items": [
      {"item_code": "NEW-001", "qty": 5, "rate": 100}
    ]
  }
}
```

### 2. Update Individual Fields
For simple field updates, just specify the fields to change.

## Common Patterns

### 1. View, Modify, Verify
```
get_document (see current state)
    ↓
update_document (make changes)
    ↓
get_document (verify changes)
```

### 2. Bulk Status Update
Use `list_documents` to find records, then update each:
```
list_documents (find records needing update)
    ↓
update_document (update each record)
```

## Security Notes

- Write permission is required for the DocType
- Sensitive fields cannot be modified by non-admin users
- Document ownership is preserved
- Audit trail is maintained for changes

## Related Tools

- **get_document** - View current document state before updating
- **create_document** - Create new documents
- **delete_document** - Remove documents
- **submit_document** - Submit draft documents
