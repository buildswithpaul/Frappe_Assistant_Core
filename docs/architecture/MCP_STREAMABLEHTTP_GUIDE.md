# MCP StreamableHTTP Integration Guide

## Overview

Frappe Assistant Core implements the **Model Context Protocol (MCP)** using **StreamableHTTP** transport with OAuth 2.0 authentication. This modern approach replaces the legacy STDIO bridge, providing better security, compatibility, and standardization.

### What is MCP StreamableHTTP?

MCP StreamableHTTP is a transport layer that:
- Uses **HTTP POST** requests for communication
- Implements **JSON-RPC 2.0** protocol
- Supports **OAuth 2.0** authentication
- Works with any HTTP client (no subprocess management)
- Enables web-based and native MCP clients

### Why We Moved from STDIO to StreamableHTTP

| Feature | STDIO Bridge (Legacy) | StreamableHTTP (Current) |
|---------|----------------------|-------------------------|
| **Authentication** | API Key in environment | OAuth 2.0 with tokens |
| **Transport** | stdin/stdout pipes | HTTP requests |
| **Client Support** | Limited to subprocess-capable clients | Any HTTP-capable client |
| **Security** | Basic API key | Industry-standard OAuth |
| **Discovery** | Manual configuration | Auto-discovery via .well-known |
| **Token Management** | No token refresh | Automatic token refresh |
| **Web Compatibility** | ❌ No | ✅ Yes |

## Architecture Overview

```mermaid
---
config:
  layout: elk
---
flowchart TB
 subgraph subGraph0["MCP Client Layer"]
        Client["MCP Client<br>Claude Desktop, MCP Inspector, etc."]
  end
 subgraph subGraph1["OAuth Discovery & Authentication"]
        Discovery["/.well-known/openid-configuration<br>OAuth Discovery Endpoint"]
        OAuth["OAuth Endpoints<br>authorize, token, register, etc."]
  end
 subgraph subGraph2["OAuth Token Validation"]
        Extract["Extract Bearer token<br>from Authorization header"]
        Validate["Validate token against<br>OAuth Bearer Token doc"]
        Check["Check token status<br>and expiration"]
        SetUser["Set user session<br>frappe.set_user"]
  end
 subgraph subGraph3["FAC MCP Server (mcp/server.py)"]
        JSONRPC["JSON-RPC 2.0<br>request handling"]
        Routing["Method routing<br>initialize, tools/list, etc."]
        MCPRegistry["Tool registry<br>integration"]
        Serialization["JSON serialization<br>with default=str"]
  end
 subgraph subGraph4["Tool Registry"]
        Discovery2["Plugin discovery<br>and loading"]
        Instantiation["Tool<br>instantiation"]
        Permissions["Permission<br>filtering"]
        Adapter["Tool adapter for<br>BaseTool compatibility"]
  end
 subgraph subGraph5["Tool Execution"]
        ArgValidation["Argument<br>validation"]
        PermCheck["Permission<br>checking"]
        Execute["Tool.execute"]
        Audit["Audit<br>logging"]
        ErrorHandle["Error<br>handling"]
  end
 subgraph subGraph6["Frappe Assistant Core - MCP Handler"]
        Endpoint["/api/method/frappe_assistant_core<br>.api.fac_endpoint.handle_mcp"]
        subGraph2
        subGraph3
        subGraph4
        subGraph5
  end
    Client -- OAuth Discovery --> Discovery
    Client -- OAuth Authorization Flow --> OAuth
    Client -- MCP Requests with Bearer Token --> Endpoint
    Endpoint --> Extract
    Extract --> Validate
    Validate --> Check
    Check --> SetUser
    SetUser --> JSONRPC
    JSONRPC --> Routing
    Routing --> MCPRegistry
    MCPRegistry --> Serialization
    Serialization --> Discovery2
    Discovery2 --> Instantiation
    Instantiation --> Permissions
    Permissions --> Adapter
    Adapter --> ArgValidation
    ArgValidation --> PermCheck
    PermCheck --> Execute
    Execute --> Audit & ErrorHandle
     Client:::clientStyle
     Discovery:::oauthStyle
     OAuth:::oauthStyle
     Extract:::validationStyle
     Validate:::validationStyle
     Check:::validationStyle
     SetUser:::validationStyle
     JSONRPC:::serverStyle
     Routing:::serverStyle
     MCPRegistry:::serverStyle
     Serialization:::serverStyle
     Discovery2:::registryStyle
     Instantiation:::registryStyle
     Permissions:::registryStyle
     Adapter:::registryStyle
     ArgValidation:::executionStyle
     PermCheck:::executionStyle
     Execute:::executionStyle
     Audit:::executionStyle
     ErrorHandle:::executionStyle
    classDef clientStyle fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef oauthStyle fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef validationStyle fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef serverStyle fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef registryStyle fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef executionStyle fill:#e0f2f1,stroke:#00695c,stroke-width:2px
```

