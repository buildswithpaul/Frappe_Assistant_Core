# External App Tool Development Guide

## Overview

This guide provides step-by-step instructions for creating tools in your custom Frappe apps that integrate seamlessly with Frappe Assistant Core. External app tools are the **recommended approach** for adding custom functionality while keeping your business logic separate from the core system.

## Why Use External App Tools?

### Benefits

- **🔄 No Core Modifications**: Keep your tools with your business logic
- **🚀 Easy Deployment**: Tools deploy with your app
- **⚙️ App-Specific Config**: Configure tools per your app's needs
- **🔒 Isolated Development**: Changes don't affect core system
- **📦 Version Control**: Tools follow your app's versioning
- **🎯 Business Focus**: Tools can be domain-specific

### Architecture

```
Your Frappe App
├── your_app/
│   ├── hooks.py                    # Register tools here
│   ├── assistant_tools/            # Tool directory
│   │   ├── __init__.py
│   │   ├── sales_analyzer.py       # Example tool
│   │   ├── inventory_manager.py    # Example tool
│   │   └── report_generator.py     # Example tool
│   └── config/
│       └── assistant_tools.json   # Optional: Tool configurations
```

## Step-by-Step Implementation

### Step 1: Create Tool Directory Structure

```bash
# Navigate to your app directory
cd apps/your_app

# Create the assistant tools directory
mkdir -p your_app/assistant_tools
touch your_app/assistant_tools/__init__.py
```

### Step 2: Create Your First Tool

Create `your_app/assistant_tools/sales_analyzer.py`:

