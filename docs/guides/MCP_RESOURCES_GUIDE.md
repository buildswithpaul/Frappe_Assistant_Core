# MCP Resources Feature Guide

## Overview

The MCP Resources feature in Frappe Assistant Core provides a way to optimize LLM context usage by serving detailed tool documentation separately from tool descriptions. When enabled, tools use minimal descriptions with resource hints, while comprehensive documentation is served via the MCP `resources/list` and `resources/read` protocol methods.

### Benefits

- **~90% reduction in tool description tokens** - Minimal descriptions are typically 80-150 characters vs 500-800+ for full descriptions
- **On-demand documentation** - LLM clients can fetch detailed docs only when needed
- **Backwards compatible** - Feature is disabled by default; existing behavior preserved
- **Smart fallback** - Tools without documentation automatically keep full descriptions

---

## Key Components

### 1. Assistant Core Settings

The resources feature is controlled by a single setting:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| **Enable Resources Feature** | Check | Disabled | When enabled, tool descriptions are minimized with resource hints |

### 2. Tool Documentation Files

Documentation is stored as Markdown files in:

```
frappe_assistant_core/
└── docs/
    └── tools/
        ├── create_document.md
        ├── list_documents.md
        ├── get_document.md
        └── ... (one file per tool)
```

### 3. Resource URIs

Resources are accessed via the `fac://` URI scheme:

```
fac://tools/{tool_name}
```

Examples:
- `fac://tools/create_document`
- `fac://tools/list_documents`
- `fac://tools/generate_report`

---

## Behavior Comparison

### Resources Feature DISABLED (Default)

**`tools/list` response:**
```json
{
  "tools": [
    {
      "name": "create_document",
      "description": "Create new Frappe documents with proper validation and child table support. Supports all DocTypes including those with child tables. WORKFLOW: First use get_doctype_info to understand the DocType structure, identify required fields and child tables, then create the document with proper field values. Child tables must be provided as arrays of objects. Referenced records must exist before creation. Returns the created document name on success.",
      "inputSchema": { ... }
    }
  ]
}
```

**`resources/list` response:**
```json
{
  "resources": []
}
```

### Resources Feature ENABLED

**`tools/list` response:**
```json
{
  "tools": [
    {
      "name": "create_document",
      "description": "Create new Frappe documents with proper validation and child table support. See fac://tools/create_document for usage guide.",
      "inputSchema": { ... }
    }
  ]
}
```

**`resources/list` response:**
```json
{
  "resources": [
    {
      "uri": "fac://tools/create_document",
      "name": "Tool: create_document",
      "description": "Usage documentation for the create_document tool",
      "mimeType": "text/markdown"
    },
    {
      "uri": "fac://tools/list_documents",
      "name": "Tool: list_documents",
      "description": "Usage documentation for the list_documents tool",
      "mimeType": "text/markdown"
    }
  ]
}
```

---

## User Guide

### Enabling the Resources Feature

#### From FAC Admin Page (Recommended)

1. Navigate to **FAC Admin** page (`/app/fac-admin`)
2. Click on the **Resources** tab
3. Toggle the **Resources Feature** switch to **Enabled**
4. Changes take effect immediately for new MCP connections

#### From Assistant Core Settings DocType

1. Navigate to `/app/assistant-core-settings`
2. Go to the **Resources** tab
3. Check the **Enable Resources Feature** checkbox
4. Click **Save**

#### Using the API

```python
import frappe

# Enable
frappe.call(
    "frappe_assistant_core.api.admin_api.toggle_resources_feature",
    enabled=True
)

# Disable
frappe.call(
    "frappe_assistant_core.api.admin_api.toggle_resources_feature",
    enabled=False
)
```

### Checking Resource Statistics

The FAC Admin page shows:

- **Resources Enabled**: Current status (Enabled/Disabled)
- **Tool Documentation Count**: Number of `.md` files in `docs/tools/`
- **Total Resources**: Total resources available when feature is enabled

---

## How It Works

### Tool Description Generation

When the resources feature is enabled:

1. **Check if tool has documentation** - Looks for `docs/tools/{tool_name}.md`
2. **If documentation exists**:
   - Extract first sentence from full description
   - Truncate to 100 characters if needed
   - Append resource hint: `See fac://tools/{tool_name} for usage guide.`
3. **If no documentation** - Keep full description (no broken links)

### Code Flow

```
MCP Request (tools/list)
        │
        ▼
┌─────────────────────────┐
│ fac_endpoint.handle_mcp │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   _import_tools()       │
│   └─ register_base_tool │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────────────────────────┐
│ _is_resources_feature_enabled()             │
│ AND                                         │
│ _has_tool_documentation(tool_name)          │
└───────────┬─────────────────────────────────┘
            │
     ┌──────┴──────┐
     │             │
   True          False
     │             │
     ▼             ▼
┌─────────┐  ┌──────────────┐
│ Minimal │  │ Full         │
│ Desc    │  │ Description  │
└─────────┘  └──────────────┘
```

---

## Impact on Custom Tools

### Tools from External Apps

Custom tools registered via the `assistant_tools` hook in your Frappe apps will:

1. **Keep full descriptions** when resources feature is enabled
2. **Not have broken resource hints** since documentation check fails
3. **Work normally** without any changes required

### Adding Documentation for Custom Tools

If you want your custom tools to benefit from minimal descriptions:

1. Create documentation files in your app or contribute to frappe_assistant_core
2. File must be named exactly `{tool_name}.md`
3. Place in `frappe_assistant_core/docs/tools/`

