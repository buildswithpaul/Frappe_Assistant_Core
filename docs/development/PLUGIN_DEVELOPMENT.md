# Plugin Development Guide

## Overview

This comprehensive guide covers creating plugins for Frappe Assistant Core. Plugins allow you to extend the system with custom functionality while maintaining clean separation from core features.

> **Note**: For most use cases, we recommend creating tools in external Frappe apps using the hooks system (see TOOL_DEVELOPMENT_TEMPLATES.md). Internal plugins are primarily for core functionality within frappe_assistant_core.

## Plugin Architecture

### Plugin Structure

```
plugins/
└── my_plugin/
    ├── __init__.py           # Python package init
    ├── plugin.py             # Plugin definition (required)
    ├── requirements.txt      # Python dependencies (optional)
    ├── README.md            # Plugin documentation (recommended)
    ├── tools/               # Plugin tools directory
    │   ├── __init__.py
    │   ├── tool1.py
    │   └── tool2.py
    └── utils/               # Plugin utilities (optional)
        ├── __init__.py
        └── helpers.py
```

### Plugin Lifecycle

1. **Discovery**: Plugin manager scans plugin directories
2. **Validation**: Environment and dependencies checked
3. **Registration**: Plugin registered in system
4. **Loading**: Plugin enabled and tools loaded
5. **Execution**: Plugin tools available for use
6. **Unloading**: Plugin disabled and resources cleaned up

## Creating a Plugin

### Step 1: Plugin Directory Setup

```bash
# Create plugin directory
mkdir -p plugins/my_awesome_plugin/tools
touch plugins/my_awesome_plugin/__init__.py
touch plugins/my_awesome_plugin/plugin.py
touch plugins/my_awesome_plugin/tools/__init__.py
```

### Step 2: Implement Plugin Class

Create `plugins/my_awesome_plugin/plugin.py`:

```python
"""
My Awesome Plugin for Frappe Assistant Core.
Provides advanced functionality for awesome operations.
"""

import frappe
from frappe import _
from frappe_assistant_core.plugins.base_plugin import BasePlugin
from typing import Dict, Any, List, Tuple, Optional


class MyAwesomePlugin(BasePlugin):
    """
    Plugin for awesome functionality.

    Provides tools for:
    - Awesome data processing
    - Advanced awesome analysis
    - Awesome visualization
    """

    def get_info(self) -> Dict[str, Any]:
        """Get plugin information"""
        return {
            'name': 'my_awesome_plugin',
            'display_name': 'My Awesome Plugin',
            'description': 'Provides awesome functionality for Frappe Assistant Core',
            'version': '1.0.0',
            'author': 'Your Name',
            'dependencies': [
                'numpy',        # Required Python packages
                'pandas',       # Will be checked during validation
                'requests'      # Add your dependencies here
            ],
            'requires_restart': False,  # Set to True if plugin needs restart
            'category': 'analysis',     # Plugin category (optional)
            'tags': ['awesome', 'analysis', 'data']  # Plugin tags (optional)
        }

    def get_tools(self) -> List[str]:
        """Get list of tools provided by this plugin"""
        return [
            'awesome_analyzer',     # Tool class names
            'awesome_processor',    # Must match tool file names
            'awesome_reporter'      # in tools/ directory
        ]

    def validate_environment(self) -> Tuple[bool, Optional[str]]:
        """Validate that plugin can be enabled"""
        info = self.get_info()
        dependencies = info['dependencies']

        # Check Python dependencies
        can_enable, error = self._check_dependencies(dependencies)
        if not can_enable:
            return can_enable, error

        # Check custom requirements
        try:
            # Example: Check if specific DocType exists
            if not frappe.db.exists("DocType", "Custom DocType"):
                return False, _("Required DocType 'Custom DocType' not found")

            # Example: Check configuration
            settings = frappe.get_single("System Settings")
            if not settings.enable_awesome_feature:
                return False, _("Awesome feature not enabled in System Settings")

            # Example: Check external service
            import requests
            response = requests.get("https://api.awesome-service.com/health", timeout=5)
            if response.status_code != 200:
                return False, _("Awesome service not available")

            self.logger.info("My Awesome Plugin validation passed")
            return True, None

        except Exception as e:
            return False, _("Environment validation failed: {0}").format(str(e))

    def get_capabilities(self) -> Dict[str, Any]:
        """Get plugin capabilities for MCP protocol"""
        return {
            "experimental": {
                "awesome_analysis": True,
                "awesome_processing": True,
                "awesome_reporting": True
            },
            "data_formats": {
                "awesome_format": True,
                "json": True,
                "csv": True
            },
            "features": {
                "real_time": False,
                "batch_processing": True,
                "visualization": True
            }
        }

    def on_enable(self) -> None:
        """Called when plugin is enabled"""
        super().on_enable()

        # Plugin-specific initialization
        self._setup_awesome_cache()
        self._register_awesome_hooks()

        # Log successful enable
        self.logger.info("My Awesome Plugin enabled with all features")

    def on_disable(self) -> None:
        """Called when plugin is disabled"""
        super().on_disable()

        # Plugin-specific cleanup
        self._cleanup_awesome_cache()
        self._unregister_awesome_hooks()

    def on_server_start(self) -> None:
        """Called when server starts with plugin enabled"""
        # Start background services if needed
        self._start_awesome_background_service()

    def on_server_stop(self) -> None:
        """Called when server stops"""
        # Stop background services
        self._stop_awesome_background_service()

    def _setup_awesome_cache(self):
        """Setup plugin-specific caching"""
        try:
            frappe.cache().hset("awesome_plugin", "initialized", True)
            self.logger.debug("Awesome cache initialized")
        except Exception as e:
            self.logger.warning(f"Failed to setup awesome cache: {str(e)}")

    def _cleanup_awesome_cache(self):
        """Cleanup plugin-specific caching"""
        try:
            frappe.cache().delete_key("awesome_plugin")
            self.logger.debug("Awesome cache cleaned up")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup awesome cache: {str(e)}")

    def _register_awesome_hooks(self):
        """Register plugin hooks"""
        # Example: Register document hooks
        # frappe.db.add_after_insert_hook("Customer", self._on_customer_insert)
        pass

    def _unregister_awesome_hooks(self):
        """Unregister plugin hooks"""
        # Clean up any registered hooks
        pass

    def _start_awesome_background_service(self):
        """Start background services"""
        # Example: Start scheduled jobs
        pass

    def _stop_awesome_background_service(self):
        """Stop background services"""
        # Example: Stop scheduled jobs
        pass
```

