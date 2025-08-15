# Frappe Assistant Core

🤖 **Professional AI Assistant for ERPNext** - Transform your ERPNext experience with intelligent AI assistance through the Model Context Protocol (MCP).

Built for businesses who want to leverage AI to streamline their ERP operations, automate workflows, and gain intelligent insights from their data.

## 🚀 Version 2.0.0 - Major Architecture Evolution (July 22, 2025)

**License Change: MIT → AGPL-3.0** | **Breaking Changes: Yes**

This major release transforms Frappe Assistant Core into a fully extensible, plugin-based platform with enhanced visualization capabilities and stronger open source protection through AGPL-3.0 licensing.

### 🌟 Release Highlights

- **🏗️ Plugin-Based Architecture**: Custom tool development with auto-discovery and runtime management
- **📊 Enhanced Visualization System**: Rebuilt chart engine with advanced dashboard support
- **🔒 Stronger Open Source Protection**: AGPL-3.0 license ensures modifications remain open source
- **🐛 Major Bug Fixes**: Tool reliability improvements and data processing enhancements
- **⚡ Performance Improvements**: 30% faster tool execution, 25% reduced memory footprint

---

### 🚀 New Features in v2.0.0

#### 🏗️ Plugin-Based Architecture

- **Custom Tool Development**: Create your own tools using the new plugin system
- **Auto-Discovery**: Zero-configuration plugin loading and registration
- **Runtime Management**: Enable/disable plugins through web interface
- **Extensible Framework**: Clean APIs for third-party developers

```python
# Example: Creating a custom plugin
class MyBusinessPlugin(BasePlugin):
    def get_info(self):
        return {
            'name': 'my_business_plugin',
            'display_name': 'My Business Tools',
            'description': 'Custom business logic tools',
            'version': '1.0.0'
        }

    def get_tools(self):
        return ['sales_analyzer', 'inventory_optimizer']
```

#### 📊 Enhanced Visualization System

- **Rebuilt Chart Engine**: Complete overhaul of chart creation system
- **Advanced Dashboard Support**: Improved dashboard creation and management
- **Multiple Chart Types**: Bar, Line, Pie, Scatter, Heatmap, Gauge, and more
- **Better Data Handling**: Improved data processing and validation
- **KPI Cards**: Professional metric tracking with trend indicators

#### 🔒 Stronger Open Source Protection

- **AGPL-3.0 License**: Ensures modifications remain open source
- **Complete Compliance**: All 125+ files properly licensed with headers
- **Network Service Requirements**: Source disclosure for SaaS usage
- **Community Growth**: Prevents proprietary forks while encouraging contributions

## 🌟 Why Choose Frappe Assistant Core?

- **🔌 Plug & Play AI Integration**: Seamlessly connect Claude and other AI assistants to your ERPNext data
- **🛡️ Enterprise Security**: Built-in permissions, audit logging, and secure authentication
- **📊 Intelligent Analytics**: AI-powered insights and visualization capabilities
- **🚀 Production Ready**: Rate limiting, comprehensive monitoring, and robust error handling
- **🏗️ Plugin Architecture**: Fully extensible with custom tool development
- **📝 Professional Logging**: Structured logging system for debugging and monitoring
- **🆓 Completely Open Source**: AGPL-3.0 licensed - strong copyleft ensuring open source ecosystem
- **🤝 Community Driven**: Built by the community, for the community

---

## 🎯 Features Overview

### 🚀 Complete Feature Set (AGPL-3.0 Licensed)

