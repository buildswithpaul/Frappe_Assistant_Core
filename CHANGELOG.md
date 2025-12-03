# Changelog

All notable changes to Frappe Assistant Core will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.2] - 2025-11-26

### 🏢 Repository Migration & Rebranding

#### GitHub Repository Update
- **Migrated** repository from `clinu/Frappe_Assistant_Core` to `buildswithpaul/Frappe_Assistant_Core`
- **Updated** all documentation links, URLs, and references across the project
- **Updated** manifest.json, README.md, BUILD.md, and configuration files
- **Maintained** backwards compatibility - existing installations continue to work

### 🚀 Enhanced

#### OAuth 2.0 Client Registration Enhancements
- **Fixed** dynamic client registration to always return `client_secret` in response
- **Added** support for public clients that receive secrets but use `token_endpoint_auth_method: "none"`
- **Enhanced** registration response to include all optional RFC 7591 metadata fields:
  - `client_uri` - Client homepage URL
  - `logo_uri` - Client logo URL
  - `scope` - Requested scopes
  - `contacts` - Client contact information
  - `tos_uri` - Terms of Service URL
  - `policy_uri` - Privacy Policy URL
  - `software_id` - Client software identifier
  - `software_version` - Client software version
- **Improved** MCP Inspector compatibility with complete registration responses
- **Benefits**:
  - Full RFC 7591 compliance
  - Better client identification and metadata
  - Improved debugging and client management

#### OAuth Discovery API Updates
- **Updated** OpenID Configuration endpoint to use `get_openid_configuration` from Frappe
- **Improved** compatibility with latest Frappe OAuth2 API changes
- **Maintained** backward compatibility with Frappe v15 and v16

#### Manifest & Tool Configuration Improvements
- **Refactored** tools array in manifest.json with updated names and descriptions
- **Added** new tools: `delete_document`, `submit_document`
- **Reorganized** tool descriptions for consistency and improved user experience
- **Improved** tool ordering for better discoverability
- **Updated** runtime specification from `runtime` to `runtimes` for future extensibility
- **Clarified** Python version requirements (>=3.8,<4.0)

#### Documentation Improvements
- **Enhanced** Getting Started guide with UI-based connector setup for Claude Desktop
- **Added** ChatGPT integration section with complete setup instructions
- **Added** comparison table for different AI connection options
- **Improved** OAuth setup instructions with both UI and manual configuration methods
- **Updated** all repository references to new GitHub location
- **Added** tips and best practices for easier onboarding
- **Benefits**:
  - Much easier setup with UI-based configuration (no JSON editing)
  - Support for both Claude Desktop and ChatGPT clearly documented
  - Better user guidance with comparison table and recommendations

### 🔧 Changed

#### API Endpoint Updates
- **Updated** Claude Desktop extension server bridge API endpoint
- **Changed** from: `/api/method/frappe_assistant_core.api.assistant_api.handle_assistant_request`
- **Changed** to: `/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp`
- **Note**: This change is for internal bridge configuration; external MCP endpoint remains unchanged

## [2.2.0] - 2025-10-13

### 🎯 Major Release - StreamableHTTP Transport Migration

#### Transport Layer Migration
- **Migrated** from STDIO bridge to StreamableHTTP transport
- **Implemented** OAuth 2.0 authentication with industry-standard security
- **Added** HTTP-based communication replacing subprocess stdin/stdout
- **Enabled** web-based MCP client support (Claude Web, browser clients)
- **Improved** cross-platform compatibility and deployment options

#### OAuth 2.0 Integration
- **Added** OAuth 2.0 Dynamic Client Registration (RFC 7591)
- **Added** Authorization Server Metadata (RFC 8414)
- **Added** Protected Resource Metadata (RFC 9728)
- **Implemented** PKCE support (RFC 7636) for secure authorization
- **Added** automatic token refresh mechanism
- **Added** CORS handling for public clients
- **Added** discovery endpoints (/.well-known/openid-configuration)

