# -*- coding: utf-8 -*-
# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Dashboard Manager Tool - Core dashboard creation and management

Provides comprehensive dashboard creation, management, and CRUD operations
for both Insights app and core Frappe Dashboard.
"""

import frappe
from frappe import _
import json
from typing import Dict, Any, List, Optional
from frappe_assistant_core.core.base_tool import BaseTool


class CreateDashboard(BaseTool):
    """
    Create Frappe dashboards with multiple charts.
    
    Creates dashboards in Frappe's Dashboard DocType with proper chart configuration
    and time series support. This is NOT for Insights app - it creates standard
    Frappe dashboards.
    """
    
    def __init__(self):
        super().__init__()
        self.name = "create_dashboard"
        self.description = self._get_description()
        self.requires_permission = None  # Permission checked dynamically per DocType
        
        self.inputSchema = {
            "type": "object",
            "properties": {
                "dashboard_name": {
                    "type": "string",
                    "description": "Dashboard title/name"
                },
                "doctype": {
                    "type": "string", 
                    "description": "Primary data source DocType"
                },
                "chart_configs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "chart_type": {
                                "type": "string",
                                "enum": ["bar", "line", "pie", "gauge", "kpi_card", "table", "funnel", "heatmap"],
                                "description": "Type of chart/widget"
                            },
                            "title": {"type": "string", "description": "Chart title"},
                            "x_field": {"type": "string", "description": "X-axis/grouping field (for bar/pie/donut charts)"},
                            "y_field": {"type": "string", "description": "Y-axis/value field (for Sum/Average aggregation)"},
                            "time_field": {"type": "string", "description": "Date/datetime field for line/heatmap charts (auto-detected if not specified)"},
                            "aggregate": {
                                "type": "string",
                                "enum": ["sum", "count", "avg", "min", "max"],
                                "default": "sum"
                            },
                            "filters": {"type": "object", "description": "Chart-specific filters"},
                            "time_span": {
                                "type": "string", 
                                "enum": ["Last Year", "Last Quarter", "Last Month", "Last Week"],
                                "description": "Time span for date-based data (matches Frappe Dashboard Chart timespan options)"
                            }
                        },
                        "required": ["chart_type", "title"]
                    },
                    "description": "Array of chart configurations"
                },
                "filters": {
                    "type": "object",
                    "description": "Global dashboard filters"
                },
                "share_with": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of users/roles to share dashboard with"
                },
                "auto_refresh": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable auto refresh"
                },
                "refresh_interval": {
                    "type": "string",
                    "enum": ["5_minutes", "15_minutes", "30_minutes", "1_hour", "24_hours"],
                    "default": "1_hour",
                    "description": "Auto refresh interval"
                },
                "template_type": {
                    "type": "string",
                    "enum": ["sales", "financial", "inventory", "hr", "executive", "custom"],
                    "default": "custom",
                    "description": "Dashboard template type"
                },
                "mobile_optimized": {
                    "type": "boolean",
                    "default": True,
                    "description": "Optimize for mobile viewing"
                }
            },
            "required": ["dashboard_name", "doctype", "chart_configs"]
        }
    
    def _get_description(self) -> str:
        """Get tool description"""
        return """Create Frappe dashboards with multiple charts. This creates standard Frappe Dashboard documents, NOT Insights dashboards.

📊 **WHAT THIS TOOL DOES:**
• Creates Frappe Dashboard DocType documents
• Adds multiple Dashboard Chart documents to the dashboard
• Configures sharing and permissions
• Sets up proper time series for charts

⚠️ **IMPORTANT:**
• This creates FRAPPE dashboards, not Insights dashboards
• Use create_dashboard_chart to create individual charts
• Charts must be created with proper time series configuration

📈 **CHART CONFIGURATION:**
• Each chart needs proper field mapping
• Line/heatmap charts need time fields (auto-detected if not specified)
• Bar/pie/donut charts use x_field for grouping
• Filters are applied at chart level

