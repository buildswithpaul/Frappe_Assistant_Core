# search_documents

Global search across all accessible documents in the Frappe system.

## When to Use

- Finding documents by keywords across multiple DocTypes
- Broad search when you don't know the exact DocType
- Quick document discovery
- Natural language queries

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| query | string | Yes | - | Search query |
| limit | integer | No | 20 | Maximum results |

## Examples

### Basic Search

```json
{
  "query": "laptop"
}
```

### Search with Limit

```json
{
  "query": "overdue invoice",
  "limit": 50
}
```

## Response Format

```json
{
  "success": true,
  "results": [
    {
      "doctype": "Item",
      "name": "LAPTOP-001",
      "title": "Dell Laptop 15 inch"
    },
    {
      "doctype": "Purchase Order",
      "name": "PO-00123",
      "title": "Laptop Purchase"
    }
  ],
  "total_count": 2
}
```

## Search Behavior

- Searches across multiple common DocTypes
- Permission-aware (only returns accessible documents)
- Searches name, title, and searchable fields
- Case-insensitive matching

## Common DocTypes Searched

- Customer, Supplier
- Item
- Sales Invoice, Purchase Invoice
- Sales Order, Purchase Order
- Task, Project
- And other configured DocTypes

## When to Use Other Tools

| Scenario | Better Tool |
|----------|-------------|
| Known DocType | `list_documents` with filters |
| Specific field search | `search_doctype` |
| Link field completion | `search_link` |
| Need full document | `get_document` |

## Related Tools

- **search_doctype** - Search within specific DocType
- **search_link** - Search for link field values
- **list_documents** - Structured document listing
- **get_document** - Get full document details
