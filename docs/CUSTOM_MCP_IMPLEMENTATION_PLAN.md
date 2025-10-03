# Custom MCP Implementation Plan

## Analysis of frappe-mcp

After reviewing `/Users/clinton/frappe/bench/frappe-bench/apps/mcp/frappe_mcp/`, here's what we learned:

### What frappe-mcp Does Right ✅

1. **Simple decorator pattern**: `@mcp.register()` and `@mcp.tool()`
2. **Werkzeug integration**: Uses `Request` and `Response` objects
3. **JSON-RPC 2.0 handling**: Proper error codes and validation
4. **Tool registry**: OrderedDict for managing tools

### What Causes Our Issues ❌

**Line 56 in `/server/tools/handlers.py`:**
```python
content.text = content.text or json.dumps(tool_result)
```

**Problem:** `json.dumps()` without `default=str` fails on datetime, Decimal, etc.

**Our old code that worked:**
```python
json.dumps(result, default=str)  # Handles all types!
```

## Our Custom Implementation

### Architecture

We'll build a **simpler, cleaner version** of frappe-mcp that:
1. ✅ Fixes serialization (uses `default=str`)
2. ✅ Removes Pydantic dependency (overkill for our needs)
3. ✅ Keeps the good parts (decorators, Werkzeug, JSON-RPC)
4. ✅ Adds Frappe-specific features (our security middleware)

### File Structure

```
frappe_assistant_core/
├── mcp/
│   ├── __init__.py          # Export MCPServer
│   ├── server.py            # Main MCPServer class (~150 lines)
│   ├── handlers.py          # Request handlers (~100 lines)
│   └── types.py            # Simple type definitions (~50 lines)
└── mcp_server.py           # Entry point (keep for compatibility)
```

### Core Implementation

#### 1. `mcp/server.py` - Main Class

```python
"""
Simple MCP Server Implementation
Based on frappe-mcp but with fixes for our use case.
"""

import json
from collections import OrderedDict
from typing import Callable, Dict, Any, Optional
from werkzeug.wrappers import Request, Response

class MCPServer:
    """Lightweight MCP server for Frappe."""

    def __init__(self, name: str = "frappe-assistant-core"):
        self.name = name
        self.tools = OrderedDict()
        self._entry_fn = None

    def register(self, allow_guest: bool = False, xss_safe: bool = True, token: str = None):
        """Decorator to register MCP endpoint with Frappe."""
        import frappe

        whitelister = frappe.whitelist(
            allow_guest=allow_guest,
            xss_safe=xss_safe,
            methods=['POST']
        )

        def decorator(fn):
            if self._entry_fn is not None:
                raise Exception('Only one MCP endpoint allowed per instance')

            self._entry_fn = fn

            def wrapper() -> Response:
                # Run user's function to import tools
                fn()

                # Handle MCP request
                request = frappe.request
                response = Response()
                return self.handle(request, response, token)

            return whitelister(wrapper)

        return decorator

    def handle(self, request: Request, response: Response, token: str = None) -> Response:
        """Handle MCP request - main entry point."""

        # Validate token if provided
        if token:
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith(f'Bearer {token}'):
                return self._error_response(response, None, -32000, 'Invalid token')

        # Only POST allowed
        if request.method != 'POST':
            response.status_code = 405
            return response

        # Parse JSON request
        try:
            data = request.get_json(force=True)
        except:
            return self._error_response(response, None, -32700, 'Parse error')

        # Check if notification
        if self._is_notification(data):
            response.status_code = 202  # Accepted
            return response

        # Get request ID
        request_id = data.get('id')
        if request_id is None:
            return self._error_response(response, None, -32600, 'Invalid Request')

        # Route method
        method = data.get('method')
        params = data.get('params', {})

        if method == 'initialize':
            result = self._handle_initialize(params)
        elif method == 'tools/list':
            result = self._handle_tools_list(params)
        elif method == 'tools/call':
            result = self._handle_tools_call(params)
        elif method == 'ping':
            result = {}
        else:
            return self._error_response(response, request_id, -32601, 'Method not found')

        # Success response
        return self._success_response(response, request_id, result)

    def tool(self, description: str = None, **annotations):
        """Decorator to register a tool."""
        def decorator(fn: Callable):
            from inspect import signature, getdoc

            tool_name = fn.__name__
            tool_desc = description or getdoc(fn) or ""

            # Generate input schema from function signature
            sig = signature(fn)
            properties = {}
            required = []

            for param_name, param in sig.parameters.items():
                param_type = self._get_json_type(param.annotation)
                properties[param_name] = {"type": param_type}

                if param.default == param.empty:
                    required.append(param_name)

            input_schema = {
                "type": "object",
                "properties": properties,
                "required": required
            }

            # Register tool
            self.tools[tool_name] = {
                "name": tool_name,
                "description": tool_desc,
                "inputSchema": input_schema,
                "annotations": annotations,
                "fn": fn
            }

            return fn

        return decorator

    def _handle_initialize(self, params):
        """Handle initialize request."""
        return {
            "protocolVersion": "2025-03-26",
            "capabilities": {
                "tools": {},
                "prompts": {},
                "resources": {}
            },
            "serverInfo": {
                "name": self.name,
                "version": "2.0.0"
            }
        }

    def _handle_tools_list(self, params):
        """Handle tools/list request."""
        tools_list = []
        for tool in self.tools.values():
            tools_list.append({
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["inputSchema"],
                **({'annotations': tool['annotations']} if tool.get('annotations') else {})
            })

        return {"tools": tools_list}

    def _handle_tools_call(self, params):
        """Handle tools/call request - THE CRITICAL FIX IS HERE."""
        tool_name = params.get('name')
        arguments = params.get('arguments', {})

        if tool_name not in self.tools:
            return {
                "content": [{
                    "type": "text",
                    "text": f"Tool '{tool_name}' not found"
                }],
                "isError": True
            }

        tool = self.tools[tool_name]
        fn = tool['fn']

        try:
            # Execute tool
            result = fn(**arguments)

            # CRITICAL FIX: Use json.dumps with default=str
            # This handles datetime, Decimal, and all other types!
            if isinstance(result, str):
                result_text = result
            else:
                result_text = json.dumps(result, default=str, indent=2)

            return {
                "content": [{
                    "type": "text",
                    "text": result_text
                }],
                "isError": False
            }

        except Exception as e:
            import traceback
            error_text = f"Error executing {tool_name}: {str(e)}\n{traceback.format_exc()}"

            return {
                "content": [{
                    "type": "text",
                    "text": error_text
                }],
                "isError": True
            }

    def _success_response(self, response: Response, request_id, result):
        """Create success response."""
        response_data = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
        response.data = json.dumps(response_data, default=str)
        response.mimetype = 'application/json'
        response.status_code = 200
        return response

    def _error_response(self, response: Response, request_id, code: int, message: str):
        """Create error response."""
        response_data = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }
        response.data = json.dumps(response_data)
        response.mimetype = 'application/json'
        response.status_code = 400
        return response

    def _is_notification(self, data):
        """Check if request is a notification."""
        method = data.get('method', '')
        return isinstance(method, str) and method.startswith('notifications/')

    def _get_json_type(self, annotation):
        """Convert Python type to JSON schema type."""
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            dict: "object",
            list: "array"
        }
        return type_map.get(annotation, "string")
```