🔧 **FEATURES:**
• Multi-chart dashboards
• User/role based sharing
• Mobile responsive
• Export to PDF/Excel"""
    
    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Create comprehensive dashboard"""
        try:
            dashboard_name = arguments.get("dashboard_name")
            doctype = arguments.get("doctype") 
            chart_configs = arguments.get("chart_configs", [])
            filters = arguments.get("filters", {})
            share_with = arguments.get("share_with", [])
            auto_refresh = arguments.get("auto_refresh", True)
            refresh_interval = arguments.get("refresh_interval", "1_hour")
            template_type = arguments.get("template_type", "custom")
            mobile_optimized = arguments.get("mobile_optimized", True)
            
            # Validate doctype access
            if not frappe.has_permission(doctype, "read"):
                return {
                    "success": False,
                    "error": f"Insufficient permissions to access {doctype} data"
                }
            
            # Try Insights app first, fallback to Frappe Dashboard
            insights_result = self._create_insights_dashboard(
                dashboard_name, doctype, chart_configs, filters, 
                share_with, auto_refresh, refresh_interval, mobile_optimized
            )
            
            if insights_result["success"]:
                return insights_result
            
            # Fallback to Frappe Dashboard
            frappe_dashboard_result = self._create_frappe_dashboard(
                dashboard_name, doctype, chart_configs, filters,
                share_with, auto_refresh, mobile_optimized
            )
            
            return frappe_dashboard_result
            
        except Exception as e:
            frappe.log_error(
                title=_("Dashboard Creation Error"),
                message=f"Error creating dashboard {dashboard_name}: {str(e)}"
            )
            
            return {
                "success": False,
                "error": str(e),
                "dashboard_name": dashboard_name
            }
    
    def _create_insights_dashboard(self, dashboard_name: str, doctype: str, 
                                 chart_configs: List[Dict], filters: Dict,
                                 share_with: List[str], auto_refresh: bool,
                                 refresh_interval: str, mobile_optimized: bool) -> Dict[str, Any]:
        """Create dashboard in Insights app (primary method)"""
        try:
            # Check if Insights app is installed
            if not self._is_insights_available():
                return {
                    "success": False,
                    "error": "Insights app not available",
                    "fallback_required": True
                }
            
            # Create dashboard charts first (before dashboard creation)
            created_charts = []
            chart_links = []
            for i, chart_config in enumerate(chart_configs):
                chart_result = self._create_dashboard_chart(
                    None, doctype, chart_config, filters  # Pass None for dashboard_id initially
                )
                if chart_result["success"]:
                    created_charts.append(chart_result["chart_name"])
                    chart_links.append({
                        "chart": chart_result["chart_id"],
                        "width": "Half"
                    })
            
            # Only create dashboard if we have at least one chart (required field constraint)
            if not chart_links:
                return {
                    "success": False,
                    "error": "No valid charts could be created for dashboard",
                    "fallback_required": True
                }
            
            # Create Dashboard document with charts already populated
            dashboard_doc = frappe.get_doc({
                "doctype": "Dashboard",
                "dashboard_name": dashboard_name,
                "module": "Custom",
                "is_standard": 0,
                "charts": chart_links  # Populate with actual chart links
            })
            dashboard_doc.insert()
            
            # Setup sharing
            self._setup_dashboard_sharing(dashboard_doc.name, share_with)
            
            return {
                "success": True,
                "dashboard_type": "insights",
                "dashboard_name": dashboard_name,
                "dashboard_id": dashboard_doc.name,
                "dashboard_url": f"/app/dashboard/{dashboard_doc.name}",
                "charts_created": len(created_charts),
                "mobile_optimized": mobile_optimized,
                "auto_refresh_interval": refresh_interval,
                "charts": created_charts,
                "permissions": share_with,
                "template_used": "insights_dashboard"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Dashboard creation failed: {str(e)}",
                "fallback_required": True
            }
    
    def _create_frappe_dashboard(self, dashboard_name: str, doctype: str,
                               chart_configs: List[Dict], filters: Dict,
                               share_with: List[str], auto_refresh: bool,
                               mobile_optimized: bool) -> Dict[str, Any]:
        """Fallback dashboard creation using core Frappe Dashboard"""
        try:
            # Create dashboard charts first (before dashboard creation)
            created_charts = []
            chart_links = []
            for i, chart_config in enumerate(chart_configs):
                chart_result = self._create_dashboard_chart(
                    None, doctype, chart_config, filters  # Pass None for dashboard_id initially
                )
                if chart_result["success"]:
                    created_charts.append(chart_result["chart_name"])
                    chart_links.append({
                        "chart": chart_result["chart_id"],
                        "width": "Half"
                    })
            
            # Only create dashboard if we have at least one chart (required field constraint)
            if not chart_links:
                return {
                    "success": False,
                    "error": "No valid charts could be created for dashboard"
                }
            
            # Create Dashboard document with charts already populated
            dashboard_doc = frappe.get_doc({
                "doctype": "Dashboard",
                "dashboard_name": dashboard_name,
                "module": "Custom",
                "is_standard": 0,
                "charts": chart_links  # Populate with actual chart links
            })
            dashboard_doc.insert()
            
            # Setup permissions
            self._setup_dashboard_sharing(dashboard_doc.name, share_with)
            
            return {
                "success": True,
                "dashboard_type": "frappe_dashboard",
                "dashboard_name": dashboard_name,
                "dashboard_id": dashboard_doc.name,
                "dashboard_url": f"/app/dashboard/{dashboard_doc.name}",
                "charts_created": len(created_charts),
                "mobile_optimized": mobile_optimized,
                "auto_refresh_interval": "manual",
                "charts": created_charts,
                "permissions": share_with,
                "template_used": "frappe_dashboard"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Frappe dashboard creation failed: {str(e)}"
            }
    
    def _is_insights_available(self) -> bool:
        """Check if Insights app is installed and available"""
        try:
            return "insights" in frappe.get_installed_apps()
        except:
            return False
    
    def _create_dashboard_chart(self, dashboard_id: str, doctype: str,
                             chart_config: Dict, global_filters: Dict) -> Dict[str, Any]:
        """Create dashboard chart with proper configuration"""
        try:
            # Handle case where dashboard_id is None (creating charts before dashboard)
            suffix = dashboard_id if dashboard_id else "Chart"
            chart_name = f"{chart_config['title']} - {suffix}"
            
            # Get DocType metadata for field validation
            meta = frappe.get_meta(doctype)
            fields = {f.fieldname: f for f in meta.fields}
            
            # Proper chart type mapping
            chart_type_map = {
                "bar": "Bar",
                "line": "Line", 
                "pie": "Pie",
                "donut": "Donut",
                "percentage": "Percentage",
                "heatmap": "Heatmap"
            }
            
            # Proper aggregation mapping
            aggregate_map = {
                "sum": "Sum",
                "count": "Count", 
                "avg": "Average",
                "min": "Min",
                "max": "Max"
            }
            
            # Base chart configuration - CORRECTED FIELD MAPPINGS
            # Combine and convert filters to proper format
            combined_filters = {**global_filters, **chart_config.get("filters", {})}
            frappe_filters = self._convert_filters_to_frappe_format(combined_filters, doctype)
            
            chart_doc_data = {
                "doctype": "Dashboard Chart",
                "chart_name": chart_name,
                "chart_type": aggregate_map.get(chart_config.get("aggregate", "count"), "Count"),  # FIXED: aggregation function
                "type": chart_type_map.get(chart_config.get("chart_type", "bar"), "Bar"),          # FIXED: visual chart type
                "document_type": doctype,
                "filters_json": json.dumps(frappe_filters)
            }
            
            # Add grouping field for non-time series charts
            if chart_config.get("chart_type") not in ["line", "heatmap"]:
                chart_doc_data["group_by_based_on"] = chart_config.get("x_field", "name")
            
            # Add value field if specified
            if chart_config.get("y_field"):
                chart_doc_data["value_based_on"] = chart_config["y_field"]
            
            # Handle time series for line and heatmap charts
            if chart_config.get("chart_type") in ["line", "heatmap"]:
                # Auto-detect time field if not specified
                time_field = chart_config.get("time_field")
                if not time_field:
                    # Try common date fields that actually exist
                    priority_date_fields = ["posting_date", "transaction_date", "date", "creation", "modified"]
                    for field in priority_date_fields:
                        if field in fields:
                            # Check if it's actually a date field
                            field_obj = fields[field]
                            if field_obj.fieldtype in ["Date", "Datetime"]:
                                time_field = field
                                break
                        elif field in ["creation", "modified"]:
                            # System fields always available
                            time_field = field
                            break
                    
                    # If no priority fields found, look for any date field
                    if not time_field:
                        for field_name, field_obj in fields.items():
                            if field_obj.fieldtype in ["Date", "Datetime"]:
                                time_field = field_name
                                break
                    
                    # Final fallback
                    if not time_field:
                        time_field = "creation"
                
                if time_field:
                    chart_doc_data["based_on"] = time_field  # CORRECT: based_on is for time series date field
                    chart_doc_data["timeseries"] = 1  # CORRECT: timeseries is boolean flag to enable time series
                    chart_doc_data["timespan"] = chart_config.get("time_span", "Last Month")
                    chart_doc_data["time_interval"] = "Daily"  # Fixed value since create_dashboard doesn't expose this
            
            # Handle time-based filtering for other chart types
            elif chart_config.get("time_span"):
                # Find a suitable date field that actually exists
                time_field = None
                priority_date_fields = ["posting_date", "transaction_date", "date", "creation", "modified"]
                for field in priority_date_fields:
                    if field in fields:
                        # Check if it's actually a date field
                        field_obj = fields[field]
                        if field_obj.fieldtype in ["Date", "Datetime"]:
                            time_field = field
                            break
                    elif field in ["creation", "modified"]:
                        # System fields always available
                        time_field = field
                        break
                
                # If no priority fields found, look for any date field
                if not time_field:
                    for field_name, field_obj in fields.items():
                        if field_obj.fieldtype in ["Date", "Datetime"]:
                            time_field = field_name
                            break
                
                if time_field:
                    chart_doc_data["based_on"] = time_field  # CORRECT: based_on is for time series date field
                    chart_doc_data["timeseries"] = 1  # CORRECT: timeseries is boolean flag to enable time series
                    chart_doc_data["timespan"] = chart_config.get("time_span")
            
            # Create the chart
            chart_doc = frappe.get_doc(chart_doc_data)
            chart_doc.insert()
            
            return {
                "success": True,
                "chart_name": chart_name,
                "chart_id": chart_doc.name,
                "visual_chart_type": chart_doc.type,        # FIXED: Visual type (Bar, Line, etc.)
                "aggregation_function": chart_doc.chart_type, # FIXED: Aggregation (Count, Sum, etc.)
                "time_series_field": chart_doc_data.get("based_on") if chart_doc_data.get("timeseries") else None
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "chart_config": chart_config
            }
    
    def _convert_filters_to_frappe_format(self, filters: Dict, doctype: str) -> List:
        """Convert filters from dict format to Frappe's list format"""
        if not filters:
            return []
        
        frappe_filters = []
        for field, condition in filters.items():
            if isinstance(condition, list) and len(condition) == 2:
                # Convert {"field": ["operator", "value"]} to ["DocType", "field", "operator", "value"]
                operator, value = condition
                frappe_filters.append([doctype, field, operator, value])
            elif isinstance(condition, (str, int, float)):
                # Convert {"field": "value"} to ["DocType", "field", "=", "value"]
                frappe_filters.append([doctype, field, "=", condition])
            else:
                # Handle other formats - convert to equality check
                frappe_filters.append([doctype, field, "=", condition])
        
        return frappe_filters
    
    def _setup_dashboard_sharing(self, dashboard_id: str, share_with: List[str]) -> Dict[str, Any]:
        """Setup dashboard sharing and permissions"""
        users_with_access = []
        
        for user_or_role in share_with:
            try:
                if frappe.db.exists("User", user_or_role):
                    frappe.share.add("Dashboard", dashboard_id, user_or_role, read=1)
                    users_with_access.append(user_or_role)
                elif frappe.db.exists("Role", user_or_role):
                    role_users = frappe.get_all("Has Role", 
                        filters={"role": user_or_role}, 
                        fields=["parent"]
                    )
                    for role_user in role_users:
                        frappe.share.add("Dashboard", dashboard_id, role_user.parent, read=1)
                        users_with_access.append(role_user.parent)
            except Exception as e:
                frappe.logger("dashboard_manager").warning(f"Failed to share with {user_or_role}: {str(e)}")
        
        return {
            "users_with_access": list(set(users_with_access)),
            "shared_count": len(set(users_with_access))
        }