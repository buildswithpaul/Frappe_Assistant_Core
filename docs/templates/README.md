# Development Templates

This directory contains templates for creating new tools and test cases. 

**For complete development guidance, see the [Development Guide](../DEVELOPMENT_GUIDE.md).**

## Available Templates

### 1. `tool_template.py`
Complete template for creating new tool categories with:
- Proper MCP schema definitions
- Error handling and validation
- Permission checks and security
- Response formatting
- Tool routing functionality

### 2. `test_template.py`
Comprehensive test template covering:
- Unit tests for individual tool methods
- Integration tests with Frappe framework
- Performance testing
- Security and permission testing
- Error scenario testing

## Quick Start Guide

### Creating a New Tool Category

1. **Copy the tool template:**
   ```bash
   cp docs/templates/tool_template.py frappe_assistant_core/tools/your_category_tools.py
   ```

2. **Replace placeholders:**
   - `[ToolCategory]` → Your category name (e.g., `Analytics`)
   - `[tool_category]` → Lowercase version (e.g., `analytics`)
   - `[module_path]` → Actual module path for imports

3. **Implement functionality:**
   - Update the `get_tools()` method with your tool definitions
   - Implement the actual tool methods
   - Add proper MCP schemas
   - Implement helper functions

4. **Create tests:**
   ```bash
   cp docs/templates/test_template.py frappe_assistant_core/tests/test_your_category_tools.py
   ```

5. **Update test file:**
   - Replace same placeholders as in tool file
   - Add specific test scenarios for your tools
   - Update mock data and expectations

### Example: Creating Analytics Tools

1. **Create tool file:**
   ```bash
   cp docs/templates/tool_template.py frappe_assistant_core/tools/analytics_tools.py
   ```

2. **Replace placeholders in analytics_tools.py:**
   - `[ToolCategory]` → `Analytics`
   - `[tool_category]` → `analytics`

3. **Create test file:**
   ```bash
   cp docs/templates/test_template.py frappe_assistant_core/tests/test_analytics_tools.py
   ```

4. **Update imports and references in both files**

5. **Add to test runner** (in `test_all.py`):
   ```python
   from frappe_assistant_core.tests.test_analytics_tools import TestAnalyticsTools, TestAnalyticsToolsIntegration
   ```

## Template Features

### Tool Template Features
- **MCP Schema Compliance**: Proper JSON schema for Model Context Protocol
- **Error Handling**: Comprehensive exception handling with Frappe-specific errors
- **Permission System**: Integration with Frappe's permission framework
- **Response Builder**: Consistent response formatting
- **Validation**: Input validation and DocType access checks
- **Logging**: Error logging and audit trail integration

### Test Template Features
- **Complete Coverage**: Unit tests, integration tests, performance tests
- **Mock Framework**: Proper mocking of Frappe objects and database calls
- **Permission Testing**: Validation of security and access controls
- **Error Scenarios**: Testing of various failure conditions
- **Performance Testing**: Execution time measurement and validation
- **Data Consistency**: Cross-operation data integrity testing

## Customization Guidelines

### Tool Customization
1. **Define your operations** in the `get_tools()` method
2. **Implement business logic** in individual tool methods
3. **Add proper validation** for your specific use cases
4. **Update helper functions** based on your requirements
5. **Add category-specific permissions** if needed

### Test Customization
1. **Update mock data** to match your tool's data structures
2. **Add specific test scenarios** for your business logic
3. **Customize performance expectations** based on your operations
4. **Add integration tests** for your specific workflows
5. **Update error scenarios** for your specific failure modes

## Best Practices

### Tool Development
- Follow Frappe coding conventions
- Use proper type hints
- Implement comprehensive error handling
- Add detailed docstrings
- Validate all inputs
- Check permissions before operations
- Log errors appropriately

### Test Development
- Test both success and failure paths
- Mock all external dependencies
- Use descriptive test names
- Test edge cases and boundary conditions
- Validate response structures
- Test performance with realistic data volumes
- Ensure test isolation and independence

## Integration Checklist

When adding a new tool category:

- [ ] Tool file created and implemented
- [ ] Test file created with comprehensive coverage
- [ ] Tool added to registry (if using dynamic registry)
- [ ] Tests added to `test_all.py` runner
- [ ] Documentation updated
- [ ] MCP schemas validated
- [ ] Permission requirements documented
- [ ] Error handling tested
- [ ] Performance benchmarks established

## Support

For questions about using these templates:
1. Check the main documentation in `/docs/`
2. Review existing tool implementations for examples
3. Run the test suite to ensure proper integration
4. Refer to Frappe framework documentation for framework-specific patterns

## Template Updates

These templates are updated as the framework evolves. When updating:
1. Maintain backward compatibility where possible
2. Update all placeholder references
3. Test template-generated code
4. Update this README with any new features or requirements