```python
"""
Sales Analyzer Tool - Analyze sales data and generate insights
"""

import frappe
from frappe import _
from typing import Dict, Any, List
from frappe_assistant_core.core.base_tool import BaseTool


class SalesAnalyzer(BaseTool):
    """
    Tool for analyzing sales data and generating business insights.

    This tool provides comprehensive sales analysis including:
    - Revenue trends and patterns
    - Customer segmentation analysis
    - Product performance metrics
    - Sales forecasting
    """

    def __init__(self):
        super().__init__()
        self.name = "sales_analyzer"
        self.description = self._get_description()
        self.category = "Sales & Analytics"
        self.source_app = "your_app"  # Replace with your actual app name

        # Declare dependencies (optional)
        self.dependencies = ["pandas", "numpy"]

        # Set permission requirements (optional)
        self.requires_permission = "Sales Order"  # User needs Sales Order access

        # Define default configuration
        self.default_config = {
            "default_period": "monthly",
            "max_records": 10000,
            "include_cancelled": False,
            "cache_results": True,
            "export_formats": ["json", "excel", "pdf"]
        }

        # Define input schema for validation
        self.inputSchema = {
            "type": "object",
            "properties": {
                "analysis_type": {
                    "type": "string",
                    "enum": ["revenue", "customers", "products", "forecast"],
                    "description": "Type of sales analysis to perform"
                },
                "date_range": {
                    "type": "object",
                    "properties": {
                        "from_date": {
                            "type": "string",
                            "format": "date",
                            "description": "Start date for analysis (YYYY-MM-DD)"
                        },
                        "to_date": {
                            "type": "string",
                            "format": "date",
                            "description": "End date for analysis (YYYY-MM-DD)"
                        }
                    },
                    "required": ["from_date", "to_date"]
                },
                "filters": {
                    "type": "object",
                    "properties": {
                        "customer_group": {"type": "string"},
                        "territory": {"type": "string"},
                        "item_group": {"type": "string"},
                        "sales_person": {"type": "string"}
                    },
                    "description": "Optional filters for analysis"
                },
                "options": {
                    "type": "object",
                    "properties": {
                        "format": {
                            "type": "string",
                            "enum": ["json", "excel", "pdf"],
                            "default": "json"
                        },
                        "include_charts": {"type": "boolean", "default": True},
                        "detailed_breakdown": {"type": "boolean", "default": False}
                    }
                }
            },
            "required": ["analysis_type", "date_range"]
        }

    def _get_description(self) -> str:
        """Get rich formatted tool description"""
        return """Analyze sales data and generate comprehensive business insights.

📊 **ANALYSIS TYPES:**
• Revenue - Revenue trends, growth rates, and patterns
• Customers - Customer segmentation and behavior analysis
• Products - Product performance and profitability analysis
• Forecast - Sales forecasting and trend prediction

📅 **DATE RANGES:**
• Flexible date range selection
• Automatic period detection (daily, weekly, monthly, quarterly)
• Year-over-year and period-over-period comparisons

🎯 **FILTERS:**
• Customer Group, Territory, Item Group filtering
• Sales Person performance analysis
• Multi-dimensional data slicing

📈 **OUTPUT FORMATS:**
• JSON data for API integration
• Excel reports with charts and tables
• PDF executive summaries with visualizations"""

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the sales analysis"""
        analysis_type = arguments.get("analysis_type")
        date_range = arguments.get("date_range", {})
        filters = arguments.get("filters", {})
        options = arguments.get("options", {})

        # Get effective configuration
        config = self.get_config()

        try:
            # Validate date range
            from_date = date_range.get("from_date")
            to_date = date_range.get("to_date")

            if not from_date or not to_date:
                return {
                    "success": False,
                    "error": "Both from_date and to_date are required"
                }

            # Route to specific analysis method
            if analysis_type == "revenue":
                result = self._analyze_revenue(from_date, to_date, filters, options, config)
            elif analysis_type == "customers":
                result = self._analyze_customers(from_date, to_date, filters, options, config)
            elif analysis_type == "products":
                result = self._analyze_products(from_date, to_date, filters, options, config)
            elif analysis_type == "forecast":
                result = self._generate_forecast(from_date, to_date, filters, options, config)
            else:
                return {
                    "success": False,
                    "error": f"Unknown analysis type: {analysis_type}"
                }

            # Format output based on requested format
            output_format = options.get("format", "json")
            formatted_result = self._format_output(result, output_format, options)

            return {
                "success": True,
                "analysis_type": analysis_type,
                "date_range": date_range,
                "filters_applied": filters,
                "result": formatted_result
            }

        except Exception as e:
            frappe.log_error(
                title=_("Sales Analysis Error"),
                message=f"Error in sales analysis: {str(e)}"
            )

            return {
                "success": False,
                "error": str(e)
            }

    def _analyze_revenue(self, from_date: str, to_date: str, filters: Dict,
                        options: Dict, config: Dict) -> Dict[str, Any]:
        """Analyze revenue trends and patterns"""
        # Build the base query
        conditions = self._build_conditions(filters)

        # Execute revenue analysis query
        revenue_data = frappe.db.sql(f"""
            SELECT
                DATE(posting_date) as date,
                SUM(base_grand_total) as revenue,
                COUNT(*) as order_count,
                AVG(base_grand_total) as avg_order_value
            FROM `tabSales Order`
            WHERE posting_date BETWEEN %s AND %s
            AND docstatus = 1
            {conditions}
            GROUP BY DATE(posting_date)
            ORDER BY posting_date
        """, (from_date, to_date), as_dict=True)

        # Calculate summary metrics
        total_revenue = sum(row['revenue'] for row in revenue_data)
        total_orders = sum(row['order_count'] for row in revenue_data)
        avg_daily_revenue = total_revenue / len(revenue_data) if revenue_data else 0

        return {
            "summary": {
                "total_revenue": total_revenue,
                "total_orders": total_orders,
                "avg_daily_revenue": avg_daily_revenue,
                "avg_order_value": total_revenue / total_orders if total_orders else 0
            },
            "daily_data": revenue_data,
            "period": f"{from_date} to {to_date}"
        }

    def _analyze_customers(self, from_date: str, to_date: str, filters: Dict,
                          options: Dict, config: Dict) -> Dict[str, Any]:
        """Analyze customer behavior and segmentation"""
        conditions = self._build_conditions(filters)

        customer_data = frappe.db.sql(f"""
            SELECT
                customer,
                customer_name,
                SUM(base_grand_total) as total_revenue,
                COUNT(*) as order_count,
                AVG(base_grand_total) as avg_order_value,
                MIN(posting_date) as first_order,
                MAX(posting_date) as last_order
            FROM `tabSales Order`
            WHERE posting_date BETWEEN %s AND %s
            AND docstatus = 1
            {conditions}
            GROUP BY customer
            ORDER BY total_revenue DESC
            LIMIT %s
        """, (from_date, to_date, config.get("max_records", 1000)), as_dict=True)

        # Customer segmentation
        if customer_data:
            revenue_values = [c['total_revenue'] for c in customer_data]
            revenue_values.sort(reverse=True)

            # Simple segmentation (top 20%, middle 60%, bottom 20%)
            total_customers = len(customer_data)
            top_20_idx = int(total_customers * 0.2)
            top_80_idx = int(total_customers * 0.8)

            segments = {
                "high_value": customer_data[:top_20_idx],
                "medium_value": customer_data[top_20_idx:top_80_idx],
                "low_value": customer_data[top_80_idx:]
            }
        else:
            segments = {"high_value": [], "medium_value": [], "low_value": []}

        return {
            "total_customers": len(customer_data),
            "segments": {
                "high_value": {
                    "count": len(segments["high_value"]),
                    "customers": segments["high_value"][:10]  # Top 10 for display
                },
                "medium_value": {
                    "count": len(segments["medium_value"]),
                    "avg_revenue": sum(c['total_revenue'] for c in segments["medium_value"]) / len(segments["medium_value"]) if segments["medium_value"] else 0
                },
                "low_value": {
                    "count": len(segments["low_value"]),
                    "avg_revenue": sum(c['total_revenue'] for c in segments["low_value"]) / len(segments["low_value"]) if segments["low_value"] else 0
                }
            },
            "top_customers": customer_data[:10],
            "period": f"{from_date} to {to_date}"
        }

    def _analyze_products(self, from_date: str, to_date: str, filters: Dict,
                         options: Dict, config: Dict) -> Dict[str, Any]:
        """Analyze product performance and profitability"""
        conditions = self._build_conditions(filters)

        product_data = frappe.db.sql(f"""
            SELECT
                soi.item_code,
                soi.item_name,
                soi.item_group,
                SUM(soi.amount) as total_revenue,
                SUM(soi.qty) as total_quantity,
                AVG(soi.rate) as avg_rate,
                COUNT(DISTINCT so.name) as order_count
            FROM `tabSales Order Item` soi
            JOIN `tabSales Order` so ON soi.parent = so.name
            WHERE so.posting_date BETWEEN %s AND %s
            AND so.docstatus = 1
            {conditions.replace('WHERE', 'AND') if conditions else ''}
            GROUP BY soi.item_code
            ORDER BY total_revenue DESC
            LIMIT %s
        """, (from_date, to_date, config.get("max_records", 1000)), as_dict=True)

        # Calculate totals for percentage calculations
        total_revenue = sum(item['total_revenue'] for item in product_data)
        total_quantity = sum(item['total_quantity'] for item in product_data)

        # Add percentage calculations
        for item in product_data:
            item['revenue_percentage'] = (item['total_revenue'] / total_revenue * 100) if total_revenue else 0
            item['quantity_percentage'] = (item['total_quantity'] / total_quantity * 100) if total_quantity else 0

        return {
            "total_products": len(product_data),
            "total_revenue": total_revenue,
            "total_quantity": total_quantity,
            "top_products_by_revenue": product_data[:10],
            "product_summary": product_data,
            "period": f"{from_date} to {to_date}"
        }

    def _generate_forecast(self, from_date: str, to_date: str, filters: Dict,
                          options: Dict, config: Dict) -> Dict[str, Any]:
        """Generate sales forecast based on historical data"""
        # This is a simplified forecast - in production you might use more sophisticated models
        conditions = self._build_conditions(filters)

        # Get historical monthly data for trend analysis
        historical_data = frappe.db.sql(f"""
            SELECT
                YEAR(posting_date) as year,
                MONTH(posting_date) as month,
                SUM(base_grand_total) as revenue,
                COUNT(*) as order_count
            FROM `tabSales Order`
            WHERE posting_date BETWEEN DATE_SUB(%s, INTERVAL 12 MONTH) AND %s
            AND docstatus = 1
            {conditions}
            GROUP BY YEAR(posting_date), MONTH(posting_date)
            ORDER BY year, month
        """, (from_date, to_date), as_dict=True)

        if len(historical_data) >= 3:  # Need at least 3 months for basic trend
            # Simple linear trend calculation
            revenues = [row['revenue'] for row in historical_data]
            months = list(range(len(revenues)))

            # Calculate simple trend (linear regression would be better)
            if len(revenues) >= 2:
                recent_avg = sum(revenues[-3:]) / 3  # Last 3 months average
                older_avg = sum(revenues[-6:-3]) / 3 if len(revenues) >= 6 else revenues[0]  # Previous 3 months
                growth_rate = ((recent_avg - older_avg) / older_avg * 100) if older_avg else 0
            else:
                growth_rate = 0
                recent_avg = revenues[-1] if revenues else 0

            # Project next 3 months
            next_month_forecast = recent_avg * (1 + growth_rate / 100)

            forecast_data = {
                "historical_trend": historical_data,
                "growth_rate_percent": round(growth_rate, 2),
                "next_month_forecast": round(next_month_forecast, 2),
                "confidence_level": "medium" if len(historical_data) >= 6 else "low"
            }
        else:
            forecast_data = {
                "error": "Insufficient historical data for forecasting (minimum 3 months required)",
                "historical_data_points": len(historical_data)
            }

        return forecast_data

    def _build_conditions(self, filters: Dict) -> str:
        """Build SQL WHERE conditions from filters"""
        conditions = []

        if filters.get("customer_group"):
            conditions.append(f"customer_group = '{filters['customer_group']}'")

        if filters.get("territory"):
            conditions.append(f"territory = '{filters['territory']}'")

        if filters.get("sales_person"):
            conditions.append(f"EXISTS (SELECT 1 FROM `tabSales Team` st WHERE st.parent = name AND st.sales_person = '{filters['sales_person']}')")

        return "AND " + " AND ".join(conditions) if conditions else ""

    def _format_output(self, result: Dict, output_format: str, options: Dict) -> Any:
        """Format the analysis result based on requested output format"""
        if output_format == "json":
            return result
        elif output_format == "excel":
            return self._create_excel_report(result, options)
        elif output_format == "pdf":
            return self._create_pdf_report(result, options)
        else:
            return result

    def _create_excel_report(self, result: Dict, options: Dict) -> Dict[str, str]:
        """Create Excel report from analysis result"""
        # In a real implementation, you would use openpyxl or xlsxwriter
        # to create an actual Excel file and return the file path/URL
        return {
            "format": "excel",
            "message": "Excel report generation would be implemented here",
            "data": result
        }

    def _create_pdf_report(self, result: Dict, options: Dict) -> Dict[str, str]:
        """Create PDF report from analysis result"""
        # In a real implementation, you would use reportlab or weasyprint
        # to create an actual PDF file and return the file path/URL
        return {
            "format": "pdf",
            "message": "PDF report generation would be implemented here",
            "data": result
        }


# Export the tool class for discovery
__all__ = ["SalesAnalyzer"]
```

