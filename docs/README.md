# Frappe Assistant Core Documentation

Welcome to the comprehensive documentation for **Frappe Assistant Core** - the open source AI assistant integration for Frappe Framework and ERPNext.

## 📚 Documentation Structure

Our documentation is organized into focused sections for easy navigation:

### 🚀 [Getting Started](getting-started/)

Quick start guides and setup instructions for new users:

- **[Getting Started Guide](getting-started/GETTING_STARTED.md)** - Complete setup guide for new users
- **[Quick Start: Claude Desktop](getting-started/QUICK_START_CLAUDE_DESKTOP.md)** - Connect Claude Desktop in 5 minutes
- **[Migration Guide](getting-started/MIGRATION_GUIDE.md)** - Migrate from STDIO to OAuth

#### OAuth Setup
- **[OAuth Setup Guide](getting-started/oauth/oauth_setup_guide.md)** - Comprehensive OAuth configuration
- **[OAuth Quick Start](getting-started/oauth/oauth_quick_start.md)** - OAuth setup in 2 minutes
- **[OAuth Changelog](getting-started/oauth/OAUTH_CHANGELOG.md)** - OAuth feature updates

---

### 🏗️ [Architecture](architecture/)

System design, technical architecture, and implementation details:

- **[Architecture Overview](architecture/ARCHITECTURE.md)** - System design and plugin architecture
- **[MCP StreamableHTTP Guide](architecture/MCP_STREAMABLEHTTP_GUIDE.md)** - OAuth + StreamableHTTP integration
- **[Technical Documentation](architecture/TECHNICAL_DOCUMENTATION.md)** - Complete technical reference
- **[Performance Guide](architecture/PERFORMANCE.md)** - Optimization and monitoring

---

### 📖 [API Reference](api/)

Complete API documentation and tool references:

- **[API Reference](api/API_REFERENCE.md)** - MCP protocol endpoints and OAuth APIs
- **[Tool Reference](api/TOOL_REFERENCE.md)** - Complete catalog of all 21 available tools

---

### 📋 [Guides](guides/)

User guides for administrators managing the system:

- **[Tool Management Guide](guides/TOOL_MANAGEMENT_GUIDE.md)** - Enable/disable tools, configure role-based access
- **[Plugin Management Guide](guides/PLUGIN_MANAGEMENT_GUIDE.md)** - Enable/disable plugins, manage tool groups
- **[MCP Resources Guide](guides/MCP_RESOURCES_GUIDE.md)** - Optimize LLM context with MCP resources

---

### 🛠️ [Development](development/)

Guides for developers building custom tools and plugins:

- **[Development Guide](development/DEVELOPMENT_GUIDE.md)** - Create custom tools and plugins
- **[External App Development](development/EXTERNAL_APP_DEVELOPMENT.md)** - Create tools in your Frappe apps (recommended)
- **[Plugin Development](development/PLUGIN_DEVELOPMENT.md)** - Create internal plugins for core features
- **[Test Case Creation Guide](development/TEST_CASE_CREATION_GUIDE.md)** - Testing patterns and best practices
- **[OAuth CORS Configuration](development/OAUTH_CORS_CONFIGURATION.md)** - CORS setup for MCP Inspector (development only)

---

### 📚 [Reference](reference/)

Additional resources and references:

- **[Changelog](reference/CHANGELOG.md)** - Version history and changes
- **[Capabilities Report](reference/CAPABILITIES_REPORT.md)** - Feature capabilities overview
- **[Templates](reference/templates)** - Documentation templates

---

## 🔍 Quick Navigation

### By User Type

**👤 End Users:**
1. Start with [Getting Started Guide](getting-started/GETTING_STARTED.md)
2. Follow [Claude Desktop Quick Start](getting-started/QUICK_START_CLAUDE_DESKTOP.md)
3. Explore [Tool Reference](api/TOOL_REFERENCE.md) to see what's possible

**👨‍💻 Developers:**
1. Review [Architecture Overview](architecture/ARCHITECTURE.md)
2. Study [Development Guide](development/DEVELOPMENT_GUIDE.md)
3. Check [API Reference](api/API_REFERENCE.md) for integration details

**🔧 System Administrators:**
1. Follow [Getting Started Guide](getting-started/GETTING_STARTED.md)
2. Configure [OAuth Setup](getting-started/oauth/oauth_setup_guide.md)
3. Review [Performance Guide](architecture/PERFORMANCE.md)

