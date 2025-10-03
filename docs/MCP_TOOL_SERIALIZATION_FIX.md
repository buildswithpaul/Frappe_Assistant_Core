# MCP Tool Serialization Fix

## Problem

MCP Inspector error: `'NoneType' object cannot be converted to 'SchemaSerializer'`

This error occurs when tools return non-JSON-serializable data types like:
- `datetime.datetime` objects
- `datetime.date` objects
- `decimal.Decimal` objects
- Other Python objects that can't be directly serialized to JSON

## Root Cause

The MCP library expects all tool responses to be JSON-serializable. When Frappe's `get_all()`, `get_doc()`, or other database methods return results with datetime fields, these objects cause serialization failures.

## Solution

Use the `serialize_for_mcp()` helper function from `frappe_assistant_core.utils.mcp_helpers`.

### Step 1: Import the Helper

```python
from frappe_assistant_core.utils.mcp_helpers import serialize_for_mcp
```

### Step 2: Wrap Return Values

**Before (causes error):**
```python
return {
    "success": True,
    "results": frappe.get_all("Customer", fields=["name", "creation"]),
}
```

**After (works correctly):**
```python
return serialize_for_mcp({
    "success": True,
    "results": frappe.get_all("Customer", fields=["name", "creation"]),
})
```

## How `serialize_for_mcp()` Works

```python
def serialize_for_mcp(data: Any) -> Any:
    """Convert non-JSON-serializable types to strings"""
    import json
    return json.loads(json.dumps(data, default=str))
```

It uses `json.dumps(data, default=str)` which converts any non-serializable object to its string representation, then parses it back to get clean Python dict/list.

## Tools Fixed

✅ **list_documents** - Serializes results from `frappe.get_all()`
✅ **search_doctype** - Serializes search results

## Tools That Need Fixing

Apply this fix to any tool that returns database results:

### Document Operations
- `get_document` - Returns full doc with datetime fields
- `update_document` - Returns updated doc
- `create_document` - Returns created doc

### Search Tools
- `search_documents` - Returns search results
- `search_link` - Returns link options

### Reports
- `generate_report` - Returns report data
- `report_list` - Returns report metadata

### Data Science
- `analyze_business_data` - Returns analysis results
- `run_database_query` - Returns query results

## Quick Fix Template

For any tool returning database data:

```python
# 1. Add import
from frappe_assistant_core.utils.mcp_helpers import serialize_for_mcp

# 2. Wrap return statement
def your_tool():
    # ... tool logic ...
    results = frappe.get_all(...)  # or any DB operation

    return serialize_for_mcp({
        "success": True,
        "results": results,
        # ... other fields ...
    })
```

## Testing

After applying the fix, test with MCP Inspector:

```bash
# Test the tool
curl -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"your_tool","arguments":{...}}}' \
  http://localhost:8000/api/method/frappe_assistant_core.mcp_server.handle_mcp
```

The response should be valid JSON without Schema Serialization errors.

## Additional MCP Helpers

### Parameter Normalization

MCP Inspector sometimes sends `{}` instead of `[]` or `null`. Use these helpers:

```python
from frappe_assistant_core.utils.mcp_helpers import (
    normalize_mcp_dict,   # Converts {} to proper dict or default
    normalize_mcp_list,   # Converts {} to proper list or default
    normalize_mcp_string, # Normalizes string parameters
    serialize_for_mcp,    # Serializes responses
)

def my_tool(
    filters: Optional[Dict] = None,
    fields: Optional[List] = None
):
    # Normalize parameters
    filters = normalize_mcp_dict(filters, default={})
    fields = normalize_mcp_list(fields, default=["name"])

    # ... tool logic ...

    # Serialize response
    return serialize_for_mcp({"success": True, "data": results})
```

## Status

- ✅ `serialize_for_mcp()` helper created
- ✅ `list_documents` fixed
- ✅ `search_doctype` fixed
- ⏳ Remaining tools need to be fixed as encountered

Apply this fix whenever you see the SchemaSerializer error!