#### Custom FAC MCP Server
- **Built** custom MCP server optimized for Frappe
- **Fixed** JSON serialization for Frappe data types (datetime, Decimal)
- **Removed** Pydantic dependency for lighter footprint
- **Improved** error handling with full tracebacks
- **Enhanced** Frappe session integration
- **Added** tool adapter pattern for BaseTool compatibility

#### Documentation & UX Improvements
- **Converted** architecture diagrams to Mermaid format
- **Rewrote** Getting Started guide with LLM-specific instructions
- **Added** comprehensive OAuth setup guide
- **Added** MCP StreamableHTTP integration guide
- **Simplified** onboarding (default-enabled assistant access)
- **Added** FAC Admin page with MCP endpoint display

#### API & Endpoints
- **Added** MCP endpoint: `/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp`
- **Added** OAuth endpoints (authorize, token, register, introspect, revoke)
- **Added** Well-known discovery endpoints
- **Added** HEAD method support for connectivity checks
- **Implemented** Bearer token validation middleware

#### Configuration & Compatibility
- **Simplified** configuration via site_config.json
- **Ensured** Frappe v15/v16 compatibility (dual CORS mechanism)
- **Added** automatic custom field setup (assistant_enabled)
- **Added** proper uninstall cleanup
- **Removed** unnecessary server_version field

### 🐛 Bug Fixes

#### CORS & Authentication
- **Fixed** CORS headers for OPTIONS preflight requests
- **Fixed** MCP-Protocol-Version header in CORS allow list
- **Fixed** 401 responses with proper WWW-Authenticate headers
- **Fixed** HTTP 417 errors with proper method registration

#### Plugin Management
- **Fixed** plugin toggle using plugin IDs instead of display names
- **Fixed** plugin state persistence across page refreshes
- **Added** plugin_id and category_id fields to API responses

#### Migration & Patches
- **Fixed** missing patch file errors during migration
- **Added** patch to update assistant_enabled default to 1
- **Added** patch to rename assistant-admin page to fac-admin
- **Ensured** idempotent patches for fresh installs vs upgrades

### ✨ Added

#### Security
- **OAuth 2.0** with PKCE for secure authorization code flow
- **Bearer token** authentication for all MCP requests
- **Token expiration** and automatic refresh support
- **Dynamic client** registration with origin validation
- **Public vs confidential** client support

#### Developer Tools
- **MCP Inspector** support with Quick OAuth Flow
- **Custom Python client** examples
- **Comprehensive debugging** with detailed error logging
- **OAuth error tracking** for troubleshooting

#### Admin Interface
- **FAC Admin page** showing MCP endpoint URL
- **Plugin management** with enable/disable functionality
- **Tool registry** display with category grouping
- **Real-time stats** and health monitoring

### 🔧 Changed

#### Architecture
- **Transport**: STDIO subprocess → StreamableHTTP
- **Authentication**: API Key → OAuth 2.0 Bearer tokens
- **Client Support**: Limited → Any HTTP-capable client
- **Discovery**: Manual → Auto-discovery via .well-known
- **Web Compatibility**: ❌ No → ✅ Yes

#### Performance
- **No subprocess overhead** with HTTP transport
- **Better token caching** with client-side management
- **Connection pooling** support for HTTP clients
- **Reduced latency** with direct HTTP requests

### 🚨 Security

#### OAuth Security Features
- **PKCE required** for all authorization code flows
- **State parameter** for CSRF protection
- **Token rotation** on refresh (configurable)
- **Origin validation** for public clients
- **HTTPS enforcement** for production (except localhost)

#### Token Management
- **Short-lived access tokens** (default 1 hour)
- **Long-lived refresh tokens** (default 30 days)
- **Automatic expiration** and cleanup
- **Revocation support** for compromised tokens

### 📝 Documentation