### Step 3: Register Tool in App Hooks

Update your `your_app/hooks.py`:

```python
# your_app/hooks.py

# ... existing hooks ...

# Register tools with Frappe Assistant Core
assistant_tools = [
    "your_app.assistant_tools.sales_analyzer.SalesAnalyzer",
    # Add more tools here as you create them
    # "your_app.assistant_tools.inventory_manager.InventoryManager",
    # "your_app.assistant_tools.report_generator.ReportGenerator",
]

# Optional: App-level tool configuration overrides
assistant_tool_configs = {
    "sales_analyzer": {
        "max_records": 5000,  # Override default of 10000
        "default_period": "quarterly",  # Override default of "monthly"
        "cache_results": True,
        "export_formats": ["json", "excel"]  # Remove PDF if not needed
    }
}
```

### Step 4: Add Site-Level Configuration (Optional)

In your `sites/your_site/site_config.json`, you can override configurations:

```json
{
  "assistant_tools": {
    "sales_analyzer": {
      "max_records": 15000,
      "include_cancelled": true,
      "cache_results": false
    }
  }
}
```

### Step 5: Test Your Tool

Create a test file `your_app/tests/test_sales_analyzer.py`:

```python
import frappe
import unittest
from datetime import datetime, timedelta
from frappe_assistant_core.core.tool_registry import get_tool_registry


class TestSalesAnalyzer(unittest.TestCase):
    """Test the sales analyzer tool"""

    def setUp(self):
        """Set up test environment"""
        self.registry = get_tool_registry()
        self.tool_name = "sales_analyzer"

    def test_tool_discovery(self):
        """Test that the tool is discovered correctly"""
        tools = self.registry.get_all_tools()
        self.assertIn(self.tool_name, tools)

        tool = self.registry.get_tool(self.tool_name)
        self.assertIsNotNone(tool)
        self.assertEqual(tool.source_app, "your_app")
        self.assertEqual(tool.category, "Sales & Analytics")

    def test_tool_execution_revenue_analysis(self):
        """Test revenue analysis execution"""
        tool = self.registry.get_tool(self.tool_name)

        # Test with valid date range
        from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")

        result = tool.execute({
            "analysis_type": "revenue",
            "date_range": {
                "from_date": from_date,
                "to_date": to_date
            }
        })

        self.assertTrue(result.get("success"))
        self.assertIn("result", result)
        self.assertIn("summary", result["result"])

    def test_tool_execution_invalid_date(self):
        """Test tool handles invalid date gracefully"""
        tool = self.registry.get_tool(self.tool_name)

        result = tool.execute({
            "analysis_type": "revenue",
            "date_range": {
                "from_date": "invalid-date",
                "to_date": "2024-01-01"
            }
        })

        self.assertFalse(result.get("success"))
        self.assertIn("error", result)

    def test_configuration_hierarchy(self):
        """Test configuration hierarchy works"""
        tool = self.registry.get_tool(self.tool_name)
        config = tool.get_config()

        # Should include all configuration levels
        self.assertIn("max_records", config)
        self.assertIn("default_period", config)
        self.assertIn("cache_results", config)


if __name__ == "__main__":
    unittest.main()
```