## Endpoint

### MCP Endpoint URL

```
POST https://your-frappe-site.com/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp
```

**Protocol:** MCP 2025-03-26 (JSON-RPC 2.0)
**Authentication:** OAuth 2.0 Bearer tokens
**Content-Type:** application/json

### Discovery Endpoint

```
GET https://your-frappe-site.com/.well-known/openid-configuration
```

This endpoint provides:
- OAuth authorization and token endpoints
- Supported grant types and response types
- PKCE support information
- Dynamic client registration endpoint (if enabled)
- **MCP-specific metadata:**
  - `mcp_endpoint`: The MCP handler URL
  - `mcp_protocol_version`: Supported MCP version
  - `mcp_transport`: Transport type (StreamableHTTP)

## Authentication Flow

### Step 1: OAuth Discovery

The client fetches the OpenID configuration to discover OAuth endpoints:

```http
GET /.well-known/openid-configuration HTTP/1.1
Host: your-frappe-site.com
```

**Response:**
```json
{
  "issuer": "https://your-frappe-site.com",
  "authorization_endpoint": "https://your-frappe-site.com/api/method/frappe.integrations.oauth2.authorize",
  "token_endpoint": "https://your-frappe-site.com/api/method/frappe.integrations.oauth2.get_token",
  "userinfo_endpoint": "https://your-frappe-site.com/api/method/frappe.integrations.oauth2.openid_profile",
  "jwks_uri": "https://your-frappe-site.com/.well-known/jwks.json",
  "registration_endpoint": "https://your-frappe-site.com/api/method/frappe_assistant_core.api.oauth_registration.register_client",
  "revocation_endpoint": "https://your-frappe-site.com/api/method/frappe.integrations.oauth2.revoke_token",
  "introspection_endpoint": "https://your-frappe-site.com/api/method/frappe.integrations.oauth2.introspect_token",
  "response_types_supported": ["code"],
  "grant_types_supported": ["authorization_code", "refresh_token"],
  "code_challenge_methods_supported": ["S256"],
  "subject_types_supported": ["public"],
  "id_token_signing_alg_values_supported": ["RS256"],
  "token_endpoint_auth_methods_supported": ["none", "client_secret_basic", "client_secret_post"],
  "mcp_endpoint": "https://your-frappe-site.com/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp",
  "mcp_protocol_version": "2025-03-26",
  "mcp_transport": "StreamableHTTP"
}
```

### Step 2: Dynamic Client Registration (Optional)

If dynamic client registration is enabled, the client can automatically register:

```http
POST /api/method/frappe_assistant_core.api.oauth_registration.register_client HTTP/1.1
Host: your-frappe-site.com
Content-Type: application/json

{
  "client_name": "MCP Inspector",
  "redirect_uris": ["http://localhost:6274/callback"],
  "token_endpoint_auth_method": "none",
  "grant_types": ["authorization_code", "refresh_token"],
  "response_types": ["code"]
}
```

**Response:**
```json
{
  "client_id": "a1b2c3d4e5",
  "client_name": "MCP Inspector",
  "redirect_uris": ["http://localhost:6274/callback"],
  "token_endpoint_auth_method": "none"
}
```

