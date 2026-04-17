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
Query and Analyse Tool for Data Science Plugin.
Executes complex SQL queries and provides data analysis capabilities.
"""

import re
from typing import Any, Dict, List

import frappe
import pandas as pd
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool


class QueryAndAnalyse(BaseTool):
    """
    Tool for executing complex SQL queries and analyzing data.

    Provides capabilities for:
    - Complex SQL query execution with joins
    - Query validation and optimization suggestions
    - Data analysis on query results
    - SELECT-only query restriction for security
    """

    def __init__(self):
        super().__init__()
        self.name = "run_database_query"
        self.description = self._get_description()
        self.requires_permission = None  # Permission checked dynamically in execute method

        self.inputSchema = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL query to execute (SELECT statements only)"},
                "analysis_type": {
                    "type": "string",
                    "enum": ["basic", "statistical", "detailed"],
                    "default": "basic",
                    "description": "Type of analysis to perform on results",
                },
                "validate_query": {
                    "type": "boolean",
                    "default": True,
                    "description": "Validate and optimize query before execution",
                },
                "format_results": {
                    "type": "boolean",
                    "default": True,
                    "description": "Format results for better readability",
                },
                "include_schema_info": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include table schema information in response",
                },
                "limit": {
                    "type": "integer",
                    "default": 100,
                    "maximum": 1000,
                    "description": "Maximum number of rows to return",
                },
            },
            "required": ["query"],
        }

    def _get_description(self) -> str:
        """Get tool description"""
        return """Execute complex SQL queries with joins and perform data analysis. Restricted to SELECT statements only. Requires System Manager role for security. Provides query validation, optimization suggestions, and statistical analysis of results."""

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute query and analyze results"""
        try:
            # Check permissions - requires System Manager role
            user_roles = frappe.get_roles()
            if "System Manager" not in user_roles:
                return {
                    "success": False,
                    "error": "Insufficient permissions. System Manager role required for query execution.",
                }

            query = arguments.get("query", "").strip()
            analysis_type = arguments.get("analysis_type", "basic")
            validate_query = arguments.get("validate_query", True)
            format_results = arguments.get("format_results", True)
            include_schema_info = arguments.get("include_schema_info", False)
            limit = min(arguments.get("limit", 100), 1000)  # Cap at 1000 rows

            # Validate query security
            validation_result = self._validate_query_security(query)
            if not validation_result["is_valid"]:
                return {"success": False, "error": validation_result["error"], "security_violation": True}

            # Query optimization suggestions
            optimization_suggestions = []
            if validate_query:
                optimization_suggestions = self._get_optimization_suggestions(query)

            # Execute query
            execution_result = self._execute_query(query, limit)
            if not execution_result["success"]:
                return execution_result

            # Analyze results
            analysis_result = self._analyze_results(execution_result["data"], analysis_type)

            # Format response
            response = {
                "success": True,
                "query_executed": query,
                "rows_returned": len(execution_result["data"]),
                "execution_time_ms": execution_result.get("execution_time_ms", 0),
                "data": execution_result["data"] if format_results else execution_result["raw_data"],
                "analysis": analysis_result,
            }

            if optimization_suggestions:
                response["optimization_suggestions"] = optimization_suggestions

            if include_schema_info:
                response["schema_info"] = self._get_schema_info(query)

            return response

        except Exception as e:
            frappe.log_error(title=_("Query and Analyse Error"), message=f"Error executing query: {str(e)}")

            return {"success": False, "error": str(e)}

    def _validate_query_security(self, query: str) -> Dict[str, Any]:
        """Validate query for security - only SELECT statements allowed"""
        query_upper = query.upper().strip()

        # Remove comments and extra whitespace
        query_clean = re.sub(r"--.*?\n|/\*.*?\*/", "", query_upper, flags=re.DOTALL)
        query_clean = re.sub(r"\s+", " ", query_clean).strip()

        # Check if it starts with SELECT
        if not query_clean.startswith("SELECT"):
            return {"is_valid": False, "error": "Only SELECT queries are allowed for security reasons."}

        # Check for dangerous keywords
        dangerous_keywords = [
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "CREATE",
            "ALTER",
            "TRUNCATE",
            "EXEC",
            "EXECUTE",
            "CALL",
            "DECLARE",
            "SET",
        ]

        for keyword in dangerous_keywords:
            if f" {keyword} " in f" {query_clean} " or query_clean.startswith(f"{keyword} "):
                return {
                    "is_valid": False,
                    "error": f"Query contains forbidden keyword: {keyword}. Only SELECT statements are allowed.",
                }

        # Check for multiple statements (basic check)
        if ";" in query.rstrip(";"):  # Allow single trailing semicolon
            return {
                "is_valid": False,
                "error": "Multiple statements not allowed. Please execute one SELECT query at a time.",
            }

        return {"is_valid": True}

    def _execute_query(self, query: str, limit: int) -> Dict[str, Any]:
        """Execute the SQL query safely"""
        try:
            import time

            start_time = time.time()

            # Add LIMIT if not present and within bounds
            if "LIMIT" not in query.upper():
                query = f"{query.rstrip(';')} LIMIT {limit}"

            # Execute query
            result = frappe.db.sql(query, as_dict=True)

            execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            return {
                "success": True,
                "data": result,
                "raw_data": result,  # Keep original for non-formatted output
                "execution_time_ms": round(execution_time, 2),
            }

        except Exception as e:
            return {"success": False, "error": f"Query execution failed: {str(e)}"}

    def _analyze_results(self, data: List[Dict], analysis_type: str) -> Dict[str, Any]:
        """Analyze query results"""
        if not data:
            return {"message": "No data returned from query"}

        try:
            df = pd.DataFrame(data)

            analysis = {
                "basic_info": {
                    "total_rows": len(df),
                    "total_columns": len(df.columns),
                    "column_names": list(df.columns),
                }
            }

            if analysis_type in ["statistical", "detailed"]:
                # Add statistical analysis for numeric columns
                numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
                if numeric_cols:
                    stats = df[numeric_cols].describe()
                    analysis["statistical_summary"] = stats.to_dict()

                # Data types info
                analysis["data_types"] = df.dtypes.astype(str).to_dict()

                # Missing values
                missing_values = df.isnull().sum()
                if missing_values.any():
                    analysis["missing_values"] = missing_values[missing_values > 0].to_dict()

            if analysis_type == "detailed":
                # Add correlation matrix for numeric columns
                if len(numeric_cols) > 1:
                    correlation_matrix = df[numeric_cols].corr()
                    analysis["correlation_matrix"] = correlation_matrix.to_dict()

                # Unique value counts for categorical columns
                categorical_cols = df.select_dtypes(include=["object"]).columns.tolist()
                if categorical_cols:
                    unique_counts = {}
                    for col in categorical_cols[:5]:  # Limit to first 5 categorical columns
                        unique_counts[col] = df[col].value_counts().head(10).to_dict()
                    analysis["unique_value_counts"] = unique_counts

            return analysis

        except Exception as e:
            return {"error": f"Analysis failed: {str(e)}"}

    def _get_optimization_suggestions(self, query: str) -> List[str]:
        """Provide query optimization suggestions"""
        suggestions = []
        query_upper = query.upper()

        # Basic optimization checks
        if "SELECT *" in query_upper:
            suggestions.append(
                "Consider selecting specific columns instead of using SELECT * for better performance"
            )

        if "WHERE" not in query_upper and "JOIN" in query_upper:
            suggestions.append("Consider adding WHERE clauses to filter data before joins")

        if query_upper.count("JOIN") > 3:
            suggestions.append("Query has multiple joins - ensure proper indexing on join columns")

        if "ORDER BY" in query_upper and "LIMIT" not in query_upper:
            suggestions.append("Consider adding LIMIT when using ORDER BY on large datasets")

        if "GROUP BY" in query_upper and "HAVING" not in query_upper:
            suggestions.append("Consider using HAVING clause to filter grouped results efficiently")

        return suggestions

    def _get_schema_info(self, query: str) -> Dict[str, Any]:
        """Extract schema information for tables used in query.

        Uses `frappe.db.get_table_columns_description` so the table name
        never appears interpolated into raw SQL from this module.
        """
        try:
            # Extract table names from query (basic implementation)
            tables = re.findall(r"FROM\s+`?(\w+)`?|JOIN\s+`?(\w+)`?", query, re.IGNORECASE)
            table_names = set()
            for match in tables:
                table_names.update([t for t in match if t])

            schema_info = {}
            for table in table_names:
                try:
                    columns = frappe.db.get_table_columns_description(table)
                    schema_info[table] = {"columns": columns, "total_columns": len(columns)}
                except Exception as e:
                    schema_info[table] = {"error": f"Could not retrieve schema: {str(e)}"}

            return schema_info

        except Exception as e:
            return {"error": f"Schema analysis failed: {str(e)}"}


# Make sure class name matches file name for discovery
query_and_analyse = QueryAndAnalyse
