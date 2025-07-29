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
Dashboard Chart Creator Tool - Create charts specifically for Frappe dashboards

Creates charts that are properly integrated with Frappe's dashboard system,
not standalone visualizations.
"""

import frappe
from frappe import _
import json
from typing import Dict, Any, Optional, List
from frappe_assistant_core.core.base_tool import BaseTool


class CreateDashboardChart(BaseTool):
    """
    Create charts specifically for Frappe dashboards.
    
    This tool creates Dashboard Chart documents that can be added to
    Frappe dashboards, not standalone image visualizations.
    """
    
    def __init__(self):
        super().__init__()
        self.name = "create_dashboard_chart"
        self.description = self._get_description()
        self.requires_permission = None
        
        self.inputSchema = {
            "type": "object",
            "properties": {
                "chart_name": {
                    "type": "string",
                    "description": "Name for the dashboard chart"
                },
                "chart_type": {
                    "type": "string",
                    "enum": ["line", "bar", "percentage", "pie", "donut", "heatmap"],
                    "description": "Visual chart type: 'line' for trends, 'bar' for comparisons, 'pie'/'donut' for proportions, 'percentage' for progress, 'heatmap' for density"
                },
                "doctype": {
                    "type": "string",
                    "description": "DocType to create chart from (e.g., 'Sales Invoice', 'Customer', 'Item')"
                },
                "aggregate_function": {
                    "type": "string",
                    "enum": ["Count", "Sum", "Average", "Group By"],
                    "default": "Count",
                    "description": "How to aggregate data: 'Count' for record counts, 'Sum' for totals, 'Average' for means, 'Group By' for grouping"
                },
                "value_based_on": {
                    "type": "string",
                    "description": "Field to aggregate when using Sum/Average (e.g., 'grand_total', 'qty', 'amount'). Required for Sum/Average functions."
                },
                "based_on": {
                    "type": "string",
                    "description": "Field to group data by (x-axis). For time series, use date fields. For categories, use text/link fields (e.g., 'customer', 'status', 'item_group')"
                },
                "time_series_based_on": {
                    "type": "string",
                    "description": "Date/datetime field for time series charts (e.g., 'posting_date', 'creation', 'transaction_date'). Required for line charts."
                },
                "timespan": {
                    "type": "string",
                    "enum": ["Last Year", "Last Quarter", "Last Month", "Last Week"],
                    "default": "Last Month",
                    "description": "Time range for the chart data (only applies to line/heatmap charts)"
                },
                "time_interval": {
                    "type": "string",
                    "enum": ["Yearly", "Quarterly", "Monthly", "Weekly", "Daily"],
                    "default": "Daily",
                    "description": "Time grouping interval for time series charts"
                },
                "filters": {
                    "type": "object",
                    "description": "Filters to apply to the data (e.g., {'status': 'Paid', 'company': 'My Company'})"
                },
                "color": {
                    "type": "string",
                    "description": "Chart color (hex code like '#5470c6' or color name)"
                },
                "dashboard_name": {
                    "type": "string",
                    "description": "Optional: Dashboard to add this chart to"
                }
            },
            "required": ["chart_name", "chart_type", "doctype", "aggregate_function"]
        }
    
    def _get_description(self) -> str:
        """Get tool description"""
        return """Create Dashboard Chart documents for Frappe's dashboard system with proper field mappings.

📊 **CHART TYPES (chart_type):**
• line - Trends over time (requires time_series_based_on)
• bar - Compare categories/groups (requires based_on for grouping)
• pie/donut - Show proportions (requires based_on for categories)
• percentage - Show progress/completion
• heatmap - Show data density patterns

📈 **AGGREGATION FUNCTIONS (aggregate_function):**
• Count - Count records (no value_based_on needed)
• Sum - Total values (requires value_based_on field)
• Average - Average values (requires value_based_on field)
• Group By - Group by categories

🔧 **FIELD REQUIREMENTS:**
• value_based_on: Required for Sum/Average (e.g., 'grand_total', 'qty')
• based_on: Required for grouping/x-axis in bar/pie/donut charts (e.g., 'customer', 'status')
• time_series_based_on: Required ONLY for line/heatmap charts (date fields like 'posting_date')