- **🔄 Modern MCP Protocol**: JSON-RPC 2.0 with modular handler architecture
- **📄 Document Operations**: Create, read, update, delete, and search Frappe documents with full permission integration
- **📈 Advanced Reporting**: Execute Frappe reports with enhanced debugging and error handling
- **📊 Data Visualization**: Create charts and graphs with inline display support
- **🔍 Advanced Analytics**: Statistical analysis and business intelligence tools with hybrid streaming
- **📄 File Processing**: Extract content from PDFs, images (OCR), spreadsheets, and documents for LLM analysis
- **🌐 SSE Bridge Integration**: Real-time streaming communication with Claude API via Server-Sent Events
- **🔎 Global Search**: Search across all accessible documents and data
- **🗂️ Metadata Access**: Query DocType schemas, permissions, and workflow information
- **📋 Audit Logging**: Comprehensive operation tracking and monitoring
- **🐍 Python Code Execution**: Execute custom Python code with full Frappe context and 30+ libraries
- **⚙️ Admin Interface**: Web-based management interface for server configuration
- **🔧 Tool Registry**: Auto-discovery tool system with zero configuration
- **🎨 Prompts Support**: Built-in prompts for artifact streaming workflows

### 🏗️ Modern Architecture Features (New in v1.2.0)

- **📦 Modular Handlers**: Separated API concerns into focused modules
- **🔧 Centralized Constants**: All configuration and strings in dedicated module
- **📝 Professional Logging**: Structured logging with proper levels and formatting
- **📋 Modern Packaging**: pyproject.toml with development and analysis dependency groups
- **🐛 Error Handling**: Robust error management with centralized error codes
- **🔍 Tool Execution Engine**: Dedicated tool validation and execution system

---

## 📦 Installation

### Prerequisites

- Frappe Framework 15+
- Python 3.11+
- MariaDB/MySQL

### Quick Installation

```bash
# Navigate to your Frappe bench
cd frappe-bench

# Get the app
bench get-app https://github.com/buildswithpaul/Frappe_Assistant_Core

# Install on site
bench --site [site-name] install-app frappe_assistant_core

# Run database migrations
bench --site [site-name] migrate
```

### Modern Package Installation (New in v1.0.0)

```bash
# Development installation with all dependencies
pip install -e .[dev,analysis,sse-bridge]

# Production installation with SSE bridge for Claude API
pip install .[sse-bridge]

# Analysis dependencies only
pip install .[analysis]

# SSE bridge for real-time Claude API integration
pip install .[sse-bridge]
```

### Configuration

```bash
# Enable through admin interface
https://your-site.com/desk#/assistant-admin

# Or via CLI
bench --site [site-name] set-config assistant_enabled 1
```

---

## 🛠️ Architecture Overview

### Plugin-Based Architecture (v2.0.0)

```
frappe_assistant_core/
├── core/
│   ├── tool_registry.py         # Dynamic tool registry with auto-discovery
│   └── base_tool.py             # Base tool class for plugins
├── plugins/                     # Plugin system with runtime management
│   ├── base_plugin.py           # Base plugin interface
│   ├── core/                    # Core tools plugin (always enabled)
│   │   ├── plugin.py            # Plugin definition
│   │   └── tools/               # Core tool implementations
│   │       ├── document_*.py    # Document operations
│   │       ├── search_*.py      # Search tools
│   │       ├── metadata_*.py    # Metadata tools
│   │       ├── report_*.py      # Report tools
│   │       └── workflow_*.py    # Workflow tools
│   ├── data_science/            # Data science plugin (optional)
│   │   ├── plugin.py            # Plugin definition
│   │   └── tools/               # Analysis tool implementations
│   │       ├── execute_python_code.py
│   │       ├── analyze_frappe_data.py
│   │       └── query_and_analyze.py
│   ├── visualization/           # Visualization plugin (optional)
│   │   ├── plugin.py            # Plugin definition
│   │   └── tools/               # Visualization tool implementations
│   │       ├── create_dashboard.py
│   │       ├── create_dashboard_chart.py
│   │       └── list_user_dashboards.py
│   └── batch_processing/        # Batch processing plugin (optional)
│   │   ├── plugin.py            # Core plugin definition
│   │   └── tools/               # Essential tool implementations
│   │       ├── document_tools.py    # Document CRUD operations
│   │       ├── search_tools.py      # Global and targeted search
│   │       ├── metadata_tools.py    # Schema and permission queries
│   │       ├── report_tools.py      # Report execution and management
│   │       └── workflow_tools.py    # Workflow operations
│   └── batch_processing/        # Bulk operations plugin

├── utils/
│   ├── plugin_manager.py        # Runtime plugin management
│   └── logger.py                # Structured logging system
├── assistant_core/
│   └── doctype/                 # Frappe DocTypes
│       └── assistant_core_settings/  # Plugin management UI
└── pyproject.toml               # Modern packaging with AGPL-3.0
```