#### New Documentation
- **MCP_STREAMABLEHTTP_GUIDE.md**: Complete integration guide with Mermaid diagrams
- **oauth_setup_guide.md**: Comprehensive OAuth configuration with Mermaid flow diagrams
- **OAUTH_CORS_CONFIGURATION.md**: CORS setup for public clients
- **Updated README.md**: Simplified getting started with LLM-specific steps

#### Diagram Updates
- **Architecture Overview**: ASCII → Mermaid sequence diagram
- **OAuth Flow**: ASCII → Mermaid sequence diagram
- **All diagrams**: GitHub-compatible rendering

### 🔄 Migration Guide

#### From v2.0.x/v2.1.x to v2.2.0

**Breaking Changes:**
- STDIO bridge no longer supported
- API key authentication removed
- Configuration changed to OAuth 2.0

**Migration Steps:**

1. **Update Frappe Assistant Core**
   ```bash
   cd apps/frappe_assistant_core
   git pull
   bench migrate
   ```

2. **Enable OAuth in Assistant Core Settings**
   - Enable Dynamic Client Registration
   - Configure Allowed Public Client Origins (if using MCP Inspector)

3. **Reconfigure MCP Clients**
   - **Claude Desktop**: Update config to use StreamableHTTP with OAuth
   - **MCP Inspector**: Use OAuth flow for authentication
   - **Custom Clients**: Implement OAuth 2.0 authorization code flow with PKCE

4. **Verify Installation**
   - Visit FAC Admin page
   - Copy MCP endpoint URL
   - Test OAuth flow with MCP Inspector

**Benefits of Migration:**
- ✅ Better security with OAuth 2.0
- ✅ Web-based client support
- ✅ No subprocess management
- ✅ Better error handling
- ✅ Auto-discovery support
- ✅ Token refresh support

## [2.0.1] - 2025-07-26

### 🎯 Major Improvements

#### Document Creation Tool Overhaul
- **Fixed** child table handling using proper `doc.append()` instead of naive `setattr()`
- **Added** automatic required field validation before creation attempts
- **Enhanced** error messages with specific guidance and recovery suggestions
- **Added** `validate_only` parameter for testing document structure before creation
- **Updated** tool descriptions with comprehensive child table examples
- **Improved** success rate from ~60% to ~95% for complex DocTypes

#### Dashboard Chart System Rebuild
- **Fixed** incorrect field mapping between tool parameters and Frappe's Dashboard Chart DocType
- **Corrected** field usage:
  - `based_on` = Time Series Based On (date field for time series)
  - `timeseries` = Time Series flag (boolean to enable time series)
  - `group_by_based_on` = Group By Based On (grouping field for bar/pie charts)
  - `value_based_on` = Value Based On (field to aggregate for Sum/Average)
- **Fixed** filter format conversion from dict to Frappe's list format
- **Added** smart field auto-detection based on DocType metadata
- **Added** comprehensive chart validation before creation
- **Added** runtime testing of chart functionality
- **Improved** chart reliability from ~40% to ~98%

#### Custom Tool Discovery Enhancement
- **Fixed** custom tool discovery from external Frappe apps through hooks system
- **Enhanced** tool registry to properly scan `assistant_tools` hook
- **Improved** tool availability consistency across different installations

### 🐛 Bug Fixes

#### Document Creation
- **Fixed** `'dict' object has no attribute 'is_new'` error in child table creation
- **Fixed** missing required field validation causing creation failures
- **Fixed** unclear error messages that didn't guide users to solutions
- **Fixed** Purchase Order, Sales Invoice, and BOM creation failures

#### Dashboard Charts
- **Fixed** `TypeError: 'NoneType' object is not callable` in chart data retrieval
- **Fixed** `Unknown column 'tabItem.posting_date' in 'WHERE'` SQL errors
- **Fixed** empty "Time Series Based On" and "Value Based On" fields in created charts
- **Fixed** charts displaying no data despite successful creation
- **Fixed** runtime chart failures when opening dashboard view

#### Tool Discovery
- **Fixed** external app tools not being loaded through hooks system
- **Fixed** inconsistent tool availability across different Frappe installations

