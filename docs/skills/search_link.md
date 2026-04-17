# How to Use search_link

## Overview

The `search_link` tool provides autocomplete-style search for Link field values. Use it to find valid values for Link fields when creating or updating documents.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `doctype` | string | **Yes** | — | Target DocType for the link |
| `query` | string | **Yes** | — | Search text |
| `filters` | object | No | `{}` | Additional filters |

## Response Format

```json
{
  "success": true,
  "result": {
    "success": true,
    "doctype": "Customer Group",
    "query": "com",
    "results": [
      {
        "value": "Commercial",
        "description": "All Customer Groups",
        "label": "Commercial"
      }
    ],
    "count": 1,
    "filters_applied": {}
  }
}
```

- `value` — the actual value to use in Link fields
- `description` — additional context (often parent or group info)
- `label` — display label

## Best Practices

1. **Use before `create_document`** — to find valid Link field values. Link fields require the exact `name` (ID), not a display title.
2. **Check `get_doctype_info` first** — to know which fields are Links and what DocType they target.
3. **Use `filters` to narrow** — e.g., search customers in a specific group: `{"customer_group": "Commercial"}`.
4. **Use `value` from results** — this is the correct value to pass to Link fields.

## Common Usage

When creating a Sales Invoice, you need a valid Customer name:
```json
{"doctype": "Customer", "query": "Grant"}
```
Then use the `value` from results (e.g., `"Grant Plastics Ltd."`) in `create_document`.
