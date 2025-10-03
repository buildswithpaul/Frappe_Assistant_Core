# StreamableHTTP Native Implementation

## What is StreamableHTTP?

StreamableHTTP is **just HTTP POST with Server-Sent Events (SSE) support**. It's not complex - it's a simple protocol:

1. **Client sends HTTP POST** with JSON-RPC 2.0 request
2. **Server responds with**:
   - **Non-streaming**: Regular HTTP response with JSON body
   - **Streaming**: HTTP response with `Content-Type: text/event-stream` and SSE format

## Key Insight: We Already Do This!

Our current implementation already handles:
- ✅ HTTP POST requests
- ✅ JSON-RPC 2.0 format
- ✅ Tool execution
- ✅ JSON responses

We just need to add **optional SSE streaming** for long-running tools.

## StreamableHTTP Protocol Spec

### Request Format (Same as now!)

```http
POST /api/method/frappe_assistant_core.mcp_server.handle_mcp HTTP/1.1
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "run_python_code",
    "arguments": {"code": "..."}
  }
}
```

### Response Format - Non-Streaming (Same as now!)

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {"type": "text", "text": "Result here"}
    ]
  }
}
```

### Response Format - Streaming (NEW - for long tools)

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Transfer-Encoding: chunked

data: {"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"Progress..."}]}}

data: {"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"More progress..."}]}}

data: {"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"Final result"}]}}

```

## Implementation Plan

### Option 1: Pure HTTP (No SSE) - Simplest

**Good for:** Most tools (90% of use cases)

```python
@frappe.whitelist(allow_guest=False, xss_safe=True)
def handle_mcp():
    """HTTP endpoint - returns JSON directly"""
    # Parse request
    request = json.loads(frappe.request.data)

    # Execute
    response = mcp_server.handle_request(request)

    # Return JSON
    frappe.response["type"] = "json"
    return response
```

**That's it!** No bridge, no complexity. Just HTTP POST → JSON response.

### Option 2: HTTP with Optional SSE - Best of Both Worlds

**Good for:** Supporting both quick tools and long-running tools

```python
@frappe.whitelist(allow_guest=False, xss_safe=True)
def handle_mcp():
    """HTTP endpoint with optional SSE streaming"""
    request = json.loads(frappe.request.data)
    method = request.get("method")

    # Check if tool supports streaming
    if method == "tools/call":
        tool_name = request["params"]["name"]
        if tool_name in STREAMING_TOOLS:
            return handle_streaming_response(request)

    # Non-streaming (default)
    response = mcp_server.handle_request(request)
    frappe.response["type"] = "json"
    return response

def handle_streaming_response(request):
    """Stream response using SSE"""
    def generate():
        # Send progress updates
        for progress in mcp_server.execute_streaming(request):
            yield f"data: {json.dumps(progress)}\n\n"

    # Set SSE headers
    frappe.response["type"] = "page"
    frappe.response.headers["Content-Type"] = "text/event-stream"
    frappe.response.headers["Cache-Control"] = "no-cache"
    frappe.response.headers["Connection"] = "keep-alive"

    return generate()
```

## Frappe-Specific Implementation

### Using Frappe's Response System

Frappe already supports streaming! Here's how:

```python
@frappe.whitelist(allow_guest=False, xss_safe=True)
def handle_mcp():
    """MCP endpoint with native Frappe streaming support"""
    import json
    from frappe_assistant_core.mcp.server import mcp_server

    # Parse request
    request_data = frappe.request.data.decode('utf-8')
    request = json.loads(request_data)

    # Get tool info
    method = request.get("method")

    # For streaming tools, use Frappe's generator response
    if method == "tools/call":
        tool_name = request["params"]["name"]

        # Check if tool supports streaming (optional enhancement)
        tool_config = mcp_server.tools.get(tool_name, {})
        if tool_config.get("streaming"):
            return stream_tool_response(request, tool_name)

    # Default: Non-streaming JSON response
    response = mcp_server.handle_request(request)

    # Serialize properly (handles datetime, etc.)
    serialized = json.loads(json.dumps(response, default=str))

    frappe.response["type"] = "json"
    return serialized

def stream_tool_response(request, tool_name):
    """Stream tool execution using SSE"""
    def event_generator():
        try:
            # Execute tool with progress callback
            for progress_data in mcp_server.execute_streaming(tool_name, request["params"]["arguments"]):
                # Format as SSE
                event = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": progress_data
                }
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as e:
            # Send error as SSE event
            error_event = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    # Set SSE headers
    frappe.response.headers["Content-Type"] = "text/event-stream"
    frappe.response.headers["Cache-Control"] = "no-cache"
    frappe.response.headers["X-Accel-Buffering"] = "no"  # Disable nginx buffering

    return event_generator()
```

