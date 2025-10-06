# 🚀 Frappe Assistant Core v2.1.1 Release Notes

**Release Date:** January 2025
**Version:** 2.1.1
**Previous Version:** 2.1.0

## 📋 Release Overview

This release introduces major improvements to CI/CD automation, enhanced SSE bridge functionality, improved error handling, and comprehensive documentation updates. Key highlights include GitHub Actions workflows, enhanced tool execution reliability, and streamlined dependency management.

---

## ✨ What's New

### 🔄 **CI/CD Automation**
- **Comprehensive GitHub Actions Workflow** (`ci.yml`)
  - Automated testing for every push and pull request
  - Service containers for Redis and MariaDB
  - Dependency caching for faster builds
  - Automated Frappe environment setup and app installation

- **Enhanced Linting Pipeline** (`linter.yml`)
  - Pre-commit hooks automation
  - Semgrep static analysis integration
  - pip-audit for dependency vulnerability scanning
  - Automated code quality checks on pull requests

### 🌉 **SSE Bridge Enhancements**
- **Unified Admin Dashboard Integration**
  - Real-time SSE bridge status monitoring in Assistant Admin page
  - One-click start/stop controls with live feedback
  - Comprehensive metrics display (connections, messages, storage backend)
  - Intelligent state handling (running/stopped/disabled/error states)

- **Enhanced Configuration Management**
  - Priority-based configuration: DocType settings → Environment variables → Defaults
  - Missing dependency detection and user-friendly error messages
  - Improved process management with PID file tracking
  - Redis backend auto-detection with fallback mechanisms

- **API Improvements**
  - New dedicated API endpoints: `api_get_sse_bridge_status`, `api_start_sse_bridge`, `api_stop_sse_bridge`
  - Better error handling and logging
  - Proper JSON response formatting
  - Enhanced client-side error reporting

### 🛠️ **Tool Execution Reliability**
Enhanced error handling in `frappe_assistant_core/api/handlers/tools.py`:
- **Detailed Error Logging**: More descriptive messages for tool not found and permission errors
- **Structured Error Responses**: Explicit handling for `frappe.ValidationError` with consistent JSON structure
- **Comprehensive Exception Handling**: Full stack trace logging for debugging
- **Improved User Experience**: Better error messages displayed to end users

### 📊 **Data Model Improvements**
- **Assistant Audit Log Refinements**
  - Changed `target_doctype` and `target_name` from link/dynamic link to data fields
  - Updated metadata including naming rules and row formatting
  - Enhanced audit trail consistency

- **Usage Statistics Refactoring**
  - Migrated from Assistant Connection Log to audit log-based activity tracking
  - More accurate representation of user engagement
  - Streamlined data model with better performance

---

## 🔧 Technical Improvements

### **Dependency Management**
- **Library Migration**: Updated from PyPDF2 to pypdf across all documentation and code
- **Dependency Resolution**: Added missing `httpx>=0.24.0` to SSE bridge requirements
- **Installation Reliability**: Enhanced pyproject.toml with proper SSE bridge extras

### **Documentation Updates**
- **Architecture Documentation**: Updated `docs/ARCHITECTURE.md` with current dependency stack
- **Technical Guides**: Refreshed `docs/FILE_EXTRACTION_TECHNICAL_GUIDE.md` with pypdf migration
- **SSE Bridge Documentation**: Comprehensive updates to integration guides reflecting UI changes
- **API Reference**: Updated connection ID formats and endpoint documentation

### **Frontend Enhancements**
- **SSE Bridge Status Loading**: Auto-refresh status on form load in `assistant_core_settings.js`
- **Real-time Monitoring**: 30-second interval status updates in Admin dashboard
- **Improved UX**: Loading states, error handling, and user guidance
- **Responsive Design**: Collapsible details and mobile-friendly layouts

---

## 🐛 Bug Fixes

### **SSE Bridge Stability**
- **Process Management**: Fixed process startup failures due to missing dependencies
- **API Call Errors**: Resolved JSON parsing errors in frontend-backend communication
- **Configuration Issues**: Fixed environment variable precedence and fallback logic
- **Status Detection**: Improved process status verification and PID file management

### **Tool Execution**
- **Error Propagation**: Better error message passing from tools to frontend
- **Permission Handling**: Enhanced permission error detection and reporting
- **Validation Errors**: Structured handling of Frappe validation exceptions

### **Data Consistency**
- **Audit Logging**: Fixed field type inconsistencies in Assistant Audit Log
- **Usage Statistics**: Resolved connection tracking after Connection Log removal
- **Configuration Sync**: Improved settings synchronization between UI and backend

