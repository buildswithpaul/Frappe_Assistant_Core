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
Input validation utilities for Frappe Assistant Core.
Provides comprehensive validation for API inputs, tool arguments, and system data.
"""

import json
import re
from typing import Any, Dict, List, Optional, Union

import frappe
from frappe import _
from frappe.utils.html_utils import sanitize_html
from jsonschema import Draft7Validator, ValidationError, validate


def validate_json_rpc(request: Dict[str, Any]) -> Optional[str]:
    """
    Validate JSON-RPC 2.0 request structure.

    Args:
        request: Request dictionary to validate

    Returns:
        Error message if invalid, None if valid
    """
    # Check required fields
    if not isinstance(request, dict):
        return "Request must be a JSON object"

    if "jsonrpc" not in request:
        return "Missing 'jsonrpc' field"

    if request.get("jsonrpc") != "2.0":
        return "Invalid 'jsonrpc' version - must be '2.0'"

    if "method" not in request:
        return "Missing 'method' field"

    if not isinstance(request.get("method"), str):
        return "'method' must be a string"

    # Check optional fields
    if "params" in request and not isinstance(request["params"], (dict, list)):
        return "'params' must be an object or array"

    if "id" in request and not isinstance(request["id"], (str, int, type(None))):
        return "'id' must be a string, number, or null"

    return None


def validate_tool_arguments(arguments: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate tool arguments against JSON schema.

    Args:
        arguments: Arguments to validate
        schema: JSON schema for validation

    Returns:
        Validation result with success flag and errors
    """
    try:
        # Validate against schema
        validate(instance=arguments, schema=schema)

        return {"success": True, "validated_arguments": arguments}

    except ValidationError as e:
        return {
            "success": False,
            "error": f"Validation error: {e.message}",
            "error_path": list(e.absolute_path) if e.absolute_path else [],
            "invalid_value": e.instance,
        }
    except Exception as e:
        return {"success": False, "error": f"Schema validation failed: {str(e)}"}


def validate_doctype_name(doctype: str) -> bool:
    """
    Validate DocType name format and existence.

    Args:
        doctype: DocType name to validate

    Returns:
        True if valid DocType
    """
    if not isinstance(doctype, str):
        return False

    if not doctype.strip():
        return False

    # Check if DocType exists
    return frappe.db.exists("DocType", doctype)


def validate_field_names(doctype: str, fields: List[str]) -> Dict[str, Any]:
    """
    Validate field names for a specific DocType.

    Args:
        doctype: DocType name
        fields: List of field names to validate

    Returns:
        Validation result with valid and invalid fields
    """
    if not validate_doctype_name(doctype):
        return {"success": False, "error": f"Invalid DocType: {doctype}"}

    try:
        # Get DocType fields
        doctype_fields = frappe.get_meta(doctype).get_valid_columns()

        valid_fields = []
        invalid_fields = []

        for field in fields:
            if field in doctype_fields or field in ["name", "creation", "modified", "owner", "modified_by"]:
                valid_fields.append(field)
            else:
                invalid_fields.append(field)

        return {
            "success": len(invalid_fields) == 0,
            "valid_fields": valid_fields,
            "invalid_fields": invalid_fields,
            "total_fields": len(fields),
        }

    except Exception as e:
        return {"success": False, "error": f"Error validating fields: {str(e)}"}


def validate_filters(filters: Dict[str, Any], doctype: str = None) -> Dict[str, Any]:
    """
    Validate filter format and structure.

    Args:
        filters: Filter dictionary to validate
        doctype: Optional DocType for field validation

    Returns:
        Validation result
    """
    if not isinstance(filters, dict):
        return {"success": False, "error": "Filters must be a dictionary"}

    valid_filters = {}
    errors = []

    for field, condition in filters.items():
        # Validate field name format
        if not isinstance(field, str) or not field.strip():
            errors.append(f"Invalid field name: {field}")
            continue

        # Validate field exists in DocType if provided
        if doctype and not _is_valid_field(doctype, field):
            errors.append(f"Field '{field}' does not exist in DocType '{doctype}'")
            continue

        # Validate condition format
        if isinstance(condition, (str, int, float, bool, type(None))):
            # Simple equality condition
            valid_filters[field] = condition
        elif isinstance(condition, list) and len(condition) == 2:
            # Operator condition [operator, value]
            operator, value = condition
            if _is_valid_operator(operator):
                valid_filters[field] = condition
            else:
                errors.append(f"Invalid operator '{operator}' for field '{field}'")
        else:
            errors.append(f"Invalid condition format for field '{field}'")

    return {"success": len(errors) == 0, "valid_filters": valid_filters, "errors": errors}


