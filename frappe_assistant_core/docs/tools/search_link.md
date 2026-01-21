# search_link

Search for link field options to find valid values for document references.

## When to Use

- Finding valid values for Link fields when creating documents
- Auto-completing customer, supplier, or item names
- Discovering document references for filters
- Validating link field values before document creation

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| doctype | string | Yes | - | Target DocType to search (e.g., 'Customer', 'Item') |
| query | string | Yes | - | Search query text |
| filters | object | No | {} | Additional filters to narrow results |

## Examples

### Search for Customers

```json
{
  "doctype": "Customer",
  "query": "ABC"
}
```

### Search for Items

```json
{
  "doctype": "Item",
  "query": "widget"
}
```

### Search with Filters

```json
{
  "doctype": "Customer",
  "query": "corp",
  "filters": {
    "customer_group": "Commercial"
  }
}
```

### Search for Active Items

```json
{
  "doctype": "Item",
  "query": "laptop",
  "filters": {
    "disabled": 0,
    "is_stock_item": 1
  }
}
```

### Search Employees

```json
{
  "doctype": "Employee",
  "query": "john",
  "filters": {
    "status": "Active"
  }
}
```

## Response Format

### Success

```json
{
  "success": true,
  "results": [
    {"value": "CUST-00001", "description": "ABC Corporation"},
    {"value": "CUST-00002", "description": "ABC Industries Ltd"},
    {"value": "CUST-00003", "description": "ABC Trading Co"}
  ],
  "count": 3,
  "doctype": "Customer",
  "query": "ABC"
}
```

### No Results

```json
{
  "success": true,
  "results": [],
  "count": 0,
  "doctype": "Customer",
  "query": "nonexistent"
}
```

### Permission Error

```json
{
  "success": false,
  "error": "Insufficient permissions to search Customer"
}
```

## Common DocTypes to Search

| DocType | Use Case |
|---------|----------|
| Customer | Sales documents, receivables |
| Supplier | Purchase documents, payables |
| Item | Stock transactions, sales/purchase |
| Employee | HR documents, expense claims |
| Company | Multi-company transactions |
| Warehouse | Stock transfers, receipts |
| Account | Journal entries, GL postings |
| Cost Center | Financial reporting dimensions |

## Practical Workflows

### Creating a Sales Invoice

1. Search for customer:
   ```json
   {"doctype": "Customer", "query": "ABC"}
   ```

2. Search for items:
   ```json
   {"doctype": "Item", "query": "widget"}
   ```

3. Create invoice with found values

### Setting Report Filters

1. Get requirements from `report_requirements`
2. Search for Link field values:
   ```json
   {"doctype": "Company", "query": ""}
   ```

3. Use found values in `generate_report`

## Combining with Other Tools

### With create_document

```json
// 1. Search for customer
{"doctype": "Customer", "query": "ABC"}
// Result: "ABC Corporation"

// 2. Create invoice
{
  "doctype": "Sales Invoice",
  "data": {
    "customer": "ABC Corporation",
    ...
  }
}
```

### With list_documents

```json
// 1. Search to get exact name
{"doctype": "Item", "query": "laptop"}
// Result: "LAPTOP-001"

// 2. Use in filters
{
  "doctype": "Stock Entry",
  "filters": {"items.item_code": "LAPTOP-001"}
}
```

## Search Behavior

- Searches across name field and title/description
- Case-insensitive matching
- Partial matches supported
- Results sorted by relevance
- Filtered by user permissions

## Related Tools

- **search_doctype** - Full-text search within a DocType
- **list_documents** - List documents with more fields
- **get_document** - Get full document details
- **create_document** - Use found values in document creation