---

## 📈 Performance Optimizations

- **Caching Improvements**: Enhanced dependency caching in CI workflows
- **Database Optimization**: Streamlined audit log queries for usage statistics
- **Frontend Performance**: Reduced API calls with intelligent status caching
- **Resource Management**: Better memory usage in SSE bridge connection handling

---

## 🔒 Security Enhancements

- **Dependency Scanning**: Automated vulnerability detection with pip-audit
- **Static Analysis**: Semgrep integration for security pattern detection
- **Input Validation**: Enhanced parameter validation in API endpoints
- **Error Information**: Sanitized error messages to prevent information leakage

---

## 📚 Documentation

### **Updated Guides**
- **SSE Bridge Integration**: Complete rewrite reflecting current implementation
- **API Reference**: Updated endpoints and response formats
- **Architecture Overview**: Current technology stack and component relationships
- **Troubleshooting**: Enhanced debugging guides with common solutions

### **New Documentation**
- **CI/CD Pipeline**: Documentation for GitHub Actions workflows
- **Development Setup**: Updated installation and configuration guides
- **Release Process**: Standardized release notes and versioning

---

## 🔄 Migration Guide

### **From v2.1.0 to v2.1.1**

1. **Update Dependencies**:
   ```bash
   pip install frappe_assistant_core[sse-bridge] --upgrade
   ```

2. **Migrate Configuration**:
   - Review SSE bridge settings in Assistant Core Settings
   - Update any hardcoded PyPDF2 references to pypdf
   - Verify environment variable configuration

3. **Database Migration**:
   ```bash
   bench migrate
   ```

4. **Verify SSE Bridge**:
   - Check SSE bridge status in Assistant Admin page
   - Test start/stop functionality
   - Verify connection metrics display

---

## 🎯 Breaking Changes

### **API Changes**
- **SSE Bridge API**: New dedicated endpoints replace direct document method calls
- **Connection ID Format**: Updated from `session_id` to `cid` parameter format
- **Error Response Structure**: Standardized error response JSON format

### **Configuration Changes**
- **Environment Variables**: New SSE bridge-specific environment variable names
- **Settings Structure**: Enhanced Assistant Core Settings with new SSE bridge fields

### **Data Model Changes**
- **Assistant Audit Log**: Field type changes for target_doctype and target_name
- **Usage Statistics**: Migration from Connection Log to Audit Log based tracking

---

## 🧪 Testing

### **Automated Testing**
- **CI Pipeline**: Comprehensive test suite execution on every commit
- **Integration Tests**: End-to-end testing of SSE bridge functionality
- **Security Testing**: Automated vulnerability scanning and static analysis
- **Performance Tests**: Connection handling and resource usage validation

### **Manual Testing**
- **SSE Bridge Operations**: Start/stop functionality across different states
- **Admin Dashboard**: Real-time status updates and metrics display
- **Error Scenarios**: Graceful handling of various failure conditions
- **Configuration Management**: Settings persistence and environment variable precedence

---

## 👥 Contributors

- **Paul Clinton** - Lead Developer & Maintainer
- **Community Contributors** - Bug reports and feature suggestions

---

## 🔗 Resources

- **GitHub Repository**: [Frappe Assistant Core](https://github.com/buildswithpaul/Frappe_Assistant_Core)
- **Documentation**: [Wiki](https://github.com/buildswithpaul/Frappe_Assistant_Core/wiki)
- **Issue Tracker**: [GitHub Issues](https://github.com/buildswithpaul/Frappe_Assistant_Core/issues)
- **Support**: [jypaulclinton@gmail.com](mailto:jypaulclinton@gmail.com)

---

## 🎉 Acknowledgments

Special thanks to the Frappe community for their continued support and feedback. This release represents significant improvements in automation, reliability, and user experience based on real-world usage and community input.

---

**Download**: [frappe_assistant_core-2.1.1.tar.gz](https://github.com/buildswithpaul/Frappe_Assistant_Core/releases/tag/v2.1.1)

**Installation**:
```bash
bench get-app frappe_assistant_core https://github.com/buildswithpaul/Frappe_Assistant_Core.git
bench install-app frappe_assistant_core
```

**With SSE Bridge**:
```bash
pip install frappe_assistant_core[sse-bridge]
```

---

*For detailed technical information, see [TECHNICAL_DOCUMENTATION.md](./docs/TECHNICAL_DOCUMENTATION.md)*