### Step 3: Authorization Code Flow with PKCE

#### 3.1: Generate PKCE Code Verifier and Challenge

```python
import secrets
import hashlib
import base64

# Generate code verifier (43-128 characters)
code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

# Generate code challenge (SHA256 hash of verifier)
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode('utf-8')).digest()
).decode('utf-8').rstrip('=')
```

#### 3.2: Authorization Request

Redirect user to authorization endpoint:

```
GET /api/method/frappe.integrations.oauth2.authorize?
    response_type=code&
    client_id=a1b2c3d4e5&
    redirect_uri=http://localhost:6274/callback&
    scope=all openid&
    code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&
    code_challenge_method=S256&
    state=random_state_string
```

#### 3.3: User Authorization

User logs into Frappe and authorizes the application. Frappe redirects back:

```
http://localhost:6274/callback?code=AUTH_CODE&state=random_state_string
```

#### 3.4: Token Exchange

Exchange authorization code for access token:

```http
POST /api/method/frappe.integrations.oauth2.get_token HTTP/1.1
Host: your-frappe-site.com
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&
code=AUTH_CODE&
redirect_uri=http://localhost:6274/callback&
code_verifier=ORIGINAL_CODE_VERIFIER&
client_id=a1b2c3d4e5
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "def50200..."
}
```

### Step 4: MCP Request with Bearer Token

Now make MCP requests with the access token:

```http
POST /api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp HTTP/1.1
Host: your-frappe-site.com
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "method": "tools/list",
  "params": {},
  "id": 1
}
```

### Step 5: Token Refresh

When the access token expires, use the refresh token:

```http
POST /api/method/frappe.integrations.oauth2.get_token HTTP/1.1
Host: your-frappe-site.com
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token&
refresh_token=def50200...&
client_id=a1b2c3d4e5
```

## Request/Response Format

### JSON-RPC 2.0 Structure

All MCP requests follow JSON-RPC 2.0 specification:

```json
{
  "jsonrpc": "2.0",
  "method": "method_name",
  "params": {},
  "id": 1
}
```

### Initialize Request

```json
{
  "jsonrpc": "2.0",
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-03-26",
    "capabilities": {}
  },
  "id": 1
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "protocolVersion": "2025-03-26",
    "capabilities": {
      "tools": {}
    },
    "serverInfo": {
      "name": "frappe-assistant-core",
      "version": "2.0.0"
    }
  },
  "id": 1
}
```

### Tools List Request

```json
{
  "jsonrpc": "2.0",
  "method": "tools/list",
  "params": {},
  "id": 2
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "tools": [
      {
        "name": "create_document",
        "description": "Create a new Frappe document",
        "inputSchema": {
          "type": "object",
          "properties": {
            "doctype": {"type": "string"},
            "data": {"type": "object"}
          },
          "required": ["doctype", "data"]
        }
      }
    ]
  },
  "id": 2
}
```

### Tool Call Request

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "list_documents",
    "arguments": {
      "doctype": "Customer",
      "limit": 5
    }
  },
  "id": 3
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "[{\"name\": \"CUST-00001\", \"customer_name\": \"ABC Corp\"}]"
      }
    ],
    "isError": false
  },
  "id": 3
}
```

### Error Response

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32603,
    "message": "Internal error: Permission denied for DocType Customer"
  },
  "id": 3
}
```

## Implementation Details

### FAC MCP Server Class

Located in [mcp/server.py](../frappe_assistant_core/mcp/server.py), our custom implementation provides:

**Key Features:**
- ✅ Proper JSON serialization (handles datetime, Decimal with `default=str`)
- ✅ No Pydantic dependency (lighter, Frappe-native)
- ✅ Full error tracebacks for debugging
- ✅ Frappe session integration
- ✅ Tool adapter for BaseTool compatibility

**Why Custom Implementation?**

We built the FAC MCP Server instead of using generic libraries because:

1. **JSON Serialization Issues**: Generic libraries don't handle Frappe's data types (datetime, Decimal) properly
2. **Frappe Integration**: Direct integration with Frappe's session, permissions, and ORM
3. **Simplified Dependencies**: No need for Pydantic or other heavy libraries
4. **Better Debugging**: Full control over error handling and logging
5. **Performance**: Optimized for Frappe's architecture

**Code Example:**

```python
from frappe_assistant_core.mcp.server import MCPServer

# Create MCP server instance
mcp = MCPServer("frappe-assistant-core")

# Register the main endpoint
@mcp.register(allow_guest=True, xss_safe=True)
def handle_mcp():
    # Perform OAuth validation
    # Import tools
    # Return None to continue with MCP handling
    return None

# Tools are registered via the tool registry
# The server handles all MCP protocol methods automatically
```

### Tool Adapter Pattern

The [mcp/tool_adapter.py](../frappe_assistant_core/mcp/tool_adapter.py) provides compatibility between our BaseTool classes and the MCP server:

**Purpose:**
- Bridge between BaseTool interface and MCP protocol
- Automatic argument validation and permission checking
- Consistent error handling and audit logging
- MCP protocol compliance

**Usage:**

```python
from frappe_assistant_core.mcp.tool_adapter import register_base_tool
from frappe_assistant_core.api.fac_endpoint import mcp

# Register an existing BaseTool with MCP server
register_base_tool(mcp, tool_instance)
```

**How it works:**

1. Creates a wrapper function that calls `tool_instance._safe_execute()`
2. Extracts tool metadata (name, description, inputSchema)
3. Registers with MCPServer using `mcp.add_tool()`
4. All BaseTool features work automatically (validation, permissions, audit, etc.)

### JSON Serialization Fix

One of the key innovations in the FAC MCP Server is proper JSON serialization:

**The Problem:**
```python
# Frappe returns datetime, Decimal, and other non-JSON types
result = frappe.get_doc("Sales Invoice", "INV-00001")
json.dumps(result)  # ❌ TypeError: Object of type datetime is not JSON serializable
```

**Our Solution:**
```python
# Use default=str to convert any type to string
json.dumps(result, default=str)  # ✅ Works perfectly
```

