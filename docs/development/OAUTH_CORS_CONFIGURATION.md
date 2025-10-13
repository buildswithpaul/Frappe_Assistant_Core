# OAuth CORS Configuration

## Do I Need CORS?

**Short Answer: NO** (for most production deployments)

### Production Deployment (Claude Desktop / Claude Web)
- ✅ **NO CORS needed**
- Uses server-to-server OAuth
- No browser security restrictions
- No configuration required

### Development/Testing (MCP Inspector)
- ⚠️ **CORS required**
- Browser-based OAuth client
- Runs in web browser at `http://localhost:6274`
- Needs CORS to make cross-origin requests

---

## Configuration Methods

### Method 1: site_config.json (RECOMMENDED)

Edit your site's `site_config.json`:

```json
{
  "oauth_cors_allowed_origins": "*"
}
```

Or for specific origins:

```json
{
  "oauth_cors_allowed_origins": ["http://localhost:6274", "http://localhost:3000"]
}
```

**Location:** `sites/[your-site]/site_config.json`

**Advantages:**
- ✅ Simple configuration
- ✅ Standard Frappe approach
- ✅ Version controlled
- ✅ No UI needed

**Restart Required:** No - changes apply immediately

---

### Method 2: Assistant Core Settings (EXPERIMENTAL)

**⚠️ This method is experimental and may change in future versions.**

1. Go to **Assistant Core Settings**
2. Enable **Dynamic Client Registration**
3. Scroll to **Allowed Public Client Origins**
4. Enter origins (one per line):
   ```
   *
   ```
   Or specific origins:
   ```
   http://localhost:6274
   http://localhost:3000
   ```

**Disadvantages:**
- ⚠️ Experimental - may change
- ⚠️ Not version controlled
- ⚠️ Requires UI access

---

## Common Scenarios

### Scenario 1: Production (Claude Desktop/Web)
**Configuration:** None needed

Leave both `site_config.json` and Assistant Core Settings empty.

```bash
# No CORS configuration needed!
```

### Scenario 2: Development with MCP Inspector
**Configuration:** Add to `site_config.json`:

```json
{
  "oauth_cors_allowed_origins": "*"
}
```

Then access MCP Inspector at: http://localhost:6274

### Scenario 3: Specific Origins Only
**Configuration:** Add to `site_config.json`:

```json
{
  "oauth_cors_allowed_origins": [
    "http://localhost:6274",
    "https://your-dev-domain.com"
  ]
}
```

---

## Security Considerations

### Using `"*"` (Wildcard)
- ⚠️ **Development Only** - Allows all origins
- ❌ **NOT for Production** - Security risk
- ✅ **Safe for localhost** testing

### Specific Origins
- ✅ **Production Safe** - Whitelist specific domains
- ✅ **Better Security** - Only trusted origins
- ✅ **Recommended** for public deployments

### No CORS (Empty)
- ✅ **Most Secure** - No browser clients allowed
- ✅ **Production Default** - Only server-to-server OAuth
- ✅ **Recommended** for production

---

## Technical Details

### How CORS Works

When a browser-based client (like MCP Inspector) makes an OAuth request:

1. Browser sends OPTIONS preflight request
2. Server checks if origin is allowed
3. Server responds with CORS headers
4. Browser allows the actual request

Without CORS configuration:
- OPTIONS request returns no CORS headers
- Browser blocks the request
- OAuth flow fails

### Implementation Notes

The CORS handler (`oauth_cors.py`) checks configuration in this order:

1. **`frappe.conf.oauth_cors_allowed_origins`** (site_config.json)
2. **Assistant Core Settings** > allowed_public_client_origins

If neither is set, CORS is disabled (production default).

### Affected Endpoints

CORS is enabled for these OAuth endpoints:

- `/.well-known/openid-configuration`
- `/.well-known/oauth-authorization-server`
- `/.well-known/oauth-protected-resource`
- `/api/method/frappe.integrations.oauth2.*`
- `/api/method/frappe_assistant_core.api.oauth_registration.register_client`
- `/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp`

---

## Troubleshooting

### CORS Error in Browser Console
```
Access to fetch at 'https://your-site.com/.well-known/...' has been blocked by CORS policy
```

**Solution:** Add CORS configuration to `site_config.json`

### MCP Inspector Not Connecting
**Check:**
1. Is `oauth_cors_allowed_origins` set in `site_config.json`?
2. Does the origin match exactly? (include protocol and port)
3. Restart bench if needed: `bench restart`

### Claude Desktop Not Working
**Note:** Claude Desktop does NOT need CORS. If it's not working, the issue is NOT CORS-related.

Check:
- OAuth Bearer Token exists in database
- Token status is "Active"
- Token has not expired
- Check Error Log in Frappe

---

## Examples

### Example 1: Local Development
```json
{
  "oauth_cors_allowed_origins": "*",
  "developer_mode": 1
}
```

### Example 2: Staging Server
```json
{
  "oauth_cors_allowed_origins": [
    "https://mcp-inspector.your-company.com",
    "http://localhost:6274"
  ]
}
```

### Example 3: Production Server
```json
{
  // No oauth_cors_allowed_origins - CORS disabled
  "developer_mode": 0
}
```

---

## FAQ

**Q: Do I need CORS for Claude Desktop?**
A: No. Claude Desktop uses server-to-server OAuth.

**Q: Do I need CORS for Claude Web (claude.ai)?**
A: No. Claude Web also uses server-to-server OAuth.

**Q: When do I need CORS?**
A: Only for browser-based OAuth clients like MCP Inspector during development.

**Q: Is it safe to use `"*"` in production?**
A: No. Only use `"*"` for local development. Use specific origins in production.

**Q: Can I use both site_config.json and Assistant Core Settings?**
A: Yes, but site_config.json takes precedence.

**Q: Do I need to restart after changing site_config.json?**
A: No. CORS changes apply immediately.

---

## References

- [RFC 6749 - OAuth 2.0](https://tools.ietf.org/html/rfc6749)
- [RFC 6750 - Bearer Token Usage](https://tools.ietf.org/html/rfc6750)
- [RFC 8414 - Authorization Server Metadata](https://tools.ietf.org/html/rfc8414)
- [MDN - CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
- [MCP Specification](https://spec.modelcontextprotocol.io/)
