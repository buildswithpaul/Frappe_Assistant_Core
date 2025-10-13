# OAuth Setup Guide for Frappe Assistant Core

## Overview

Frappe Assistant Core supports **OAuth 2.0 Dynamic Client Registration** (RFC 7591), allowing MCP clients like Claude Desktop and MCP Inspector to automatically register and connect without manual OAuth client setup.

This guide will help you configure OAuth for your Frappe Assistant Core installation.

---

## Quick Start

### For Most Users

1. Go to **Assistant Core Settings**
2. Click the **OAuth** tab
3. Check ✅ **Enable Dynamic Client Registration**
4. For MCP Inspector, add `http://localhost:6274` to **Allowed Public Client Origins**
5. Save

That's it! Your MCP clients can now auto-register.

---

## Detailed Configuration

### Main Settings

#### 1. Enable Dynamic Client Registration

**What it does:** Allows MCP tools to automatically register as OAuth clients without manual setup.

**When to enable:**
- ✅ Using Claude Desktop with MCP
- ✅ Using MCP Inspector for testing
- ✅ Building custom MCP clients
- ❌ Only using manually-created OAuth clients

**Default:** Enabled

---

#### 2. Allowed Public Client Origins

**What it does:** Controls which browser-based OAuth clients can connect.

**Security Note:** Public clients (browser-based) can't keep secrets secure, so we restrict them by origin.

**How to configure:**

**Option A: Allow Specific Origins (Recommended)**
```
http://localhost:6274
https://your-mcp-app.com
```

**Option B: Allow All (Development Only)**
```
*
```

**Option C: Block All Public Clients (Most Secure)**
```
(leave blank)
```

**Common Values:**
- `http://localhost:6274` - MCP Inspector (local development)
- `http://localhost:3000` - Your custom MCP client (local dev)
- `*` - Allow all (NOT recommended for production)

---

### Advanced Settings (Collapsed by Default)

Most users won't need these. Click "Advanced OAuth Settings" to expand.

#### Show Authorization Server Metadata

**What it does:** Exposes OAuth server info at `/.well-known/oauth-authorization-server`

**Default:** Enabled
**When to disable:** Never (required for auto-discovery)

---

#### Show Protected Resource Metadata

**What it does:** Exposes resource info at `/.well-known/oauth-protected-resource`

**Default:** Enabled
**When to disable:** If you don't want to expose resource metadata publicly

---


---

**When to enable:** Advanced federation scenarios only

---

### Resource Metadata (Optional, Collapsed by Default)

These fields customize metadata shown to OAuth clients. Most users can ignore these.

#### Resource Name
**Default:** "Frappe Assistant Core"
**Example:** "ACME Corp ERP System"

#### Documentation URL
**Default:** "https://github.com/buildswithpaul/Frappe_Assistant_Core"
**Example:** "https://docs.acme.com/api"

#### Policy URI
**Optional:** Link to your privacy policy

#### Terms of Service URI
**Optional:** Link to your terms of service

#### Supported Scopes
**Optional:** List of OAuth scopes (one per line)
**Example:**
```
all
openid
profile
email
```

---

## Common Scenarios

### Scenario 1: Claude Desktop with MCP

**Goal:** Use Claude Desktop to access Frappe via MCP

**Configuration:**
1. Enable Dynamic Client Registration: ✅
2. Allowed Public Client Origins: (leave blank - Claude Desktop is not browser-based)
3. Save

**Why:** Claude Desktop uses confidential client authentication, not public client.

---

### Scenario 2: MCP Inspector (Testing)

**Goal:** Test MCP server with MCP Inspector tool

**Configuration:**
1. Enable Dynamic Client Registration: ✅
2. Allowed Public Client Origins:
   ```
   http://localhost:6274
   ```
3. Save

**Why:** MCP Inspector runs in the browser and uses public client flow.

---

### Scenario 3: Custom Browser-Based MCP Client

**Goal:** Build your own web-based MCP client

**Configuration:**