This simple but critical fix is implemented in [mcp/server.py:398](../frappe_assistant_core/mcp/server.py#L398):

```python
# CRITICAL FIX: Use json.dumps with default=str
# This handles datetime, Decimal, and all other non-JSON types!
if isinstance(result, str):
    result_text = result
else:
    # The key fix: default=str converts any type to string
    result_text = json.dumps(result, default=str, indent=2)
```

### Token Validation Flow

Implemented in [api/fac_endpoint.py:99-167](../frappe_assistant_core/api/fac_endpoint.py#L99-L167):

```python
# Check for Bearer token in Authorization header
auth_header = frappe.request.headers.get("Authorization", "")

if not auth_header.startswith("Bearer "):
    # Return 401 with WWW-Authenticate header per RFC 9728
    return unauthorized_response()

# Validate OAuth token
token = auth_header[7:]  # Remove "Bearer " prefix

# Validate token using Frappe's OAuth Bearer Token doctype
bearer_token = frappe.get_doc("OAuth Bearer Token", {"access_token": token})

# Check if token is active
if bearer_token.status != "Active":
    raise frappe.AuthenticationError("Token is not active")

# Check if token has expired
if bearer_token.expiration_time < datetime.datetime.now():
    raise frappe.AuthenticationError("Token has expired")

# Set the user session
frappe.set_user(bearer_token.user)
```

**401 Response Format (RFC 9728 compliant):**

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer realm="Frappe Assistant Core",
                  error="invalid_token",
                  error_description="Token has expired",
                  resource_metadata="https://your-site.com/.well-known/oauth-protected-resource"
Content-Type: application/json

{
  "error": "invalid_token",
  "message": "Token has expired"
}
```

## Troubleshooting

### Connection Issues

**Problem:** Cannot connect to MCP endpoint

**Solutions:**
1. Verify endpoint URL is correct
2. Check that Frappe site is accessible
3. Ensure `frappe_assistant_core` app is installed
4. Check that user has `assistant_enabled = 1`
5. Verify no firewall blocking requests

### OAuth Discovery Fails

**Problem:** Cannot fetch `/.well-known/openid-configuration`

**Solutions:**
1. Check that OAuth discovery is enabled in Assistant Core Settings
2. Verify Frappe site URL is correct (include https://)
3. Test endpoint directly in browser
4. Check server logs for errors

### Dynamic Client Registration Fails

**Problem:** Registration endpoint returns error

**Solutions:**
1. Verify "Enable Dynamic Client Registration" is checked in settings
2. Check that redirect_uris use HTTPS (or localhost for development)
3. Verify token_endpoint_auth_method is valid ("none", "client_secret_basic", "client_secret_post")
4. Check if origin is allowed in "Allowed Public Client Origins" (for browser-based clients)

### Token Validation Fails

**Problem:** 401 Unauthorized response

**Solutions:**
1. Check that Bearer token is included in Authorization header
2. Verify token hasn't expired (tokens have limited lifetime)
3. Try refreshing the token using refresh_token grant
4. Check that token exists in OAuth Bearer Token doctype
5. Verify token status is "Active"
6. Check server logs for detailed error message

### Tool Execution Fails

**Problem:** Tool returns error or doesn't work

**Solutions:**
1. Verify user has permissions for the DocType
2. Check that required plugins are enabled
3. Verify tool arguments match inputSchema
4. Check Frappe error log for detailed errors
5. Test the operation manually in Frappe UI

## Security Considerations

### Token Security

- **Never share access tokens** - they provide full access to your account
- **Use HTTPS** - always use HTTPS in production to protect tokens in transit
- **Token Storage** - clients should store tokens securely (encrypted storage)
- **Token Lifetime** - tokens expire after a set time (default: 1 hour)
- **Refresh Tokens** - use refresh tokens to get new access tokens

### PKCE (Proof Key for Code Exchange)

PKCE is **required** for all OAuth flows to prevent authorization code interception:

- **Code Verifier**: Random 43-128 character string
- **Code Challenge**: SHA256 hash of code verifier
- **Validation**: Server verifies code_verifier matches code_challenge

### Dynamic Client Registration

When dynamic client registration is enabled:

- **Public Clients** require CORS configuration (Allowed Public Client Origins)
- **Confidential Clients** can register without restrictions
- **HTTPS Required** for production redirect URIs (localhost allowed for development)

## Performance Optimization

### Token Caching

Clients should cache access tokens until they expire:

```python
class MCPClient:
    def __init__(self):
        self.access_token = None
        self.token_expires_at = None

    def get_access_token(self):
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token

        # Refresh token or re-authenticate
        self.refresh_access_token()
        return self.access_token
```

### Connection Pooling

Use HTTP connection pooling for better performance:

```python
import requests

session = requests.Session()
session.headers.update({"Authorization": f"Bearer {access_token}"})

# Reuse connection for multiple requests
response = session.post(mcp_url, json=request1)
response = session.post(mcp_url, json=request2)
```

### Request Batching

While MCP doesn't support batch requests, you can optimize by:
- Requesting only needed fields in tool calls
- Using appropriate page limits for list operations
- Caching tool metadata (tools/list doesn't change frequently)

## Additional Resources

- [OAuth Setup Guide](../getting-started/oauth/oauth_setup_guide.md) - Detailed OAuth configuration
- [API Reference](../api/API_REFERENCE.md) - Complete API documentation
- [Architecture](ARCHITECTURE.md) - System architecture overview
- [Tool Reference](../api/TOOL_REFERENCE.md) - Available tools documentation

## Support

- **GitHub Issues**: https://github.com/buildswithpaul/Frappe_Assistant_Core/issues
- **Documentation**: https://github.com/buildswithpaul/Frappe_Assistant_Core/tree/main/docs
- **Email**: jypaulclinton@gmail.com

---

**Version:** 2.2.0+
**Last Updated:** January 2025
**Protocol:** MCP 2025-03-26 with StreamableHTTP transport
