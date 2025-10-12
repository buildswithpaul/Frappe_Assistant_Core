# Development Guide

## Overview

This guide provides a comprehensive overview of all development approaches for extending Frappe Assistant Core. There are two primary methods for adding custom tools, each suited for different use cases.

## Development Approaches

### 1. External App Tools (Recommended)

**Best for**: Custom business logic, app-specific features, client projects

External app tools are the **recommended approach** for most use cases. They allow you to:
- Keep tools with your business logic
- Deploy tools with your app
- Maintain separate version control
- Avoid modifying core system

**Quick Start**:
```bash
# In your app directory
mkdir -p your_app/assistant_tools
touch your_app/assistant_tools/__init__.py
```

**For detailed implementation**: See [EXTERNAL_APP_DEVELOPMENT.md](EXTERNAL_APP_DEVELOPMENT.md)

### 2. Internal Plugins

**Best for**: Core functionality, system-wide features

Internal plugins are for features that should be part of the core system:
- System utilities
- Framework integrations
- Features used across multiple apps

**Quick Start**:
```bash
# In frappe_assistant_core
mkdir -p plugins/my_plugin/tools
touch plugins/my_plugin/plugin.py
```

**For detailed implementation**: See [PLUGIN_DEVELOPMENT.md](PLUGIN_DEVELOPMENT.md)

## Decision Matrix

| Criteria | External App Tools | Internal Plugins |
|----------|-------------------|------------------|
| **Location** | Your app directory | frappe_assistant_core/plugins |
| **Deployment** | With your app | With core system |
| **Updates** | Independent | Requires core update |
| **Access** | Your app only | System-wide |
| **Testing** | In your app | In core test suite |
| **Best For** | Business features | System features |

## Tool Development Basics

### Base Tool Structure

All tools inherit from `BaseTool`:

```python
from frappe_assistant_core.core.base_tool import BaseTool

class MyTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "my_tool"
        self.description = self._get_description()
        self.category = "My Category"
        self.source_app = "my_app"  # or "frappe_assistant_core"
    
    def execute(self, arguments):
        # Tool logic here
        return {"success": True, "data": result}
```

### MCP Schema Requirements

Tools must define input schemas following the Model Context Protocol:

```python
self.inputSchema = {
    "type": "object",
    "properties": {
        "param1": {"type": "string", "description": "Parameter description"},
        "param2": {"type": "integer", "minimum": 0}
    },
    "required": ["param1"]
}
```

## Templates and Examples

### Using Templates

Ready-to-use templates are available:

1. **Tool Template**: `/docs/templates/tool_template.py`
   - Complete tool structure
   - Error handling patterns
   - Permission checks
   - Response formatting

2. **Test Template**: `/docs/templates/test_template.py`
   - Unit test patterns
   - Integration tests
   - Mock strategies
   - Performance tests

**Usage**:
```bash
# Copy and customize
cp docs/templates/tool_template.py your_app/assistant_tools/my_tool.py
cp docs/templates/test_template.py your_app/tests/test_my_tool.py
```

## Testing Guidelines

### Test Structure

```python
from frappe_assistant_core.tests.base_test import BaseAssistantTest

class TestMyTool(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # Test setup
    
    def test_tool_functionality(self):
        # Test implementation
```

### Running Tests

```bash
# For external app tools
bench run-tests --app your_app

# For internal plugins
bench run-tests --app frappe_assistant_core
```

## Security Considerations

### Permission Checks

Always validate permissions:

```python
if not frappe.has_permission(doctype, "read"):
    return {
        "success": False,
        "error": "Insufficient permissions"
    }
```

### Input Validation

Validate all inputs:

```python
# Check DocType exists
if not frappe.db.exists("DocType", doctype):
    return {
        "success": False,
        "error": f"DocType '{doctype}' does not exist"
    }
```

### Sensitive Data

Never expose sensitive fields:

```python
# Use get_safe_filters() for automatic filtering
safe_data = self.get_safe_filters(data)
```

## Configuration Management

### External App Configuration

In your app's `hooks.py`:

```python
# Tool registration
assistant_tools = [
    "your_app.assistant_tools.sales_analyzer.SalesAnalyzer",
    "your_app.assistant_tools.inventory_manager.InventoryManager"
]

# Tool configuration
assistant_tool_configs = {
    "sales_analyzer": {
        "max_records": 5000,
        "cache_timeout": 300
    }
}
```

### Internal Plugin Configuration

Plugins can use the centralized config system:

```python
config = self.get_config()  # Merges defaults with site config
max_records = config.get("max_records", 1000)
```

## Best Practices

### Code Organization

1. **Single Responsibility**: One tool, one purpose
2. **Clear Naming**: Descriptive tool and method names
3. **Comprehensive Docs**: Docstrings for all methods
4. **Type Hints**: Use typing for clarity

### Error Handling

```python
try:
    # Operation
    result = perform_operation()
except Exception as e:
    frappe.log_error(
        title=f"{self.name} Error",
        message=str(e)
    )
    return {
        "success": False,
        "error": str(e)
    }
```

### Performance

1. **Pagination**: Always paginate large datasets
2. **Caching**: Use Frappe's cache for expensive operations
3. **Batch Operations**: Process in batches when possible
4. **Timeouts**: Set appropriate timeouts for long operations

## Deployment

### External App Tools

Tools deploy automatically with your app:

```bash
bench get-app your_app
bench --site site1.local install-app your_app
# Tools are immediately available
```

### Internal Plugins

Plugins are available after updating frappe_assistant_core:

```bash
bench update --apps frappe_assistant_core
```

## Debugging

### Enable Debug Logging

```python
# In your tool
frappe.logger().debug(f"{self.name}: Processing {len(data)} records")
```

### Common Issues

1. **Tool Not Found**: Check registration in hooks.py
2. **Permission Errors**: Verify user roles and DocType permissions
3. **Schema Validation**: Ensure MCP schema matches parameters
4. **Import Errors**: Check all dependencies are installed

## Migration Guide

### From Monolithic to Plugin Architecture

If migrating existing tools:

1. Move tool class to appropriate location
2. Inherit from `BaseTool`
3. Add MCP schema definition
4. Update tool registration
5. Test thoroughly

## Resources

### Documentation

- **Architecture Details**: [ARCHITECTURE.md](../architecture/ARCHITECTURE.md)
- **API Reference**: [API_REFERENCE.md](../api/API_REFERENCE.md)
- **Tool Catalog**: [TOOL_REFERENCE.md](../api/TOOL_REFERENCE.md)
- **Testing Guide**: [TEST_CASE_CREATION_GUIDE.md](TEST_CASE_CREATION_GUIDE.md)

### Examples

- **Core Tools**: `/frappe_assistant_core/core/document_tools.py`
- **Plugin Tools**: `/plugins/data_science/tools/`
- **External Apps**: See hooks documentation

## Getting Help

1. Check existing tool implementations
2. Review test cases for patterns
3. Use templates as starting points
4. Follow Frappe development guidelines

## Next Steps

1. **Choose your approach**: External app or internal plugin
2. **Use templates**: Start with provided templates
3. **Follow patterns**: Use existing tools as reference
4. **Test thoroughly**: Use the test template
5. **Document well**: Update your app's documentation