def validate_sql_query(query: str) -> Dict[str, Any]:
    """
    Validate SQL query for security and syntax.

    Args:
        query: SQL query to validate

    Returns:
        Validation result with security analysis
    """
    if not isinstance(query, str) or not query.strip():
        return {"success": False, "error": "Query must be a non-empty string"}

    query = query.strip()

    # Security checks
    security_issues = []

    # Check for non-SELECT statements
    query_upper = query.upper()
    dangerous_keywords = [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "CREATE",
        "ALTER",
        "TRUNCATE",
        "REPLACE",
        "GRANT",
        "REVOKE",
        "EXEC",
        "EXECUTE",
    ]

    for keyword in dangerous_keywords:
        if keyword in query_upper:
            security_issues.append(f"Dangerous keyword detected: {keyword}")

    # Check for multiple statements
    if ";" in query.rstrip(";"):
        security_issues.append("Multiple statements not allowed")

    # Check for comments that might hide malicious code
    if "--" in query or "/*" in query:
        security_issues.append("Comments in queries not allowed")

    # Basic syntax validation
    syntax_valid = True
    syntax_error = None

    try:
        # Basic checks for SELECT query structure
        if not query_upper.startswith("SELECT"):
            syntax_valid = False
            syntax_error = "Query must start with SELECT"

        # Check for balanced parentheses
        if query.count("(") != query.count(")"):
            syntax_valid = False
            syntax_error = "Unbalanced parentheses"

    except Exception as e:
        syntax_valid = False
        syntax_error = f"Syntax validation error: {str(e)}"

    return {
        "success": len(security_issues) == 0 and syntax_valid,
        "security_issues": security_issues,
        "syntax_valid": syntax_valid,
        "syntax_error": syntax_error,
        "query_type": "SELECT" if query_upper.startswith("SELECT") else "UNKNOWN",
    }


def validate_plugin_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate plugin configuration structure.

    Args:
        config: Plugin configuration to validate

    Returns:
        Validation result
    """
    required_fields = ["name", "version"]
    optional_fields = ["description", "author", "dependencies", "requires_restart"]

    errors = []
    warnings = []

    # Check required fields
    for field in required_fields:
        if field not in config:
            errors.append(f"Missing required field: {field}")
        elif not isinstance(config[field], str) or not config[field].strip():
            errors.append(f"Field '{field}' must be a non-empty string")

    # Validate optional fields
    if "dependencies" in config:
        if not isinstance(config["dependencies"], list):
            errors.append("Dependencies must be a list")
        else:
            for dep in config["dependencies"]:
                if not isinstance(dep, str):
                    errors.append(f"Invalid dependency format: {dep}")

    if "requires_restart" in config and not isinstance(config["requires_restart"], bool):
        warnings.append("requires_restart should be a boolean")

    # Validate version format
    if "version" in config:
        version_pattern = r"^\d+\.\d+\.\d+.*$"
        if not re.match(version_pattern, config["version"]):
            warnings.append("Version should follow semantic versioning (x.y.z)")

    return {"success": len(errors) == 0, "errors": errors, "warnings": warnings, "validated_config": config}


def validate_mcp_tool_schema(tool_schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate MCP tool schema format.

    Args:
        tool_schema: Tool schema to validate

    Returns:
        Validation result
    """
    required_fields = ["name", "description", "inputSchema"]

    errors = []

    # Check required fields
    for field in required_fields:
        if field not in tool_schema:
            errors.append(f"Missing required field: {field}")

    # Validate name format
    if "name" in tool_schema:
        name = tool_schema["name"]
        if not isinstance(name, str) or not name.strip():
            errors.append("Tool name must be a non-empty string")
        elif not re.match(r"^[a-z][a-z0-9_]*$", name):
            errors.append("Tool name must be lowercase with underscores only")

    # Validate description
    if "description" in tool_schema:
        desc = tool_schema["description"]
        if not isinstance(desc, str) or len(desc.strip()) < 10:
            errors.append("Description must be at least 10 characters")

    # Validate input schema
    if "inputSchema" in tool_schema:
        schema = tool_schema["inputSchema"]
        if not isinstance(schema, dict):
            errors.append("inputSchema must be a JSON Schema object")
        else:
            # Validate JSON Schema format
            try:
                Draft7Validator.check_schema(schema)
            except Exception as e:
                errors.append(f"Invalid JSON Schema: {str(e)}")

    return {"success": len(errors) == 0, "errors": errors, "tool_name": tool_schema.get("name", "unknown")}


