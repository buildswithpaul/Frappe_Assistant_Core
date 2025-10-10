# MCP Configuration Settings

The **MCP Configuration** tab in Assistant Core Settings is now fully functional! These settings control how your MCP server identifies itself and what protocol it uses.

## What Changed

Previously, these values were hard-coded throughout the codebase. Now they're **read from settings** and used dynamically across all MCP-related components.

## Configuration Fields

### 1. **MCP Server Name** (Editable)
- **Purpose**: Unique identifier for your MCP server instance
- **Default**: `frappe-assistant-core`
- **Used in**:
  - MCP initialization handshake (`initialize` request)
  - Server discovery endpoints
- **Example**: Change to `my-company-erp-assistant` to customize

### 2. **MCP Protocol Version** (Read-only)
- **Purpose**: Declares which MCP specification version you support
- **Default**: `2025-03-26`
- **Used in**:
  - `initialize` response
  - OAuth discovery metadata (`/.well-known/openid-configuration`)
  - MCP discovery endpoint
- **Note**: Read-only because changing this requires code changes to support different spec versions

### 3. **Transport Type** (Read-only)
- **Purpose**: Declares the transport protocol used
- **Default**: `StreamableHTTP`
- **Used in**:
  - OAuth discovery metadata
  - MCP discovery endpoint
- **Note**: StreamableHTTP enables OAuth 2.0 authentication, which is required for Claude and MCP Inspector

## Where These Values Are Used

### 1. MCP Server Initialization
**File**: [`mcp/server.py`](frappe_assistant_core/mcp/server.py)

When an MCP client (like Claude) calls the `initialize` method, the server now responds with values from settings:

```json
{
  "protocolVersion": "2025-03-26",  // From settings
  "serverInfo": {
    "name": "frappe-assistant-core",  // From settings
    "version": "2.0.0"
  }
}
```

### 2. OAuth Discovery Endpoints
**File**: [`api/oauth_discovery.py`](frappe_assistant_core/api/oauth_discovery.py)

#### `/.well-known/openid-configuration`
Now includes MCP metadata from settings:
```json
{
  "mcp_endpoint": "https://your-site/api/method/...",
  "mcp_transport": "StreamableHTTP",        // From settings
  "mcp_protocol_version": "2025-03-26"      // From settings
}
```

#### `/api/method/frappe_assistant_core.api.oauth_discovery.mcp_discovery`
Returns server information using settings values:
```json
{
  "mcp_transport": "StreamableHTTP",        // From settings
  "mcp_protocol_version": "2025-03-26",    // From settings
  "server_info": {
    "name": "frappe-assistant-core"        // From hooks
  }
}
```

### 3. MCP Endpoint Registration
**File**: [`api/fac_endpoint.py`](frappe_assistant_core/api/fac_endpoint.py)

The MCP server instance is now created with the server name from settings:
```python
mcp = MCPServer(_get_mcp_server_name())
```

## How to Use

1. **Navigate to**: Setup → Assistant Core Settings → MCP Configuration tab

2. **Customize Server Name** (if desired):
   - Change `mcp_server_name` to reflect your organization
   - Example: `acme-corp-assistant`, `company-erp-tools`, etc.

3. **Save**: Click Save to apply changes

4. **Verify**: Check the discovery endpoints to see your changes:
   ```bash
   curl https://your-site/.well-known/openid-configuration | jq .mcp_protocol_version
   ```

## Benefits

✅ **Single source of truth** - Configuration in one place
✅ **Dynamic updates** - Changes take effect immediately
✅ **Customizable identity** - Brand your MCP server
✅ **Future-proof** - Easy to update when new MCP versions release
✅ **Consistent** - All endpoints use the same values

## Technical Details

### Fallback Behavior
If settings can't be loaded (e.g., during installation), the code uses sensible defaults:
- **Server Name**: `frappe-assistant-core`
- **Protocol Version**: `2025-03-26`
- **Transport**: `StreamableHTTP`

### Performance
Settings are fetched once per request, so there's minimal overhead. The values are lightweight (strings) and cached by Frappe's `get_single()` mechanism.

## Future Enhancements

Possible future additions:
- Support for multiple MCP protocol versions
- Custom transport implementations
- Server capability declarations (tools, prompts, resources, sampling)
- Per-user server names for multi-tenant setups

## Related Documentation

- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [OAuth Discovery](oauth_discovery.py)
- [MCP Server Implementation](mcp/server.py)
- [Debugging Guide](DEBUGGING_MCP.md)
