# search_doctype

Search within a specific DocType using full-text search across searchable fields.

## When to Use

- Finding documents by keywords across multiple fields
- Broad search when you don't know exact field names
- Discovering documents matching general criteria
- Full-text search across name, title, and other searchable fields

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| doctype | string | Yes | - | DocType to search in |
| query | string | Yes | - | Search query text |
| limit | integer | No | 20 | Maximum results to return |

## Examples

### Search Customers

```json
{
  "doctype": "Customer",
  "query": "electronics"
}
```

### Search Items

```json
{
  "doctype": "Item",
  "query": "stainless steel"
}
```

### Search with Limit

```json
{
  "doctype": "Sales Invoice",
  "query": "overdue",
  "limit": 50
}
```

### Search Employees

```json
{
  "doctype": "Employee",
  "query": "manager",
  "limit": 10
}
```

## Response Format

### Success

```json
{
  "success": true,
  "results": [
    {
      "name": "CUST-00001",
      "customer_name": "ABC Electronics",
      "customer_group": "Commercial",
      "territory": "United States"
    },
    {
      "name": "CUST-00002",
      "customer_name": "XYZ Electronics Corp",
      "customer_group": "Retail",
      "territory": "United Kingdom"
    }
  ],
  "count": 2,
  "doctype": "Customer",
  "query": "electronics",
  "searched_fields": ["name", "customer_name", "email_id"]
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

## Search vs Link Search

| Feature | search_doctype | search_link |
|---------|---------------|-------------|
| Purpose | Full document discovery | Link field completion |
| Fields returned | Multiple fields | Name and description |
| Search scope | All searchable fields | Name and title |
| Use case | Exploration | Form filling |

## Searchable Fields

Each DocType has specific fields marked as searchable:

| DocType | Commonly Searchable Fields |
|---------|---------------------------|
| Customer | name, customer_name, email_id |
| Item | name, item_name, item_code, description |
| Employee | name, employee_name, company_email |
| Supplier | name, supplier_name, supplier_group |
| Sales Invoice | name, customer, status |
| Purchase Order | name, supplier, status |

## Practical Examples

### Find Customers in a Territory

```json
{
  "doctype": "Customer",
  "query": "California"
}
```

### Find Items by Description

```json
{
  "doctype": "Item",
  "query": "waterproof outdoor"
}
```

### Find Pending Invoices

```json
{
  "doctype": "Sales Invoice",
  "query": "unpaid"
}
```

## Combining with Other Tools

### Discovery Workflow

1. Search broadly:
   ```json
   {"doctype": "Customer", "query": "tech"}
   ```

2. Get full details:
   ```json
   {"doctype": "Customer", "name": "CUST-00001"}
   ```

3. List related documents:
   ```json
   {"doctype": "Sales Invoice", "filters": {"customer": "CUST-00001"}}
   ```

## Permission Filtering

- Results are filtered by user permissions
- Only documents the user can read are returned
- DocType-level and document-level permissions apply

## Search Behavior

- Searches across multiple fields simultaneously
- Partial matching supported
- Case-insensitive
- Results ordered by relevance

## Related Tools

- **search_link** - Simpler search for link field completion
- **list_documents** - Structured filtering with specific criteria
- **get_document** - Get full document after finding it
- **get_doctype_info** - Understand which fields are searchable