**Development:**
1. Enable Dynamic Client Registration: ✅
2. Allowed Public Client Origins:
   ```
   http://localhost:3000
   http://localhost:5173
   ```

**Production:**
1. Enable Dynamic Client Registration: ✅
2. Allowed Public Client Origins:
   ```
   https://your-app.com
   ```

---

### Scenario 4: Maximum Security (Manual OAuth Clients Only)

**Goal:** Disable auto-registration, require manual OAuth client creation

**Configuration:**
1. Enable Dynamic Client Registration: ❌
2. Save

**Result:** All OAuth clients must be manually created in **OAuth Client** DocType.

---

## Testing Your Configuration

### Method 1: Using MCP Inspector

1. Configure OAuth settings (enable dynamic registration + add `http://localhost:6274`)
2. Open MCP Inspector: http://localhost:6274/
3. Select "Streamable HTTP" transport
4. Enter URL: `https://your-frappe-site.com/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp`
5. Click "Open Auth Settings"
6. Click "Quick OAuth Flow"
7. Authorize when prompted

**Success:** You should see "Authentication Complete" ✅

---

### Method 2: Check Discovery Endpoints

Visit these URLs in your browser (replace `your-frappe-site.com`):

**OpenID Configuration:**
```
https://your-frappe-site.com/.well-known/openid-configuration
```

**Should show:**
- `registration_endpoint` (if dynamic registration enabled)
- `code_challenge_methods_supported: ["S256"]` (PKCE support)
- `jwks_uri`

**Authorization Server Metadata:**
```
https://your-frappe-site.com/.well-known/oauth-authorization-server
```

**Protected Resource Metadata:**
```
https://your-frappe-site.com/.well-known/oauth-protected-resource
```

---

## Troubleshooting

### Issue: "Dynamic client registration is not enabled"

**Solution:** Go to Assistant Core Settings → OAuth → Enable "Enable Dynamic Client Registration"

---

### Issue: "redirect_uris must be https"

**Causes:**
1. Using `http://` in production (not localhost)
2. Client sending non-localhost http:// redirect URI

**Solutions:**
- ✅ Use `https://` for production redirect URIs
- ✅ Use `http://localhost:` or `http://127.0.0.1:` for local development only
- ✅ Enable Frappe developer mode to allow http:// during testing

---

### Issue: "CORS error" when registering client

**Causes:**
1. Origin not in Allowed Public Client Origins
2. Client is browser-based but origin not whitelisted

**Solutions:**
- Add client origin to "Allowed Public Client Origins"
- OR use `*` for development (not production!)

**Example:**
```
http://localhost:6274
```

---

### Issue: "Failed to discover OAuth metadata"

**Causes:**
1. Wrong MCP endpoint URL
2. Server not accessible
3. Metadata endpoints disabled

**Solutions:**
- Verify URL format: `https://your-site.com/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp`
- Check "Show Authorization Server Metadata" is enabled
- Test discovery endpoint: `https://your-site.com/.well-known/openid-configuration`

---

### Issue: OAuth works locally but not via devtunnel/ngrok

**Cause:** MCP Inspector redirect URL transformation (localhost:6274 → devtunnel URL)

**Solution:**
This is a known limitation when:
- MCP Inspector runs on localhost:6274
- OAuth server runs on devtunnel/ngrok
- Browser redirects transform localhost → devtunnel host

**Workarounds:**
1. Test locally without devtunnel (recommended)
2. Run MCP Inspector through same devtunnel
3. Use confidential client (Claude Desktop) instead

---

## Security Best Practices

### 1. Allowed Public Client Origins

**Production:**
- ❌ Never use `*` in production
- ✅ Whitelist only trusted origins
- ✅ Use HTTPS origins only (except localhost)

**Development:**
- ✅ Use `*` or specific localhost URLs
- ✅ Use separate dev/prod configurations

---

### 2. Skip Authorization

**Never enable in production**
- This bypasses user consent
- Creates security risk
- Only for testing/development

---

