# list_documents

Search and list Frappe documents with filtering, pagination, and field selection. This is the primary tool for data exploration and discovery.

## When to Use

- Finding records by criteria (e.g., "show me all active customers")
- Browsing document lists (e.g., "list recent sales invoices")
- Data exploration and discovery
- Getting counts and summaries

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| doctype | string | Yes | - | The Frappe DocType name (e.g., 'Customer', 'Sales Invoice', 'Item') |
| filters | object | No | {} | Search filters as key-value pairs |
| fields | array | No | ['name', 'creation', 'modified'] | Specific fields to retrieve |
| limit | integer | No | 20 | Maximum records to return (max: 1000) |
| order_by | string | No | 'creation desc' | Sort order for results |

### Filter Operators

Filters support various comparison operators:

| Operator | Example | Description |
|----------|---------|-------------|
| `=` (default) | `{"status": "Active"}` | Exact match |
| `!=` | `{"status": ["!=", "Cancelled"]}` | Not equal |
| `>` | `{"creation": [">", "2024-01-01"]}` | Greater than |
| `>=` | `{"grand_total": [">=", 1000]}` | Greater than or equal |
| `<` | `{"qty": ["<", 10]}` | Less than |
| `<=` | `{"amount": ["<=", 500]}` | Less than or equal |
| `like` | `{"customer_name": ["like", "%Corp%"]}` | Pattern match |
| `in` | `{"status": ["in", ["Active", "Lead"]]}` | In list |
| `not in` | `{"status": ["not in", ["Cancelled"]]}` | Not in list |
| `between` | `{"creation": ["between", ["2024-01-01", "2024-12-31"]]}` | Range |

## Examples

### List all customers
```json
{
  "doctype": "Customer"
}
```

### Find active items with specific fields
```json
{
  "doctype": "Item",
  "filters": {"disabled": 0},
  "fields": ["item_code", "item_name", "item_group", "stock_uom"],
  "limit": 100
}
```

### Search sales invoices by date range
```json
{
  "doctype": "Sales Invoice",
  "filters": {
    "posting_date": [">=", "2024-01-01"],
    "status": ["!=", "Cancelled"]
  },
  "order_by": "posting_date desc"
}
```

### Find customers by type and territory
```json
{
  "doctype": "Customer",
  "filters": {
    "customer_type": "Company",
    "territory": "United States"
  },
  "fields": ["name", "customer_name", "customer_group", "territory"]
}
```

### List pending purchase orders
```json
{
  "doctype": "Purchase Order",
  "filters": {
    "status": ["in", ["To Receive and Bill", "To Receive", "To Bill"]],
    "docstatus": 1
  },
  "order_by": "transaction_date desc",
  "limit": 50
}
```

## Response Format

```json
{
  "success": true,
  "doctype": "Customer",
  "data": [
    {"name": "CUST-00001", "customer_name": "ABC Corp", ...},
    {"name": "CUST-00002", "customer_name": "XYZ Ltd", ...}
  ],
  "count": 2,
  "total_count": 150,
  "has_more": true,
  "filters_applied": {"status": "Active"},
  "message": "Found 2 Customer records"
}
```

## Common Patterns

### 1. Data Exploration Workflow
```
list_documents (find records) → get_document (get details)
```

### 2. Pagination
For large datasets, use `limit` to page through results:
- First page: `limit: 20`
- Next pages: Adjust filters or use offset patterns

### 3. Performance Tips
- Request only needed fields to improve response time
- Use specific filters to reduce result set
- Avoid `limit: 1000` unless necessary

## Security Notes

- Results are filtered by user's permissions
- Sensitive fields (passwords, API keys) are automatically redacted
- For `User` DocType, non-admin users only see their own record

## Related Tools

- **get_document** - Get complete details of a specific document
- **search_documents** - Global search across all DocTypes
- **search_doctype** - Text search within a specific DocType
- **get_doctype_info** - Understand DocType structure before querying
