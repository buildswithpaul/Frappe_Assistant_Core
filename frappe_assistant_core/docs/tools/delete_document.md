# delete_document

Delete an existing Frappe document from the system.

## When to Use

- Removing records that are no longer needed
- Cleaning up test data
- Deleting invalid or duplicate entries
- Removing records before re-importing

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| doctype | string | Yes | - | The DocType name (e.g., 'Customer', 'Item') |
| name | string | Yes | - | The document name/ID to delete |
| force | boolean | No | false | Force deletion even with dependencies |

## Examples

### Delete a Customer

```json
{
  "doctype": "Customer",
  "name": "CUST-00001"
}
```

### Delete an Item

```json
{
  "doctype": "Item",
  "name": "ITEM-00001"
}
```

### Force Delete with Dependencies

```json
{
  "doctype": "Customer",
  "name": "CUST-00001",
  "force": true
}
```

## Response Format

### Success

```json
{
  "success": true,
  "doctype": "Customer",
  "name": "CUST-00001",
  "message": "Customer 'CUST-00001' deleted successfully"
}
```

### Document Not Found

```json
{
  "success": false,
  "error": "Customer 'CUST-00001' not found",
  "doctype": "Customer",
  "name": "CUST-00001"
}
```

### Dependency Error

```json
{
  "success": false,
  "error": "Cannot delete Customer 'CUST-00001' because it is linked to other documents. Use force=true to override.",
  "doctype": "Customer",
  "name": "CUST-00001",
  "dependency_error": true
}
```

### Permission Error

```json
{
  "success": false,
  "error": "Insufficient permissions to delete Customer document",
  "doctype": "Customer",
  "name": "CUST-00001",
  "permission_error": true
}
```

## Important Notes

### Dependencies

Documents may be linked to other records. Common dependency scenarios:

| DocType | Common Dependencies |
|---------|---------------------|
| Customer | Sales Orders, Sales Invoices, Quotations |
| Item | Stock Entries, Purchase Orders, Sales Invoices |
| Supplier | Purchase Orders, Purchase Invoices |
| Employee | Leave Applications, Salary Slips |

### Force Delete

Using `force: true` will:
- Delete the document regardless of dependencies
- May leave orphaned references in other documents
- Should be used with caution

### Submitted Documents

- Submitted documents (docstatus=1) typically cannot be deleted
- Cancel the document first, then delete
- Some DocTypes may have specific cancellation requirements

### Permissions

- Delete permission is checked for the specific DocType
- Document-level permissions are also verified
- Administrators can delete most documents

## Recommended Workflow

1. **Verify** the document exists using `get_document`
2. **Check** for dependencies before deletion
3. **Consider** cancellation for submitted documents
4. **Use force** only when dependencies are acceptable to break

## Related Tools

- **get_document** - Verify document exists before deletion
- **list_documents** - Find documents to delete
- **update_document** - Archive or deactivate instead of deleting
- **submit_document** - May need to cancel submitted docs first