### Step 3: Create Plugin Tools

Each tool should be in a separate file in the `tools/` directory.

Create `plugins/my_awesome_plugin/tools/awesome_analyzer.py`:

```python
"""
Awesome Analyzer Tool for My Awesome Plugin.
Performs awesome analysis on data.
"""

import frappe
from frappe import _
from typing import Dict, Any
from frappe_assistant_core.core.base_tool import BaseTool


class AwesomeAnalyzer(BaseTool):
    """
    Tool for performing awesome analysis.

    Provides capabilities for:
    - Data awesomeness scoring
    - Awesome pattern detection
    - Awesome insights generation
    """

    def __init__(self):
        super().__init__()
        self.name = "awesome_analyzer"
        self.description = "Analyze data for awesomeness patterns and insights"
        self.requires_permission = None  # Or specify required DocType

        self.inputSchema = {
            "type": "object",
            "properties": {
                "data_source": {
                    "type": "string",
                    "description": "Source of data to analyze"
                },
                "analysis_type": {
                    "type": "string",
                    "enum": ["basic", "advanced", "comprehensive"],
                    "default": "basic",
                    "description": "Type of awesome analysis to perform"
                },
                "parameters": {
                    "type": "object",
                    "description": "Analysis parameters"
                },
                "output_format": {
                    "type": "string",
                    "enum": ["json", "report", "visualization"],
                    "default": "json",
                    "description": "Format for analysis results"
                }
            },
            "required": ["data_source"]
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute awesome analysis"""
        data_source = arguments.get("data_source")
        analysis_type = arguments.get("analysis_type", "basic")
        parameters = arguments.get("parameters", {})
        output_format = arguments.get("output_format", "json")

        try:
            # Validate plugin is enabled
            self._check_plugin_enabled()

            # Perform analysis based on type
            if analysis_type == "basic":
                result = self._basic_awesome_analysis(data_source, parameters)
            elif analysis_type == "advanced":
                result = self._advanced_awesome_analysis(data_source, parameters)
            elif analysis_type == "comprehensive":
                result = self._comprehensive_awesome_analysis(data_source, parameters)
            else:
                return {
                    "success": False,
                    "error": f"Unknown analysis type: {analysis_type}"
                }

            # Format output
            formatted_result = self._format_output(result, output_format)

            return {
                "success": True,
                "data_source": data_source,
                "analysis_type": analysis_type,
                "output_format": output_format,
                "result": formatted_result
            }

        except Exception as e:
            frappe.log_error(
                title=_("Awesome Analysis Error"),
                message=f"Error in awesome analysis: {str(e)}"
            )

            return {
                "success": False,
                "error": str(e),
                "data_source": data_source
            }

    def _check_plugin_enabled(self):
        """Check if the awesome plugin is properly enabled"""
        if not frappe.cache().hget("awesome_plugin", "initialized"):
            frappe.throw(_("Awesome plugin not properly initialized"))

    def _basic_awesome_analysis(self, data_source: str, parameters: Dict) -> Dict:
        """Perform basic awesome analysis"""
        # Your awesome analysis logic here
        return {
            "awesomeness_score": 85.5,
            "patterns_found": ["awesome_pattern_1", "awesome_pattern_2"],
            "insights": ["Data shows high awesomeness potential"]
        }

    def _advanced_awesome_analysis(self, data_source: str, parameters: Dict) -> Dict:
        """Perform advanced awesome analysis"""
        # More sophisticated analysis
        return {
            "awesomeness_score": 92.3,
            "detailed_patterns": {
                "pattern_1": {"confidence": 0.95, "impact": "high"},
                "pattern_2": {"confidence": 0.87, "impact": "medium"}
            },
            "recommendations": ["Increase awesome factor by 15%"]
        }

    def _comprehensive_awesome_analysis(self, data_source: str, parameters: Dict) -> Dict:
        """Perform comprehensive awesome analysis"""
        # Most detailed analysis
        return {
            "executive_summary": "Data exhibits exceptional awesomeness",
            "detailed_metrics": {"score": 96.7, "rank": "excellent"},
            "full_report": "Complete awesome analysis report..."
        }

    def _format_output(self, result: Dict, output_format: str) -> Any:
        """Format analysis output"""
        if output_format == "json":
            return result
        elif output_format == "report":
            return self._generate_awesome_report(result)
        elif output_format == "visualization":
            return self._generate_awesome_visualization(result)
        else:
            return result

    def _generate_awesome_report(self, result: Dict) -> str:
        """Generate awesome report format"""
        return f"AWESOME ANALYSIS REPORT\n{'-'*30}\n{result}"

    def _generate_awesome_visualization(self, result: Dict) -> Dict:
        """Generate awesome visualization"""
        return {
            "chart_type": "awesome_chart",
            "data": result,
            "visualization_url": "/awesome/viz/123"
        }


# Export tool class for discovery
awesome_analyzer = AwesomeAnalyzer
```