### Step 6: Run Tests

```bash
# Run the specific test
bench run-tests --app your_app --module your_app.tests.test_sales_analyzer

# Or run all tests for your app
bench run-tests --app your_app
```

## Advanced Features

### Configuration Management

Tools support a three-level configuration hierarchy:

1. **Tool Defaults** (in tool code)
2. **App-Level Overrides** (in hooks.py)
3. **Site-Level Overrides** (in site_config.json)

```python
# In your tool's execute method
config = self.get_config()
max_records = config.get("max_records", 1000)  # Gets resolved value
```

### Dependency Management

Declare dependencies for automatic validation:

```python
class MyTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.dependencies = [
            "pandas",           # Required for data processing
            "numpy",            # Required for calculations
            "matplotlib",       # Optional for charts
            "your_custom_lib"   # Your custom modules
        ]
```

### Permission Integration

Control tool access based on Frappe permissions:

```python
class MyTool(BaseTool):
    def __init__(self):
        super().__init__()
        # Require specific DocType permission
        self.requires_permission = "Sales Order"

        # Or check custom permissions in execute method

    def execute(self, arguments):
        # Custom permission check
        if not frappe.has_permission("Customer", "read"):
            return {"success": False, "error": "Insufficient permissions"}

        # Tool logic...
```

