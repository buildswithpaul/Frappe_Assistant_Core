# Migration Guide: STDIO Bridge to StreamableHTTP with OAuth

## Overview

Frappe Assistant Core v2.0+ uses **OAuth-authenticated StreamableHTTP** instead of the STDIO bridge for better security, standardization, and compatibility with modern MCP clients.

This guide will help you migrate your existing setup to the new OAuth-based architecture.

## Why Migrate?

### Benefits of StreamableHTTP + OAuth

| Feature | STDIO Bridge (Old) | StreamableHTTP + OAuth (New) |
|---------|-------------------|------------------------------|
| **Security** | API Key in environment variables | Industry-standard OAuth 2.0 |
| **Token Management** | Static API keys | Automatic token refresh |
| **Client Support** | Limited (subprocess-capable only) | Universal (any HTTP client) |
| **Web Compatibility** | ❌ No | ✅ Yes (browser-based clients) |
| **Discovery** | Manual configuration | Auto-discovery via .well-known |
| **Standards Compliance** | Custom | RFC 6749, 7591, 8414, 9728 |
| **Process Management** | Subprocess spawning | Standard HTTP requests |
| **Debugging** | Limited subprocess logs | Full HTTP request/response logs |

### What's Changed

**Architecture:**
- ❌ Old: `frappe_assistant_stdio_bridge.py` subprocess
- ✅ New: HTTP endpoint `/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp`

**Authentication:**
- ❌ Old: `FRAPPE_API_KEY` and `FRAPPE_API_SECRET` environment variables
- ✅ New: OAuth 2.0 Bearer tokens with automatic refresh

**Protocol:**
- ❌ Old: STDIO pipes (stdin/stdout)
- ✅ New: StreamableHTTP (HTTP POST requests)

**Discovery:**
- ❌ Old: Manual endpoint configuration
- ✅ New: Auto-discovery via `/.well-known/openid-configuration`

## Migration Steps

### Step 1: Update Frappe Assistant Core

Ensure you're running v2.0 or later:

```bash
cd /path/to/frappe-bench

# Update the app
bench get-app --branch main https://github.com/buildswithpaul/Frappe_Assistant_Core

# Or if already installed, pull latest
cd apps/frappe_assistant_core
git pull origin main
cd ../..

# Migrate
bench --site your-site migrate

# Restart
bench restart
```

### Step 2: Enable OAuth Features

1. **Login to Frappe** as Administrator
2. **Go to**: Desk → Setup → Integrations → Assistant Core Settings
3. **OAuth tab:**
   - ✅ Enable "Show Authorization Server Metadata"
   - ✅ Enable "Enable Dynamic Client Registration"
   - ✅ Enable "Show Protected Resource Metadata"
4. **Save**

### Step 3: Update Client Configuration

Choose your migration path based on your client:

---

## Migration for Claude Desktop Users

### Old Configuration (STDIO Bridge)

**File:** `claude_desktop_config.json`

```json
{
  "mcpServers": {
    "frappe-assistant": {
      "command": "python",
      "args": ["/path/to/frappe_assistant_stdio_bridge.py"],
      "env": {
        "FRAPPE_SITE": "your-site.localhost",
        "FRAPPE_API_KEY": "your-api-key",
        "FRAPPE_API_SECRET": "your-api-secret"
      }
    }
  }
}
```

### New Configuration (StreamableHTTP + OAuth)

**File:** `claude_desktop_config.json`

```json
{
  "mcpServers": {
    "frappe-assistant": {
      "url": "https://your-site.com/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp",
      "transport": "streamablehttp",
      "oauth": {
        "discoveryUrl": "https://your-site.com/.well-known/openid-configuration",
        "clientName": "Claude Desktop"
      }
    }
  }
}
```

**What Happens:**
1. Claude Desktop will fetch OAuth configuration from `discoveryUrl`
2. Automatically register as an OAuth client (if dynamic registration enabled)
3. Open browser for user authorization
4. Store and manage access/refresh tokens automatically
5. Refresh tokens when they expire

### Testing the New Configuration

1. **Restart Claude Desktop**
2. **Start a new conversation**
3. **When prompted**, authorize Claude Desktop in your browser
4. **Test:** Type "List my customers"