Example for a custom tool `my_custom_tool`:

```markdown
# my_custom_tool

## Description

Does something awesome with your data.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| input_data | object | Yes | The data to process |

## Examples

### Basic Usage

```json
{
  "input_data": {"key": "value"}
}
```

## Notes

- Important consideration 1
- Important consideration 2
```

---

## MCP Protocol Integration

### resources/list Method

Returns all available tool documentation resources.

**Request:**

```json
{
  "jsonrpc": "2.0",
  "method": "resources/list",
  "params": {},
  "id": 1
}
```

**Response (when enabled):**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "resources": [
      {
        "uri": "fac://tools/create_document",
        "name": "Tool: create_document",
        "description": "Usage documentation for the create_document tool",
        "mimeType": "text/markdown"
      }
    ]
  },
  "id": 1
}
```

**Response (when disabled):**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "resources": []
  },
  "id": 1
}
```

### resources/read Method

Reads the content of a specific resource.

**Request:**

```json
{
  "jsonrpc": "2.0",
  "method": "resources/read",
  "params": {
    "uri": "fac://tools/create_document"
  },
  "id": 2
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "contents": [
      {
        "uri": "fac://tools/create_document",
        "mimeType": "text/markdown",
        "text": "# create_document\n\n## Description\n\nCreate new Frappe documents..."
      }
    ]
  },
  "id": 2
}
```

**Error (resource not found):**

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32602,
    "message": "Tool documentation not found: unknown_tool"
  },
  "id": 2
}
```

---

## API Reference

### Admin API Endpoints

#### Get Resource Statistics

```http
POST /api/method/frappe_assistant_core.api.admin_api.get_resource_stats
Authorization: token api_key:api_secret
```

**Response:**

```json
{
  "success": true,
  "tool_docs_count": 28,
  "total_resources": 28,
  "resources_enabled": true
}
```

#### Toggle Resources Feature

```http
POST /api/method/frappe_assistant_core.api.admin_api.toggle_resources_feature
Authorization: token api_key:api_secret
Content-Type: application/json

{
  "enabled": 1
}
```

**Response:**

```json
{
  "success": true,
  "message": "Resources feature enabled. Tool descriptions will be minimized.",
  "enabled": true
}
```

#### Get Tool Documentation List

```http
POST /api/method/frappe_assistant_core.api.admin_api.get_tool_docs_list
Authorization: token api_key:api_secret
```

**Response:**

```json
{
  "success": true,
  "tool_docs": [
    {
      "tool_name": "create_document",
      "uri": "fac://tools/create_document",
      "size": 5147
    },
    {
      "tool_name": "list_documents",
      "uri": "fac://tools/list_documents",
      "size": 3896
    }
  ]
}
```

---

## Technical Details

### Files Modified

| File | Purpose |
|------|---------|
| `mcp/tool_adapter.py` | Checks resources feature + docs existence |
| `core/tool_registry.py` | Conditional minimal descriptions |
| `core/base_tool.py` | `get_minimal_description()` method |
| `api/handlers/resources.py` | Resource list/read handlers |
| `api/admin_api.py` | Toggle and stats endpoints |

### Database Setting

The setting is stored in the `Assistant Core Settings` Single DocType:

```sql
SELECT enable_resources_feature
FROM `tabSingles`
WHERE doctype = 'Assistant Core Settings'
AND field = 'enable_resources_feature';
```

### Cache Considerations

- Setting is read directly from DB (`frappe.db.get_single_value`) to avoid cache issues
- Changes take effect immediately without server restart
- Each MCP request checks the current setting value

---

## Troubleshooting

### Resources Not Showing After Enable

1. **Check the setting is saved:**
   ```python
   frappe.db.get_single_value("Assistant Core Settings", "enable_resources_feature")
   # Should return 1
   ```

2. **Verify documentation files exist:**
   ```bash
   ls -la apps/frappe_assistant_core/frappe_assistant_core/docs/tools/
   ```

3. **Test with curl:**
   ```bash
   curl -X POST "http://localhost:8000/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"resources/list","params":{},"id":1}'
   ```

### Tool Still Showing Full Description

This is expected behavior if:
- The tool doesn't have a documentation file in `docs/tools/{tool_name}.md`
- Custom tools from external apps won't have documentation by default

### Resource Read Returns Error

Check that:
1. The URI format is correct: `fac://tools/{tool_name}`
2. The `.md` file exists in `docs/tools/`
3. File permissions allow reading

---

## Best Practices

### When to Enable Resources

Enable the resources feature when:
- Your LLM client supports MCP resources
- You want to reduce token usage
- You have many tools with long descriptions

Keep disabled when:
- Using clients that don't support resources
- Token usage is not a concern
- You prefer self-contained tool descriptions

### Writing Tool Documentation

1. **Start with a clear description** - First sentence becomes the minimal description
2. **Include all parameters** - Document every input parameter
3. **Provide examples** - Show common use cases
4. **Add notes/warnings** - Call out important considerations

---

## Related Documentation

- [API Reference](../api/API_REFERENCE.md) - Complete MCP endpoint documentation
- [Tool Reference](../api/TOOL_REFERENCE.md) - All available tools
- [Architecture Overview](../architecture/ARCHITECTURE.md) - System design
- [Plugin Management Guide](PLUGIN_MANAGEMENT_GUIDE.md) - Enable/disable plugins

---

**Version:** 2.1.0+
**Last Updated:** January 2025
**MCP Protocol:** 2025-03-26
