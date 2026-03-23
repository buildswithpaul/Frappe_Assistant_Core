# How to Use search (Vector Search) and fetch

## Overview

Two tools provide AI-powered semantic search:

1. **`search`** — performs semantic/vector search across documents. Returns basic results (name, doctype).
2. **`fetch`** — retrieves full document content by ID for detailed analysis after search.

**Note:** These tools require a configured vector store (e.g., OpenAI Vector Store). If no vector store is configured, `search` returns empty results.

## search Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | **Yes** | Natural language search query |

## fetch Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | **Yes** | Document ID in format `"doctype/name"` (e.g., `"Customer/CUST-00001"`) |

## Response Format

### search
```json
{
  "success": true,
  "result": {
    "results": [
      { "name": "DOC-001", "doctype": "Sales Invoice", ... }
    ]
  }
}
```

### fetch
```json
{
  "success": true,
  "result": {
    "content": "... full document content ..."
  }
}
```

## When to Use vs Other Search Tools

| Need | Tool | Why |
|------|------|-----|
| Semantic/meaning-based search | `search` | Uses AI embeddings to find conceptually related documents |
| Exact text match across DocTypes | `search_documents` | Keyword-based global search |
| Filtered structured query | `list_documents` | SQL-like filters on specific fields |
| Search within one DocType | `search_doctype` | Text search on configured search fields |

## Best Practices

1. **Use natural language queries** — semantic search works best with descriptive queries like "procurement process for raw materials" rather than single keywords.
2. **Follow up with `fetch`** — search results are minimal; use `fetch` with the document ID to get full content.
3. **Fall back to other tools** — if search returns empty results, the vector store may not be configured. Use `search_documents` or `list_documents` instead.
4. **ID format for fetch** — always use `"DocType/document_name"` format (e.g., `"Customer/Grant Plastics Ltd."`).