### Architecture Benefits (v2.0.0)

- **🔌 Dynamic Plugin Loading**: Auto-discovery and zero-configuration setup
- **🔄 Runtime Management**: Enable/disable plugins without restart
- **🧵 Thread-Safe Operations**: Concurrent plugin operations with proper locking
- **📊 Enhanced Visualization**: Rebuilt chart system with advanced capabilities
- **🏗️ Extensible Framework**: Clean APIs for third-party plugin development
- **⚙️ Atomic State Management**: Plugin operations with rollback support
- **🔧 External App Integration**: Seamless integration with custom Frappe apps
- **📋 Hierarchical Configuration**: Multi-level configuration management

---

## 🔧 Tool Development

### 🌟 External App Tools (Recommended)

Create tools in your custom Frappe apps using the hooks system:

```python
# In your_app/hooks.py
assistant_tools = [
    "your_app.assistant_tools.sales_analyzer.SalesAnalyzer",
    "your_app.assistant_tools.inventory_manager.InventoryManager"
]

# Optional: App-level configuration overrides
assistant_tool_configs = {
    "sales_analyzer": {
        "timeout": 60,
        "max_records": 5000
    }
}
```

**Benefits:**

- 🔧 **No Core Modifications**: Keep tools with your business logic
- 🚀 **Easy Deployment**: Tools deploy with your app
- ⚙️ **App-Specific Config**: Configure tools per your app's needs
- 🔒 **Isolated Development**: Changes don't affect core system

See [EXTERNAL_APP_DEVELOPMENT.md](docs/EXTERNAL_APP_DEVELOPMENT.md) for complete guide.

### 🔌 Internal Plugin Tools

For core functionality within frappe_assistant_core:

```python
# frappe_assistant_core/plugins/my_plugin/plugin.py
class MyPlugin(BasePlugin):
    def get_tools(self):
        return ["my_tool", "another_tool"]
```

See [PLUGIN_DEVELOPMENT.md](docs/PLUGIN_DEVELOPMENT.md) for plugin development.

---

## 🔧 Available Tools

### 📦 Core Plugin (Always Enabled)

**Document Operations**

- `create_document` - Create new documents with validation
- `get_document` - Fetch document data with permissions
- `update_document` - Update existing documents
- `delete_document` - Delete documents safely
- `list_documents` - List documents with advanced filtering
- `submit_document` - Submit documents for workflow

**Search & Discovery**

- `search_documents` - Global search across all accessible documents
- `search_doctype` - Search within specific DocTypes
- `search_link` - Search for link field values

**Metadata & Schema**

- `get_doctype_info` - Get comprehensive DocType information
- `metadata_doctype_fields` - Get DocType field definitions
- `metadata_permissions` - Check DocType permissions
- `metadata_workflow` - Get workflow information

**Reports & Analysis**

- `generate_report` - Execute Frappe reports with enhanced error handling
- `get_report_data` - Get report data with caching

**Workflow Operations**

- `run_workflow` - Execute workflow actions with validation

### 🧪 Data Science Plugin

**Python Execution & Analysis**

- `execute_python_code` - Secure Python execution with data science libraries
- `analyze_frappe_data` - Statistical analysis of Frappe data
- `query_and_analyze` - SQL query execution with analysis

### 📊 Visualization Plugin

**Dashboard & Chart Creation**

- `create_dashboard` - Create Frappe dashboards with multiple charts
- `create_dashboard_chart` - Create individual charts for dashboards
- `list_user_dashboards` - List user's accessible dashboards

### ⚡ Batch Processing Plugin

**Bulk Operations**

- Background task processing and bulk operations with progress tracking

---

## 🚀 Getting Started

### 1. Claude Desktop Integration

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

### 2. Basic Usage Examples

#### Document Operations

