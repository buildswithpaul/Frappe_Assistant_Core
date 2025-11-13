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

import json
from typing import Any, Dict, List

import frappe
from frappe import _


class ReportTools:
    """
    Shared utility class for Frappe report operations.

    This class provides the core business logic for report-related operations
    that is used by the individual tool classes (generate_report.py, report_list.py,
    report_requirements.py). Each tool class extends BaseTool and delegates to
    methods in this utility class.

    Methods:
    - execute_report(): Execute reports (Query, Script, Report Builder)
    - list_reports(): List available reports with filtering
    - get_report_columns(): Get report metadata and requirements
    - _validate_filters(): Validate filter values before execution
    """

    @staticmethod
    def execute_report(
        report_name: str, filters: Dict[str, Any] = None, format: str = "json"
    ) -> Dict[str, Any]:
        """Execute a Frappe report"""
        try:
            # Check if report exists
            if not frappe.db.exists("Report", report_name):
                return {"success": False, "error": f"Report '{report_name}' not found"}

            # Check permissions
            if not frappe.has_permission("Report", "read", report_name):
                return {"success": False, "error": f"No permission to access report '{report_name}'"}

            # Get report document
            report_doc = frappe.get_doc("Report", report_name)

            # Validate filters before execution
            validation_result = ReportTools._validate_filters(filters or {}, report_doc)
            if not validation_result.get("valid"):
                return {
                    "success": False,
                    "error": "Invalid filter values provided",
                    "validation_errors": validation_result.get("errors", []),
                    "suggestions": validation_result.get("suggestions", []),
                }

            # Execute report based on type
            if report_doc.report_type == "Query Report":
                result = ReportTools._execute_query_report(report_doc, filters or {})
            elif report_doc.report_type == "Script Report":
                result = ReportTools._execute_script_report(report_doc, filters or {})
            elif report_doc.report_type == "Report Builder":
                result = ReportTools._execute_report_builder(report_doc, filters or {})
            else:
                return {"success": False, "error": f"Unsupported report type: {report_doc.report_type}"}

            # Add debug information for troubleshooting
            # Handle different result structures
            if isinstance(result, dict):
                # Report Builder returns different structure than Script/Query reports
                if report_doc.report_type == "Report Builder":
                    # Report Builder returns {'keys': [...], 'values': [[...], ...]}
                    data = result.get("values", [])
                    columns = result.get("keys", [])
                else:
                    # Script/Query reports return {'result': [...], 'columns': [...]}
                    data = result.get("result", [])
                    columns = result.get("columns", [])

                debug_info = {
                    "success": True,
                    "report_name": report_name,
                    "report_type": report_doc.report_type,
                    "data": data,
                    "columns": columns,
                    "message": result.get("message"),
                    "filters_applied": filters or {},
                    "auto_filters_added": "Automatic date range and company filters applied if missing",
                    "raw_result_keys": list(result.keys()) if result else [],
                    "data_count": len(data) if data else 0,
                    "result_type": type(result).__name__ if result else "None",
                }
            elif isinstance(result, list):
                # Some reports (Report Builder) might return a list directly
                # Extract columns from first dict if available
                columns = []
                if result and len(result) > 0 and isinstance(result[0], dict):
                    columns = list(result[0].keys())

                debug_info = {
                    "success": True,
                    "report_name": report_name,
                    "report_type": report_doc.report_type,
                    "data": result,
                    "columns": columns,
                    "message": None,
                    "filters_applied": filters or {},
                    "auto_filters_added": "Automatic date range and company filters applied if missing",
                    "raw_result_keys": [],
                    "data_count": len(result) if result else 0,
                    "result_type": "list",
                }
            else:
                return {"success": False, "error": f"Unexpected result type: {type(result).__name__}"}

            # Add debug info if no data found
            data = debug_info.get("data", [])
            if not data or len(data) == 0:
                debug_info["debug_info"] = {
                    "filters_used": filters,
                    "result_structure": result,
                    "error_from_result": result.get("error") if isinstance(result, dict) else None,
                }

            return debug_info

        except Exception as e:
            frappe.log_error(f"assistant Execute Report Error: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def list_reports(module: str = None, report_type: str = None) -> Dict[str, Any]:
        """Get list of available reports"""
        try:
            filters = {}
            if module:
                filters["module"] = module
            if report_type:
                filters["report_type"] = report_type

            reports = frappe.get_all(
                "Report",
                filters=filters,
                fields=["name", "report_name", "report_type", "module", "is_standard", "disabled"],
                order_by="report_name",
            )

            # Filter by permissions
            accessible_reports = []
            for report in reports:
                if frappe.has_permission("Report", "read", report.name):
                    accessible_reports.append(report)

            return {
                "success": True,
                "reports": accessible_reports,
                "count": len(accessible_reports),
                "filters_applied": {"module": module, "report_type": report_type},
            }

        except Exception as e:
            frappe.log_error(f"assistant List Reports Error: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_report_columns(report_name: str) -> Dict[str, Any]:
        """Get column information for a report"""
        try:
            if not frappe.db.exists("Report", report_name):
                return {"success": False, "error": f"Report '{report_name}' not found"}

            if not frappe.has_permission("Report", "read", report_name):
                return {"success": False, "error": f"No permission to access report '{report_name}'"}

            report_doc = frappe.get_doc("Report", report_name)
            columns = []

            if report_doc.report_type == "Query Report":
                # Try to get columns from query execution with minimal filters
                try:
                    # Try with empty filters first
                    result = ReportTools._execute_query_report(report_doc, {}, get_columns_only=True)
                    columns = result.get("columns", [])
                except Exception as e:
                    # If that fails, try with default company
                    try:
                        default_company = frappe.db.get_single_value("Global Defaults", "default_company")
                        if default_company:
                            result = ReportTools._execute_query_report(
                                report_doc, {"company": default_company}, get_columns_only=True
                            )
                            columns = result.get("columns", [])
                    except Exception:
                        frappe.log_error(f"Error getting columns from query report: {str(e)}")
                        # Return basic info if column extraction fails
                        columns = [
                            {
                                "label": "Data not available - requires filters",
                                "fieldname": "info",
                                "fieldtype": "Data",
                            }
                        ]
            elif report_doc.report_type == "Report Builder":
                # Get columns from report builder configuration
                for col in report_doc.columns:
                    columns.append(
                        {
                            "fieldname": col.fieldname,
                            "label": col.label,
                            "fieldtype": col.fieldtype,
                            "width": col.width,
                        }
                    )

            # Add helpful filter guidance based on report name patterns
            filter_guidance = []
            if "sales_analytics" in report_name.lower():
                filter_guidance.append("Required: 'doc_type' (Sales Invoice, Sales Order, Quotation, etc.)")
                filter_guidance.append("Required: 'tree_type' (Customer, Item, Territory, etc.)")
                filter_guidance.append("Optional: 'from_date' and 'to_date' (defaults to last 12 months)")
                filter_guidance.append("Optional: 'company' (uses default company if not specified)")
            elif report_doc.report_type == "Script Report":
                filter_guidance.append(
                    "Script Reports often have mandatory filters - use report_requirements tool to discover exact filter definitions"
                )

            result = {
                "success": True,
                "report_name": report_name,
                "report_type": report_doc.report_type,
                "columns": columns,
            }

            if filter_guidance:
                result["filter_guidance"] = filter_guidance

            return result

        except Exception as e:
            frappe.log_error(f"assistant Get Report Columns Error: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _handle_prepared_report_execution(report_doc, filters):
        """
        Smart handler for prepared reports with polling support for AI/MCP tools:
        1. Check for existing completed prepared report
        2. Try quick execution if appropriate
        3. Queue background job and WAIT for completion (polling)
        4. Return data when ready or timeout gracefully
        """
        import time

        from frappe.core.doctype.prepared_report.prepared_report import (
            get_completed_prepared_report,
            make_prepared_report,
        )
        from frappe.desk.query_report import get_prepared_report_result, run

        try:
            # Check if a completed prepared report exists with these filters
            prepared_report_name = get_completed_prepared_report(
                filters=filters, user=frappe.session.user, report_name=report_doc.name
            )

            if prepared_report_name:
                # Found existing prepared report - retrieve cached data
                result = get_prepared_report_result(report_doc, filters, dn=prepared_report_name)

                if result and result.get("result"):
                    # Successfully retrieved cached data
                    prepared_doc = result.get("doc")
                    return {
                        "result": result.get("result", []),
                        "columns": result.get("columns", []),
                        "message": result.get("message"),
                        "prepared_report": True,
                        "source": "cached",
                        "prepared_report_name": prepared_report_name,
                        "generated_at": str(prepared_doc.modified) if prepared_doc else None,
                        "status": "completed",
                    }

            # Get report timeout configuration
            report_timeout = frappe.get_value("Report", report_doc.name, "timeout") or 120

            # Try quick direct execution for fast reports
            if report_timeout < 60:
                try:
                    direct_result = run(
                        report_name=report_doc.name,
                        filters=filters,
                        user=frappe.session.user,
                        ignore_prepared_report=True,  # Force direct execution
                    )

                    if direct_result and direct_result.get("result"):
                        return {
                            "result": direct_result.get("result", []),
                            "columns": direct_result.get("columns", []),
                            "message": direct_result.get("message"),
                            "prepared_report": False,
                            "source": "direct_execution",
                            "status": "completed",
                        }
                except Exception as e:
                    # Quick execution failed, fall through to background job
                    frappe.log_error(f"Quick execution failed for {report_doc.name}: {str(e)}")

            # ===== Queue and WAIT for completion with polling =====

            # Queue the background job
            prepared_report = make_prepared_report(report_name=report_doc.name, filters=filters)
            prepared_report_name = prepared_report.get("name")

            # Poll for completion with exponential backoff
            max_wait_time = min(report_timeout, 300)  # Cap at 5 minutes for MCP tools
            poll_interval = 2.0  # Start with 2 seconds
            max_poll_interval = 15.0  # Max 15 seconds between polls
            elapsed_time = 0

            frappe.db.commit()  # Ensure job is committed to DB

            while elapsed_time < max_wait_time:
                time.sleep(poll_interval)
                elapsed_time += poll_interval

                # Check prepared report status - get fresh data
                frappe.db.rollback()
                prepared_doc = frappe.get_doc("Prepared Report", prepared_report_name)

                if prepared_doc.status == "Completed":
                    # Report is ready! Retrieve and return data
                    result = get_prepared_report_result(report_doc, filters, dn=prepared_report_name)

                    if result and result.get("result"):
                        return {
                            "result": result.get("result", []),
                            "columns": result.get("columns", []),
                            "message": result.get("message"),
                            "prepared_report": True,
                            "source": "background_job_completed",
                            "prepared_report_name": prepared_report_name,
                            "wait_time_seconds": int(elapsed_time),
                            "status": "completed",
                        }

                elif prepared_doc.status == "Error":
                    # Report generation failed
                    error_message = prepared_doc.error_message or "Unknown error during report generation"
                    return {
                        "success": False,
                        "result": [],
                        "columns": [],
                        "error": f"Report generation failed: {error_message}",
                        "prepared_report_name": prepared_report_name,
                        "status": "error",
                    }

                # Exponential backoff - increase poll interval
                poll_interval = min(poll_interval * 1.5, max_poll_interval)

            # Timeout reached - report is still processing
            return {
                "result": [],
                "columns": [],
                "success": True,
                "status": "timeout",
                "prepared_report": True,
                "prepared_report_name": prepared_report_name,
                "message": f"Report generation is taking longer than expected ({int(max_wait_time)}s timeout reached). The report is still being generated in the background. You can retry with the same filters in a few minutes to retrieve the cached result.",
                "retry_guidance": f"Use report_name='{report_doc.name}' with the same filters to retrieve results.",
                "wait_time_seconds": int(elapsed_time),
            }

        except Exception as e:
            frappe.log_error(f"Prepared report handling error for {report_doc.name}: {str(e)}")
            raise e

    @staticmethod
    def _execute_query_report(report_doc, filters, get_columns_only=False):
        """Execute a Query Report"""
        from frappe.desk.query_report import run

        # Check if this is a prepared report
        if getattr(report_doc, "prepared_report", False) and not getattr(
            report_doc, "disable_prepared_report", False
        ):
            return ReportTools._handle_prepared_report_execution(report_doc, filters)

        try:
            # Add default filters for common requirements and clean None values
            if not filters:
                filters = {}

            # Clean any None values from filters that could cause startswith errors
            cleaned_filters = {}
            for key, value in filters.items():
                if value is not None:
                    cleaned_filters[key] = value
            filters = cleaned_filters

            # Add default date filters if missing - use current fiscal year dates
            if not filters.get("from_date") and not filters.get("to_date"):
                try:
                    # Get current fiscal year
                    fiscal_year = frappe.db.get_value(
                        "Fiscal Year",
                        {"disabled": 0},
                        ["year_start_date", "year_end_date"],
                        order_by="year_start_date desc",
                    )

                    if fiscal_year:
                        filters["from_date"] = str(fiscal_year[0])  # Fiscal year start
                        filters["to_date"] = str(fiscal_year[1])  # Fiscal year end
                    else:
                        # Fallback to last 12 months if no fiscal year found
                        from frappe.utils import add_months, getdate

                        today = getdate()
                        filters["to_date"] = str(today)
                        filters["from_date"] = str(add_months(today, -12))
                except Exception:
                    # Fallback to last 12 months on any error
                    from frappe.utils import add_months, getdate

                    today = getdate()
                    filters["to_date"] = str(today)
                    filters["from_date"] = str(add_months(today, -12))
            elif not filters.get("to_date") and filters.get("from_date"):
                from frappe.utils import getdate

                filters["to_date"] = str(getdate())
            elif not filters.get("from_date") and filters.get("to_date"):
                from frappe.utils import add_months, getdate

                filters["from_date"] = str(add_months(getdate(filters["to_date"]), -12))

            # Add company filter if required and not provided
            if "company" not in filters and frappe.db.exists("Company"):
                default_company = frappe.db.get_single_value("Global Defaults", "default_company")
                if default_company:
                    filters["company"] = str(default_company)

            # Add report-specific default parameters
            report_name_lower = report_doc.name.lower()

            # Sales Analytics defaults
            if "sales analytics" in report_name_lower and "value_quantity" not in filters:
                filters["value_quantity"] = "Value"

            # Quotation Trends defaults
            if "quotation trends" in report_name_lower and "based_on" not in filters:
                filters["based_on"] = "Item"

            # Final cleanup - ensure all filter values are strings or proper types
            final_filters = {}
            for key, value in filters.items():
                if value is not None:
                    # Convert dates to strings if they're not already
                    if hasattr(value, "strftime"):  # datetime object
                        final_filters[key] = value.strftime("%Y-%m-%d")
                    elif isinstance(value, (str, int, float, bool)):
                        final_filters[key] = value
                    else:
                        final_filters[key] = str(value)
            filters = final_filters

            return run(
                report_name=report_doc.name,
                filters=filters,
                user=frappe.session.user,
                is_tree=getattr(report_doc, "is_tree", 0),
                parent_field=getattr(report_doc, "parent_field", None),
            )
        except Exception as e:
            # If execution fails, try to get just column info
            if "company" in str(e).lower() and "required" in str(e).lower():
                return {
                    "result": [],
                    "columns": [],
                    "message": f"Report requires filters: {str(e)}",
                    "error": "missing_required_filters",
                }
            raise e

    @staticmethod
    def _execute_script_report(report_doc, filters):
        """Execute a Script Report"""
        from frappe.desk.query_report import run

        try:
            # Ensure filters is a proper dict and clean None values
            if not isinstance(filters, dict):
                filters = {}

            # Clean any None values from filters that could cause startswith errors
            cleaned_filters = {}
            for key, value in filters.items():
                if value is not None:
                    cleaned_filters[key] = value
            filters = cleaned_filters

            # Add default date filters if missing - use current fiscal year dates
            if not filters.get("from_date") and not filters.get("to_date"):
                try:
                    # Get current fiscal year
                    fiscal_year = frappe.db.get_value(
                        "Fiscal Year",
                        {"disabled": 0},
                        ["year_start_date", "year_end_date"],
                        order_by="year_start_date desc",
                    )

                    if fiscal_year:
                        filters["from_date"] = str(fiscal_year[0])  # Fiscal year start
                        filters["to_date"] = str(fiscal_year[1])  # Fiscal year end
                    else:
                        # Fallback to last 12 months if no fiscal year found
                        from frappe.utils import add_months, getdate

                        today = getdate()
                        filters["to_date"] = str(today)
                        filters["from_date"] = str(add_months(today, -12))
                except Exception:
                    # Fallback to last 12 months on any error
                    from frappe.utils import add_months, getdate

                    today = getdate()
                    filters["to_date"] = str(today)
                    filters["from_date"] = str(add_months(today, -12))
            elif not filters.get("to_date") and filters.get("from_date"):
                from frappe.utils import getdate

                filters["to_date"] = str(getdate())
            elif not filters.get("from_date") and filters.get("to_date"):
                from frappe.utils import add_months, getdate

                filters["from_date"] = str(add_months(getdate(filters["to_date"]), -12))

            # For Accounts Receivable Summary, ensure company is set
            if report_doc.name == "Accounts Receivable Summary" and not filters.get("company"):
                default_company = frappe.db.get_single_value("Global Defaults", "default_company")
                if default_company:
                    filters["company"] = str(default_company)

            # Add default company for reports that need it
            if not filters.get("company"):
                default_company = frappe.db.get_single_value("Global Defaults", "default_company")
                if default_company:
                    filters["company"] = str(default_company)

            # Add report-specific default parameters
            report_name_lower = report_doc.name.lower()

            # Sales Analytics defaults
            if "sales analytics" in report_name_lower and "value_quantity" not in filters:
                filters["value_quantity"] = "Value"

            # Quotation Trends defaults
            if "quotation trends" in report_name_lower and "based_on" not in filters:
                filters["based_on"] = "Item"

            # Apply default values from JavaScript filter definitions
            filters = ReportTools._apply_filter_defaults(report_doc, filters)

            # Final cleanup - ensure all filter values are strings or proper types
            final_filters = {}
            for key, value in filters.items():
                if value is not None:
                    # Convert dates to strings if they're not already
                    if hasattr(value, "strftime"):  # datetime object
                        final_filters[key] = value.strftime("%Y-%m-%d")
                    elif isinstance(value, (str, int, float, bool)):
                        final_filters[key] = value
                    else:
                        final_filters[key] = str(value)
            filters = final_filters

            # Check if this is a prepared report (after all filter processing)
            if getattr(report_doc, "prepared_report", False) and not getattr(
                report_doc, "disable_prepared_report", False
            ):
                return ReportTools._handle_prepared_report_execution(report_doc, filters)

            return run(report_name=report_doc.name, filters=filters, user=frappe.session.user)

        except Exception as e:
            frappe.log_error(f"Script report execution error for {report_doc.name}: {str(e)}")

            # Provide helpful error messages for common issues
            error_message = str(e)
            if "'NoneType' object has no attribute 'startswith'" in error_message:
                error_message = f"Missing required filters for {report_doc.name}. This report requires mandatory filters that were not provided. Use the report_requirements tool to discover required filters."
                if "sales_analytics" in report_doc.name.lower():
                    error_message += " For Sales Analytics, you need: 'doc_type' (e.g., 'Sales Invoice') and 'tree_type' (e.g., 'Customer')."
            elif "required" in error_message.lower() and any(
                word in error_message.lower() for word in ["filter", "field", "parameter"]
            ):
                error_message = f"Missing required filters for {report_doc.name}: {error_message}. Use the report_requirements tool to discover all required filters."

            return {
                "result": [],
                "columns": [],
                "message": f"Script report execution failed: {error_message}",
                "error": error_message,
                "suggestion": f"Use report_requirements tool with report_name='{report_doc.name}' to discover required filters, then retry with proper filters.",
            }

    @staticmethod
    def _execute_report_builder(report_doc, filters):
        """Execute a Report Builder report"""
        import json as json_module

        from frappe.desk.reportview import execute

        # Parse report configuration from JSON field
        report_config = {}
        if report_doc.json:
            try:
                report_config = json_module.loads(report_doc.json)
            except Exception:
                pass

        # Get sort configuration
        sort_by = report_config.get("sort_by")
        sort_order = report_config.get("sort_order", "desc")

        # Build order_by string
        # Note: sort_by from Report Builder json is in format "Doctype.field"
        # For doctypes with spaces, Frappe's execute() handles the backtick quoting
        order_by = None
        if sort_by:
            # Just use the field name without the doctype prefix
            # Frappe's reportview will add the proper table reference
            if "." in sort_by:
                field_name = sort_by.split(".")[-1]  # Get just the field name
                order_by = f"`{field_name}` {sort_order}"
            else:
                order_by = f"`{sort_by}` {sort_order}"

        # Get columns from JSON config
        # Format: [["fieldname", "Doctype"], ["fieldname2", "Doctype"], ...]
        fields = None
        columns_config = report_config.get("columns", [])
        if columns_config and len(columns_config) > 0:
            try:
                fields = []
                for col in columns_config:
                    if isinstance(col, list) and len(col) >= 1:
                        # Extract field name from ["fieldname", "Doctype"] format
                        fieldname = col[0]
                        fields.append(fieldname)
                    elif isinstance(col, str):
                        # Direct field name
                        fields.append(col)

                # Only use extracted fields if we got at least one
                if not fields:
                    fields = None
            except Exception as e:
                frappe.log_error(f"Error extracting fields from Report Builder columns: {str(e)}")
                fields = None

        # If no fields from config, try from report_doc.columns child table
        if not fields and report_doc.columns:
            try:
                fields = []
                for col in report_doc.columns:
                    if hasattr(col, "fieldname"):
                        fields.append(col.fieldname)
                    elif isinstance(col, dict) and "fieldname" in col:
                        fields.append(col["fieldname"])

                # Only use extracted fields if we got at least one
                if not fields:
                    fields = None
            except Exception as e:
                frappe.log_error(f"Error extracting fields from Report doc columns: {str(e)}")
                fields = None

        # Note: If fields is None or empty, we need to get all standard fields from the DocType
        if not fields:
            # Get all standard fields from the doctype meta
            try:
                meta = frappe.get_meta(report_doc.ref_doctype)
                fields = [
                    df.fieldname
                    for df in meta.fields
                    if df.fieldtype not in ["Table", "Section Break", "Column Break", "HTML", "Button"]
                ]
                # Always include name field
                if "name" not in fields:
                    fields.insert(0, "name")
            except Exception as e:
                frappe.log_error(f"Error getting meta fields for {report_doc.ref_doctype}: {str(e)}")
                fields = None

        return execute(
            doctype=report_doc.ref_doctype,
            filters=filters,
            fields=fields,
            order_by=order_by,
            limit_page_length=1000,
        )

    @staticmethod
    def _validate_filters(filters: Dict[str, Any], report_doc) -> Dict[str, Any]:
        """Validate filter values against database to catch invalid references early"""
        errors = []
        suggestions = []

        # Common Link field filters to validate
        link_validations = {
            "company": "Company",
            "customer": "Customer",
            "supplier": "Supplier",
            "item": "Item",
            "project": "Project",
            "cost_center": "Cost Center",
            "warehouse": "Warehouse",
        }

        for filter_key, doctype in link_validations.items():
            if filter_key in filters and filters[filter_key]:
                filter_value = filters[filter_key]

                # Skip validation for list values (used in group reports)
                if isinstance(filter_value, list):
                    continue

                # Check if the referenced document exists
                if not frappe.db.exists(doctype, filter_value):
                    errors.append(f"Invalid {filter_key}: '{filter_value}' does not exist in {doctype}")

                    # Try to find similar names to suggest
                    try:
                        similar = frappe.get_all(
                            doctype, filters={"name": ["like", f"%{filter_value}%"]}, fields=["name"], limit=3
                        )
                        if similar:
                            suggestions.append(
                                f"Did you mean one of these {doctype} names? {', '.join([s.name for s in similar])}"
                            )
                        else:
                            # If no similar matches, show first few valid options
                            valid_options = frappe.get_all(doctype, fields=["name"], limit=5)
                            if valid_options:
                                suggestions.append(
                                    f"Valid {doctype} names include: {', '.join([v.name for v in valid_options])}"
                                )
                    except Exception:
                        pass

        # Validate Select field options
        select_validations = {
            "tree_type": [
                "Customer",
                "Supplier",
                "Item",
                "Customer Group",
                "Supplier Group",
                "Item Group",
                "Territory",
                "Order Type",
                "Project",
            ],
            "doc_type": [
                "Sales Invoice",
                "Sales Order",
                "Quotation",
                "Purchase Invoice",
                "Purchase Order",
                "Purchase Receipt",
                "Delivery Note",
            ],
            "value_quantity": ["Value", "Quantity"],
            "range": ["Weekly", "Monthly", "Quarterly", "Half-Yearly", "Yearly"],
        }

        for filter_key, valid_options in select_validations.items():
            if filter_key in filters and filters[filter_key]:
                filter_value = filters[filter_key]
                if filter_value not in valid_options:
                    errors.append(
                        f"Invalid {filter_key}: '{filter_value}'. Must be one of: {', '.join(valid_options)}"
                    )

        # Validate date formats
        date_fields = ["from_date", "to_date", "posting_date", "transaction_date"]
        for date_field in date_fields:
            if date_field in filters and filters[date_field]:
                try:
                    from frappe.utils import getdate

                    getdate(filters[date_field])
                except Exception:
                    errors.append(
                        f"Invalid {date_field}: '{filters[date_field]}'. Expected format: YYYY-MM-DD"
                    )

        return {"valid": len(errors) == 0, "errors": errors, "suggestions": suggestions}

    @staticmethod
    def _apply_filter_defaults(report_doc, filters):
        """Apply default filter values from JavaScript filter definitions for Script Reports"""
        import os
        import re

        # Only apply for Script Reports
        if report_doc.report_type != "Script Report":
            return filters

        try:
            # Get the report's JavaScript file path
            module_name = report_doc.module
            report_name = report_doc.name
            report_folder = report_name.lower().replace(" ", "_").replace("-", "_")
            module_folder = module_name.lower().replace(" ", "_")

            # Search for the JS file in installed apps
            for app in frappe.get_installed_apps():
                app_path = frappe.get_app_path(app)
                js_path = os.path.join(
                    app_path, module_folder, "report", report_folder, f"{report_folder}.js"
                )

                if os.path.exists(js_path):
                    # Read and parse the JavaScript file
                    with open(js_path, encoding="utf-8") as f:
                        js_content = f.read()

                    # Extract filter definitions
                    filters_start = js_content.find("filters:")
                    if filters_start == -1:
                        continue

                    # Find the filter array using bracket counting
                    bracket_start = js_content.find("[", filters_start)
                    if bracket_start == -1:
                        continue

                    bracket_count = 0
                    bracket_end = -1
                    for i in range(bracket_start, len(js_content)):
                        if js_content[i] == "[":
                            bracket_count += 1
                        elif js_content[i] == "]":
                            bracket_count -= 1
                            if bracket_count == 0:
                                bracket_end = i
                                break

                    if bracket_end == -1:
                        continue

                    filters_text = js_content[bracket_start + 1 : bracket_end]

                    # Parse filter objects
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
                                obj_content = filters_text[current_obj_start + 1 : i]
                                filter_objects.append(obj_content)
                                current_obj_start = None

                    # Extract default values from each filter
                    for filter_obj in filter_objects:
                        # Extract fieldname
                        fieldname_match = re.search(r'fieldname:\s*["\']([^"\']+)["\']', filter_obj)
                        if not fieldname_match:
                            continue
                        fieldname = fieldname_match.group(1)

                        # Skip if filter already has a value
                        if fieldname in filters and filters[fieldname] is not None:
                            continue

                        # Extract default value
                        default_match = re.search(r'default:\s*["\']([^"\']+)["\']', filter_obj)
                        if default_match:
                            default_value = default_match.group(1)
                            filters[fieldname] = default_value

                    break  # Found and processed the JS file

        except Exception as e:
            # Log error but don't fail the report execution
            frappe.log_error(f"Error applying filter defaults for {report_doc.name}: {str(e)}")

        return filters