def validate_user_input(input_data: str, max_length: int = 10000) -> Dict[str, Any]:
    """
    Validate user input for security and format.

    Args:
        input_data: User input to validate
        max_length: Maximum allowed length

    Returns:
        Validation result
    """
    if not isinstance(input_data, str):
        return {"success": False, "error": "Input must be a string"}

    issues = []

    # Length check
    if len(input_data) > max_length:
        issues.append(f"Input too long: {len(input_data)} > {max_length}")

    # Security checks
    dangerous_patterns = [
        r"<script[^>]*>.*?</script>",  # Script tags
        r"javascript:",  # JavaScript URLs
        r"on\w+\s*=",  # Event handlers
        r"<iframe[^>]*>",  # IFrames
        r"<object[^>]*>",  # Objects
        r"<embed[^>]*>",  # Embeds
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, input_data, re.IGNORECASE):
            issues.append(f"Potentially dangerous content detected: {pattern}")

    # Character encoding check
    try:
        input_data.encode("utf-8")
    except UnicodeEncodeError:
        issues.append("Invalid character encoding")

    return {
        "success": len(issues) == 0,
        "issues": issues,
        "sanitized_input": _sanitize_input(input_data),
        "input_length": len(input_data),
    }


def _is_valid_field(doctype: str, field: str) -> bool:
    """Check if field exists in DocType"""
    try:
        meta = frappe.get_meta(doctype)
        valid_fields = meta.get_valid_columns()
        standard_fields = ["name", "creation", "modified", "owner", "modified_by"]
        return field in valid_fields or field in standard_fields
    except Exception:
        return False


def _is_valid_operator(operator: str) -> bool:
    """Check if filter operator is valid"""
    valid_operators = [
        "=",
        "!=",
        ">",
        ">=",
        "<",
        "<=",
        "like",
        "not like",
        "in",
        "not in",
        "between",
        "is",
        "is not",
    ]
    return operator.lower() in valid_operators


def _sanitize_input(input_data: str) -> str:
    """Sanitize user input.

    Delegates to Frappe's nh3/bleach-backed sanitizer rather than matching
    tags with regular expressions. The three patterns this used to run could
    not see past the first level of nesting: ``<scr<script>ipt>`` came out as
    ``<script>``, and ``<script\n>`` was not recognised as a tag at all
    because the pattern could not cross a newline. An allow-list parser
    decides what a tag is by parsing, which is the only way to get this right.
    """
    return sanitize_html(input_data, always_sanitize=True).strip()


def validate_email(email: str) -> bool:
    """Validate email format"""
    if not isinstance(email, str):
        return False

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_url(url: str) -> bool:
    """Validate URL format"""
    if not isinstance(url, str):
        return False

    pattern = r"^https?://[^\s/$.?#].[^\s]*$"
    return bool(re.match(pattern, url))


def validate_json_string(json_str: str) -> Dict[str, Any]:
    """Validate JSON string format"""
    try:
        parsed = json.loads(json_str)
        return {"success": True, "parsed_data": parsed}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Invalid JSON: {str(e)}"}