### 3. Public vs Confidential Clients

**Public Clients** (browser-based):
- Cannot keep secrets
- Require CORS configuration
- Must use PKCE (automatic)
- Examples: MCP Inspector, web apps

**Confidential Clients** (backend):
- Can keep client_secret secure
- No CORS needed
- Examples: Claude Desktop, server apps

---

## Version Compatibility

This OAuth implementation works with:

✅ **Frappe v15** - Uses Assistant Core Settings (this configuration)
✅ **Frappe v16+** - Automatically uses native Frappe OAuth Settings

**Upgrade Path:**
When upgrading Frappe v15 → v16:
- Configuration automatically migrates to native OAuth Settings
- No manual changes needed
- All existing OAuth clients continue working

---

## Technical Details

### Supported RFCs

- ✅ RFC 6749 - OAuth 2.0 Authorization Framework
- ✅ RFC 7591 - Dynamic Client Registration
- ✅ RFC 7636 - PKCE (Proof Key for Code Exchange)
- ✅ RFC 8414 - Authorization Server Metadata
- ✅ RFC 9728 - Protected Resource Metadata

### Supported Grant Types

- ✅ Authorization Code (with PKCE)
- ✅ Refresh Token

### Supported Token Endpoint Auth Methods

- `client_secret_basic` - Client credentials in Authorization header
- `client_secret_post` - Client credentials in POST body
- `none` - Public clients (PKCE required)

---

## Further Help

### Documentation Links

