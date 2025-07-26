# Frappe Assistant Core Documentation

Welcome to the comprehensive documentation for **Frappe Assistant Core** - the open source AI assistant integration for Frappe Framework and ERPNext.

## 📚 Documentation Overview

### 🚀 Quick Start
- **[Main README](../README.md)**: Installation, features, and getting started
- **[Contributing Guidelines](../CONTRIBUTING.md)**: How to contribute to the project
- **[Professional Services](../COMMERCIAL.md)**: Available consulting and development services

### 📖 Technical Documentation
- **[Technical Documentation](TECHNICAL_DOCUMENTATION.md)**: Complete technical reference
  - Architecture and system design
  - Development history and recent improvements
  - Tool system implementation
  - API documentation
  - Installation and setup guide
  - Testing and troubleshooting

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

### 🔒 Security Documentation
- **[Comprehensive Security Guide](../COMPREHENSIVE_SECURITY_GUIDE.md)**: Complete security reference
  - Security architecture and implementation
  - Role-based access control
  - Secure code execution with sandboxing
  - SQL query validation and safety
  - Attack prevention and mitigation
  - Audit trails and monitoring
  - Best practices for administrators

## 🔧 Available Tools

### 📄 Core Document Management (6 tools)
- `create_document` - Create new documents
- `get_document` - Retrieve specific documents  
- `update_document` - Update existing documents
- `list_documents` - List and search documents
- `delete_document` - Delete documents
- `submit_document` - Submit documents for approval

### 🔍 Search & Metadata (3 tools)
- `search_documents` - Global search across all data
- `get_doctype_info` - DocType schemas and fields
- `run_workflow` - Execute document workflows

### 📊 Reporting & Analytics (3 tools)
- `generate_report` - Execute Frappe reports
- `get_report_data` - Get detailed report information
- `analyze_business_data` - Statistical analysis

### 💻 Advanced Data Tools (2 tools)
- `run_python_code` - Custom Python code execution (System Manager only)
- `run_database_query` - Custom SQL with analysis (System Manager only)

### 📊 Visualization Plugin (3 tools)
- `create_dashboard` - Create Frappe dashboards with multiple charts
- `create_dashboard_chart` - Create individual Dashboard Chart documents
- `list_user_dashboards` - List user's accessible dashboards

**Note**: Visualization plugin must be enabled in settings. Creates Frappe Dashboard documents, not Insights dashboards.

## 🌟 Recent Major Improvements

### ✅ Fixed Issues
- **Document List Tool**: Now returns correct results instead of 0 records
- **Visualization Plugin**: Streamlined to 3 essential tools with proper chart creation
- **Report Execution**: Enhanced debugging and error handling

### 🆕 New Features
- **Inline Chart Display**: Base64 encoded images in conversation
- **Enhanced Tool Descriptions**: Better guidance for AI assistants
- **MIT License**: Completely open source with no restrictions

## 🤝 Contributing

We welcome contributions! Here's how to get involved:

1. **🐛 Report Issues**: Use [GitHub Issues](hhttps://github.com/buildswithpaul/Frappe_Assistant_Core/issues)
2. **💡 Suggest Features**: Join [GitHub Discussions](hhttps://github.com/buildswithpaul/Frappe_Assistant_Core/discussions)
3. **🔧 Contribute Code**: Follow our [Contributing Guidelines](../CONTRIBUTING.md)
4. **📚 Improve Docs**: Help us make documentation better

## 📞 Support

### 🆓 Community Support
- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and community help
- **Frappe Forum**: General Frappe/ERPNext support

### 💼 Professional Services
- **Custom Development**: Tailored solutions for your needs
- **Implementation Support**: Expert setup and configuration
- **Training & Consulting**: Team training and best practices
- **Contact**: [jypaulclinton@gmail.com](mailto:jypaulclinton@gmail.com)

## 📄 License

This project is licensed under the **MIT License**, which means:
- ✅ Free for commercial and personal use
- ✅ Modify and distribute freely
- ✅ No restrictions or limitations
- ✅ Community-driven development

## 🚀 Quick Links

- **[Installation Guide](../README.md#-quick-start)**
- **[Tool Usage Examples](TOOL_USAGE_GUIDE.md#example-user-scenarios)**
- **[Architecture Overview](TECHNICAL_DOCUMENTATION.md#architecture)**
- **[Recent Improvements](TECHNICAL_DOCUMENTATION.md#recent-improvements)**
- **[Contributing Guide](../CONTRIBUTING.md)**

---

**Ready to get started?** Check out our [Quick Start Guide](../README.md#-quick-start) or dive into the [Technical Documentation](TECHNICAL_DOCUMENTATION.md) for detailed implementation information.

**Questions?** Reach out via [email](mailto:jypaulclinton@gmail.com).