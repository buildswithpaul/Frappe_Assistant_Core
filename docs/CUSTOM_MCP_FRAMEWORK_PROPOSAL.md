# Custom MCP Framework Proposal

## Problem Statement

After migrating to `frappe-mcp` library, we're experiencing issues that didn't exist before:
- ❌ Serialization errors: `'NoneType' object cannot be converted to 'SchemaSerializer'`
- ❌ Parameter handling quirks: MCP Inspector sends `{}` instead of `[]`
- ❌ Added complexity: Extra layer of abstraction
- ✅ **All 21 tools worked perfectly before migration**

## Root Cause Analysis

### What Was Working (Pre-Migration)

**Architecture:**
```
Client → assistant_api.py → tool_registry.execute_tool() → BaseTool._safe_execute() → Tools
```

**Response Flow:**
1. Tools return plain Python dicts
2. `_safe_execute()` wraps results with audit/timing
3. API layer serializes to JSON using `json.dumps(result, default=str)`
4. **Perfect serialization - datetime, Decimal, etc. all handled automatically**

### What's Breaking (Post-Migration with frappe-mcp)

**Architecture:**
```
Client → frappe-mcp wrapper → @mcp.tool decorator → Tools
```

**Issues:**
1. `frappe-mcp` uses Pydantic `SchemaSerializer` which doesn't auto-convert types
2. We're adding workarounds (`serialize_for_mcp()`) that shouldn't be needed
3. Lost the proven `_safe_execute()` wrapper functionality
4. Extra dependency that's causing more problems than it solves

## Proposed Solution: Custom HTTP StreamableHTTP Framework

### Why Build Our Own?

1. ✅ **We already have 21 working tools** - just need HTTP transport
2. ✅ **Simple decorator-based approach** - similar to `@frappe.whitelist()`
3. ✅ **Proven serialization** - reuse existing JSON handling
4. ✅ **Full control** - no external library quirks
5. ✅ **MCP Spec Compliance** - implement exactly what we need

### Architecture

```python
# frappe_assistant_core/mcp/server.py

class MCPServer:
    def __init__(self):
        self.tools = {}
        self.prompts = {}

    def tool(self, description: str, **annotations):
        """Decorator to register MCP tools"""
        def decorator(func):
            tool_spec = {
                "name": func.__name__,
                "description": description,
                "inputSchema": self._generate_schema(func),
                "annotations": annotations
            }
            self.tools[func.__name__] = {
                "spec": tool_spec,
                "handler": func
            }
            return func
        return decorator

    def handle_request(self, request: dict) -> dict:
        """Main MCP request handler - StreamableHTTP"""
        method = request.get("method")

        if method == "initialize":
            return self._handle_initialize(request)
        elif method == "tools/list":
            return self._handle_tools_list(request)
        elif method == "tools/call":
            return self._handle_tools_call(request)
        # ... other methods

    def _handle_tools_call(self, request: dict) -> dict:
        """Execute tool with proper serialization"""
        params = request.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in self.tools:
            return self._error_response(request, -32601, f"Tool not found: {tool_name}")

        try:
            # Execute tool
            handler = self.tools[tool_name]["handler"]
            result = handler(**arguments)

            # CRITICAL: Use proven JSON serialization
            serialized_result = json.loads(json.dumps(result, default=str))

            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(serialized_result, indent=2)
                    }]
                }
            }
        except Exception as e:
            return self._error_response(request, -32603, str(e))

# Global instance
mcp = MCPServer()
```

### Usage (Same as Before!)

```python
from frappe_assistant_core.mcp.server import mcp
from frappe_assistant_core.core.security_middleware import secure_mcp_tool, with_audit

@mcp.tool(
    description="List documents",
    annotations={"readOnlyHint": True}
)
@with_audit(tool_name="list_documents")
@secure_mcp_tool(allowed_roles=["System Manager", "Assistant User"])
def list_documents(doctype: str, filters: dict = None) -> dict:
    # Tool logic - returns plain dict
    results = frappe.get_all(doctype, filters=filters)
    return {
        "success": True,
        "results": results  # datetime fields will be auto-converted!
    }
```