### By Topic

**OAuth & Authentication:**
- [OAuth Setup Guide](getting-started/oauth/oauth_setup_guide.md)
- [OAuth Quick Start](getting-started/oauth/oauth_quick_start.md)
- [MCP StreamableHTTP Guide](architecture/MCP_STREAMABLEHTTP_GUIDE.md)

**MCP Protocol:**
- [MCP StreamableHTTP Guide](architecture/MCP_STREAMABLEHTTP_GUIDE.md)
- [MCP Resources Guide](guides/MCP_RESOURCES_GUIDE.md) - Optimize context with resources
- [API Reference](api/API_REFERENCE.md)
- [Architecture Overview](architecture/ARCHITECTURE.md)

**Tool Development:**
- [Development Guide](development/DEVELOPMENT_GUIDE.md)
- [External App Development](development/EXTERNAL_APP_DEVELOPMENT.md)
- [Plugin Development](development/PLUGIN_DEVELOPMENT.md)

**Tool & Plugin Management:**
- [Tool Management Guide](guides/TOOL_MANAGEMENT_GUIDE.md) - Enable/disable tools, role-based access
- [Plugin Management Guide](guides/PLUGIN_MANAGEMENT_GUIDE.md) - Enable/disable plugins
- [Architecture Overview](architecture/ARCHITECTURE.md) - System design

---

## 🔧 System Overview

Frappe Assistant Core provides **21 tools** organized in a plugin-based architecture:

### Core Plugins (Always Enabled)
- **Document Operations** - CRUD operations for all Frappe DocTypes
- **Search & Discovery** - Global and targeted search capabilities
- **Metadata Tools** - DocType information and schema discovery
- **Report Tools** - Execute Frappe reports and analytics
- **Workflow Tools** - Workflow actions and queue management

### Optional Plugins (Can be enabled/disabled)
- **Data Science Plugin** - Python code execution, statistical analysis
- **Visualization Plugin** - Charts, dashboards, and KPIs
- **Batch Processing Plugin** - Bulk operations and data import
- **WebSocket Plugin** - Real-time streaming (experimental)

### External App Tools
- Tools from your custom Frappe apps
- Discovered automatically via hooks
- Full integration with core features

---

## 🎯 Key Features

- **🔌 OAuth 2.0 Authentication** - Industry-standard security with dynamic client registration
- **🌐 MCP StreamableHTTP** - Modern HTTP-based protocol (RFC 9728 compliant)
- **📚 MCP Resources** - Optimize LLM context by serving tool docs via resources (~80% token savings)
- **🔒 Enterprise Security** - Role-based permissions, audit logging, sensitive data filtering
- **📦 Plugin Architecture** - Extensible framework for custom business logic
- **🔄 Frappe v15/v16 Compatible** - Works with both Frappe versions
- **⚡ Performance Optimized** - Fast, stateless, and scalable

---

## 📖 Documentation Conventions

### File Naming
- `UPPERCASE.md` - Major documentation files
- `lowercase.md` - Supplementary files
- Folders use `lowercase-with-hyphens`

### Links
- All internal links use relative paths
- External links use absolute URLs
- Broken links? [Report an issue](https://github.com/buildswithpaul/Frappe_Assistant_Core/issues)

### Code Examples
- Python examples use Frappe v15 compatible code
- Shell commands show both development and production usage
- Configuration examples include comments

---

## 🆘 Need Help?

### Community Support
- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/buildswithpaul/Frappe_Assistant_Core/issues)
- 💬 **Questions**: [GitHub Discussions](https://github.com/buildswithpaul/Frappe_Assistant_Core/discussions)
- 📧 **Email**: jypaulclinton@gmail.com

### Professional Support
- Custom development and integration
- Priority bug fixes and features
- Training and consulting

---

## 🤝 Contributing

Want to improve the documentation?

1. **Fork the repository**
2. **Create a branch** for your changes
3. **Follow our documentation style**
4. **Submit a pull request**

See [Contributing Guidelines](../CONTRIBUTING.md) for details.

---

## 📄 License

This project is licensed under the **AGPL-3.0 License**.

See the [LICENSE](../LICENSE) file for details.

---

**Version:** 2.0.0+
**Last Updated:** January 2025
**Protocol:** MCP 2025-03-26 with OAuth 2.0