#### 2. `mcp_server.py` - Entry Point (Updated)

```python
"""MCP Server using custom implementation."""

import frappe
from frappe_assistant_core.mcp.server import MCPServer

# Create MCP instance
mcp = MCPServer("frappe-assistant-core")

# Import tools helper functions here...
def _check_assistant_enabled(user):
    # ... existing code ...

def _import_core_tools():
    # ... existing code ...

def _import_external_tools():
    # ... existing code ...

def _filter_disabled_tools():
    # ... existing code ...

# Register endpoint
@mcp.register(allow_guest=False, xss_safe=True, token="your_bearer_token")
def handle_mcp():
    """Main MCP endpoint."""
    # Check assistant enabled
    if not _check_assistant_enabled(frappe.session.user):
        frappe.throw("Assistant access disabled")

    # Import tools
    _import_core_tools()
    _import_external_tools()
    _filter_disabled_tools()
```

#### 3. Tool Migration (NO CHANGES NEEDED!)

```python
# Tools work exactly as before!
from frappe_assistant_core.mcp_server import mcp
from frappe_assistant_core.core.security_middleware import secure_mcp_tool, with_audit

@mcp.tool(
    description="List documents",
    readOnlyHint=True
)
@with_audit(tool_name="list_documents")
@secure_mcp_tool(allowed_roles=["System Manager", "Assistant User"])
def list_documents(doctype: str, filters: dict = None) -> dict:
    results = frappe.get_all(doctype, filters=filters)
    return {
        "success": True,
        "results": results  # datetime fields auto-serialized!
    }
```

## Key Improvements Over frappe-mcp

| Feature | frappe-mcp | Our Implementation |
|---------|-----------|-------------------|
| **Serialization** | ❌ `json.dumps()` fails on datetime | ✅ `json.dumps(default=str)` handles everything |
| **Dependencies** | ❌ Pydantic (heavy) | ✅ Just Werkzeug (already in Frappe) |
| **Code Size** | ~500 lines | ~200 lines |
| **Error Handling** | ❌ Silent failures | ✅ Full traceback in errors |
| **Token Auth** | ❌ Not built-in | ✅ Optional Bearer token support |
| **Frappe Integration** | ⚠️ Generic | ✅ Frappe-specific optimizations |

## Migration Steps

### Phase 1: Create New Implementation (1 hour)
1. Create `frappe_assistant_core/mcp/` directory
2. Copy `server.py` implementation above
3. Test with one tool

### Phase 2: Update Entry Point (30 min)
1. Update `mcp_server.py` to use new `MCPServer`
2. Keep all existing helper functions
3. Test initialization

### Phase 3: Verify All Tools (30 min)
1. All tools already use `@mcp.tool()` - no changes needed!
2. Test each tool category
3. Verify serialization works

### Phase 4: Remove frappe-mcp (15 min)
1. `pip uninstall frappe-mcp`
2. Remove from `requirements.txt`
3. Clean up imports

**Total Time: 2-3 hours**

## Benefits

1. ✅ **Fixes serialization issues** - `default=str` handles all types
2. ✅ **Simpler codebase** - 200 lines vs 500+ with dependencies
3. ✅ **Full control** - we can fix/enhance immediately
4. ✅ **No breaking changes** - tools work as-is
5. ✅ **Better errors** - full traceback for debugging
6. ✅ **Frappe-native** - uses Frappe patterns and helpers

## Conclusion

We're building a **streamlined version of frappe-mcp** that:
- Takes the good parts (decorators, Werkzeug, JSON-RPC)
- Fixes the bad parts (serialization, complexity)
- Adds Frappe-specific features (security, audit)

**It's not reinventing the wheel - it's making a better wheel that fits our car!** 🚗