If successful, you'll see data from your Frappe system!

---

## Migration for Custom Clients

### Old STDIO Bridge Client

```python
import subprocess
import json

# Old: Launch subprocess
process = subprocess.Popen(
    ["python", "frappe_assistant_stdio_bridge.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    env={
        "FRAPPE_SITE": "your-site.localhost",
        "FRAPPE_API_KEY": "api_key",
        "FRAPPE_API_SECRET": "api_secret"
    }
)

# Send request
request = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}
process.stdin.write(json.dumps(request).encode() + b"\n")
process.stdin.flush()

# Read response
response = json.loads(process.stdout.readline())
```

### New OAuth Client

```python
import requests
from urllib.parse import urlencode
import secrets
import hashlib
import base64

class FrappeAssistantOAuthClient:
    def __init__(self, site_url):
        self.site_url = site_url
        self.access_token = None
        self.refresh_token = None
        self.client_id = None

        # Discover OAuth configuration
        discovery_url = f"{site_url}/.well-known/openid-configuration"
        self.config = requests.get(discovery_url).json()

    def register_client(self, client_name="My MCP Client"):
        """Register OAuth client via dynamic client registration"""
        registration_data = {
            "client_name": client_name,
            "redirect_uris": ["http://localhost:8080/callback"],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"]
        }

        response = requests.post(
            self.config["registration_endpoint"],
            json=registration_data
        )
        client_info = response.json()
        self.client_id = client_info["client_id"]
        return client_info

    def authorize(self):
        """Perform OAuth authorization code flow with PKCE"""
        # Generate PKCE parameters
        code_verifier = base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).decode('utf-8').rstrip('=')

        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')

        # Build authorization URL
        auth_params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": "http://localhost:8080/callback",
            "scope": "all openid",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": secrets.token_urlsafe(16)
        }

        auth_url = f"{self.config['authorization_endpoint']}?{urlencode(auth_params)}"
        print(f"Visit: {auth_url}")

        # Get authorization code (from redirect - implement callback server)
        authorization_code = input("Enter authorization code: ")

        # Exchange code for tokens
        token_data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": "http://localhost:8080/callback",
            "code_verifier": code_verifier,
            "client_id": self.client_id
        }

        token_response = requests.post(
            self.config["token_endpoint"],
            data=token_data
        ).json()

        self.access_token = token_response["access_token"]
        self.refresh_token = token_response.get("refresh_token")

    def call_mcp(self, method, params=None):
        """Make MCP request with Bearer token authentication"""
        if not self.access_token:
            raise Exception("Not authenticated. Call authorize() first.")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": 1
        }

        response = requests.post(
            self.config["mcp_endpoint"],
            headers=headers,
            json=request
        )

        return response.json()

    def refresh_access_token(self):
        """Refresh expired access token"""
        if not self.refresh_token:
            raise Exception("No refresh token available")

        token_data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id
        }

        token_response = requests.post(
            self.config["token_endpoint"],
            data=token_data
        ).json()

        self.access_token = token_response["access_token"]
        self.refresh_token = token_response.get("refresh_token", self.refresh_token)


# Usage
client = FrappeAssistantOAuthClient("https://your-site.com")
client.register_client("My MCP Client")
client.authorize()

# Make requests
tools = client.call_mcp("tools/list")
print(tools)

result = client.call_mcp("tools/call", {
    "name": "list_documents",
    "arguments": {"doctype": "Customer", "limit": 5}
})
print(result)
```

---

## Troubleshooting Migration

### Issue: "OAuth discovery failed"

**Cause:** OAuth discovery endpoints not accessible

**Solutions:**
1. Verify `frappe_assistant_core` is installed and migrated
2. Check Assistant Core Settings → OAuth tab settings are enabled
3. Test endpoint: `curl https://your-site.com/.well-known/openid-configuration`
4. Check Frappe error logs: `bench --site your-site logs`

### Issue: "Dynamic client registration disabled"

**Cause:** Dynamic registration not enabled in settings