```python
# Create a customer
result = document_create({
    "doctype": "Customer",
    "customer_name": "Acme Corp",
    "customer_group": "All Customer Groups"
})

# Read customer data
customer = document_read({
    "doctype": "Customer",
    "name": "CUST-2024-001"
})
```

#### Data Analysis

```python
# Analyze sales data
code = """
import pandas as pd
sales_data = frappe.get_all("Sales Invoice",
    fields=["grand_total", "posting_date", "customer"])
df = pd.DataFrame(sales_data)
monthly_sales = df.groupby(df['posting_date'].dt.month)['grand_total'].sum()
print("Monthly Sales Analysis:")
print(monthly_sales)
"""

result = execute_python_code({"code": code})
```

### 3. Advanced Features

#### Plugin Management (NEW in v2.0.0)

```python
# Enable/disable plugins through web interface
# Navigate to: https://your-site.com/desk#/assistant-admin

# Or via Python API
from frappe_assistant_core.utils.plugin_manager import PluginManager
pm = PluginManager()

# List available plugins
plugins = pm.get_available_plugins()

# Enable a plugin
pm.enable_plugin('visualization')

# Disable a plugin
pm.disable_plugin('data_science')
```

#### Enhanced Visualization (NEW in v2.0.0)

```python
# Create advanced charts
result = create_chart({
    "chart_type": "bar",
    "data_source": "Sales Invoice",
    "x_field": "posting_date",
    "y_field": "grand_total",
    "filters": {"status": "Paid"}
})

# Create KPI cards with trends
kpi = create_kpi_card({
    "title": "Monthly Revenue",
    "value_field": "grand_total",
    "comparison_period": "last_month"
})
```

#### Hybrid Streaming (Smart Artifact Creation)

- **Small Results**: Displayed directly in chat
- **Large Results**: Automatically streamed to artifacts for unlimited depth
- **Threshold**: 20 lines output triggers artifact streaming

#### Prompts Support

- `enforce_artifact_streaming_analysis`
- `create_business_intelligence_report`
- `stream_python_analysis_to_artifact`

---

## 🚨 Breaking Changes & Migration (v2.0.0)

### License Impact

⚠️ **Critical**: Review AGPL-3.0 compliance requirements

- All derivative works must be AGPL-3.0 licensed
- SaaS deployments must provide source code access to users
- Commercial use requires AGPL compliance or dual licensing

### API Changes

⚠️ **Development Impact**: Some APIs have been refactored

- **Plugin Registration**: New plugin-based system
- **Tool Configuration**: Updated configuration format
- **Hook System**: Enhanced with external app support

### Migration Steps

#### For End Users

1. **License Review**: Understand AGPL-3.0 implications
2. **Update Deployment**: Test in staging environment first
3. **Verify Functionality**: Ensure all tools work as expected

#### For Developers

1. **License Headers**: Add AGPL-3.0 headers to custom code
2. **Plugin Migration**: Convert custom tools to plugin architecture
3. **API Updates**: Update to new plugin registration system

#### For SaaS Providers

1. **Compliance Review**: Ensure AGPL-3.0 compliance
2. **Source Availability**: Implement source code provision mechanism
3. **User Notification**: Inform users of their source code rights

---

## 📊 Performance & Monitoring

### Performance Improvements (v2.0.0)

#### System Optimization

- **30% faster tool execution** through optimized plugin loading
- **25% reduced memory footprint** with better resource management
- **Enhanced error recovery** with graceful failure handling
- **50% faster repeated operations** with improved caching system

#### Scalability Enhancements

- **Plugin lazy loading** reduces startup time
- **Concurrent tool execution** support
- **Better database query optimization**
- **Enhanced connection pooling**

### Monitoring & Logging

```python
# Enable debug logging
from frappe_assistant_core.utils.logger import api_logger
api_logger.setLevel('DEBUG')

# Check system health
from frappe_assistant_core.tools.registry import get_assistant_tools
tools = get_assistant_tools()
print(f"Available tools: {len(tools)}")
```

### Audit Trail

