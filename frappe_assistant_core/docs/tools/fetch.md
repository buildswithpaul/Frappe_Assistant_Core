# fetch

ChatGPT-compatible document retrieval tool.

## Overview

This is a ChatGPT MCP connector-compatible fetch tool. It retrieves complete document content for detailed analysis and citation after using the `search` tool.

## When to Use

- After finding documents with `search` tool
- Getting full document content for analysis
- Retrieving documents for ChatGPT citation
- When using ChatGPT as the MCP client

## Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| id | string | Yes | Document ID in format "DocType/Name" |

## ID Format

The ID must be in the format `DocType/Name`:
- `Customer/CUST-00001`
- `Sales Invoice/SINV-00123`
- `Item/LAPTOP-001`

This matches the `id` field returned by the `search` tool.

## Example

```json
{
  "id": "Sales Invoice/SINV-00123"
}
```

## Response Format

Returns document in ChatGPT's required format:

```json
{
  "id": "Sales Invoice/SINV-00123",
  "title": "SINV-00123",
  "text": "# Sales Invoice: SINV-00123\n\n**Customer Name**: ABC Corporation\n**Grand Total**: 15000.00\n\n## All Fields\n\n```json\n{\"customer\": \"ABC Corporation\", ...}\n```",
  "url": "https://site.com/app/sales-invoice/SINV-00123",
  "metadata": {
    "doctype": "Sales Invoice",
    "modified": "2024-06-15 10:30:00",
    "owner": "user@company.com",
    "docstatus": 1
  }
}
```

## Text Field Structure

The `text` field is formatted as readable markdown:
1. Document header with DocType and name
2. Key fields (title, subject, description, etc.)
3. Full document data as JSON block

## Metadata

The `metadata` object includes:
- `doctype` - Document type
- `modified` - Last modification timestamp
- `owner` - Document owner
- `docstatus` - Document status (0=Draft, 1=Submitted, 2=Cancelled)

## URL for Citation

The `url` field provides a direct link for citation in ChatGPT responses.

## Security

- Permission checks are enforced
- Sensitive fields are filtered
- Returns error if document not accessible

## Error Handling

Invalid ID format:
```json
{
  "error": "Invalid document ID format. Expected 'doctype/name', got: invalid_id"
}
```

Document not found:
```json
{
  "error": "Document not found: Customer/NONEXISTENT"
}
```

## Workflow with ChatGPT

1. User asks about specific data
2. **Search** for relevant documents:
   ```json
   {"query": "ABC company invoices"}
   ```
3. **Fetch** full content for analysis:
   ```json
   {"id": "Sales Invoice/SINV-00123"}
   ```
4. ChatGPT analyzes content and provides response with citation

## Related Tools

- **search** - Find documents first
- **get_document** - Standard document retrieval (non-ChatGPT clients)
