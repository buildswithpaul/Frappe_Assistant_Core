# How to Use search and fetch (ChatGPT connectors)

## Overview

`search` and `fetch` exist to satisfy **ChatGPT's MCP connector contract**, which requires a tool named exactly `search` taking a single `query` string, and a `fetch` tool that returns a document by ID. They are shape adapters, not a separate search engine.

**There is no vector store and no semantic search.** `search` runs the same keyword search as `search_documents` in its global mode and reshapes the output to `{id, title, url}`. Earlier versions of this document described AI embeddings; that was never implemented.

**If you are not a ChatGPT connector, do not use these tools.** Use `search_documents` (richer results, DocType scoping, filters, link resolution) and `get_document` (full field data, no string reformatting).

## search

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | **Yes** | Search text. Keyword matching — not semantic. |

```json
{
  "results": [
    {
      "id": "Customer/Grant Plastics Ltd.",
      "title": "Grant Plastics Ltd.",
      "url": "https://site.example.com/app/customer/Grant Plastics Ltd."
    }
  ]
}
```

- Fixed at 20 results; there is no `limit` parameter.
- `id` is always `"DocType/name"` — feed it straight to `fetch`.
- `title` falls back to the document name when no title field is present.
- On error this returns `{"results": []}` rather than an error, because ChatGPT requires that shape. An empty result therefore does not distinguish "nothing matched" from "something failed" — a reason to prefer `search_documents`.

## fetch

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | **Yes** | Document ID as `"DocType/name"`, e.g. `"Customer/CUST-00001"` |

```json
{
  "id": "Customer/CUST-00001",
  "title": "Grant Plastics Ltd.",
  "text": "# Customer: CUST-00001\n\n**Customer Name**: Grant Plastics Ltd.\n\n## All Fields\n\n```json\n{...}\n```",
  "url": "https://site.example.com/app/customer/CUST-00001",
  "metadata": {"doctype": "Customer", "modified": "...", "owner": "...", "docstatus": 0}
}
```

- `text` is a markdown rendering with the full document embedded as JSON — built for citation, not for programmatic field access.
- Permissions are enforced exactly as in `get_document`: role-based DocType gating plus Frappe permissions, with sensitive fields filtered by role.
- A missing document, a malformed ID, or a permission failure raises an error rather than returning empty.

## When to use what

| Need | Tool |
|------|------|
| ChatGPT connector citation flow | `search` then `fetch` |
| Any other client searching for records | `search_documents` |
| Full field data for a known record | `get_document` |
| Filtered or counted record sets | `list_documents` |
