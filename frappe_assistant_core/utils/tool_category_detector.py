# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Tool Category Detector - Automatically detects tool categories based on code analysis.

Categories:
- read_only: Tools that only read data (perm_type="read")
- write: Tools that modify data (perm_type in write/create/submit/cancel/amend)
- read_write: Tools that both read and write data
- privileged: Tools with elevated access (delete data, execute code, run queries)
"""

import ast
import inspect
from typing import Optional, Set

import frappe

# Map perm_type values to categories
PERM_TYPE_CATEGORIES = {
    "read": "read_only",
    "write": "write",
    "create": "write",
    "delete": "privileged",
    "submit": "write",
    "cancel": "write",
    "amend": "write",
    "export": "read_only",
    "import": "write",
    "print": "read_only",
    "email": "read_only",
    "share": "write",
    "report": "read_only",
}

# Tools that are always categorized as privileged (hardcoded list)
# These tools have elevated access - can delete data, execute code, or run queries
PRIVILEGED_TOOLS = {
    "execute_python_code",
    "run_python_code",
    "query_and_analyze",
    "run_database_query",
    "delete_document",
}

# Tools that are always categorized as read_only (hardcoded list)
READ_ONLY_TOOLS = {
    # Document tools
    "get_document",
    "list_documents",
    # Search tools
    "search_documents",
    "search_doctype",
    "search_link",
    "search",  # ChatGPT search
    "fetch",  # ChatGPT fetch
    # Metadata tools
    "get_doctype_info",
    "metadata_doctype",
    # Report tools
    "report_execute",
    "report_list",
    "report_requirements",  # Only reads report metadata
    "generate_report",  # Executes reports (read operation)
    # Workflow tools
    "workflow_list",
    "workflow_status",
    # Data science tools (read-only analysis)
    "analyze_frappe_data",
    "analyze_business_data",  # Only analyzes data, no modifications
    "extract_file_content",  # Only reads file content
    # Visualization tools (read-only)
    "list_user_dashboards",  # Only lists dashboards
}

# Tools that are always categorized as write (hardcoded list)
WRITE_TOOLS = {
    # Document tools
    "create_document",
    "update_document",
    "submit_document",
    # Workflow tools
    "run_workflow",
    # Visualization tools (create/modify)
    "create_dashboard",
    "create_dashboard_chart",
}


class ToolCategoryDetector:
    """Detects tool category by analyzing the tool's source code."""

    def __init__(self):
        self.logger = frappe.logger("tool_category_detector")

    def detect_category(self, tool_instance) -> str:
        """
        Detect the category of a tool based on its code.

        Args:
            tool_instance: An instance of a tool class

        Returns:
            Category string: 'read_only', 'write', 'read_write', or 'privileged'
        """
        tool_name = getattr(tool_instance, "name", None)

        # Check hardcoded lists first (fastest path)
        if tool_name:
            if tool_name in PRIVILEGED_TOOLS:
                return "privileged"
            if tool_name in READ_ONLY_TOOLS:
                return "read_only"
            if tool_name in WRITE_TOOLS:
                return "write"

        # Try to detect from source code
        try:
            perm_types = self._extract_perm_types(tool_instance)
            return self._categorize_from_perm_types(perm_types)
        except Exception as e:
            self.logger.warning(f"Failed to detect category for {tool_name}: {e}")
            return "read_write"  # Default to most permissive non-privileged category

    def _extract_perm_types(self, tool_instance) -> Set[str]:
        """
        Extract perm_type values used in the tool's execute method.

        Uses AST parsing to find:
        - validate_document_access(..., perm_type="...")
        - frappe.has_permission(..., perm_type="...")
        - perm_type="..." keyword arguments
        """
        perm_types = set()

        try:
            # Get source code of the execute method or the class
            source = inspect.getsource(tool_instance.__class__)
            tree = ast.parse(source)

            for node in ast.walk(tree):
                # Look for keyword arguments named 'perm_type'
                if isinstance(node, ast.keyword):
                    if node.arg == "perm_type" and isinstance(node.value, ast.Constant):
                        perm_types.add(str(node.value.value))

                # Look for string literals that match perm_type values
                # This catches cases like perm_type=perm_type where perm_type is passed in
                if isinstance(node, ast.Call):
                    func_name = self._get_func_name(node)
                    if func_name in ("validate_document_access", "has_permission"):
                        # Check positional and keyword arguments
                        for keyword in node.keywords:
                            if keyword.arg == "perm_type":
                                if isinstance(keyword.value, ast.Constant):
                                    perm_types.add(str(keyword.value.value))

        except Exception as e:
            self.logger.debug(f"Could not parse source for perm_types: {e}")

        return perm_types

    def _get_func_name(self, node: ast.Call) -> Optional[str]:
        """Extract function name from an AST Call node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None

    def _categorize_from_perm_types(self, perm_types: Set[str]) -> str:
        """
        Determine category based on the perm_types found.

        Args:
            perm_types: Set of perm_type strings found in code

        Returns:
            Category string
        """
        if not perm_types:
            return "read_write"  # Unknown, assume mixed

        # Check for privileged operations (elevated access)
        if "delete" in perm_types:
            return "privileged"

        # Check for write operations
        write_ops = {"write", "create", "submit", "cancel", "amend", "import", "share"}
        has_write = bool(perm_types & write_ops)

        # Check for read operations
        read_ops = {"read", "export", "print", "email", "report"}
        has_read = bool(perm_types & read_ops)

        if has_write and has_read:
            return "read_write"
        elif has_write:
            return "write"
        elif has_read:
            return "read_only"
        else:
            return "read_write"  # Unknown operations, assume mixed


# Global detector instance
_detector: Optional[ToolCategoryDetector] = None


def get_detector() -> ToolCategoryDetector:
    """Get or create the global detector instance."""
    global _detector
    if _detector is None:
        _detector = ToolCategoryDetector()
    return _detector


def detect_tool_category(tool_instance) -> str:
    """
    Convenience function to detect a tool's category.

    Args:
        tool_instance: An instance of a tool class

    Returns:
        Category string: 'read_only', 'write', 'read_write', or 'privileged'
    """
    return get_detector().detect_category(tool_instance)


def get_category_info(category: str) -> dict:
    """
    Get display information for a category.

    Args:
        category: Category string

    Returns:
        Dict with label, color, and description
    """
    categories = {
        "read_only": {
            "label": "Read Only",
            "color": "green",
            "icon": "fa-eye",
            "description": "This tool only reads data, no modifications are made",
        },
        "write": {
            "label": "Write",
            "color": "yellow",
            "icon": "fa-edit",
            "description": "This tool can create or modify data",
        },
        "read_write": {
            "label": "Read & Write",
            "color": "blue",
            "icon": "fa-exchange-alt",
            "description": "This tool can both read and modify data",
        },
        "privileged": {
            "label": "Privileged",
            "color": "orange",
            "icon": "fa-shield-alt",
            "description": "This tool has elevated access - can delete data, execute code, or run database queries",
        },
        # Keep backward compatibility for existing data
        "dangerous": {
            "label": "Privileged",
            "color": "orange",
            "icon": "fa-shield-alt",
            "description": "This tool has elevated access - can delete data, execute code, or run database queries",
        },
    }
    return categories.get(category, categories["read_write"])
