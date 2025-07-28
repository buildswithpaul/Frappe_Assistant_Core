"""
Tool Template for Frappe Assistant Core
Template for creating new tools using the clean architecture

Instructions:
1. Replace ExampleTool with your tool name (e.g., "SalesAnalyzer", "InventoryManager")
2. Replace example_tool with lowercase underscore version (e.g., "sales_analyzer", "inventory_manager")
3. Replace Example Category with your tool category (e.g., "Sales & Analytics", "Inventory Management")
4. Replace frappe_assistant_core with your app name if creating external app tool
5. Implement the execute() method with your business logic
6. Update the input schema and configuration as needed
7. Create corresponding test file using test_template.py

For External App Tools (Recommended):
- Place in: your_app/assistant_tools/example_tool.py
- Register in: your_app/hooks.py

For Internal Plugin Tools:
- Place in: frappe_assistant_core/plugins/[plugin_name]/tools/example_tool.py
- Register in: plugin.py get_tools() method
"""

import frappe
from frappe import _
from typing import Dict, Any, Optional, List
from frappe_assistant_core.core.base_tool import BaseTool


class ExampleTool(BaseTool):
    """
    [Brief description of what this tool does]
    
    Provides capabilities for:
    - [Main capability 1]
    - [Main capability 2]
    - [Main capability 3]
    
    Example usage:
    {
        "operation": "analyze",
        "doctype": "Sales Order",
        "filters": {"status": "Submitted"},
        "options": {"include_details": true}
    }
    """
    
    def __init__(self):
        super().__init__()
        self.name = "example_tool"
        self.description = self._get_description()
        self.category = "Example Category"
        
        # Set source app - use "frappe_assistant_core" for internal plugins
        # or your app name for external app tools
        self.source_app = "frappe_assistant_core"  # e.g., "your_app" or "frappe_assistant_core"
        
        # Optional: Declare dependencies for automatic validation
        self.dependencies = [
            # "pandas",    # Example: for data processing
            # "requests",  # Example: for API calls
        ]
        
        # Optional: Set permission requirements
        # Use None for no specific permission, or specify a DocType
        self.requires_permission = None  # or "Sales Order", "Customer", etc.
        
        # Tool-specific default configuration
        self.default_config = {
            "max_records": 1000,
            "timeout": 30,
            "cache_results": True,
            "default_filters": {},
            "output_format": "json"
        }
        
        # Define input schema for validation
        self.inputSchema = {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["analyze", "process", "export"],
                    "description": "Type of operation to perform"
                },
                "doctype": {
                    "type": "string",
                    "description": "Name of the DocType to operate on"
                },
                "filters": {
                    "type": "object",
                    "description": "Filter criteria for the operation",
                    "default": {}
                },
                "options": {
                    "type": "object",
                    "properties": {
                        "include_details": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include detailed information in results"
                        },
                        "output_format": {
                            "type": "string",
                            "enum": ["json", "csv", "excel"],
                            "default": "json",
                            "description": "Format for output data"
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 5000,
                            "default": 100,
                            "description": "Maximum number of records to process"
                        }
                    }
                }
            },
            "required": ["operation", "doctype"]
        }
    
    def _get_description(self) -> str:
        """Get rich formatted tool description"""
        return """[Detailed description of what the tool does]

🚀 **OPERATIONS:**
• Analyze - [Description of analyze operation]
• Process - [Description of process operation]
• Export - [Description of export operation]

📊 **FEATURES:**
• [Feature 1] - [Description]
• [Feature 2] - [Description]
• [Feature 3] - [Description]

⚙️ **CONFIGURATION:**
• Configurable limits and timeouts
• Multiple output formats supported
• Flexible filtering options"""
    
    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool operation"""
        operation = arguments.get("operation")
        doctype = arguments.get("doctype")
        filters = arguments.get("filters", {})
        options = arguments.get("options", {})
        
        # Get effective configuration (site > app > tool defaults)
        config = self.get_config()
        
        try:
            # Validate DocType exists
            if not frappe.db.exists("DocType", doctype):
                return {
                    "success": False,
                    "error": f"DocType '{doctype}' does not exist"
                }
            
            # Check permissions
            if not frappe.has_permission(doctype, "read"):
                return {
                    "success": False,
                    "error": f"No read permission for {doctype}"
                }
            
            # Route to specific operation
            if operation == "analyze":
                result = self._analyze_data(doctype, filters, options, config)
            elif operation == "process":
                result = self._process_data(doctype, filters, options, config)
            elif operation == "export":
                result = self._export_data(doctype, filters, options, config)
            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}"
                }
            
            return {
                "success": True,
                "operation": operation,
                "doctype": doctype,
                "filters_applied": filters,
                "result": result
            }
            
        except Exception as e:
            frappe.log_error(
                title=_("ExampleTool Error"),
                message=f"Error in {self.name}: {str(e)}"
            )
            
            return {
                "success": False,
                "error": str(e)
            }
    
    def _analyze_data(self, doctype: str, filters: Dict, options: Dict, config: Dict) -> Dict[str, Any]:
        """
        Analyze data based on the provided criteria
        
        Args:
            doctype: The DocType to analyze
            filters: Query filters
            options: Operation options
            config: Effective configuration
            
        Returns:
            Analysis results
        """
        # Get configuration values
        max_records = config.get("max_records", 1000)
        limit = min(options.get("limit", 100), max_records)
        include_details = options.get("include_details", False)
        
        # Build query filters
        query_filters = {**config.get("default_filters", {}), **filters}
        
        # Execute query
        documents = frappe.get_all(
            doctype,
            filters=query_filters,
            limit=limit,
            order_by="creation desc"
        )
        
        # Perform analysis
        analysis_result = {
            "total_records": len(documents),
            "summary": {
                "analyzed_count": len(documents),
                "filters_applied": query_filters,
                "analysis_timestamp": frappe.utils.now()
            }
        }
        
        if include_details:
            analysis_result["details"] = [
                {
                    "name": doc.name,
                    "analyzed": True,
                    # Add your analysis logic here
                }
                for doc in documents
            ]
        
        # TODO: Implement your specific analysis logic here
        # Examples:
        # - Calculate statistics (sum, average, count)
        # - Identify patterns or trends
        # - Generate insights
        # - Create summary reports
        
        return analysis_result
    
    def _process_data(self, doctype: str, filters: Dict, options: Dict, config: Dict) -> Dict[str, Any]:
        """
        Process data based on the provided criteria
        
        Args:
            doctype: The DocType to process
            filters: Query filters
            options: Operation options
            config: Effective configuration
            
        Returns:
            Processing results
        """
        # Get configuration values
        max_records = config.get("max_records", 1000)
        limit = min(options.get("limit", 100), max_records)
        
        # Build query filters
        query_filters = {**config.get("default_filters", {}), **filters}
        
        # Execute query
        documents = frappe.get_all(
            doctype,
            filters=query_filters,
            limit=limit,
            order_by="creation desc"
        )
        
        # Process documents
        processed_count = 0
        errors = []
        
        for doc in documents:
            try:
                # TODO: Implement your specific processing logic here
                # Examples:
                # - Update document fields
                # - Create related documents
                # - Send notifications
                # - Perform calculations
                # - Validate data
                
                processed_count += 1
                
            except Exception as e:
                errors.append({
                    "document": doc.name,
                    "error": str(e)
                })
        
        return {
            "processed_count": processed_count,
            "total_documents": len(documents),
            "errors": errors,
            "processing_timestamp": frappe.utils.now()
        }
    
    def _export_data(self, doctype: str, filters: Dict, options: Dict, config: Dict) -> Dict[str, Any]:
        """
        Export data based on the provided criteria
        
        Args:
            doctype: The DocType to export
            filters: Query filters
            options: Operation options
            config: Effective configuration
            
        Returns:
            Export results
        """
        # Get configuration values
        max_records = config.get("max_records", 1000)
        limit = min(options.get("limit", 100), max_records)
        output_format = options.get("output_format", config.get("output_format", "json"))
        
        # Build query filters
        query_filters = {**config.get("default_filters", {}), **filters}
        
        # Execute query
        documents = frappe.get_all(
            doctype,
            filters=query_filters,
            limit=limit,
            order_by="creation desc"
        )
        
        # Format data for export
        export_data = []
        for doc in documents:
            # Get full document data if needed
            full_doc = frappe.get_doc(doctype, doc.name)
            export_data.append({
                "name": doc.name,
                "data": full_doc.as_dict(),
                "export_timestamp": frappe.utils.now()
            })
        
        # Handle different export formats
        if output_format == "json":
            result = {
                "format": "json",
                "data": export_data
            }
        elif output_format == "csv":
            result = {
                "format": "csv",
                "message": "CSV export would be implemented here",
                "data": export_data
            }
        elif output_format == "excel":
            result = {
                "format": "excel", 
                "message": "Excel export would be implemented here",
                "data": export_data
            }
        else:
            result = {
                "format": "json",
                "data": export_data
            }
        
        return {
            "export_format": output_format,
            "exported_count": len(export_data),
            "result": result,
            "export_timestamp": frappe.utils.now()
        }


# Helper functions for complex operations
def perform_advanced_analysis(data: List[Dict], analysis_type: str) -> Dict[str, Any]:
    """
    Perform advanced analysis on the provided data
    
    Args:
        data: List of data records to analyze
        analysis_type: Type of analysis to perform
        
    Returns:
        Analysis results
    """
    # TODO: Implement advanced analysis logic
    # Examples:
    # - Statistical analysis
    # - Trend detection
    # - Pattern recognition
    # - Correlation analysis
    
    return {
        "analysis_type": analysis_type,
        "data_points": len(data),
        "results": {
            "summary": "Analysis completed",
            "insights": []
        }
    }


def validate_custom_permissions(operation: str, doctype: str) -> bool:
    """
    Validate custom permissions for the tool
    
    Args:
        operation: The operation being performed
        doctype: The DocType being accessed
        
    Returns:
        True if user has permission, False otherwise
    """
    # TODO: Implement custom permission logic
    # Examples:
    # - Check user roles
    # - Validate operation-specific permissions
    # - Check custom permission rules
    
    user_roles = frappe.get_roles()
    
    # Define role requirements for different operations
    required_roles = {
        "analyze": ["System Manager", "Analytics User"],
        "process": ["System Manager", "Data Processor"],
        "export": ["System Manager", "Data Exporter"]
    }
    
    if operation not in required_roles:
        return False
    
    return any(role in user_roles for role in required_roles[operation])


def get_custom_configuration() -> Dict[str, Any]:
    """
    Get custom configuration for the tool
    
    Returns:
        Configuration dictionary
    """
    # TODO: Implement configuration retrieval
    # This could read from:
    # - Frappe settings
    # - Custom DocTypes
    # - Configuration files
    # - Environment variables
    
    return {
        "feature_enabled": True,
        "advanced_mode": False,
        "custom_settings": {}
    }


# Export the tool class for discovery
# For external apps: This enables the tool to be discovered via hooks
# For internal plugins: The plugin.py file will reference this class
__all__ = ["ExampleTool"]


# Usage Examples (for documentation):
"""
External App Registration (in your_app/hooks.py):

assistant_tools = [
    "your_app.assistant_tools.example_tool.ExampleTool"
]

assistant_tool_configs = {
    "example_tool": {
        "max_records": 5000,
        "timeout": 60,
        "default_filters": {"status": "Active"}
    }
}

Internal Plugin Registration (in plugin.py):

class YourPlugin(BasePlugin):
    def get_tools(self):
        return ["example_tool"]

Example API Call:

{
    "tool": "example_tool",
    "arguments": {
        "operation": "analyze",
        "doctype": "Sales Order",
        "filters": {"status": "Submitted"},
        "options": {
            "include_details": true,
            "output_format": "json",
            "limit": 100
        }
    }
}
"""