- All operations logged with user, timestamp, and result
- Connection tracking and monitoring
- Error tracking with detailed context
- Performance metrics and timing

---

## 🔒 Security Features

- **Role-Based Access Control**: Tools filtered by user permissions
- **Secure Python Execution**: Sandboxed environment with restricted imports
- **Authentication Required**: API key and session validation
- **Audit Logging**: Complete operation tracking
- **Permission Integration**: Respects Frappe's built-in permission system

---

## 📄 License

This project is licensed under the GNU Affero General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

### Commercial Use

This software is free for both personal and commercial use. You can:

- ✅ Use in commercial projects
- ✅ Modify and distribute
- ✅ Include in proprietary software
- ✅ Sell services around it

### Enterprise Support

Looking for enterprise features, support, or custom development?
Contact us at jypaulclinton@gmail.com

---

## 📚 Documentation Hub

### 🚀 Quick Start

- [Installation Guide](#-installation) - Quick setup and configuration
- [Getting Started](#-getting-started) - Basic usage examples
- [Plugin Management](#plugin-management-new-in-v200) - Enable/disable plugins

### 📖 User Guides

- [Tool Usage Guide](docs/TOOL_USAGE_GUIDE.md) - Comprehensive tool reference for LLMs
- [External App Development](docs/EXTERNAL_APP_DEVELOPMENT.md) - 🌟 Create tools in your Frappe apps (Recommended)
- [Plugin Development](docs/PLUGIN_DEVELOPMENT.md) - Internal plugin development guide
- [Tool Development Templates](docs/TOOL_DEVELOPMENT_TEMPLATES.md) - Code templates and examples

### 🔧 Technical Reference

- [Architecture Overview](docs/ARCHITECTURE.md) - Complete system architecture and design
- [API Reference](docs/API_REFERENCE.md) - Complete API documentation
- [Technical Documentation](docs/TECHNICAL_DOCUMENTATION.md) - Detailed technical implementation
- [Security Guide](docs/COMPREHENSIVE_SECURITY_GUIDE.md) - Security features and best practices
- [Capabilities Report](docs/CAPABILITIES_REPORT.md) - Complete feature overview

### 🤝 Contributing

- [Contributing Guidelines](Contributing.md) - How to contribute to the project
- [Test Case Creation Guide](docs/TEST_CASE_CREATION_GUIDE.md) - Testing best practices
- [Commercial Services](COMMERCIAL.md) - Professional support and development services

---

## 🤝 Contributing

This is an open-source AGPL-3.0 licensed project. Contributions are welcome!

1. Fork the repository
2. Create a feature branch
3. Follow the modular architecture patterns
4. Add tests for new functionality
5. Update documentation
6. Submit a pull request

### Architecture Guidelines

- **Use Modular Handlers**: Add new functionality in separate handler modules
- **Leverage Constants**: All strings and configuration in `constants/definitions.py`
- **Professional Logging**: Use `api_logger` instead of print statements
- **Follow Patterns**: Maintain consistency with existing code structure

---

## 🌟 Support & Community

- **GitHub Repository**: [Frappe Assistant Core](https://github.com/buildswithpaul/Frappe_Assistant_Core)
- **Issues**: GitHub Issues for bug reports and feature requests
- **Discussions**: GitHub Discussions for questions and community support
- **Email**: jypaulclinton@gmail.com for direct support

---

## 🚀 Roadmap

### Planned Features (v2.1.0)

- **Websocket Integration**: Websocket integration
- **Batch Processing Support**: Support Batch Processing Of Tools
- **Advanced Analytics**: Machine learning integrations
- **Real-time Collaboration**: WebSocket-based features

### Long-term Vision (v3.0.0)

- **Multi-tenant Architecture**: Enhanced scalability
- **Advanced Security**: Enhanced authentication options
- **International Support**: Multi-language capabilities
- **Cloud Integration**: Native cloud service integration

---

**Built with ❤️ by the community, for the community**

_Last Updated: July 2025 - Version 2.0.0_
_Architecture: Plugin-Based, Extensible, Open Source (AGPL-3.0)_
