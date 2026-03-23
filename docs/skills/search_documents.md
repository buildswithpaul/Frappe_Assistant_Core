# How to Use search_documents

## Overview

The `search_documents` tool performs a **global** full-text search across multiple DocTypes simultaneously. It searches across User, DocType, Contact, Customer, Supplier, Item, Company, Employee, Task, and Project.

**Important:** This is a global search — there is NO `doctype` parameter. To search within a specific DocType, use `search_doctype` instead.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | **Yes** | — | Search text |
| `limit` | integer | No | 20 | Maximum results |

## Response Format

```json
{
  "success": true,
  "result": {
    "success": true,
    "query": "Administrator",
    "results": [
      { "name": "Administrator", "doctype": "User" }
    ],
    "count": 1,
    "total_found": 1,
    "searched_doctypes": [
      "User", "DocType", "Contact", "Customer", "Supplier",
      "Item", "Company", "Employee", "Task", "Project"
    ]
  }
}
```

Key points:
- Results include `name` and `doctype` — use `get_document` to get full details.
- `searched_doctypes` shows which DocTypes were searched.
- Results may be empty if no matches are found across any of the searched DocTypes.

## Best Practices

1. **Use for discovery** — when the user says "find anything about X" without specifying a DocType.
2. **Follow up with `get_document`** — search results only include name and doctype, not full data.
3. **Keep queries short** — single words or short phrases work best.
4. **Use `search_doctype` for targeted search** — if you know the DocType, `search_doctype` is more precise.

## When to Use Each Search Tool

| Scenario | Tool | Why |
|----------|------|-----|
| "Find anything about Acme Corp" | `search_documents` | Global search across all DocTypes |
| "Show me all active customers" | `list_documents` | Structured query with exact filters |
| "Search for items containing 'bolt'" | `search_doctype` | Search within a specific DocType |
| "Find a customer starting with 'Grant'" | `search_link` | Link field autocomplete-style search |
| "What DocTypes exist for inventory?" | `search_doctype` with `doctype: "DocType"` | Search DocType names |
| "Semantic search for procurement process" | `search` (vector) | AI-powered semantic search |

## Edge Cases

- **Limited DocType coverage** — only searches ~10 core DocTypes, not all DocTypes in the system.
- **No filter support** — cannot narrow by status, date, or other fields. Use `list_documents` for filtered queries.
- **Minimal result data** — only returns `name` and `doctype`. Always follow up with `get_document` for details.