### Step 4: Add Dependencies (Optional)

Create `plugins/my_awesome_plugin/requirements.txt`:

```txt
numpy>=1.21.0
pandas>=1.3.0
requests>=2.25.0
matplotlib>=3.5.0
```

### Step 5: Add Documentation

Create `plugins/my_awesome_plugin/README.md`:

````markdown
# My Awesome Plugin

## Overview

This plugin provides awesome functionality for Frappe Assistant Core.

## Features

- Awesome data analysis
- Advanced awesome processing
- Comprehensive awesome reporting

## Installation

1. Ensure dependencies are installed:
   ```bash
   pip install numpy pandas requests matplotlib
   ```
````

2. Enable plugin in Assistant Core Settings

## Usage

### Awesome Analyzer Tool

```json
{
  "tool": "awesome_analyzer",
  "arguments": {
    "data_source": "Customer",
    "analysis_type": "advanced",
    "output_format": "report"
  }
}
```

## Configuration

No additional configuration required.

## Troubleshooting

### Plugin Not Loading

- Check dependencies are installed
- Verify plugin validation passes
- Review error logs

````

## Advanced Plugin Features

### Custom Configuration

Create custom DocTypes for plugin configuration:

```python
# In plugin.py
def on_enable(self):
    super().on_enable()
    self._create_plugin_config()

def _create_plugin_config(self):
    """Create plugin configuration DocType if needed"""
    if not frappe.db.exists("DocType", "My Awesome Plugin Settings"):
        # Create custom DocType for plugin settings
        pass
````

### Plugin Dependencies

Handle dependencies between plugins:

```python
def validate_environment(self):
    # Check for other plugins
    plugin_manager = get_plugin_manager()

    if 'data_science' not in plugin_manager.loaded_plugins:
        return False, _("Requires Data Science plugin to be enabled")

    return super().validate_environment()
```

### Event Hooks

Register for Frappe events:

```python
def on_enable(self):
    super().on_enable()

    # Register for document events
    frappe.connect("before_save", self._on_document_save)
    frappe.connect("after_insert", self._on_document_insert)

def _on_document_save(self, doc, method):
    """Handle document save events"""
    if doc.doctype == "Customer":
        # Perform awesome processing
        pass
```

### Background Jobs

Schedule background processing:

```python
def on_enable(self):
    super().on_enable()
    self._schedule_awesome_jobs()

def _schedule_awesome_jobs(self):
    """Schedule background jobs"""
    frappe.enqueue(
        "my_awesome_plugin.tasks.process_awesome_data",
        queue="long",
        timeout=300,
        job_name="awesome_data_processing"
    )
```

### Custom APIs

Add plugin-specific API endpoints:

```python
# In plugin tools or separate file
@frappe.whitelist(allow_guest=False)
def awesome_api_endpoint():
    """Custom API endpoint for plugin"""
    frappe.only_for("System Manager")

    try:
        # Plugin-specific API logic
        return {"success": True, "data": "awesome_result"}
    except Exception as e:
        frappe.log_error(title="Awesome API Error", message=str(e))
        frappe.throw(_("API call failed: {0}").format(str(e)))
