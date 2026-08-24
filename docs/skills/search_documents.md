# How to Use search_documents

## Overview

`search_documents` is the **single** text-search tool. It has three modes, chosen by the arguments you pass:

| Mode | How to get it | What it does |
|------|---------------|--------------|
| **global** | omit `doctype` | Full-text search across every DocType the user can read |
| **doctype** | pass `doctype` | Text match within that DocType's search fields |
| **link_value** | `purpose: "link_value"` + `doctype` | Autocomplete-style resolution of a Link field value |

It replaces the older `search_documents` / `search_doctype` / `search_link` trio — those three differed only in these arguments, so they are now one tool.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | **Yes** | — | Text to search for. Short queries work best. |
| `doctype` | string | No | — | DocType to search within. Omit for global. **Required** when `purpose` is `link_value`. |
| `purpose` | string | No | `documents` | `documents` finds records; `link_value` resolves a Link field value. |
| `filters` | object | No | `{}` | Narrows the search, e.g. `{"status": "Active"}`. Requires `doctype`. |
| `limit` | integer | No | 20 | Max results, capped at 100. |

## Mode 1 — global search (omit `doctype`)

```json
{"query": "Grant Plastics"}
```

```json
{
  "success": true,
  "query": "Grant Plastics",
  "search_mode": "global",
  "index": "__global_search",
  "results": [
    {"doctype": "Customer", "name": "Grant Plastics Ltd.", "content": "customer_name || Grant Plastics Ltd."},
    {"doctype": "Sales Invoice", "name": "SINV-00042", "content": "customer || Grant Plastics Ltd."}
  ],
  "count": 2,
  "has_more": false
}
```

- Searches Frappe's full-text index, so it matches **content**, not just document IDs — a customer name inside an invoice is findable.
- `index` tells you which path ran. `"__global_search"` is the full-text index. `"name_scan"` means the index had nothing for this query, so a narrower ID-substring scan over common DocTypes ran instead — in that case a miss does **not** prove the record is absent, so retry with a `doctype`.
- `content` is a truncated snippet of the indexed text, useful for judging relevance.
- Results carry `doctype` + `name` only. Follow up with `get_document` for full data.

## Mode 2 — search within one DocType (pass `doctype`)

```json
{"doctype": "Customer", "query": "Grant"}
```

```json
{
  "success": true,
  "doctype": "Customer",
  "query": "Grant",
  "search_mode": "doctype",
  "results": [{"name": "Grant Plastics Ltd.", "customer_name": "Grant Plastics Ltd."}],
  "count": 1,
  "search_fields": ["customer_name", "tax_id", "website"],
  "filters_applied": {}
}
```

- `search_fields` reports which fields were matched — these come from the DocType's own declared search fields, plus its title field. If the field you need is not listed, use `list_documents` with a `like` filter instead.
- `filters` combines with the text match: `{"doctype": "Customer", "query": "Grant", "filters": {"disabled": 0}}`.

## Mode 3 — resolve a Link field value (`purpose: "link_value"`)

```json
{"doctype": "Customer Group", "query": "com", "purpose": "link_value"}
```

```json
{
  "success": true,
  "doctype": "Customer Group",
  "search_mode": "link_value",
  "results": [{"value": "Commercial", "description": "All Customer Groups", "label": "Commercial"}],
  "count": 1,
  "filters_applied": {}
}
```

- `value` is what you pass to the Link field — Link fields need the exact ID, not a display title.
- This mode honours the DocType's custom search query (Frappe `standard_queries` hooks), so it returns what the desk UI would offer.
- Use it **before** `create_document` or `update_document` whenever a Link field value came from user prose.

## When NOT to use this tool

| Need | Use instead | Why |
|------|-------------|-----|
| "Show me all active customers" | `list_documents` | Exact filters, pagination, total counts |
| "How many invoices last month?" | `list_documents` | This tool does not count or aggregate |
| Invoices between two dates | `list_documents` | Date-range filters, not text matching |
| Full field data for a known record | `get_document` | Search returns identifiers, not full documents |

`search_documents` answers *"find me something matching this text"*. `list_documents` answers *"give me the records matching these conditions"*.

## Best Practices

1. **Start global, then narrow.** No `doctype` when you don't know where the thing lives; add `doctype` once you do.
2. **Always follow up with `get_document`.** Search returns identifiers and a snippet, not full records.
3. **Use `link_value` before writing.** It is the reliable way to turn "Grant Plastics" into a valid Link value.
4. **Keep queries short.** A name or code beats a sentence.
5. **Check `index` on an empty global result.** `"name_scan"` means the full-text index was not consulted, so retry with a `doctype` before concluding nothing exists.

## Permissions

All three modes enforce both DocType-level and row-level permissions. Global hits from the full-text index are re-checked individually, because that index only knows DocType-level access — a User Permission restricting rows is applied on top before anything is returned.

## Edge Cases

- **Global search needs a synced index.** `__global_search` is populated by Frappe's scheduled sync and only covers DocTypes marked for global search. Where it is empty, the `name_scan` fallback matches document IDs only.
- **`filters` without `doctype` is rejected**, rather than silently ignored — filter fieldnames cannot be resolved without a DocType.
- **`purpose: "link_value"` without `doctype` is rejected** — there is no Link target to search.