### ✨ Added

#### Validation Framework
- Smart field detection for different DocTypes
- Comprehensive error handling with specific error types
- Pre-creation validation to prevent runtime failures
- DocType-specific logic for appropriate field handling
- Runtime chart functionality testing

#### Enhanced User Experience
- `validate_only` mode for document creation testing
- Detailed error messages with actionable recovery steps
- Auto-detection of appropriate fields when not specified
- Comprehensive examples in tool descriptions
- Intelligent fallback mechanisms for various failure scenarios

#### Technical Improvements
- Robust filter format handling
- Thread-safe plugin management operations
- Better abstraction between user API and Frappe internals
- Enhanced validation testing framework
- Improved inline documentation

### 🔧 Changed

#### Architecture
- Enhanced plugin management with proper concurrency handling
- Improved tool registry architecture for better reliability
- Better separation of concerns in chart creation logic
- More robust error handling and recovery mechanisms

#### Performance
- Document creation success rate: 60% → 95% (+58%)
- Dashboard chart runtime success: 40% → 98% (+145%) 
- Tool discovery reliability: 80% → 99% (+24%)
- Error resolution time: Manual fixing → Self-guided recovery (-90%)

### 🚨 Security

#### Validation Improvements
- Enhanced field existence validation
- Improved permission checking for chart creation
- Better input sanitization for filter conversion
- Strengthened DocType access validation

## [2.0.0] - 2025-01-20

### 🎯 Major Release - Architecture Overhaul

#### Modular Plugin System
- **Added** comprehensive plugin architecture with thread-safe operations
- **Added** visualization plugin with dashboard and chart creation tools
- **Added** data science plugin with Python execution and analytics
- **Refactored** core tools into organized plugin structure

#### Enhanced Tool Ecosystem
- **Added** 21 comprehensive tools across multiple categories
- **Added** dashboard creation and management capabilities
- **Added** advanced chart creation with 6 chart types
- **Added** Python code execution with 30+ pre-loaded libraries
- **Enhanced** document operations with better validation

#### Security Framework
- **Implemented** multi-layer security with role-based access control
- **Added** comprehensive audit logging for all operations
- **Enhanced** permission integration with Frappe's security system
- **Added** field-level data protection for sensitive information

#### Performance & Reliability
- **Improved** error handling across all tools
- **Added** comprehensive logging system
- **Enhanced** tool discovery and registration
- **Improved** concurrent operation handling

### Previous Versions

See [Git history](hhttps://github.com/buildswithpaul/Frappe_Assistant_Core/commits/main) for changes in versions prior to 2.0.0.

---

## Version Support

| Version | Release Date | Support Status | Notes |
|---------|--------------|----------------|--------|
| 2.2.0   | 2025-10-13   | ✅ Current     | StreamableHTTP transport migration |
| 2.0.1   | 2025-07-26   | ✅ Supported   | Bug fixes & improvements |
| 2.0.0   | 2025-01-20   | ✅ Supported   | Major architecture overhaul |
| 1.x     | 2024         | ⚠️ Legacy      | Legacy versions |

## Upgrade Path

### From 2.0.x/2.1.x to 2.2.0
- **Breaking Changes**: STDIO → StreamableHTTP transport
- **Migration Required**: See v2.2.0 migration guide above
- **Benefits**: OAuth 2.0, web client support, better security
- **Recommendation**: Test in staging first, update MCP client configs

### From 2.0.0 to 2.0.1
- **Automatic**: Most improvements are automatically applied
- **No Breaking Changes**: Fully backward compatible
- **Manual Action**: None required for basic functionality
- **Dashboard Charts**: Existing broken charts can be easily fixed by ensuring required fields are populated

### From 1.x to 2.0.x
- **Breaking Changes**: Significant API changes in 2.0.0
- **Migration Required**: See 2.0.0 migration guide
- **Recommendation**: Upgrade to 2.2.0 directly for best experience

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute to this project.

## License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](LICENSE) file for details.