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

### Support

- GitHub Issues: https://github.com/buildswithpaul/Frappe_Assistant_Core/issues
- Frappe Forum: https://discuss.frappe.io/

---

## Changelog

### v2.0.0
- Added OAuth 2.0 Dynamic Client Registration (RFC 7591)
- Added Authorization Server Metadata (RFC 8414)
- Added Protected Resource Metadata (RFC 9728)
- Added PKCE support (RFC 7636)
- Added CORS handling for public clients
- Simplified configuration in Assistant Core Settings
- Automatic Frappe v15/v16 compatibility