## Key Changes Needed

### 1. MCP Server Class Enhancement

```python
class MCPServer:
    def __init__(self):
        self.tools = {}
        self.streaming_tools = set()

    def tool(self, description: str, streaming: bool = False, **annotations):
        """Register tool with streaming support"""
        def decorator(func):
            tool_name = func.__name__
            self.tools[tool_name] = {
                "spec": {...},
                "handler": func,
                "streaming": streaming
            }
            if streaming:
                self.streaming_tools.add(tool_name)
            return func
        return decorator

    def execute_streaming(self, tool_name: str, arguments: dict):
        """Execute tool with streaming support"""
        handler = self.tools[tool_name]["handler"]

        # If handler is a generator, yield each item
        result = handler(**arguments)
        if hasattr(result, '__iter__') and not isinstance(result, (str, dict, list)):
            # It's a generator - stream each item
            for item in result:
                yield {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(item, default=str)
                    }]
                }
        else:
            # Regular result - return once
            yield {
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, default=str)
                }]
            }
```

### 2. Tool Implementation (Optional Streaming)

```python
# Regular tool (non-streaming)
@mcp.tool(description="List documents")
def list_documents(doctype: str):
    results = frappe.get_all(doctype)
    return {"success": True, "results": results}

# Streaming tool (for long operations)
@mcp.tool(description="Run Python code", streaming=True)
def run_python_code(code: str):
    """Generator function for streaming"""
    yield {"status": "Starting execution..."}

    # Execute code
    result = exec(code)

    yield {"status": "Execution complete"}
    yield {"result": result}
```

## Answer to Your Question

**How to make it StreamableHTTP without a bridge?**

1. **For 90% of tools (quick response):**
   - Just return JSON from HTTP POST
   - No streaming needed
   - **Already works!**

2. **For 10% of tools (long-running):**
   - Make tool handler a generator
   - Detect generator in execute
   - Return SSE response with `Content-Type: text/event-stream`
   - Frappe supports this natively!

**No bridge needed because:**
- ✅ It's just HTTP POST (Frappe handles this)
- ✅ JSON-RPC 2.0 (we already do this)
- ✅ SSE streaming (Frappe supports generators)

## What Changes to Accommodate This?

### Minimal Changes:

1. **Add streaming support to MCPServer class** (~20 lines)
   ```python
   def execute_streaming(self, tool_name, arguments):
       # Handle generators
   ```

2. **Update endpoint to detect streaming** (~30 lines)
   ```python
   if tool_supports_streaming:
       return stream_tool_response(request)
   else:
       return json_response(request)
   ```

3. **Make long-running tools generators** (optional)
   ```python
   @mcp.tool(streaming=True)
   def run_python_code(code):
       yield progress...
   ```

### That's It!

**Total new code: ~50 lines**
**Bridge needed: None**
**External dependencies: None**

StreamableHTTP is just a fancy name for "HTTP with optional SSE". We can do this natively in Frappe!

## Example: Complete Implementation

```python
# frappe_assistant_core/mcp/endpoint.py

import json
import frappe
from frappe_assistant_core.mcp.server import mcp_server

@frappe.whitelist(allow_guest=False, xss_safe=True)
def handle_mcp():
    """
    MCP StreamableHTTP endpoint.

    Supports both:
    - Regular JSON responses (for quick tools)
    - SSE streaming (for long-running tools)
    """
    # Parse request
    request = json.loads(frappe.request.data)
    method = request.get("method")

    # Check for streaming
    if method == "tools/call":
        tool_name = request["params"]["name"]
        if mcp_server.is_streaming_tool(tool_name):
            return _stream_response(request, tool_name)

    # Regular JSON response
    response = mcp_server.handle_request(request)
    serialized = json.loads(json.dumps(response, default=str))

    frappe.response["type"] = "json"
    return serialized

def _stream_response(request, tool_name):
    """Handle SSE streaming for long-running tools"""
    def generate():
        for event in mcp_server.execute_streaming(tool_name, request["params"]["arguments"]):
            yield f"data: {json.dumps(event, default=str)}\n\n"

    frappe.response.headers["Content-Type"] = "text/event-stream"
    frappe.response.headers["Cache-Control"] = "no-cache"
    return generate()
```

**That's the entire implementation!** No bridge, no complexity, just HTTP + optional SSE.