**Solutions:**
1. Go to Assistant Core Settings → OAuth tab
2. ✅ Enable "Enable Dynamic Client Registration"
3. Save and try again

**Alternative:** Manually create OAuth Client in Frappe:
1. Go to Desk → Setup → Integrations → OAuth Client
2. Create new OAuth Client
3. Set redirect URIs, grant types, etc.
4. Use `client_id` (and `client_secret` for confidential clients) in your configuration

### Issue: "401 Unauthorized" during MCP requests

**Cause:** Token expired or invalid

**Solutions:**
1. Check token hasn't expired (default: 1 hour lifetime)
2. Use refresh_token to get new access_token
3. Re-authenticate if refresh fails
4. Verify Bearer token is correctly included in Authorization header

### Issue: "CORS error" (browser-based clients)

**Cause:** Origin not whitelisted for public clients

**Solutions:**
1. Go to Assistant Core Settings → OAuth tab
2. Add your origin to "Allowed Public Client Origins"
   - Example: `http://localhost:6274` for MCP Inspector
3. Or use `*` for development (not recommended for production)
4. Save and try again

### Issue: "redirect_uris must use https"

**Cause:** Non-HTTPS redirect URI for non-localhost

**Solutions:**
1. Use HTTPS for production redirect URIs
2. Localhost/127.0.0.1 with HTTP is allowed for development
3. Enable Frappe developer mode for testing with HTTP:
   ```bash
   bench --site your-site set-config developer_mode 1
   ```

---

## Backwards Compatibility

### Can I still use the STDIO bridge?

**Yes**, for backwards compatibility, but it's **deprecated**:

1. The old STDIO bridge still works in v2.0
2. Uses the same API as before (no breaking changes)
3. **However:**
   - ⚠️ Will be removed in a future major version
   - ⚠️ Not receiving new features or improvements
   - ⚠️ Security updates will focus on OAuth path

**Recommendation:** Migrate to OAuth as soon as possible.

### Running Both Simultaneously

You can run both STDIO and OAuth simultaneously during migration:

```json
{
  "mcpServers": {
    "frappe-stdio-legacy": {
      "command": "python",
      "args": ["/path/to/frappe_assistant_stdio_bridge.py"],
      "env": {...}
    },
    "frappe-oauth-new": {
      "url": "https://your-site.com/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp",
      "transport": "streamablehttp",
      "oauth": {...}
    }
  }
}
```

Test the OAuth version thoroughly before removing the STDIO configuration.

---

## Rollback Plan

If you need to rollback temporarily:

### Step 1: Revert Client Configuration

Change your client config back to STDIO bridge format.

### Step 2: Keep Old API Keys

Don't delete your old API keys until OAuth migration is complete and tested.

### Step 3: Report Issues

If you encounter issues:
1. Report on GitHub: https://github.com/buildswithpaul/Frappe_Assistant_Core/issues
2. Include error messages and logs
3. Mention you're migrating from STDIO to OAuth

---

## Post-Migration Checklist

After successful migration:

- [ ] OAuth authentication working
- [ ] Can list tools via MCP
- [ ] Can execute tools successfully
- [ ] Token refresh working automatically
- [ ] Tested with your typical workflows
- [ ] Removed old STDIO bridge configuration
- [ ] (Optional) Revoked old API keys for security

---

## Additional Resources

- [MCP StreamableHTTP Guide](../architecture/MCP_STREAMABLEHTTP_GUIDE.md) - Complete OAuth and StreamableHTTP documentation
- [OAuth Setup Guide](oauth/oauth_setup_guide.md) - Detailed OAuth configuration
- [API Reference](../api/API_REFERENCE.md) - Updated API documentation
- [Architecture](../architecture/ARCHITECTURE.md) - New architecture overview

---

## Getting Help

**Community Support:**
- GitHub Issues: https://github.com/buildswithpaul/Frappe_Assistant_Core/issues
- GitHub Discussions: https://github.com/buildswithpaul/Frappe_Assistant_Core/discussions

**Professional Support:**
- Email: jypaulclinton@gmail.com
- Custom migration assistance available

---

**Migration Version:** 1.x → 2.0+
**Last Updated:** January 2025
**Status:** Recommended for all users