### Endpoint

```python
# frappe_assistant_core/mcp/endpoint.py

@frappe.whitelist(allow_guest=False, xss_safe=True)
def handle_mcp():
    """HTTP StreamableHTTP endpoint for MCP"""
    from frappe_assistant_core.mcp.server import mcp

    # Import all tools (auto-register via decorators)
    _import_tools()

    # Get request
    request = json.loads(frappe.request.data)

    # Handle request
    response = mcp.handle_request(request)

    # Return JSON
    frappe.response["type"] = "json"
    return response
```

## Implementation Benefits

### 1. Simplicity
- **One file** (`mcp/server.py`) ~200 lines
- **No external dependencies** except `frappe`
- **Reuse existing code**: security middleware, audit logging, tool registry

### 2. Proven Reliability
- **Reuse JSON serialization**: `json.dumps(result, default=str)` - handles everything
- **Keep `@secure_mcp_tool`**: Security layers already work
- **Keep `@with_audit`**: Audit logging already works

### 3. Full Control
- **Fix quirks immediately**: No waiting for library updates
- **Custom features**: Add Frappe-specific optimizations
- **No breaking changes**: Control our own destiny

### 4. MCP Spec Compliance
- **StreamableHTTP transport**: HTTP POST with JSON-RPC 2.0
- **Standard methods**: initialize, tools/list, tools/call
- **Proper error codes**: -32700 (parse), -32600 (invalid), etc.

## Migration Path

### Phase 1: Build Core Framework (2-3 hours)
1. Create `frappe_assistant_core/mcp/server.py`
2. Implement `MCPServer` class with decorators
3. Add JSON-RPC 2.0 handling
4. Create endpoint in `mcp/endpoint.py`

### Phase 2: Migrate Tools (1 hour)
1. Change import: `from frappe_assistant_core.mcp.server import mcp`
2. Keep all decorators the same
3. No tool code changes needed!

### Phase 3: Testing (1 hour)
1. Test with MCP Inspector
2. Test with stdio bridge
3. Verify all 21 tools work

### Phase 4: Remove frappe-mcp (15 min)
1. Uninstall: `pip uninstall frappe-mcp`
2. Remove from requirements.txt
3. Clean up migration artifacts

**Total Time: ~5 hours vs. days/weeks of fixing frappe-mcp issues**

## Comparison

| Aspect | frappe-mcp | Custom Framework |
|--------|-----------|------------------|
| **Working Tools** | ❌ Serialization issues | ✅ All 21 tools work |
| **Complexity** | ❌ External library + workarounds | ✅ Single ~200 line file |
| **Control** | ❌ Library limitations | ✅ Full control |
| **Debugging** | ❌ Black box | ✅ Our code, easy debug |
| **Maintenance** | ❌ Wait for fixes | ✅ Fix immediately |
| **Dependencies** | ❌ frappe-mcp + pydantic | ✅ Just frappe |

## Recommendation

**Build our own MCP framework** because:

1. ✅ **It's simpler** - 200 lines vs. external library
2. ✅ **It's proven** - reuses working code
3. ✅ **It's maintainable** - we control it
4. ✅ **It works** - no serialization issues
5. ✅ **It's fast** - 5 hours vs. endless debugging

The `frappe-mcp` library was meant to simplify, but it's adding complexity. We have a working foundation - we just need HTTP StreamableHTTP transport.

## Next Steps

If approved:
1. Create `frappe_assistant_core/mcp/` module
2. Implement `MCPServer` class
3. Test with one tool
4. Migrate all tools
5. Remove frappe-mcp dependency

**Let's build something simple that works!** 🚀
