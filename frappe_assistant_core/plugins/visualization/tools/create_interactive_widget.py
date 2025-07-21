"""
Create Interactive Widget Tool - Dynamic dashboard components

Creates interactive widgets with drill-down, filtering,
and dynamic data refresh capabilities.
"""

import frappe
from frappe import _
from typing import Dict, Any
from frappe_assistant_core.core.base_tool import BaseTool


class CreateInteractiveWidget(BaseTool):
    """
    Tool for creating interactive dashboard widgets.
    
    Provides capabilities for:
    - Interactive charts with drill-down
    - Dynamic filters and controls
    - Real-time data refresh
    - Cross-widget interactions
    """
    
    def __init__(self):
        super().__init__()
        self.name = "create_interactive_widget"
        self.description = self._get_description()
        self.requires_permission = None  # Permission checked dynamically
        
        self.inputSchema = {
            "type": "object",
            "properties": {
                "widget_type": {
                    "type": "string",
                    "enum": [
                        "drill_down_chart", "filter_control", "dynamic_table", 
                        "real_time_metric", "alert_widget", "action_button"
                    ],
                    "description": "Type of interactive widget"
                },
                "title": {
                    "type": "string",
                    "description": "Widget title"
                },
                "data_source": {
                    "type": "object",
                    "properties": {
                        "doctype": {"type": "string"},
                        "fields": {"type": "array"},
                        "filters": {"type": "object"},
                        "refresh_interval": {"type": "integer"}
                    },
                    "description": "Widget data configuration"
                },
                "interactions": {
                    "type": "object",
                    "properties": {
                        "drill_down_levels": {"type": "array"},
                        "click_actions": {"type": "array"},
                        "filter_targets": {"type": "array"},
                        "hover_behaviors": {"type": "object"}
                    },
                    "description": "Interactive behavior configuration"
                },
                "appearance": {
                    "type": "object",
                    "properties": {
                        "size": {"type": "string"},
                        "position": {"type": "object"},
                        "theme": {"type": "string"},
                        "animation": {"type": "boolean"}
                    },
                    "description": "Widget appearance settings"
                },
                "real_time_settings": {
                    "type": "object",
                    "properties": {
                        "auto_refresh": {"type": "boolean"},
                        "refresh_interval": {"type": "integer"},
                        "alert_thresholds": {"type": "object"},
                        "notification_settings": {"type": "object"}
                    },
                    "description": "Real-time behavior configuration"
                }
            },
            "required": ["widget_type", "title", "data_source"]
        }
    
    def _get_description(self) -> str:
        """Get tool description"""
        return """Create interactive dashboard widgets with drill-down, real-time updates, filter controls, and cross-widget interactions."""
    
    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Create interactive widget"""
        try:
            # Import the actual interactive widgets manager
            from ..tools.interactive_widgets import InteractiveWidgets
            
            # Create interactive widgets manager and execute
            widget_manager = InteractiveWidgets()
            return widget_manager.execute(arguments)
            
        except Exception as e:
            frappe.log_error(
                title=_("Interactive Widget Creation Error"),
                message=f"Error creating interactive widget: {str(e)}"
            )
            
            return {
                "success": False,
                "error": str(e)
            }


# Make sure class name matches file name for discovery
create_interactive_widget = CreateInteractiveWidget