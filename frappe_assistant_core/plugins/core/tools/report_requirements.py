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
Report Requirements Tool for Core Plugin.
Understand report requirements, structure, and metadata before execution.
"""

import frappe
from frappe import _
from typing import Dict, Any
from frappe_assistant_core.core.base_tool import BaseTool


class ReportRequirements(BaseTool):
    """
    Tool for analyzing report requirements, structure, and metadata.
    
    Provides capabilities for:
    - Required filter discovery
    - Column structure analysis
    - Report metadata and configuration
    - Filter guidance for complex reports
    - Error prevention for report execution
    """
    
    def __init__(self):
        super().__init__()
        self.name = "report_requirements"
        self.description = "📋 REPORT REQUIREMENTS ANALYZER - Understand what you need before running reports! 🎯 **ESSENTIAL FOR**: Discovering required filters when generate_report fails, understanding what data inputs are needed, preventing filter errors before execution, planning successful report runs 💡 **USE WHEN**: Generate_report gives you filter errors, need to know what options are available, planning complex report execution, understanding report capabilities ⚡ **PREVENTS ERRORS**: Shows exactly what filters are required and optional for successful report execution, plus complete report metadata and structure"
        self.requires_permission = None  # Permission checked dynamically per report
        
        self.inputSchema = {
            "type": "object",
            "properties": {
                "report_name": {
                    "type": "string", 
                    "description": "Exact name of the Frappe report to analyze (e.g., 'Sales Analytics', 'Accounts Receivable Summary'). This helps understand available fields, required filters, and report structure before execution."
                },
                "include_metadata": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to include technical metadata (creation date, owner, SQL query, etc.) - useful for developers and administrators."
                },
                "include_columns": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to include column structure information."
                },
                "include_filters": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to include filter requirements and guidance."
                }
            },
            "required": ["report_name"]
        }
    
    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute report requirements analysis"""
        report_name = arguments.get("report_name")
        include_metadata = arguments.get("include_metadata", False)
        include_columns = arguments.get("include_columns", True)
        include_filters = arguments.get("include_filters", True)
        
        try:
            # Import the report implementation for column analysis
            from .report_tools import ReportTools
            
            # Get basic column and filter info from existing implementation
            column_result = ReportTools.get_report_columns(report_name)
            
            if not column_result.get("success", False):
                return column_result
            
            # Start building comprehensive response
            result = {
                "success": True,
                "report_name": report_name,
                "report_type": column_result.get("report_type"),
            }
            
            # Add columns if requested
            if include_columns:
                result["columns"] = column_result.get("columns", [])
            
            # Add filter guidance if requested
            if include_filters:
                if "filter_guidance" in column_result:
                    result["filter_guidance"] = column_result["filter_guidance"]
                
                # Add filter requirements analysis
                result["filter_requirements"] = self._analyze_filter_requirements(report_name, column_result.get("report_type"))
            
            # Add comprehensive metadata if requested
            if include_metadata:
                metadata = self._get_comprehensive_metadata(report_name)
                if metadata:
                    result["metadata"] = metadata
            
            return result
            
        except Exception as e:
            frappe.log_error(
                title=_("Report Requirements Error"),
                message=f"Error analyzing report requirements: {str(e)}"
            )
            
            return {
                "success": False,
                "error": str(e)
            }
    
    def _analyze_filter_requirements(self, report_name: str, report_type: str) -> Dict[str, Any]:
        """Analyze filter requirements for the report"""
        requirements = {
            "common_required_filters": [],
            "common_optional_filters": [],
            "guidance": []
        }
        
        # Add specific guidance based on report name patterns
        report_lower = report_name.lower()
        
        if "sales_analytics" in report_lower or "sales analytics" in report_lower:
            requirements["common_required_filters"] = [
                "doc_type (Sales Invoice, Sales Order, Quotation, etc.)",
                "tree_type (Customer, Item, Territory, etc.)",
                "value_quantity (Value or Quantity)"
            ]
            requirements["common_optional_filters"] = [
                "from_date and to_date (defaults to current fiscal year)",
                "company (uses default company if not specified)"
            ]
            requirements["guidance"].append("For Sales Analytics: Use doc_type='Sales Invoice', tree_type='Customer', and value_quantity='Value' for customer-wise revenue analysis")
            
        elif "quotation trends" in report_lower:
            requirements["common_required_filters"] = [
                "based_on (Item, Customer, Territory, etc.)"
            ]
            requirements["common_optional_filters"] = [
                "from_date and to_date (defaults to current fiscal year)",
                "company (uses default company if not specified)"
            ]
            requirements["guidance"].append("For Quotation Trends: based_on field is mandatory - use 'Item' for item-wise trends or 'Customer' for customer-wise analysis")
            
        elif "profit" in report_lower and "loss" in report_lower:
            requirements["common_required_filters"] = ["company", "from_date", "to_date"]
            requirements["guidance"].append("P&L Statement requires company and date range for financial period analysis")
            
        elif "receivable" in report_lower:
            requirements["common_required_filters"] = ["company"]
            requirements["common_optional_filters"] = ["customer", "as_on_date"]
            requirements["guidance"].append("Accounts Receivable typically needs company filter, optionally filter by specific customer")
            
        elif "balance_sheet" in report_lower or "balance sheet" in report_lower:
            requirements["common_required_filters"] = ["company", "as_on_date"]
            requirements["guidance"].append("Balance Sheet requires company and specific date for financial position")
            
        # General guidance based on report type
        if report_type == "Script Report":
            requirements["guidance"].append("Script Reports often have mandatory filters - check report definition or try execution to discover requirements")
        elif report_type == "Query Report":
            requirements["guidance"].append("Query Reports may require company or date filters depending on the underlying query")
        
        return requirements
    
    def _get_comprehensive_metadata(self, report_name: str) -> Dict[str, Any]:
        """Get comprehensive report metadata - merged from get_report_data functionality"""
        try:
            # Check if report exists
            if not frappe.db.exists("Report", report_name):
                return {"error": f"Report '{report_name}' not found"}
            
            # Get report document
            report = frappe.get_doc("Report", report_name)
            
            # Check permission
            if not frappe.has_permission("Report", "read", report):
                return {"error": f"Insufficient permissions to access report '{report_name}'"}
            
            # Build comprehensive metadata
            metadata = {
                "basic_info": {
                    "name": getattr(report, 'name', ''),
                    "report_name": getattr(report, 'report_name', ''),
                    "report_type": getattr(report, 'report_type', ''),
                    "module": getattr(report, 'module', ''),
                    "is_standard": getattr(report, 'is_standard', False),
                    "disabled": getattr(report, 'disabled', False),
                    "description": getattr(report, 'description', ''),
                    "ref_doctype": getattr(report, 'ref_doctype', ''),
                },
                "system_info": {
                    "creation": str(getattr(report, 'creation', '')),
                    "modified": str(getattr(report, 'modified', '')),
                    "owner": getattr(report, 'owner', ''),
                    "modified_by": getattr(report, 'modified_by', '')
                }
            }
            
            # Add type-specific technical information
            report_type = getattr(report, 'report_type', '')
            if report_type == "Query Report":
                metadata["technical_config"] = {
                    "query": getattr(report, 'query', ''),
                    "prepared_report": getattr(report, 'prepared_report', False),
                    "disable_prepared_report": getattr(report, 'disable_prepared_report', False)
                }
            elif report_type == "Script Report":
                metadata["technical_config"] = {
                    "has_javascript": bool(getattr(report, 'javascript', '')),
                    "has_json_config": bool(getattr(report, 'json', ''))
                }
            
            # Try to extract advanced filter configuration
            try:
                if report_type == "Query Report" and getattr(report, 'json', ''):
                    import json
                    report_config = json.loads(report.json)
                    if "filters" in report_config:
                        metadata["advanced_filters"] = report_config["filters"]
                elif report_type == "Script Report":
                    # Try to get filters from the report module
                    module_name = report.module
                    report_module_name = f"{module_name}.report.{report.name.lower().replace(' ', '_')}"
                    try:
                        report_module = frappe.get_module(report_module_name)
                        if hasattr(report_module, 'get_filters'):
                            metadata["advanced_filters"] = report_module.get_filters()
                        elif hasattr(report_module, 'filters'):
                            metadata["advanced_filters"] = report_module.filters
                    except Exception:
                        pass
            except Exception:
                pass
                
            return metadata
            
        except Exception as e:
            return {"error": f"Error getting metadata: {str(e)}"}


# Make sure class name matches file name for discovery
report_requirements = ReportRequirements