```

## Plugin Testing

### Unit Tests

Create `tests/test_my_awesome_plugin.py`:

```python
import unittest
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe_assistant_core.plugins.my_awesome_plugin.plugin import MyAwesomePlugin


class TestMyAwesomePlugin(FrappeTestCase):
    """Test My Awesome Plugin functionality"""

    def setUp(self):
        self.plugin = MyAwesomePlugin()

    def test_plugin_info(self):
        """Test plugin information"""
        info = self.plugin.get_info()

        self.assertEqual(info['name'], 'my_awesome_plugin')
        self.assertIn('description', info)
        self.assertIn('version', info)

    def test_environment_validation(self):
        """Test environment validation"""
        can_enable, error = self.plugin.validate_environment()

        # Should pass if dependencies are installed
        if can_enable:
            self.assertIsNone(error)
        else:
            self.assertIsNotNone(error)

    def test_plugin_tools(self):
        """Test plugin tool loading"""
        tools = self.plugin.get_tools()

        self.assertIn('awesome_analyzer', tools)
        self.assertTrue(len(tools) > 0)
```

### Integration Tests

Test tools through the MCP protocol:

```python
def test_awesome_analyzer_integration(self):
    """Test awesome analyzer through MCP"""
    from frappe_assistant_core.core.tool_registry import get_tool_registry

    registry = get_tool_registry()
    tool = registry.get_tool("awesome_analyzer")

    self.assertIsNotNone(tool)

    result = tool.execute({
        "data_source": "test_data",
        "analysis_type": "basic"
    })

    self.assertTrue(result["success"])
```

## Best Practices

### 1. Error Handling

```python
def execute(self, arguments):
    try:
        # Tool logic
        return {"success": True, "result": result}
    except CustomPluginError as e:
        # Handle plugin-specific errors
        return {"success": False, "error": str(e), "type": "plugin_error"}
    except Exception as e:
        # Handle unexpected errors
        frappe.log_error(title="Plugin Error", message=str(e))
        return {"success": False, "error": "Internal plugin error"}
```

### 2. Resource Management

```python
def execute(self, arguments):
    resource = None
    try:
        resource = acquire_expensive_resource()
        result = process_with_resource(resource)
        return {"success": True, "result": result}
    finally:
        if resource:
            release_resource(resource)
```

### 3. Configuration Management

```python
def get_plugin_config(self):
    """Get plugin configuration"""
    return frappe.cache().get_value(
        f"plugin_config:{self.get_info()['name']}",
        lambda: self._load_plugin_config()
    )
```

### 4. Logging

```python
def execute(self, arguments):
    self.logger.info(f"Starting awesome analysis for {arguments.get('data_source')}")

    try:
        result = self._perform_analysis(arguments)
        self.logger.info("Awesome analysis completed successfully")
        return result
    except Exception as e:
        self.logger.error(f"Awesome analysis failed: {str(e)}")
        raise
```

## Publishing Plugins

### 1. Plugin Package Structure

```
my_awesome_plugin/
├── setup.py                 # Python package setup
├── README.md                # Documentation
├── LICENSE                  # License file
├── requirements.txt         # Dependencies
├── my_awesome_plugin/       # Plugin code
│   ├── __init__.py
│   ├── plugin.py
│   └── tools/
└── tests/                   # Test suite
    └── test_plugin.py
```

### 2. Distribution

- Create Python package with `setup.py`
- Publish to PyPI or private repository
- Provide installation instructions
- Include comprehensive documentation

### 3. Versioning

- Follow semantic versioning (x.y.z)
- Maintain compatibility matrix
- Provide migration guides for breaking changes
- Test against multiple Frappe versions

## Troubleshooting

### Common Issues

1. **Plugin Not Discovered**

   - Check directory structure
   - Verify `plugin.py` exists
   - Check for syntax errors
   - Review discovery logs

2. **Validation Failures**

   - Install missing dependencies
   - Check permission requirements
   - Verify external service availability
   - Review validation error messages

3. **Tool Not Loading**

   - Check tool class names match file names
   - Verify inheritance from BaseTool
   - Check for import errors
   - Review tool registration logs

4. **Runtime Errors**
   - Check Frappe permissions
   - Verify plugin is enabled
   - Review error logs
   - Test with minimal arguments

### Debug Mode

Enable debug logging for plugins:

```python
# In plugin code
import logging
logging.getLogger("frappe_assistant_core").setLevel(logging.DEBUG)
```

This comprehensive guide should help you create powerful, maintainable plugins for Frappe Assistant Core. Remember to follow Frappe coding standards and thoroughly test your plugins before deployment.
