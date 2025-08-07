# Frappe Assistant Core Documentation

Welcome to the comprehensive documentation for **Frappe Assistant Core** - the open source AI assistant integration for Frappe Framework and ERPNext.

## 📚 Documentation Index

### 🚀 Quick Start
- **[Main README](../README.md)**: Installation, setup, and getting started
- **[Contributing Guidelines](../CONTRIBUTING.md)**: How to contribute to the project

### 📖 Core Documentation
- **[Tool Reference Guide](TOOL_REFERENCE.md)**: Complete catalog of all 21 available tools
- **[Development Guide](DEVELOPMENT_GUIDE.md)**: How to create custom tools (external apps or internal plugins)
- **[Architecture Overview](ARCHITECTURE.md)**: System design and technical architecture
- **[API Reference](API_REFERENCE.md)**: MCP protocol endpoints and tool APIs
- **[SSE Bridge Integration](SSE_BRIDGE_INTEGRATION.md)**: Claude API Integration Guide
  - Real-time streaming communication setup
  - Development and production deployment
  - Authentication and configuration
  - Troubleshooting and monitoring
  - Complete usage examples

### 🛠️ Tool Reference
- **[Tool Usage Guide](TOOL_USAGE_GUIDE.md)**: Comprehensive guide for using all available tools
  - Tool categories and descriptions
  - Usage patterns and workflows
  - Best practices for LLMs
  - Field naming conventions
  - Error handling strategies
  
### 🛠️ Specialized Guides
- **[External App Development](EXTERNAL_APP_DEVELOPMENT.md)**: Create tools in your Frappe apps (recommended)
- **[Internal Plugin Development](PLUGIN_DEVELOPMENT.md)**: Create internal plugins for core features
- **[Test Case Creation Guide](TEST_CASE_CREATION_GUIDE.md)**: Testing patterns and best practices

### 🔒 Security & Operations
- **[Comprehensive Security Guide](../COMPREHENSIVE_SECURITY_GUIDE.md)**: Security architecture and best practices
- **[Technical Documentation](TECHNICAL_DOCUMENTATION.md)**: Complete technical reference and troubleshooting

## 🔧 System Overview

Frappe Assistant Core provides **21 tools** organized in a plugin-based architecture:

| Plugin | Tools | Purpose |
|--------|--------|---------|
| **Core** | 19 tools | Essential Frappe operations (always enabled) |
| **Data Science** | 3 tools | Python execution and statistical analysis |
| **Visualization** | 3 tools | Dashboard and chart creation |

**All tools respect Frappe permissions and security policies.**

For detailed tool descriptions and usage patterns, see the **[Tool Reference Guide](TOOL_REFERENCE.md)**.

## 🚀 Development Quick Start

### Creating Tools in Your App (Recommended)

```bash
# 1. Create tool directory
mkdir -p your_app/assistant_tools
touch your_app/assistant_tools/__init__.py

# 2. Use template
cp docs/templates/tool_template.py your_app/assistant_tools/my_tool.py

# 3. Register in hooks.py
echo 'assistant_tools = ["your_app.assistant_tools.my_tool.MyTool"]' >> your_app/hooks.py
```

**Complete guide**: [External App Development](EXTERNAL_APP_DEVELOPMENT.md)

### Creating Internal Plugins

```bash
# 1. Create plugin structure
mkdir -p plugins/my_plugin/tools
touch plugins/my_plugin/plugin.py

# 2. Use template
cp docs/templates/tool_template.py plugins/my_plugin/tools/my_tool.py
```

**Complete guide**: [Internal Plugin Development](PLUGIN_DEVELOPMENT.md)

## 🌟 Key Features

- **🏗️ Plugin Architecture**: Modular, extensible design
- **🔌 Auto-Discovery**: Zero-configuration tool loading
- **🔒 Enterprise Security**: Role-based access with audit trails
- **🐍 Python Sandbox**: Safe code execution environment
- **📊 Rich Analytics**: Statistical analysis and visualization
- **⚡ High Performance**: Optimized for production workloads
- **📝 Comprehensive Testing**: Full test coverage with templates
- **⚖️ MIT Licensed**: Free for all commercial and personal use

## 🤝 Contributing

We welcome contributions! Ways to get involved:

1. **🐛 Report Issues**: [GitHub Issues](https://github.com/buildswithpaul/Frappe_Assistant_Core/issues)
2. **💡 Suggest Features**: [GitHub Discussions](https://github.com/buildswithpaul/Frappe_Assistant_Core/discussions)  
3. **🔧 Contribute Code**: Follow our [Contributing Guidelines](../CONTRIBUTING.md)
4. **📚 Improve Documentation**: Help make docs better

## 📞 Support

### 🆓 Community Support
- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and community help
- **Frappe Forum**: General Frappe/ERPNext support

### 💼 Professional Services
Custom development, implementation support, training & consulting available.
**Contact**: [jypaulclinton@gmail.com](mailto:jypaulclinton@gmail.com)

## 📄 License

This project is **MIT Licensed** - free for commercial and personal use with no restrictions.

## 🎯 Quick Navigation

| I want to... | Go to... |
|---------------|----------|
| **Use existing tools** | [Tool Reference Guide](TOOL_REFERENCE.md) |
| **Create custom tools** | [Development Guide](DEVELOPMENT_GUIDE.md) |
| **Understand the system** | [Architecture Overview](ARCHITECTURE.md) |
| **Integrate via API** | [API Reference](API_REFERENCE.md) |
| **Set up testing** | [Test Case Creation Guide](TEST_CASE_CREATION_GUIDE.md) |
| **Get started quickly** | [Main README](../README.md) |

---

**Ready to get started?** Check out the [Tool Reference Guide](TOOL_REFERENCE.md) to see what's available, or the [Development Guide](DEVELOPMENT_GUIDE.md) to start building your own tools.