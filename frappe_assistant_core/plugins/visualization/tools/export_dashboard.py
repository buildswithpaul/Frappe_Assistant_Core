"""
Export Dashboard Tool - Dashboard export in multiple formats

Exports dashboards to PDF, Excel, PowerPoint, and image formats
with professional formatting and customization options.
"""

import frappe
from frappe import _
from typing import Dict, Any
from frappe_assistant_core.core.base_tool import BaseTool


class ExportDashboard(BaseTool):
    """
    Tool for exporting dashboards in various formats.
    
    Provides capabilities for:
    - Multi-format export (PDF, Excel, PNG, PowerPoint)
    - Professional formatting and styling
    - Scheduled report generation
    - Bulk export operations
    """
    
    def __init__(self):
        super().__init__()
        self.name = "export_dashboard"
        self.description = self._get_description()
        self.requires_permission = None  # Permission checked dynamically
        
        self.input_schema = {
            "type": "object",
            "properties": {
                "dashboard_name": {
                    "type": "string",
                    "description": "Name of dashboard to export"
                },
                "export_format": {
                    "type": "string",
                    "enum": ["pdf", "excel", "png", "powerpoint", "csv", "json"],
                    "description": "Export format"
                },
                "include_data": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include underlying data in export"
                },
                "layout_options": {
                    "type": "object",
                    "properties": {
                        "page_orientation": {"type": "string", "enum": ["portrait", "landscape"]},
                        "page_size": {"type": "string", "enum": ["A4", "A3", "Letter", "Legal"]},
                        "include_header": {"type": "boolean"},
                        "include_footer": {"type": "boolean"},
                        "charts_per_page": {"type": "integer"}
                    },
                    "description": "Layout and formatting options"
                },
                "branding": {
                    "type": "object",
                    "properties": {
                        "company_logo": {"type": "boolean"},
                        "watermark": {"type": "string"},
                        "custom_header": {"type": "string"},
                        "custom_footer": {"type": "string"}
                    },
                    "description": "Branding and customization options"
                },
                "filters": {
                    "type": "object",
                    "description": "Apply filters before export"
                },
                "schedule": {
                    "type": "object",
                    "properties": {
                        "enabled": {"type": "boolean"},
                        "frequency": {"type": "string", "enum": ["daily", "weekly", "monthly"]},
                        "recipients": {"type": "array"},
                        "email_subject": {"type": "string"}
                    },
                    "description": "Scheduled export settings"
                }
            },
            "required": ["dashboard_name", "export_format"]
        }
    
    def _get_description(self) -> str:
        """Get tool description"""
        return """Export dashboards in professional formats with customization and scheduling capabilities.

📎 **EXPORT FORMATS:**
• PDF Reports - Professional presentation format
• Excel Workbooks - Data analysis and manipulation
• PowerPoint Slides - Executive presentations
• PNG Images - High-quality dashboard screenshots
• CSV Data - Raw data for further analysis
• JSON Format - Structured data export

📝 **PROFESSIONAL FORMATTING:**
• Corporate Templates - Business-ready layouts
• Page Layout Control - Portrait/landscape, sizes
• Header/Footer - Company branding and metadata
• Chart Arrangement - Optimal spacing and sizing
• Logo Integration - Company branding inclusion

📅 **SCHEDULED EXPORTS:**
• Automated Reports - Daily, weekly, monthly delivery
• Email Distribution - Automatic recipient delivery
• Custom Scheduling - Specific dates and times
• Report Subscriptions - User-managed preferences

⚙️ **ADVANCED OPTIONS:**
• Filter Application - Export with specific data filters
• Data Inclusion - Choose chart only or chart + data
• Bulk Export - Multiple dashboards at once
• Custom Watermarks - Security and ownership marking
• Quality Settings - Resolution and compression control"""
    
    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Export dashboard"""
        try:
            # Import the actual export manager
            from ..tools.sharing_manager import ExportDashboard as ExportDashboardImpl
            
            # Create export manager and execute
            export_manager = ExportDashboardImpl()
            return export_manager.execute(arguments)
            
        except Exception as e:
            frappe.log_error(
                title=_("Dashboard Export Error"),
                message=f"Error exporting dashboard: {str(e)}"
            )
            
            return {
                "success": False,
                "error": str(e)
            }


# Make sure class name matches file name for discovery
export_dashboard = ExportDashboard