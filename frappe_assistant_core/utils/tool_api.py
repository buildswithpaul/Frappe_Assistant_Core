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
Secure API Layer for Tool Orchestration.

This module provides a clean, documented API for LLM code to orchestrate
multiple Frappe Assistant tools without exposing internal directory structure
or implementation details.

Security: All methods maintain permission checks, read-only constraints,
and user context management.
"""

from typing import Any, Dict, List, Optional

import frappe


class FrappeAssistantAPI:
    """
    Unified API for tool orchestration within run_python_code sandbox.

    This API provides secure access to Frappe Assistant tools WITHOUT exposing
    internal directory structure or implementation details.

    Security guarantees:
    - All methods maintain permission checks
    - Read-only database access
    - User context management
    - Audit logging (inherited from tool execution)
    - No file system or network access

    Usage:
        Available as 'tools' in run_python_code sandbox
        Example: result = tools.generate_report("Sales Analytics", {...})
    """

    def __init__(self, current_user: str):
        """
        Initialize API with user context.

        Args:
            current_user: Current user for permission checks and audit trail
        """
        self.current_user = current_user
        self._report_tools = None

    # ========== REPORT OPERATIONS ==========

    def list_reports(self, module: Optional[str] = None, report_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get list of available reports (permission-filtered).

        Args:
            module: Optional filter by module (e.g., "Accounts", "Selling", "Stock")
            report_type: Optional filter by type ("Query Report", "Script Report", "Report Builder")

        Returns:
            dict with:
                - success (bool): Whether operation succeeded
                - reports (list): List of report dicts with name, type, module
                - count (int): Number of accessible reports
                - filters_applied (dict): Filters that were applied

        Example:
            # Get all selling reports
            result = tools.list_reports(module="Selling")
            for report in result["reports"]:
                print(f"{report['report_name']} ({report['report_type']})")
        """
        self._ensure_report_tools()
        return self._report_tools.list_reports(module, report_type)

    def get_report_info(self, report_name: str) -> Dict[str, Any]:
        """
        Get report metadata and requirements BEFORE executing.

        Use this FIRST to discover:
        - Required filters and their types
        - Available columns
        - Whether it's a prepared report (requires background processing)
        - Filter guidance with examples

        Args:
            report_name: Exact name of the report

        Returns:
            dict with:
                - success (bool): Whether operation succeeded
                - columns (list): Column definitions
                - filter_guidance (list): Required and optional filters
                - prepared_report_info (dict): Background processing details
                - filter_requirements (dict): Detailed filter analysis

        Example:
            # Check what filters are needed
            info = tools.get_report_info("Sales Analytics")
            print("Filter guidance:", info["filter_guidance"])

            # Then execute with proper filters
            result = tools.generate_report("Sales Analytics",
                filters={"doc_type": "Sales Invoice", "tree_type": "Customer"})
        """
        self._ensure_report_tools()
        return self._report_tools.get_report_columns(report_name)

    def generate_report(
        self, report_name: str, filters: Optional[Dict[str, Any]] = None, format: str = "json"
    ) -> Dict[str, Any]:
        """
        Execute a Frappe report with automatic prepared report handling.

        IMPORTANT: Many reports require specific filters. If you get an error
        about missing filters, use tools.get_report_info() first to discover
        what filters are needed.

        Prepared reports (large reports like Stock Balance, Sales Analytics):
        - Automatically queued for background processing
        - Polls for completion (up to 5 minutes)
        - Returns data when ready
        - Subsequent calls with same filters return cached results instantly

        Args:
            report_name: Exact name of the report
            filters: Filter dictionary (REQUIRED for most reports)
            format: Output format - "json", "csv", or "excel" (default: "json")

        Returns:
            dict with:
                - success (bool): Whether operation succeeded
                - data (list): Report data rows
                - columns (list): Column definitions
                - message (str): Status message
                - status (str): "completed", "timeout", or "error"

        Workflow Example:
            # For unknown reports, check requirements first
            info = tools.get_report_info("Sales Analytics")

            # Then execute with proper filters
            result = tools.generate_report("Sales Analytics",
                filters={
                    "doc_type": "Sales Invoice",
                    "tree_type": "Customer",
                    "from_date": "2024-01-01",
                    "to_date": "2024-12-31"
                })

            if result["success"]:
                data = result["data"]
                # Process data in Python (saves tokens!)
                top_customers = sorted(data, key=lambda x: x.get("revenue", 0), reverse=True)[:10]
                print(f"Top 10 customers: {top_customers}")
        """
        self._ensure_report_tools()
        return self._report_tools.execute_report(report_name, filters or {}, format)

    # ========== DOCUMENT OPERATIONS ==========

    def get_document(self, doctype: str, name: str) -> Dict[str, Any]:
        """
        Get a single document by name (permission-checked).

        Args:
            doctype: Document type (e.g., "Sales Invoice", "Customer")
            name: Document name/ID (e.g., "INV-001", "CUST-00001")

        Returns:
            dict with:
                - success (bool): Whether operation succeeded
                - data (dict): Document data (if successful)
                - error (str): Error message (if failed)

        Example:
            invoice = tools.get_document("Sales Invoice", "INV-001")
            if invoice["success"]:
                print(f"Total: {invoice['data']['grand_total']}")
        """
        try:
            if not frappe.has_permission(doctype, "read"):
                return {"success": False, "error": f"No permission to read {doctype}"}

            doc = frappe.get_doc(doctype, name)

            # Convert frappe._dict to plain Python dict for pandas compatibility
            data = dict(doc.as_dict())

            return {"success": True, "data": data}

        except frappe.PermissionError as e:
            return {"success": False, "error": f"Permission denied: {str(e)}"}
        except frappe.DoesNotExistError:
            return {"success": False, "error": f"{doctype} '{name}' not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_documents(
        self,
        doctype: str,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Get multiple documents with filters (permission-checked).

        Args:
            doctype: Document type (e.g., "Customer", "Item")
            filters: Filter dictionary (e.g., {"territory": "USA"})
            fields: List of fields to fetch (default: ["*"] = all fields)
            limit: Maximum records to return (default: 100)

        Returns:
            dict with:
                - success (bool): Whether operation succeeded
                - data (list): List of document dicts
                - count (int): Number of documents returned
                - error (str): Error message (if failed)

        Example:
            # Get US customers with specific fields
            result = tools.get_documents("Customer",
                filters={"territory": "USA"},
                fields=["name", "customer_name", "customer_group"],
                limit=50)

            if result["success"]:
                for customer in result["data"]:
                    print(f"{customer['customer_name']} - {customer['customer_group']}")
        """
        try:
            if not frappe.has_permission(doctype, "read"):
                return {"success": False, "error": f"No permission to read {doctype}"}

            raw_data = frappe.get_all(doctype, filters=filters or {}, fields=fields or ["*"], limit=limit)

            # Convert frappe._dict objects to plain Python dicts for pandas compatibility
            # This prevents "invalid __array_struct__" errors when using with pandas
            data = [dict(item) for item in raw_data]

            return {"success": True, "data": data, "count": len(data)}

        except frappe.PermissionError as e:
            return {"success": False, "error": f"Permission denied: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== SEARCH OPERATIONS ==========

    def search(self, query: str, doctype: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        """
        Search across Frappe (permission-checked).

        Args:
            query: Search query string
            doctype: Optional - limit search to specific doctype
            limit: Maximum results (default: 20)

        Returns:
            dict with:
                - success (bool): Whether operation succeeded
                - results (list): List of matching documents
                - count (int): Number of results
                - error (str): Error message (if failed)

        Example:
            # Search for customers
            result = tools.search("john", doctype="Customer")
            if result["success"]:
                for item in result["results"]:
                    print(item)
        """
        try:
            if doctype and not frappe.has_permission(doctype, "read"):
                return {"success": False, "error": f"No permission to search {doctype}"}

            # Use Frappe's built-in search
            if doctype:
                results = frappe.get_all(
                    doctype,
                    filters=[["name", "like", f"%{query}%"]],
                    fields=["name"],
                    limit=limit,
                )
            else:
                # Global search (limited for security)
                results = []

            return {"success": True, "results": results, "count": len(results)}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== METADATA OPERATIONS ==========

    def get_doctype_info(self, doctype: str) -> Dict[str, Any]:
        """
        Get metadata about a doctype (fields, links, permissions).

        Useful for understanding what data is available before querying.

        Args:
            doctype: Document type name (e.g., "Sales Invoice")

        Returns:
            dict with:
                - success (bool): Whether operation succeeded
                - fields (list): Field definitions
                - links (list): Link fields to other doctypes
                - is_table (bool): Whether this is a child table
                - is_submittable (bool): Whether documents can be submitted
                - error (str): Error message (if failed)

        Example:
            info = tools.get_doctype_info("Sales Invoice")
            if info["success"]:
                for field in info["fields"]:
                    print(f"{field['fieldname']}: {field['fieldtype']}")
        """
        try:
            if not frappe.has_permission(doctype, "read"):
                return {"success": False, "error": f"No permission to access {doctype} metadata"}

            meta = frappe.get_meta(doctype)

            return {
                "success": True,
                "fields": [
                    {
                        "fieldname": f.fieldname,
                        "label": f.label,
                        "fieldtype": f.fieldtype,
                        "options": f.options,
                        "reqd": f.reqd,
                    }
                    for f in meta.fields
                ],
                "links": [
                    {"fieldname": f.fieldname, "label": f.label, "options": f.options}
                    for f in meta.fields
                    if f.fieldtype == "Link"
                ],
                "is_table": meta.istable,
                "is_submittable": meta.is_submittable,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== INTERNAL HELPERS ==========

    def _ensure_report_tools(self):
        """Lazy-load ReportTools to avoid circular imports"""
        if not self._report_tools:
            from frappe_assistant_core.plugins.core.tools.report_tools import ReportTools

            self._report_tools = ReportTools

    def __repr__(self):
        """Provide helpful documentation when inspected in Python"""
        return """FrappeAssistantAPI - Secure tool orchestration for run_python_code

Available methods:

📊 Report Operations:
  • list_reports(module=None, report_type=None)
  • get_report_info(report_name)
  • generate_report(report_name, filters={}, format="json")

📄 Document Operations:
  • get_document(doctype, name)
  • get_documents(doctype, filters={}, fields=["*"], limit=100)

🔍 Search Operations:
  • search(query, doctype=None, limit=20)

📋 Metadata Operations:
  • get_doctype_info(doctype)

Examples:
  # Report workflow (handles dependencies)
  info = tools.get_report_info("Sales Analytics")
  result = tools.generate_report("Sales Analytics", {"doc_type": "Sales Invoice"})

  # Multi-source analysis
  sales = tools.generate_report("Sales Report", {...})
  customers = tools.get_documents("Customer", filters={"territory": "USA"})

All methods maintain security: permission checks, read-only access, user context."""