- [MCP Inspector Documentation](https://github.com/modelcontextprotocol/inspector)
- [OAuth 2.0 RFC 6749](https://datatracker.ietf.org/doc/html/rfc6749)
- [Dynamic Client Registration RFC 7591](https://datatracker.ietf.org/doc/html/rfc7591)

---

## OAuth Flow for MCP Clients

This section explains how MCP clients (like Claude Desktop, MCP Inspector, or custom applications) interact with Frappe's OAuth system.

### Complete OAuth Flow Overview

```mermaid
sequenceDiagram
    participant Client as MCP Client<br/>(Claude Desktop, MCP Inspector, etc.)
    participant Discovery as /.well-known/openid-configuration
    participant Register as Dynamic Client Registration
    participant Auth as Authorization Endpoint
    participant Token as Token Endpoint
    participant MCP as MCP Endpoint

    Note over Client,MCP: Phase 1: Discovery
    Client->>Discovery: GET /.well-known/openid-configuration
    Discovery-->>Client: OAuth endpoints, PKCE support,<br/>registration endpoint, MCP endpoint URL

    Note over Client,MCP: Phase 2: Registration (Optional)
    Client->>Register: POST register_client<br/>(client_name, redirect_uris)
    Register-->>Client: client_id<br/>(+ client_secret for confidential clients)

    Note over Client,MCP: Phase 3: Authorization
    Client->>Auth: Redirect to /authorize<br/>with PKCE challenge (code_challenge)
    Note over Auth: User logs in and authorizes
    Auth-->>Client: Redirect with authorization code

    Note over Client,MCP: Phase 4: Token Exchange
    Client->>Token: POST get_token<br/>(code, code_verifier)
    Token-->>Client: access_token, refresh_token, expires_in

    Note over Client,MCP: Phase 5: API Access
    Client->>MCP: POST handle_mcp<br/>Authorization: Bearer {access_token}<br/>MCP request (tools/list, tools/call)
    MCP-->>Client: MCP response

    Note over Client,MCP: Phase 6: Token Refresh (when expired)
    Client->>Token: POST get_token<br/>(grant_type=refresh_token)
    Token-->>Client: new access_token, refresh_token
```

### Phase 1: Discovery

**What the client does:**
```http
GET /.well-known/openid-configuration HTTP/1.1
Host: your-frappe-site.com
```

**What Frappe returns:**
```json
{
  "issuer": "https://your-frappe-site.com",
  "authorization_endpoint": "https://your-frappe-site.com/api/method/frappe.integrations.oauth2.authorize",
  "token_endpoint": "https://your-frappe-site.com/api/method/frappe.integrations.oauth2.get_token",
  "registration_endpoint": "https://your-frappe-site.com/api/method/frappe_assistant_core.api.oauth_registration.register_client",
  "jwks_uri": "https://your-frappe-site.com/api/method/frappe_assistant_core.api.oauth_discovery.jwks",
  "response_types_supported": ["code"],
  "grant_types_supported": ["authorization_code", "refresh_token"],
  "code_challenge_methods_supported": ["S256"],
  "token_endpoint_auth_methods_supported": ["none", "client_secret_basic", "client_secret_post"],
  "mcp_endpoint": "https://your-frappe-site.com/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp",
  "mcp_protocol_version": "2025-03-26",
  "mcp_transport": "StreamableHTTP"
}
```

**Key information extracted:**
- `authorization_endpoint` - Where to send users for authorization
- `token_endpoint` - Where to exchange codes for tokens
- `registration_endpoint` - Where to register new clients (if enabled)
- `code_challenge_methods_supported` - PKCE is supported (S256)
- `mcp_endpoint` - The MCP server endpoint
- `token_endpoint_auth_methods_supported` - "none" means public clients supported

### Phase 2: Registration (Optional)

**When needed:** If the client doesn't have a pre-registered `client_id`

**What the client does:**
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

**What Frappe returns:**
```json
{
  "client_id": "a1b2c3d4e5f6g7h8",
  "client_name": "MCP Inspector",
  "redirect_uris": ["http://localhost:6274/callback"],
  "token_endpoint_auth_method": "none",
  "grant_types": ["authorization_code", "refresh_token"],
  "response_types": ["code"],
  "client_id_issued_at": 1704067200
}
```

**Client stores:** `client_id` for future use

### Phase 3: Authorization

**Step 1: Generate PKCE parameters**

```python
import secrets
import hashlib
import base64

# Generate 32 random bytes, base64url encode
code_verifier = base64.urlsafe_b64encode(
    secrets.token_bytes(32)
).decode('utf-8').rstrip('=')

# SHA256 hash of verifier, base64url encode
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode('utf-8')).digest()
).decode('utf-8').rstrip('=')
```

**Step 2: Redirect user to authorization endpoint**

```http
GET /api/method/frappe.integrations.oauth2.authorize?
    response_type=code&
    client_id=a1b2c3d4e5f6g7h8&
    redirect_uri=http://localhost:6274/callback&
    scope=all openid&
    code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&
    code_challenge_method=S256&
    state=random_state_value HTTP/1.1
Host: your-frappe-site.com
```

**Step 3: User authorizes**

User sees Frappe login screen (if not logged in), then authorization screen showing:
- Client name: "MCP Inspector"
- Requested permissions: "all", "openid"
- Approve/Deny buttons

**Step 4: Frappe redirects back**

```http
HTTP/1.1 302 Found
Location: http://localhost:6274/callback?
    code=AUTH_CODE_123456789&
    state=random_state_value
```

**Client receives:** Authorization code and validates state matches

### Phase 4: Token Exchange

**What the client does:**
```http
POST /api/method/frappe.integrations.oauth2.get_token HTTP/1.1
Host: your-frappe-site.com
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&
code=AUTH_CODE_123456789&
redirect_uri=http://localhost:6274/callback&
code_verifier=ORIGINAL_CODE_VERIFIER_FROM_STEP_1&
client_id=a1b2c3d4e5f6g7h8
```

**What Frappe does:**
1. Validates authorization code hasn't been used
2. Validates redirect_uri matches original request
3. Validates code_verifier SHA256 hash matches stored code_challenge
4. Validates client_id matches authorization request
5. Creates OAuth Bearer Token in database

**What Frappe returns:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "def502001234567890abcdef...",
  "scope": "all openid"
}
```

**Client stores:**
- `access_token` - For MCP API requests
- `refresh_token` - For getting new access_token when expired
- `expires_in` - When to refresh (3600 seconds = 1 hour)

### Phase 5: MCP API Access

**What the client does:**
```http
POST /api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp HTTP/1.1
Host: your-frappe-site.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "method": "tools/list",
  "params": {},
  "id": 1
}
```

**What Frappe does:**
1. Extracts Bearer token from Authorization header
2. Queries OAuth Bearer Token doctype for token
3. Validates token status is "Active"
4. Validates token hasn't expired
5. Sets user session to token owner
6. Checks user has `assistant_enabled = 1`
7. Processes MCP request
8. Returns MCP response

**What Frappe returns:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "tools": [
      {
        "name": "list_documents",
        "description": "List documents from a DocType",
        "inputSchema": {...}
      }
    ]
  },
  "id": 1
}
```

**If token expired:**
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

### Phase 6: Token Refresh

**When:** Client receives 401 with "Token has expired" error

**What the client does:**
```http
POST /api/method/frappe.integrations.oauth2.get_token HTTP/1.1
Host: your-frappe-site.com
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token&
refresh_token=def502001234567890abcdef...&
client_id=a1b2c3d4e5f6g7h8
```

**What Frappe does:**
1. Validates refresh_token exists and is active
2. Validates client_id matches
3. Creates new OAuth Bearer Token
4. May rotate refresh_token (returns new one)

**What Frappe returns:**
```json
{
  "access_token": "NEW_ACCESS_TOKEN_xyz...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "NEW_REFRESH_TOKEN_or_SAME...",
  "scope": "all openid"
}
```

**Client updates stored tokens and retries original request**

---

## Security Considerations in OAuth Flow

### PKCE (Proof Key for Code Exchange)

**Why required:**
Prevents authorization code interception attacks.

**How it works:**
1. Client generates random `code_verifier` (43-128 characters)
2. Client calculates `code_challenge` = BASE64URL(SHA256(code_verifier))
3. Client sends `code_challenge` with authorization request
4. Frappe stores `code_challenge` with authorization code
5. Client sends `code_verifier` with token exchange
6. Frappe validates SHA256(code_verifier) matches stored code_challenge
7. If match, token issued; if not, rejected

**Result:** Even if authorization code is intercepted, attacker can't exchange it without the original code_verifier.

### State Parameter

**Purpose:** Prevents CSRF attacks

**How to use:**
1. Client generates random state value
2. Stores state in session/memory
3. Includes state in authorization request
4. Validates state in callback matches stored value
5. Rejects if state doesn't match

### Token Security

**Access Token:**
- Short lifetime (default 1 hour)
- Transmitted in Authorization header (not URL)
- Validated on every MCP request
- Automatically expires

**Refresh Token:**
- Longer lifetime (default 30 days)
- Only used for token endpoint
- Can be revoked by user
- May rotate on refresh

### Public vs Confidential Clients

**Public Clients** (e.g., MCP Inspector, browser apps):
- Cannot securely store client_secret
- Use `token_endpoint_auth_method: "none"`
- **Must** use PKCE for security
- Require CORS configuration

**Confidential Clients** (e.g., server applications):
- Can securely store client_secret
- Use `client_secret_basic` or `client_secret_post` auth
- PKCE optional but recommended
- No CORS needed

---

### Support

- GitHub Issues: https://github.com/buildswithpaul/Frappe_Assistant_Core/issues
- Frappe Forum: https://discuss.frappe.io/

---

## Changelog

### v2.2.0
- Migrated from STDIO to StreamableHTTP transport with OAuth 2.0
- Added OAuth 2.0 Dynamic Client Registration (RFC 7591)
- Added Authorization Server Metadata (RFC 8414)
- Added Protected Resource Metadata (RFC 9728)
- Added PKCE support (RFC 7636)
- Added CORS handling for public clients
- Simplified configuration in Assistant Core Settings
- Automatic Frappe v15/v16 compatibility
- Added comprehensive OAuth flow documentation for MCP clients
- Converted documentation diagrams to Mermaid format