## Discovery and Hooks Integration

### How Tool Discovery Works

1. **Frappe App Hooks**: Your app declares tools in `hooks.py`
2. **Plugin Manager**: Scans all installed apps for `assistant_tools` hook
3. **Tool Loading**: Imports and instantiates declared tool classes
4. **Registry**: Makes tools available through unified interface

### Hook Configuration

```python
# In your_app/hooks.py

# Basic tool registration
assistant_tools = [
    "your_app.assistant_tools.sales_analyzer.SalesAnalyzer"
]

# Advanced hook with conditional loading
def get_assistant_tools():
    """Dynamically determine which tools to load"""
    tools = ["your_app.assistant_tools.sales_analyzer.SalesAnalyzer"]

    # Conditionally add tools based on app settings
    if frappe.db.get_single_value("Your App Settings", "enable_advanced_analytics"):
        tools.append("your_app.assistant_tools.advanced_analytics.AdvancedAnalytics")

    return tools

assistant_tools = get_assistant_tools
```

## Best Practices

### 1. Tool Design

- **Single Responsibility**: Each tool should have one clear purpose
- **Descriptive Names**: Use clear, action-oriented tool names
- **Rich Descriptions**: Provide detailed descriptions with examples
- **Input Validation**: Always validate inputs using JSON schema

