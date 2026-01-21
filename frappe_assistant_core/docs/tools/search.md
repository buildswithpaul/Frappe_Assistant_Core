# search

ChatGPT-compatible search tool for finding documents.

## Overview

This is a ChatGPT MCP connector-compatible search tool. It provides a simplified interface for document search that follows ChatGPT's specific requirements.

## When to Use

- When using ChatGPT as the MCP client
- Simple document discovery
- Getting document IDs for follow-up with `fetch`

## Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| query | string | Yes | Natural language search query |

## Example

```json
{
  "query": "overdue invoices for ABC company"
}
```

## Response Format

Returns results in ChatGPT's required format:

```json
{
  "results": [
    {
      "id": "Sales Invoice/SINV-00123",
      "title": "Invoice for ABC Corp",
      "url": "https://site.com/app/sales-invoice/SINV-00123"
    },
    {
      "id": "Sales Invoice/SINV-00124",
      "title": "Invoice for ABC Corp - Services",
      "url": "https://site.com/app/sales-invoice/SINV-00124"
    }
  ]
}
```

## ID Format

The `id` field uses the format `DocType/Name`:
- `Customer/CUST-00001`
- `Sales Invoice/SINV-00123`
- `Item/ITEM-00456`

Use this ID with the `fetch` tool to get complete document content.

## Workflow with ChatGPT

1. **Search** for documents:
   ```json
   {"query": "customer ABC"}
   ```

2. **Fetch** full content using returned ID:
   ```json
   {"id": "Customer/CUST-00001"}
   ```

## URL for Citation

The `url` field provides a direct link for citation purposes in ChatGPT responses.

## Related Tools

- **fetch** - Retrieve full document content by ID
- **search_documents** - Standard search (non-ChatGPT clients)
