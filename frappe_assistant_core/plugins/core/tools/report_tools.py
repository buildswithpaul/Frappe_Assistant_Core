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

from .report_requirements import VALUE_CONSTRAINED_FIELDTYPES, discover_filter_definitions


class ReportTools:
    """
    Shared utility class for Frappe report operations.

    This class provides the core business logic for report-related operations
    that is used by the individual tool classes (generate_report.py, report_list.py,
    report_requirements.py). Each tool class extends BaseTool and delegates to
    methods in this utility class.

    Methods:
    - execute_report(): Execute reports (Query Reports, Script Reports, Custom Reports)
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

            # Resolve the report's declared filter contract once, then use it for
            # both validation and defaulting so every code path agrees on it.
            definitions = ReportTools._filter_definitions(report_doc)

            # Validate filters before execution
            validation_result = ReportTools._validate_filters(filters or {}, report_doc, definitions)
            if not validation_result.get("valid"):
                return {
                    "success": False,
                    "error": "Invalid filter values provided",
                    "validation_errors": validation_result.get("errors", []),
                    "error_details": validation_result.get("error_details", []),
                    "suggestions": validation_result.get("suggestions", []),
                }

            # Snapshot user-provided filter keys before auto-defaults are injected
            user_filter_keys = set((filters or {}).keys())
            # Use a single dict so auto-defaults mutate it in-place
            effective_filters = dict(filters) if filters else {}

            # Execute report based on type
            if report_doc.report_type == "Query Report":
                result = ReportTools._execute_query_report(report_doc, effective_filters)
            elif report_doc.report_type == "Script Report":
                result = ReportTools._execute_script_report(report_doc, effective_filters, definitions)
            elif report_doc.report_type == "Report Builder":
                return {
                    "success": False,
                    "error": "Report Builder reports are not supported. Report Builder creates simple filtered views of DocTypes. For business intelligence and analytics, please use Script Reports, Query Reports, or Custom Reports instead.",
                }
            else:
                return {"success": False, "error": f"Unsupported report type: {report_doc.report_type}"}

            # Handle different result structures
            if isinstance(result, dict):
                # Extract the final filters that were actually used
                final_filters = result.pop("_final_filters", effective_filters)

                # Script/Query reports return {'result': [...], 'columns': [...]}
                raw_data = result.get("result", [])
                columns = result.get("columns", [])

                # Convert frappe._dict objects to plain Python dicts for pandas compatibility
                # This prevents "invalid __array_struct__" errors when using with pandas
                data = [dict(row) if isinstance(row, dict) else row for row in raw_data]

                # Determine which filters were auto-injected
                auto_added = {k: v for k, v in final_filters.items() if k not in user_filter_keys}

                debug_info = {
                    "success": True,
                    "report_name": report_name,
                    "report_type": report_doc.report_type,
                    "data": data,
                    "columns": columns,
                    "message": result.get("message"),
                    "filters_applied": final_filters,
                    "filters_auto_added": auto_added if auto_added else None,
                    "raw_result_keys": list(result.keys()) if result else [],
                    "data_count": len(data) if data else 0,
                    "result_type": type(result).__name__ if result else "None",
                }
            else:
                return {"success": False, "error": f"Unexpected result type: {type(result).__name__}"}

            # Add actionable guidance when report returns no data
            data = debug_info.get("data", [])
            if not data or len(data) == 0:
                debug_info["suggestion"] = (
                    f"Report returned 0 rows. This usually means the auto-defaulted filters "
                    f"(e.g. fiscal year dates, company) don't match any data. "
                    f"Call report_requirements('{report_name}') to see all mandatory filters "
                    f"with their valid options, then retry with explicit filter values."
                )
                if auto_added:
                    debug_info["suggestion"] += (
                        f" Auto-added filters were: {auto_added}. "
                        f"Check that these values match data in your system."
                    )

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

            result = run(
                report_name=report_doc.name,
                filters=filters,
                user=frappe.session.user,
                is_tree=getattr(report_doc, "is_tree", 0),
                parent_field=getattr(report_doc, "parent_field", None),
            )
            if isinstance(result, dict):
                result["_final_filters"] = filters
            return result
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
    def _execute_script_report(report_doc, filters, definitions=None):
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

            # Apply the defaults the report itself declares
            filters = ReportTools._apply_filter_defaults(report_doc, filters, definitions)

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

            result = run(report_name=report_doc.name, filters=filters, user=frappe.session.user)
            if isinstance(result, dict):
                result["_final_filters"] = filters
            return result

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
    def _validate_filters(filters: Dict[str, Any], report_doc, definitions=None) -> Dict[str, Any]:
        """Validate filter values against the report's own declared filter contract.

        Accepted values come from the same discovery that ``report_requirements``
        advertises, so the two tools cannot disagree about their own contract.

        A hardcoded fieldname -> values map used to stand in for this, and it was
        wrong in both directions. ``range`` alone means four different things
        across the standard apps: ageing buckets as Data ("30, 60, 90, 120") on
        the AR/AP and Stock Ageing reports, Weekly..Yearly on Sales/Stock
        Analytics, Daily|Weekly|Monthly on Website Analytics, and Monthly|Quarterly
        on Sales Pipeline Analytics. The map rejected the first group's advertised
        defaults outright and accepted values the last two do not offer
        (issue #229).

        A filter the report does not declare is left alone: guessing is what
        created the mismatch, and the report itself reports a real error.
        """
        errors = []
        suggestions = []
        details = []

        if definitions is None:
            definitions = ReportTools._filter_definitions(report_doc)

        for filter_key, filter_value in filters.items():
            if not filter_value:
                continue

            definition = definitions.get(filter_key)
            if not definition:
                continue

            fieldtype = definition.get("fieldtype")
            options = definition.get("options")

            # A constrained value set: validate membership against this report's
            # own options, and name them in the error.
            if fieldtype in VALUE_CONSTRAINED_FIELDTYPES and isinstance(options, list) and options:
                if isinstance(filter_value, list):
                    continue  # multi-value selection, not a single enum choice
                if filter_value not in options:
                    errors.append(
                        f"Invalid {filter_key}: '{filter_value}'. Must be one of: {', '.join(options)}"
                    )
                    details.append(
                        {
                            "fieldname": filter_key,
                            "type": "invalid_option",
                            "value": filter_value,
                            "accepted_values": options,
                        }
                    )
                continue

            # A Link target: validate the referenced record exists. `options` is
            # only a DocType when the report says so — on some filters it names a
            # companion fieldname instead (party -> party_type).
            if fieldtype == "Link" and isinstance(options, str) and options:
                if isinstance(filter_value, list):
                    continue  # list values are used by grouped reports
                if not frappe.db.exists("DocType", options):
                    continue
                if not frappe.db.exists(options, filter_value):
                    errors.append(f"Invalid {filter_key}: '{filter_value}' does not exist in {options}")
                    details.append(
                        {
                            "fieldname": filter_key,
                            "type": "unknown_record",
                            "value": filter_value,
                            "target_doctype": options,
                        }
                    )
                    suggestions.extend(ReportTools._link_value_suggestions(options, filter_value))
                continue

            if fieldtype in ("Date", "Datetime"):
                try:
                    from frappe.utils import getdate

                    getdate(filter_value)
                except Exception:
                    errors.append(f"Invalid {filter_key}: '{filter_value}'. Expected format: YYYY-MM-DD")
                    details.append({"fieldname": filter_key, "type": "invalid_date", "value": filter_value})

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "suggestions": suggestions,
            "error_details": details,
        }

    @staticmethod
    def _filter_definitions(report_doc) -> Dict[str, Any]:
        """The report's declared filter contract, or {} when discovery finds nothing."""
        try:
            return discover_filter_definitions(report_doc)
        except Exception as e:
            frappe.log_error(
                title=_("Report Filter Discovery Error"),
                message=f"Error discovering filters for {report_doc.name}: {str(e)}",
            )
            return {}

    @staticmethod
    def _link_value_suggestions(doctype: str, filter_value) -> list:
        """Name-like candidates for an unknown Link value, or valid examples."""
        try:
            similar = frappe.get_all(
                doctype, filters={"name": ["like", f"%{filter_value}%"]}, fields=["name"], limit=3
            )
            if similar:
                return [f"Did you mean one of these {doctype} names? {', '.join([s.name for s in similar])}"]

            valid_options = frappe.get_all(doctype, fields=["name"], limit=5)
            if valid_options:
                return [f"Valid {doctype} names include: {', '.join([v.name for v in valid_options])}"]
        except Exception:
            pass

        return []

    @staticmethod
    def _apply_filter_defaults(report_doc, filters, definitions=None):
        """Apply the default filter values the report itself declares.

        Uses the shared discovery rather than a private parser. A second
        hand-rolled JS regex lived here and could disagree with the definitions
        report_requirements advertises — the same class of divergence as the
        validator's hardcoded value map (issue #229).
        """
        try:
            if definitions is None:
                definitions = ReportTools._filter_definitions(report_doc)

            for fieldname, definition in definitions.items():
                default = definition.get("default")
                if default in (None, ""):
                    continue
                # Never override a value the caller supplied.
                if filters.get(fieldname) is not None:
                    continue
                filters[fieldname] = default

        except Exception as e:
            # Log error but don't fail the report execution
            frappe.log_error(f"Error applying filter defaults for {report_doc.name}: {str(e)}")

        return filters