### 2. Error Handling

```python
def execute(self, arguments):
    try:
        # Tool logic
        return {"success": True, "result": result}
    except PermissionError as e:
        return {"success": False, "error": "Permission denied", "type": "permission"}
    except ValidationError as e:
        return {"success": False, "error": str(e), "type": "validation"}
    except Exception as e:
        frappe.log_error(title="Tool Error", message=str(e))
        return {"success": False, "error": "Internal error", "type": "system"}
```

### 3. Performance

- **Database Queries**: Use efficient queries with proper indexing
- **Caching**: Cache expensive operations when possible
- **Pagination**: Limit result sets for large datasets
- **Async Operations**: Consider background jobs for long-running tasks

### 4. Security

- **Permission Checks**: Always validate user permissions
- **Input Sanitization**: Sanitize all user inputs
- **SQL Injection**: Use parameterized queries
- **Sensitive Data**: Never log sensitive information

### 5. Testing

- **Unit Tests**: Test individual tool functions
- **Integration Tests**: Test tool discovery and execution
- **Permission Tests**: Verify permission checks work
- **Error Tests**: Test error handling scenarios

## Deployment Checklist

### Pre-Deployment

- [ ] All tools have comprehensive tests
- [ ] Documentation is complete and accurate
- [ ] Permission requirements are clearly defined
- [ ] Configuration options are documented
- [ ] Dependencies are declared and available

### Deployment

```bash
# Install/update your app
bench get-app your_app
bench install-app your_app

# Or if already installed
bench update --pull

# Restart to reload hooks
bench restart

# Verify tool discovery
bench console
>>> from frappe_assistant_core.core.tool_registry import get_tool_registry
>>> registry = get_tool_registry()
>>> tools = registry.get_all_tools()
>>> print([t for t in tools.keys() if 'your_tool_name' in t])
```

### Post-Deployment

- [ ] Verify tools appear in Assistant Core Settings
- [ ] Test tool execution through API
- [ ] Check logs for any errors
- [ ] Verify permissions work correctly
- [ ] Monitor tool performance

## Troubleshooting

### Common Issues

1. **Tool Not Discovered**

   - Check hooks.py syntax
   - Verify import paths are correct
   - Ensure `__init__.py` files exist
   - Check for Python syntax errors in tool files

2. **Permission Errors**

   - Verify user has required DocType permissions
   - Check `requires_permission` setting
   - Test with System Manager role

3. **Import Errors**

   - Check all dependencies are installed
   - Verify import paths in tool files
   - Check for circular imports

4. **Configuration Not Working**
   - Verify JSON syntax in site_config.json
   - Check configuration key names match exactly
   - Test configuration hierarchy

### Debug Mode

Enable detailed logging:

```python
# In your tool
import logging
logger = logging.getLogger("your_app.assistant_tools")
logger.setLevel(logging.DEBUG)

def execute(self, arguments):
    logger.debug(f"Executing {self.name} with arguments: {arguments}")
    # Tool logic...
```

## Support and Resources

- **Core Documentation**: See ARCHITECTURE.md for system overview
- **Tool Templates**: See TOOL_DEVELOPMENT_TEMPLATES.md for more examples
- **Plugin Development**: See PLUGIN_DEVELOPMENT.md for internal plugins
- **Frappe Framework**: [Frappe Documentation](https://frappeframework.com/docs)

This guide provides everything you need to create powerful, production-ready tools in your Frappe apps that integrate seamlessly with Frappe Assistant Core.
