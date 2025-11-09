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
    """assistant tools for Frappe report operations"""

    @staticmethod
    def get_tools() -> List[Dict]:
        """Return list of report-related assistant tools"""
        return [
            {
                "name": "generate_report",
                "description": "🏆 PROFESSIONAL BUSINESS REPORTS - Your FIRST choice for sales analysis, financial reporting, and business intelligence! 🎯 **USE THIS FOR**: Sales analysis, profit reports, customer insights, inventory tracking, financial statements ⚡ **INSTANT ACCESS** to 183+ pre-built business reports including: Sales Analytics (revenue, trends, territory performance), Profit & Loss Statement, Accounts Receivable Summary, Item-wise Sales History, Territory-wise Sales ✅ **ALWAYS TRY THIS FIRST** before using analysis tools - these reports are pre-optimized for business users, professionally formatted, ready for management presentation, and include proper calculations and totals. Use 'report_list' to discover available reports, then execute with filters. IMPORTANT: Many reports require mandatory filters - use report_requirements tool first if you get errors.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "report_name": {
                            "type": "string",
                            "description": "Exact name of the Frappe report to execute (e.g., 'Accounts Receivable Summary', 'Sales Analytics', 'Stock Balance'). Use report_list to find available reports.",
                        },
                        "filters": {
                            "type": "object",
                            "default": {},
                            "description": "Report-specific filters as key-value pairs. IMPORTANT: Many reports have mandatory filters like 'doc_type', 'tree_type', etc. Common optional filters: {'company': 'Your Company'}, {'from_date': '2024-01-01', 'to_date': '2024-12-31'}, {'customer': 'Customer Name'}. For Sales Analytics: requires 'doc_type' (Sales Invoice/Sales Order/Quotation) and 'tree_type' (Customer/Item/Territory). Use report_requirements tool to discover required filters if report fails.",
                        },
                        "format": {
                            "type": "string",
                            "enum": ["json", "csv", "excel"],
                            "default": "json",
                            "description": "Output format. Use 'json' for data analysis, 'csv' for exports, 'excel' for spreadsheet files.",
                        },
                    },
                    "required": ["report_name"],
                },
            },
            {
                "name": "report_list",
                "description": "🔍 DISCOVER BUSINESS REPORTS - Find the perfect report for your business question! 🎯 **ESSENTIAL FOR**: Finding sales reports, financial analysis, inventory tracking, HR reports ⚡ **183+ REPORTS AVAILABLE** across modules: Selling (Sales Analytics, Territory Analysis, Customer Reports), Accounts (P&L, Balance Sheet, Receivables, Payables), Stock (Inventory Reports, Item Movement, Valuation), HR (Payroll, Attendance, Leave Reports) 💡 **SMART TIP**: Use this BEFORE trying to analyze raw data - there's likely already a perfect report!",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "module": {
                            "type": "string",
                            "description": "Filter by Frappe module (e.g., 'Accounts', 'Selling', 'Stock', 'HR', 'CRM'). Leave empty to see all modules.",
                        },
                        "report_type": {
                            "type": "string",
                            "enum": ["Report Builder", "Query Report", "Script Report"],
                            "description": "Filter by report type. Script Reports are usually the most powerful for analytics. Leave empty to see all types.",
                        },
                    },
                },
            },
            {
                "name": "report_requirements",
                "description": "📋 REPORT STRUCTURE ANALYZER - Understand report requirements before execution! 🎯 **ESSENTIAL FOR**: Discovering required filters when generate_report fails, understanding available data fields, planning report execution 💡 **USE WHEN**: You get filter errors from generate_report, need to understand report capabilities, want to know what data is available ⚡ **PREVENTS ERRORS**: Shows exactly what filters are required and optional for successful report execution",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "report_name": {
                            "type": "string",
                            "description": "Exact name of the Frappe report to analyze (e.g., 'Sales Analytics', 'Accounts Receivable Summary'). This helps understand available fields, required filters, and report structure before execution.",
                        }
                    },
                    "required": ["report_name"],
                },
            },
        ]

    @staticmethod
    def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a report tool with given arguments"""
        if tool_name == "generate_report":
            return ReportTools.execute_report(**arguments)
        elif tool_name == "report_list":
            return ReportTools.list_reports(**arguments)
        elif tool_name == "report_requirements":
            return ReportTools.get_report_columns(**arguments)
        else:
            raise Exception(f"Unknown report tool: {tool_name}")

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
            data = result.get("result", [])
            debug_info = {
                "success": True,
                "report_name": report_name,
                "report_type": report_doc.report_type,
                "data": data,
                "columns": result.get("columns", []),
                "message": result.get("message"),
                "filters_applied": filters or {},
                "auto_filters_added": "Automatic date range and company filters applied if missing",
                "raw_result_keys": list(result.keys()) if result else [],
                "data_count": len(data) if data else 0,
                "result_type": type(result).__name__ if result else "None",
            }

            # Add debug info if no data found
            if not data or len(data) == 0:
                debug_info["debug_info"] = {
                    "filters_used": filters,
                    "result_structure": result,
                    "error_from_result": result.get("error") if result else None,
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
                    "Script Reports often have mandatory filters - check report definition or try execution to discover requirements"
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

        # Check if this is a prepared report
        if getattr(report_doc, "prepared_report", False) and not getattr(
            report_doc, "disable_prepared_report", False
        ):
            return ReportTools._handle_prepared_report_execution(report_doc, filters)

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
        from frappe.desk.reportview import execute

        return execute(
            doctype=report_doc.ref_doctype,
            filters=filters,
            fields=[col.fieldname for col in report_doc.columns],
            order_by=report_doc.sort_by,
            limit_page_length=1000,
        )
