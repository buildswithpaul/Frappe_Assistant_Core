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

from typing import Any, Dict

import frappe
from frappe import _

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
        self.description = "Get report metadata including required and optional filters, columns, and execution requirements. Use this tool before executing reports to understand what filters are mandatory, what exact filter values are valid, and how to structure the report request. This prevents filter errors and helps plan successful report execution. Returns complete report metadata including filter definitions with field types (Link, Select, Date), valid enum options for select fields, column structure, report type, and capabilities. IMPORTANT: Use this FIRST before calling generate_report to understand what exact filter values are needed - Link fields require exact database names (e.g., exact Company name, Customer name), Select fields show valid enum values. Essential when generate_report returns filter errors or when planning complex report execution."
        self.requires_permission = None  # Permission checked dynamically per report

        self.inputSchema = {
            "type": "object",
            "properties": {
                "report_name": {
                    "type": "string",
                    "description": "Exact name of the Frappe report to analyze (e.g., 'Sales Analytics', 'Accounts Receivable Summary'). This helps understand available fields, required filters, valid filter options, and report structure before execution.",
                },
                "include_metadata": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to include technical metadata (creation date, owner, SQL query, etc.) - useful for developers and administrators.",
                },
                "include_columns": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to include column structure information.",
                },
                "include_filters": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to include filter requirements and guidance.",
                },
            },
            "required": ["report_name"],
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

            # Get report document for prepared report info
            report_doc = frappe.get_doc("Report", report_name)

            # Start building comprehensive response
            result = {
                "success": True,
                "report_name": report_name,
                "report_type": column_result.get("report_type"),
                "prepared_report": getattr(report_doc, "prepared_report", False),
                "disable_prepared_report": getattr(report_doc, "disable_prepared_report", False),
            }

            # Add prepared report guidance
            if getattr(report_doc, "prepared_report", False) and not getattr(
                report_doc, "disable_prepared_report", False
            ):
                report_timeout = frappe.get_value("Report", report_name, "timeout") or 120
                result["prepared_report_info"] = {
                    "requires_background_processing": True,
                    "typical_execution_time": f"{report_timeout // 60} minutes for large datasets",
                    "behavior": "First execution automatically waits for completion (up to 5 minutes). Subsequent calls with same filters retrieve cached results instantly.",
                    "recommendation": "The tool will automatically wait for report completion. If timeout occurs, retry with the same filters to retrieve cached results.",
                }
            else:
                result["prepared_report_info"] = {
                    "requires_background_processing": False,
                    "behavior": "Direct execution - returns results immediately.",
                }

            # Add columns if requested
            if include_columns:
                result["columns"] = column_result.get("columns", [])

            # Add filter guidance if requested
            if include_filters:
                if "filter_guidance" in column_result:
                    result["filter_guidance"] = column_result["filter_guidance"]

                # Add filter requirements analysis
                result["filter_requirements"] = self._analyze_filter_requirements(
                    report_name, column_result.get("report_type")
                )

                # For Script Reports, try to parse filters from JS file and add to main response
                if column_result.get("report_type") == "Script Report":
                    module_name = report_doc.module
                    parsed_filters = self._parse_script_report_filters(report_name, module_name)

                    if parsed_filters and parsed_filters.get("filters"):
                        result["filters_definition"] = parsed_filters["filters"]
                        result["required_filter_names"] = parsed_filters.get("required_filters", [])
                        result["optional_filter_names"] = parsed_filters.get("optional_filters", [])

                        # Override filter_requirements with parsed data instead of pattern-based guesses
                        result["filter_requirements"] = self._build_requirements_from_parsed_filters(
                            parsed_filters
                        )

            # Add comprehensive metadata if requested
            if include_metadata:
                metadata = self._get_comprehensive_metadata(report_name)
                if metadata:
                    result["metadata"] = metadata

            return result

        except Exception as e:
            frappe.log_error(
                title=_("Report Requirements Error"), message=f"Error analyzing report requirements: {str(e)}"
            )

            return {"success": False, "error": str(e)}

    def _build_requirements_from_parsed_filters(self, parsed_filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build filter requirements from parsed filter definitions.

        Args:
            parsed_filters: Dictionary with 'filters', 'required_filters', 'optional_filters'

        Returns:
            Dictionary with human-readable filter requirements and guidance
        """
        requirements = {"common_required_filters": [], "common_optional_filters": [], "guidance": []}

        # Build human-readable descriptions for each filter
        for filter_def in parsed_filters.get("filters", []):
            fieldname = filter_def.get("fieldname", "")
            label = filter_def.get("label", fieldname)
            fieldtype = filter_def.get("fieldtype", "")
            options = filter_def.get("options")
            default = filter_def.get("default")
            is_required = filter_def.get("required", False)

            # Build description
            description = f"{fieldname}"
            if label and label != fieldname:
                description = f"{fieldname} ({label})"

            # Add type and options info
            if fieldtype == "Select" and options and isinstance(options, list):
                options_str = ", ".join(options[:3])  # Show first 3 options
                if len(options) > 3:
                    options_str += f", ... ({len(options)} options)"
                description += f" - Select: {options_str}"
            elif fieldtype == "Link" and options:
                description += f" - Link to {options}"
            elif fieldtype:
                description += f" - {fieldtype}"

            # Add default value info
            if default:
                description += f" (default: {default})"

            # Categorize
            if is_required:
                requirements["common_required_filters"].append(description)
            else:
                requirements["common_optional_filters"].append(description)

        # Add guidance
        if requirements["common_required_filters"]:
            requirements["guidance"].append(
                f"This report requires {len(requirements['common_required_filters'])} mandatory filters. "
                "All required filters must be provided for successful execution."
            )

        if requirements["common_optional_filters"]:
            requirements["guidance"].append(
                f"Additionally, {len(requirements['common_optional_filters'])} optional filters are available "
                "to refine results. These have default values if not specified."
            )

        return requirements

    def _analyze_filter_requirements(self, report_name: str, report_type: str) -> Dict[str, Any]:
        """Analyze filter requirements for the report (fallback for pattern-based matching)"""
        requirements = {"common_required_filters": [], "common_optional_filters": [], "guidance": []}

        # Add specific guidance based on report name patterns
        report_lower = report_name.lower()

        if "sales_analytics" in report_lower or "sales analytics" in report_lower:
            requirements["common_required_filters"] = [
                "doc_type (Sales Invoice, Sales Order, Quotation, etc.)",
                "tree_type (Customer, Item, Territory, etc.)",
                "value_quantity (Value or Quantity)",
            ]
            requirements["common_optional_filters"] = [
                "from_date and to_date (defaults to current fiscal year)",
                "company (uses default company if not specified)",
            ]
            requirements["guidance"].append(
                "For Sales Analytics: Use doc_type='Sales Invoice', tree_type='Customer', and value_quantity='Value' for customer-wise revenue analysis"
            )

        elif "quotation trends" in report_lower:
            requirements["common_required_filters"] = ["based_on (Item, Customer, Territory, etc.)"]
            requirements["common_optional_filters"] = [
                "from_date and to_date (defaults to current fiscal year)",
                "company (uses default company if not specified)",
            ]
            requirements["guidance"].append(
                "For Quotation Trends: based_on field is mandatory - use 'Item' for item-wise trends or 'Customer' for customer-wise analysis"
            )

        elif "profit" in report_lower and "loss" in report_lower:
            requirements["common_required_filters"] = ["company", "from_date", "to_date"]
            requirements["guidance"].append(
                "P&L Statement requires company and date range for financial period analysis"
            )

        elif "receivable" in report_lower:
            requirements["common_required_filters"] = ["company"]
            requirements["common_optional_filters"] = ["customer", "as_on_date"]
            requirements["guidance"].append(
                "Accounts Receivable typically needs company filter, optionally filter by specific customer"
            )

        elif "balance_sheet" in report_lower or "balance sheet" in report_lower:
            requirements["common_required_filters"] = ["company", "as_on_date"]
            requirements["guidance"].append(
                "Balance Sheet requires company and specific date for financial position"
            )

        # General guidance based on report type
        if report_type == "Script Report":
            requirements["guidance"].append(
                "Script Reports often have mandatory filters - check filter definitions or use filters_definition field for exact requirements"
            )
        elif report_type == "Query Report":
            requirements["guidance"].append(
                "Query Reports may require company or date filters depending on the underlying query"
            )

        return requirements

    def _parse_script_report_filters(self, report_name: str, module_name: str) -> Dict[str, Any]:
        """
        Parse JavaScript filter definitions from Script Report .js file.

        Args:
            report_name: Name of the report
            module_name: Module name (e.g., "Selling", "Stock")

        Returns:
            Dictionary containing parsed filters, or None if parsing fails
        """
        import os
        import re

        try:
            # Construct path to JS file
            # Format: apps/{app_name}/{module}/report/{report_name}/{report_name}.js
            report_folder = report_name.lower().replace(" ", "_").replace("-", "_")
            module_folder = module_name.lower().replace(" ", "_")

            # Find the app that contains this module
            for app in frappe.get_installed_apps():
                app_path = frappe.get_app_path(app)
                js_path = os.path.join(
                    app_path, module_folder, "report", report_folder, f"{report_folder}.js"
                )

                if os.path.exists(js_path):
                    # Read JavaScript file
                    with open(js_path, encoding="utf-8") as f:
                        js_content = f.read()

                    # Extract filter array using regex
                    # Pattern: frappe.query_reports["Report Name"] = { filters: [...] }
                    # Need to handle nested objects with proper bracket counting
                    pattern = r'frappe\.query_reports\[["\'].*?["\']\]\s*=\s*\{.*?filters:\s*\[(.*?)\]'

                    # Find the start of filters array
                    filters_start = js_content.find("filters:")
                    if filters_start == -1:
                        frappe.logger().debug(f"No 'filters:' found in JS file for {report_name}")
                        return None

                    # Find the opening bracket
                    bracket_start = js_content.find("[", filters_start)
                    if bracket_start == -1:
                        frappe.logger().debug(f"No opening bracket after 'filters:' for {report_name}")
                        return None

                    # Count brackets to find matching closing bracket
                    bracket_count = 0
                    bracket_end = bracket_start
                    for i in range(bracket_start, len(js_content)):
                        if js_content[i] == "[":
                            bracket_count += 1
                        elif js_content[i] == "]":
                            bracket_count -= 1
                            if bracket_count == 0:
                                bracket_end = i
                                break

                    if bracket_count != 0:
                        frappe.logger().debug(f"Mismatched brackets in filters array for {report_name}")
                        return None

                    # Extract filter content (inside the brackets)
                    filters_text = js_content[bracket_start + 1 : bracket_end]
                    parsed_filters = self._parse_js_filter_array(filters_text)
                    return parsed_filters

            frappe.logger().debug(f"JS file not found for {report_name}")
            return None

        except Exception as e:
            frappe.log_error(f"Error parsing Script Report filters for {report_name}: {str(e)}")
            return None

    def _parse_js_filter_array(self, filters_text: str) -> Dict[str, Any]:
        """
        Parse JavaScript filter array text into Python dictionary.

        Args:
            filters_text: String containing JavaScript filter objects

        Returns:
            Dictionary with 'filters', 'required_filters', 'optional_filters'
        """
        import re

        filters = []
        required_filters = []
        optional_filters = []

        # Split into individual filter objects using proper brace counting
        filter_objects = []
        brace_count = 0
        current_obj_start = None

        for i, char in enumerate(filters_text):
            if char == "{":
                if brace_count == 0:
                    current_obj_start = i
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0 and current_obj_start is not None:
                    # Extract complete object (excluding braces)
                    obj_content = filters_text[current_obj_start + 1 : i]
                    filter_objects.append(obj_content)
                    current_obj_start = None

        for filter_obj in filter_objects:
            filter_def = {}

            # Extract fieldname
            fieldname_match = re.search(r'fieldname:\s*["\']([^"\']+)["\']', filter_obj)
            if fieldname_match:
                filter_def["fieldname"] = fieldname_match.group(1)
            else:
                continue  # Skip if no fieldname

            # Extract label
            label_match = re.search(
                r'label:\s*__\(["\']([^"\']+)["\']\)|label:\s*["\']([^"\']+)["\']', filter_obj
            )
            if label_match:
                filter_def["label"] = label_match.group(1) or label_match.group(2)

            # Extract fieldtype
            fieldtype_match = re.search(r'fieldtype:\s*["\']([^"\']+)["\']', filter_obj)
            if fieldtype_match:
                filter_def["fieldtype"] = fieldtype_match.group(1)

            # Extract options (can be array or string)
            options_match = re.search(r'options:\s*(\[[\s\S]*?\]|["\'][^"\']+["\'])', filter_obj)
            if options_match:
                options_str = options_match.group(1)
                if options_str.startswith("["):
                    # Array format - extract string values
                    option_values = re.findall(r'["\']([^"\']+)["\']', options_str)
                    filter_def["options"] = option_values
                else:
                    # String format (e.g., Link to DocType)
                    filter_def["options"] = options_str.strip("\"'")

            # Extract default value
            default_match = re.search(r'default:\s*["\']([^"\']+)["\']|default:\s*(\d+)', filter_obj)
            if default_match:
                filter_def["default"] = default_match.group(1) or default_match.group(2)

            # Extract required flag
            reqd_match = re.search(r"reqd:\s*(1|true)", filter_obj, re.IGNORECASE)
            filter_def["required"] = bool(reqd_match)

            filters.append(filter_def)

            # Categorize as required or optional
            if filter_def["required"]:
                required_filters.append(filter_def["fieldname"])
            else:
                optional_filters.append(filter_def["fieldname"])

        return {
            "filters": filters,
            "required_filters": required_filters,
            "optional_filters": optional_filters,
        }

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
                    "name": getattr(report, "name", ""),
                    "report_name": getattr(report, "report_name", ""),
                    "report_type": getattr(report, "report_type", ""),
                    "module": getattr(report, "module", ""),
                    "is_standard": getattr(report, "is_standard", False),
                    "disabled": getattr(report, "disabled", False),
                    "description": getattr(report, "description", ""),
                    "ref_doctype": getattr(report, "ref_doctype", ""),
                },
                "system_info": {
                    "creation": str(getattr(report, "creation", "")),
                    "modified": str(getattr(report, "modified", "")),
                    "owner": getattr(report, "owner", ""),
                    "modified_by": getattr(report, "modified_by", ""),
                },
            }

            # Add type-specific technical information
            report_type = getattr(report, "report_type", "")
            if report_type == "Query Report":
                metadata["technical_config"] = {
                    "query": getattr(report, "query", ""),
                    "prepared_report": getattr(report, "prepared_report", False),
                    "disable_prepared_report": getattr(report, "disable_prepared_report", False),
                }
            elif report_type == "Script Report":
                metadata["technical_config"] = {
                    "has_javascript": bool(getattr(report, "javascript", "")),
                    "has_json_config": bool(getattr(report, "json", "")),
                }

            # Try to extract advanced filter configuration
            try:
                if report_type == "Query Report" and getattr(report, "json", ""):
                    import json

                    report_config = json.loads(report.json)
                    if "filters" in report_config:
                        metadata["advanced_filters"] = report_config["filters"]

                elif report_type == "Script Report":
                    # NEW: Parse JavaScript file for filter definitions
                    module_name = report.module
                    parsed_filters = self._parse_script_report_filters(report_name, module_name)

                    if parsed_filters:
                        metadata["advanced_filters"] = parsed_filters
                    else:
                        # Fallback: Try Python module (legacy support)
                        report_module_name = f"{module_name}.report.{report.name.lower().replace(' ', '_')}"
                        try:
                            report_module = frappe.get_module(report_module_name)
                            if hasattr(report_module, "get_filters"):
                                metadata["advanced_filters"] = report_module.get_filters()
                            elif hasattr(report_module, "filters"):
                                metadata["advanced_filters"] = report_module.filters
                        except Exception:
                            pass
            except Exception as e:
                frappe.logger().debug(f"Error extracting filters for {report_name}: {str(e)}")

            return metadata

        except Exception as e:
            return {"error": f"Error getting metadata: {str(e)}"}


# Make sure class name matches file name for discovery
report_requirements = ReportRequirements
