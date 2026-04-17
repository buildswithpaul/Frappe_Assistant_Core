# How to Use search_doctype

## Overview

The `search_doctype` tool searches within a **specific** DocType using its configured search fields. Unlike `search_documents` (global), this targets one DocType and searches its text fields.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `doctype` | string | **Yes** | — | DocType to search within |
| `query` | string | **Yes** | — | Search text |
| `limit` | integer | No | 20 | Max results |

## Response Format

```json
{
  "success": true,
  "result": {
    "success": true,
    "doctype": "Customer",
    "query": "Grant",
    "results": [
      {
        "name": "Grant Plastics Ltd.",
        "customer_name": "Grant Plastics Ltd.",
        "tax_id": null,
        "website": null
      }
    ],
    "count": 1,
    "search_fields": ["customer_name", "tax_id", "loyalty_program_tier", "website"]
  }
}
```

Key: `search_fields` tells you which fields were searched. Results include those fields plus `name`.

## When to Use Each Search Tool

| Need | Tool |
|------|------|
| Search across all DocTypes | `search_documents` |
| Search within one DocType by text | `search_doctype` |
| Find link field values (autocomplete) | `search_link` |
| Structured query with exact filters | `list_documents` |

## Best Practices

1. **Use when you know the DocType** — more precise than global `search_documents`.
2. **Check `search_fields`** — the response tells you which fields matched. If the field you need isn't in search_fields, use `list_documents` with a `like` filter instead.
3. **Short queries work best** — single words or names.