💡 **EXAMPLES:**
• Bar chart of sales by customer: chart_type='bar', based_on='customer', aggregate_function='Sum', value_based_on='grand_total'
• Line chart of monthly revenue: chart_type='line', time_series_based_on='posting_date', aggregate_function='Sum', value_based_on='grand_total'  
• Pie chart of status distribution: chart_type='pie', based_on='status', aggregate_function='Count'
• Simple count chart: chart_type='bar', aggregate_function='Count' (no grouping)"""
    
    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Create dashboard chart"""
        try:
            chart_name = arguments.get("chart_name")
            chart_type = arguments.get("chart_type")  # Visual type: line, bar, pie, etc.
            doctype = arguments.get("doctype")
            aggregate_function = arguments.get("aggregate_function", "Count")  # Aggregation: Count, Sum, Average
            
            # Validate doctype access
            if not frappe.has_permission(doctype, "read"):
                return {
                    "success": False,
                    "error": f"Insufficient permissions to access {doctype} data"
                }
            
            # Get DocType metadata for field validation
            meta = frappe.get_meta(doctype)
            available_fields = {f.fieldname: f for f in meta.fields}
            
            # Validate required fields based on aggregation function
            field_validation_result = self._validate_required_fields(arguments, available_fields, chart_type, aggregate_function)
            if not field_validation_result["success"]:
                return field_validation_result
            
            # Create the Dashboard Chart document with correct field mappings
            chart_doc = self._create_chart_document(chart_name, chart_type, doctype, arguments, aggregate_function)
            
            # Validate chart fields are appropriate for the DocType
            field_validation = self._validate_chart_fields_for_doctype(chart_doc.as_dict(), available_fields)
            if not field_validation["success"]:
                return {
                    "success": False,
                    "error": "; ".join(field_validation["errors"]),
                    "warnings": field_validation.get("warnings", []),
                    "error_type": "field_validation_error"
                }
            
            # Validate chart before creation (optional - skip if validation fails but still allow creation)
            validation_result = self._validate_chart_before_creation(chart_doc.as_dict())
            chart_validation_warning = None
            if not validation_result["success"]:
                chart_validation_warning = f"Chart validation warning: {validation_result.get('error', 'Unknown validation issue')}"
                validation_result = {"success": True, "data_points": 0, "chart_validated": False}
            
            chart_doc.insert()
            
            # Add to dashboard if specified
            dashboard_added = False
            if arguments.get("dashboard_name"):
                dashboard_added = self._add_to_dashboard(chart_doc.name, arguments["dashboard_name"])
            
            result = {
                "success": True,
                "chart_name": chart_name,
                "chart_id": chart_doc.name,
                "chart_type": chart_type,
                "aggregate_function": aggregate_function,
                "chart_url": f"/app/dashboard-chart/{chart_doc.name}",
                "added_to_dashboard": arguments.get("dashboard_name") if dashboard_added else None,
                "data_points": validation_result.get("data_points", 0),
                "chart_validated": validation_result.get("chart_validated", False)
            }
            
            # Include any warnings from field validation and chart validation
            field_warnings = field_validation_result.get("warnings", [])
            doctype_field_warnings = field_validation.get("warnings", [])
            chart_warnings = validation_result.get("warnings", [])
            all_warnings = field_warnings + doctype_field_warnings + chart_warnings
            
            # Add chart validation warning if present
            if chart_validation_warning:
                all_warnings.append(chart_validation_warning)
                
            if all_warnings:
                result["warnings"] = all_warnings
                
            return result
            
        except Exception as e:
            frappe.log_error(
                title=_("Dashboard Chart Creation Error"),
                message=f"Error creating chart {arguments.get('chart_name')}: {str(e)}"
            )
            
            return {
                "success": False,
                "error": str(e)
            }
    
    def _validate_required_fields(self, arguments: Dict, available_fields: Dict, chart_type: str, aggregate_function: str) -> Dict[str, Any]:
        """Validate required fields based on chart type and aggregation function"""
        errors = []
        warnings = []
        
        # Validate document_type is accessible
        doctype = arguments.get("doctype")
        if not frappe.has_permission(doctype, "read"):
            errors.append(f"No read permission for DocType '{doctype}'")
        
        # Validate Sum/Average requires value_based_on
        if aggregate_function in ["Sum", "Average"]:
            value_field = arguments.get("value_based_on")
            if not value_field:
                errors.append(f"{aggregate_function} aggregation requires 'value_based_on' field")
            elif value_field not in available_fields and value_field not in ["name", "creation", "modified"]:
                errors.append(f"Field '{value_field}' not found in {doctype}")
            elif value_field in available_fields:
                field_type = available_fields[value_field].fieldtype
                if field_type not in ["Int", "Float", "Currency", "Percent", "Data"]:
                    warnings.append(f"Field '{value_field}' is {field_type}, may not be suitable for {aggregate_function}")
        
        # Validate line and heatmap charts require time_series_based_on
        if chart_type in ["line", "heatmap"]:
            time_field = arguments.get("time_series_based_on")
            if not time_field:
                # Try to auto-detect
                time_field = self._detect_date_field(available_fields)
                if not time_field:
                    errors.append(f"{chart_type.title()} charts require 'time_series_based_on' field with a date/datetime field")
                else:
                    arguments["time_series_based_on"] = time_field
                    warnings.append(f"Auto-detected time field: {time_field}")
            elif time_field not in available_fields and time_field not in ["creation", "modified"]:
                errors.append(f"Time series field '{time_field}' not found in {doctype}")
            elif time_field in available_fields:
                field_type = available_fields[time_field].fieldtype
                if field_type not in ["Date", "Datetime"]:
                    errors.append(f"Time series field '{time_field}' must be Date or Datetime, got {field_type}")
        
        # Validate that non-time series charts don't have time_series_based_on when they should use based_on instead
        elif chart_type in ["bar", "pie", "donut", "percentage"]:
            time_field = arguments.get("time_series_based_on")
            if time_field:
                warnings.append(f"{chart_type.title()} charts don't need 'time_series_based_on'. Use 'based_on' for grouping instead.")
                # Don't auto-move it to based_on as user might have both specified
        
        # Validate bar/pie/donut charts need based_on for meaningful grouping
        if chart_type in ["bar", "pie", "donut"]:
            based_on = arguments.get("based_on")
            if not based_on:
                # Try to auto-detect grouping field
                based_on = self._detect_grouping_field(available_fields)
                if based_on:
                    arguments["based_on"] = based_on
                    warnings.append(f"Auto-detected grouping field: {based_on}")
                else:
                    warnings.append("No suitable grouping field found, using 'name' field")
            elif based_on in available_fields:
                field_type = available_fields[based_on].fieldtype
                if field_type not in ["Select", "Link", "Data", "Small Text"]:
                    warnings.append(f"Field '{based_on}' is {field_type}, may create too many groups")
        
        # Validate filters reference existing fields
        filters = arguments.get("filters", {})
        if filters:
            for field in filters.keys():
                if field not in available_fields and field not in ["name", "creation", "modified", "owner"]:
                    errors.append(f"Filter field '{field}' not found in {doctype}")
        
        if errors:
            return {
                "success": False,
                "error": "; ".join(errors),
                "warnings": warnings
            }
        
        result = {"success": True}
        if warnings:
            result["warnings"] = warnings
        
        return result
    
    def _create_chart_document(self, chart_name: str, chart_type: str, doctype: str, arguments: Dict, aggregate_function: str):
        """Create Dashboard Chart document with correct field mappings"""
        
        # Map visual chart types to Frappe's 'type' field
        visual_type_map = {
            "line": "Line",
            "bar": "Bar", 
            "pie": "Pie",
            "donut": "Donut",
            "percentage": "Percentage",
            "heatmap": "Heatmap"
        }
        
        # Create base chart document
        chart_data = {
            "doctype": "Dashboard Chart",
            "chart_name": chart_name,
            "type": visual_type_map.get(chart_type, "Bar"),  # Visual chart type
            "document_type": doctype,
            "filters_json": json.dumps(self._convert_filters_to_frappe_format(arguments.get("filters", {}), doctype))
        }
        
        # Configure chart based on Frappe's exact requirements
        has_grouping = arguments.get("based_on") and chart_type in ["bar", "pie", "donut"]
        
        if has_grouping:
            # GROUPING CHARTS: Use chart_type="Group By" 
            # This matches Frappe validation: if chart_type == "Group By", requires group_by_based_on
            chart_data["chart_type"] = "Group By"
            chart_data["group_by_based_on"] = arguments["based_on"]  # REQUIRED for Group By
            chart_data["group_by_type"] = aggregate_function  # Count, Sum, Average
            
            # For Sum/Average group by, need aggregate_function_based_on
            if aggregate_function in ["Sum", "Average"]:
                if arguments.get("value_based_on"):
                    chart_data["aggregate_function_based_on"] = arguments["value_based_on"]  # REQUIRED for Sum/Average Group By
                else:
                    return {
                        "success": False,
                        "error": f"value_based_on is required for {aggregate_function} aggregation with grouping"
                    }
            
        else:
            # TIME SERIES OR SIMPLE AGGREGATION: Use chart_type=Count/Sum/Average
            # This matches Frappe validation: if chart_type != "Group By", requires based_on
            chart_data["chart_type"] = aggregate_function  # Count, Sum, Average
            
            if chart_type in ["line", "heatmap"]:
                # Time series charts
                time_field = arguments.get("time_series_based_on") or self._detect_date_field(available_fields) or "creation"
                chart_data["based_on"] = time_field  # REQUIRED for non-Group By charts
                chart_data["timeseries"] = 1
                chart_data["timespan"] = arguments.get("timespan", "Last Month")
                chart_data["time_interval"] = arguments.get("time_interval", "Daily")
            else:
                # Simple aggregation charts (no grouping, no time series)
                # Still need based_on for Frappe validation, but timeseries=0
                chart_data["based_on"] = self._detect_date_field(available_fields) or "creation"  # REQUIRED for non-Group By charts
                chart_data["timeseries"] = 0
            
            # For Sum/Average, need value_based_on  
            if aggregate_function in ["Sum", "Average"]:
                if arguments.get("value_based_on"):
                    chart_data["value_based_on"] = arguments["value_based_on"]
                else:
                    return {
                        "success": False,
                        "error": f"value_based_on is required for {aggregate_function} aggregation"
                    }
        
        # Add color if specified
        if arguments.get("color"):
            chart_data["color"] = arguments["color"]
        
        # Debug logging to understand what's being created
        frappe.logger("dashboard_chart").info(f"Creating chart with data: {json.dumps(chart_data, indent=2)}")
        
        return frappe.get_doc(chart_data)
    
    def _convert_filters_to_frappe_format(self, filters: Dict, doctype: str) -> List:
        """Convert filters from dict format to Frappe's list format"""
        # Return empty list for no filters (Frappe handles this correctly)
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
    
    def _validate_chart_before_creation(self, chart_data: Dict) -> Dict[str, Any]:
        """Validate chart configuration by testing data retrieval"""
        try:
            # Test chart data retrieval using Frappe's dashboard chart logic
            from frappe.desk.doctype.dashboard_chart.dashboard_chart import get
            
            # Create a temporary chart object for testing
            test_chart = frappe._dict(chart_data)
            
            # Test data retrieval
            test_result = get(chart=test_chart)
            
            if not test_result or not test_result.get('data'):
                return {
                    "success": False,
                    "error": "Chart validation failed: No data returned from chart query",
                    "suggestion": "Check that the DocType has data matching the specified filters and fields"
                }
            
            return {
                "success": True,
                "data_points": len(test_result.get('data', [])),
                "chart_validated": True
            }
            
        except Exception as e:
            error_msg = str(e)
            
            # Provide specific guidance based on error
            if "does not exist" in error_msg.lower():
                return {
                    "success": False,
                    "error": f"Chart validation failed: {error_msg}",
                    "error_type": "field_not_found",
                    "suggestion": "Use get_doctype_info tool to verify field names exist in the target DocType"
                }
            elif "permission" in error_msg.lower():
                return {
                    "success": False,
                    "error": f"Chart validation failed: {error_msg}",
                    "error_type": "permission_error", 
                    "suggestion": "Ensure you have read permissions for the target DocType"
                }
            else:
                return {
                    "success": False,
                    "error": f"Chart validation failed: {error_msg}",
                    "error_type": "validation_error",
                    "suggestion": "Check chart configuration: field names, filters, and DocType access"
                }
    
    def _detect_date_field(self, available_fields: Dict) -> Optional[str]:
        """Auto-detect suitable date field for time series"""
        # Priority order for date fields (only check if they actually exist)
        priority_fields = ["posting_date", "transaction_date", "date", "creation", "modified"]
        
        # Only check priority fields that actually exist in the DocType
        for field_name in priority_fields:
            if field_name in available_fields:
                field = available_fields[field_name]
                if field.fieldtype in ["Date", "Datetime"]:
                    return field_name
            elif field_name in ["creation", "modified"]:
                # creation and modified always exist as system fields
                return field_name
        
        # Look for any date/datetime field that exists
        for field_name, field in available_fields.items():
            if field.fieldtype in ["Date", "Datetime"]:
                return field_name
        
        # If no date fields found, use creation as fallback
        return "creation"
    
    def _detect_grouping_field(self, available_fields: Dict) -> Optional[str]:
        """Auto-detect suitable grouping field based on DocType and available fields"""
        # Priority order for grouping fields (only check existing fields)  
        priority_fields = ["status", "type", "category", "group", "customer", "supplier", "item_code", "item_group"]
        
        # Only check priority fields that actually exist
        for field_name in priority_fields:
            if field_name in available_fields:
                field = available_fields[field_name]
                if field.fieldtype in ["Select", "Link", "Data", "Small Text"]:
                    return field_name
        
        # Look for any suitable grouping field
        for field_name, field in available_fields.items():
            if field.fieldtype in ["Select", "Link"] and not field.hidden:
                return field_name
        
        # Look for data fields that might be good for grouping
        for field_name, field in available_fields.items():
            if field.fieldtype in ["Data", "Small Text"] and not field.hidden:
                # Avoid fields that look like they contain unique values
                if not any(keyword in field_name.lower() for keyword in ["code", "number", "id", "name", "description"]):
                    return field_name
        
        return "name"  # Default to name field
    
    def _validate_chart_fields_for_doctype(self, chart_data: Dict, available_fields: Dict) -> Dict[str, Any]:
        """Validate that chart fields are appropriate for the target DocType"""
        warnings = []
        errors = []
        
        doctype = chart_data.get("document_type")
        timeseries_enabled = chart_data.get("timeseries")
        time_series_field = chart_data.get("based_on") if timeseries_enabled else None
        group_field = chart_data.get("group_by_based_on")  # Only for Group By charts
        value_field = chart_data.get("value_based_on")
        aggregate_field = chart_data.get("aggregate_function_based_on")  # Only for Group By with Sum/Average
        
        # Validate time series field exists and is date type (when time series is enabled)
        if timeseries_enabled and time_series_field and time_series_field not in ["creation", "modified"]:
            if time_series_field not in available_fields:
                errors.append(f"Time series field '{time_series_field}' does not exist in {doctype}")
            else:
                field = available_fields[time_series_field]
                if field.fieldtype not in ["Date", "Datetime"]:
                    errors.append(f"Time series field '{time_series_field}' is not a date field (type: {field.fieldtype})")
        
        # Validate grouping field exists
        if group_field and group_field not in ["name", "creation", "modified"]:
            if group_field not in available_fields:
                errors.append(f"Grouping field '{group_field}' does not exist in {doctype}")
            else:
                field = available_fields[group_field]
                if field.fieldtype not in ["Select", "Link", "Data", "Small Text", "Date", "Datetime"]:
                    warnings.append(f"Grouping field '{group_field}' ({field.fieldtype}) may create too many groups")
        
        # Validate value field for aggregation
        if value_field and value_field not in ["name", "creation", "modified"]:
            if value_field not in available_fields:
                errors.append(f"Value field '{value_field}' does not exist in {doctype}")
            else:
                field = available_fields[value_field]
                if field.fieldtype not in ["Int", "Float", "Currency", "Percent"]:
                    warnings.append(f"Value field '{value_field}' ({field.fieldtype}) may not be suitable for aggregation")
        
        # Validate aggregate function field for Group By charts
        if aggregate_field and aggregate_field not in ["name", "creation", "modified"]:
            if aggregate_field not in available_fields:
                errors.append(f"Aggregate field '{aggregate_field}' does not exist in {doctype}")
            else:
                field = available_fields[aggregate_field]
                if field.fieldtype not in ["Int", "Float", "Currency", "Percent"]:
                    warnings.append(f"Aggregate field '{aggregate_field}' ({field.fieldtype}) may not be suitable for aggregation")
        
        if errors:
            return {
                "success": False,
                "errors": errors,
                "warnings": warnings
            }
        
        return {
            "success": True,
            "warnings": warnings
        }
    
    def _add_to_dashboard(self, chart_id: str, dashboard_name: str) -> bool:
        """Add chart to existing dashboard"""
        try:
            dashboard = frappe.get_doc("Dashboard", dashboard_name)
            dashboard.append("charts", {
                "chart": chart_id,
                "width": "Half"
            })
            dashboard.save()
            return True
        except Exception as e:
            frappe.logger("dashboard_chart").warning(f"Failed to add chart to dashboard: {str(e)}")
            return False