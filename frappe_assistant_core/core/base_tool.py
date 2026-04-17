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
Base class for all MCP tools with configuration and dependency management.
"""

import json
import time
import traceback
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _


class BaseTool(ABC):
    """
    Base class for all Frappe Assistant Core tools.

    Attributes:
        name: Tool identifier used in MCP protocol
        description: Human-readable description
        inputSchema: JSON schema for tool inputs
        requires_permission: DocType permission required
        category: Tool category for organization
        source_app: App that provides this tool
        dependencies: List of required dependencies
        default_config: Default configuration values
    """

    def __init__(self):
        self.name: str = ""
        self.description: str = ""
        self.inputSchema: Dict[str, Any] = {}
        self.requires_permission: Optional[str] = None
        self.category: str = "Custom"
        self.source_app: str = "frappe_assistant_core"
        self.dependencies: List[str] = []
        self.default_config: Dict[str, Any] = {}
        self.logger = frappe.logger(self.__class__.__module__)
        self._config_cache: Optional[Dict[str, Any]] = None

    @abstractmethod
    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool with given arguments.

        Args:
            arguments: Tool-specific arguments

        Returns:
            Tool execution result

        Raises:
            frappe.PermissionError: If user lacks permission
            frappe.ValidationError: If arguments are invalid
        """
        pass

    def validate_arguments(self, arguments: Dict[str, Any]) -> None:
        """
        Validate arguments against input schema.

        Args:
            arguments: Arguments to validate

        Raises:
            frappe.ValidationError: If validation fails
        """
        # Implement JSON schema validation
        required_fields = self.inputSchema.get("required", [])
        properties = self.inputSchema.get("properties", {})

        # Check required fields
        for field in required_fields:
            if field not in arguments:
                frappe.throw(_("Missing required field: {0}").format(field), frappe.ValidationError)

        # Validate field types
        for field, value in arguments.items():
            if field in properties:
                expected_type = properties[field].get("type")
                if not self._validate_type(value, expected_type):
                    frappe.throw(
                        _("Invalid type for field {0}: expected {1}").format(field, expected_type),
                        frappe.ValidationError,
                    )

    def check_permission(self) -> None:
        """
        Check if current user has required permissions.

        Raises:
            frappe.PermissionError: If permission check fails
        """
        if self.requires_permission:
            if not frappe.has_permission(self.requires_permission, "read"):
                frappe.throw(
                    _("Insufficient permissions to execute {0}").format(self.name), frappe.PermissionError
                )

    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate value matches expected JSON schema type"""
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        if expected_type in type_map:
            return isinstance(value, type_map[expected_type])
        return True

    def to_mcp_format(self) -> Dict[str, Any]:
        """Convert tool to MCP protocol format"""
        return {"name": self.name, "description": self.description, "inputSchema": self.inputSchema}

    def _safe_execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Safely execute tool with error handling, timing, and audit logging.

        Args:
            arguments: Tool arguments

        Returns:
            Execution result with success/error status
        """
        start_time = time.time()

        try:
            # Check dependencies
            deps_valid, deps_error = self.validate_dependencies()
            if not deps_valid:
                return {"success": False, "error": deps_error, "error_type": "DependencyError"}

            # Check permissions
            self.check_permission()

            # Validate arguments
            self.validate_arguments(arguments)

            # Execute tool
            result = self.execute(arguments)

            # Calculate execution time
            execution_time = time.time() - start_time

            # Detect tool-reported failure: the tool returned normally but its
            # payload is a dict with {"success": False}. Without this, every
            # non-raising tool call was being logged as Success even when the
            # tool explicitly signalled an error in its return value.
            tool_reported_failure = isinstance(result, dict) and result.get("success") is False

            if tool_reported_failure:
                response = {
                    "success": False,
                    "result": result,
                    "error": result.get("error") or "Tool reported failure",
                    "error_type": "ToolReportedError",
                    "execution_time": execution_time,
                }
                self.log_execution(arguments, response, execution_time, status="Error")
                self.logger.info(
                    f"{self.name} reported failure in {execution_time:.3f}s: {response['error']}"
                )
            else:
                response = {"success": True, "result": result, "execution_time": execution_time}
                self.log_execution(arguments, response, execution_time, status="Success")
                self.logger.info(f"Successfully executed {self.name} in {execution_time:.3f}s")

            return response

        except frappe.PermissionError as e:
            execution_time = time.time() - start_time
            response = {
                "success": False,
                "error": str(e),
                "error_type": "PermissionError",
                "execution_time": execution_time,
            }

            self.log_execution(arguments, response, execution_time, status="Permission Denied")

            frappe.log_error(title=_("Permission Error"), message=f"{self.name}: {str(e)}")

            return response

        except frappe.ValidationError as e:
            execution_time = time.time() - start_time
            response = {
                "success": False,
                "error": str(e),
                "error_type": "ValidationError",
                "execution_time": execution_time,
            }

            self.log_execution(arguments, response, execution_time, status="Error")

            frappe.log_error(title=_("Validation Error"), message=f"{self.name}: {str(e)}")

            return response

        except TimeoutError as e:
            execution_time = time.time() - start_time
            response = {
                "success": False,
                "error": str(e),
                "error_type": "Timeout",
                "execution_time": execution_time,
            }

            self.log_execution(
                arguments,
                response,
                execution_time,
                status="Timeout",
                traceback_str=traceback.format_exc(),
            )

            frappe.log_error(title=_("Tool Timeout"), message=f"{self.name}: {str(e)}")

            return response

        except Exception as e:
            execution_time = time.time() - start_time
            tb = traceback.format_exc()
            response = {
                "success": False,
                "error": str(e),
                "error_type": "ExecutionError",
                "execution_time": execution_time,
            }

            self.log_execution(
                arguments,
                response,
                execution_time,
                status="Error",
                traceback_str=tb,
            )

            self.logger.error(f"Tool execution failed: {self.name} - {str(e)}", exc_info=True)
            frappe.log_error(
                title=_("Tool Execution Error"),
                message=f"Tool: {self.name}\nError: {str(e)}\nType: {type(e).__name__}\nArgs: {arguments}\n\nFull traceback:\n{tb}",
            )

            return response

    def get_metadata(self) -> Dict[str, Any]:
        """
        Get tool metadata for admin/debugging purposes.

        Returns:
            Tool metadata including class info, permissions, etc.
        """
        return {
            "name": self.name,
            "description": self.description,
            "class": self.__class__.__name__,
            "module": self.__class__.__module__,
            "source_app": self.source_app,
            "category": self.category,
            "requires_permission": self.requires_permission,
            "dependencies": self.dependencies,
            "inputSchema": self.inputSchema,
            "default_config": self.default_config,
        }

    def get_config(self) -> Dict[str, Any]:
        """
        Get effective configuration using hierarchy: site > app > tool defaults.

        Returns:
            Merged configuration dictionary
        """
        if self._config_cache is not None:
            return self._config_cache

        # Start with tool defaults
        config = self.default_config.copy()

        # Apply app-level configuration from hooks
        app_config = self._get_app_config()
        if app_config:
            config.update(app_config)

        # Apply site-level configuration
        site_config = self._get_site_config()
        if site_config:
            config.update(site_config)

        # Cache the result
        self._config_cache = config
        return config

    def _get_app_config(self) -> Dict[str, Any]:
        """Get app-level configuration from hooks"""
        try:
            from frappe.utils import get_hooks

            tool_configs = get_hooks("assistant_tool_configs") or {}
            return tool_configs.get(self.name, {})
        except Exception:
            return {}

    def _get_site_config(self) -> Dict[str, Any]:
        """Get site-level configuration from site_config.json"""
        try:
            site_config = frappe.conf.get("assistant_tools", {})
            return site_config.get(self.name, {})
        except Exception:
            return {}

    def validate_dependencies(self) -> Tuple[bool, Optional[str]]:
        """
        Check if all tool dependencies are available.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.dependencies:
            return True, None

        missing_deps = []
        for dep in self.dependencies:
            try:
                # Try to import the dependency
                __import__(dep)
            except ImportError:
                missing_deps.append(dep)

        if missing_deps:
            return False, f"Missing dependencies: {', '.join(missing_deps)}"

        return True, None

    def clear_config_cache(self):
        """Clear cached configuration to force reload"""
        self._config_cache = None

    def log_execution(
        self,
        arguments: Dict[str, Any],
        result: Dict[str, Any],
        execution_time: float,
        status: str = "Success",
        traceback_str: Optional[str] = None,
    ):
        """
        Log tool execution for audit purposes.

        Args:
            arguments: Tool arguments (sensitive data will be sanitized)
            result: Execution result
            execution_time: Time taken in seconds
            status: Audit-log status value — one of "Success", "Error",
                "Timeout", "Permission Denied". Must match the DocType Select.
            traceback_str: Full Python traceback on exception paths. None otherwise.
        """
        try:
            from frappe_assistant_core.utils.audit_trail import log_tool_execution

            # Extract the actual tool result (not the wrapper) for audit logging
            if result.get("success") and "result" in result:
                actual_tool_output = result["result"]
            else:
                actual_tool_output = result

            sanitized_output = self._sanitize_data(actual_tool_output)

            log_tool_execution(
                tool_name=self.name,
                user=frappe.session.user,
                arguments=self._sanitize_arguments(arguments),
                status=status,
                execution_time=execution_time,
                source_app=self.source_app,
                error_message=result.get("error") if status != "Success" else None,
                error_type=result.get("error_type"),
                traceback_str=traceback_str,
                output_data=sanitized_output,
            )
        except Exception as e:
            # Don't fail tool execution due to logging issues
            self.logger.warning(f"Failed to log execution for {self.name}: {str(e)}")

    def _sanitize_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from arguments for logging"""
        sensitive_keys = ["password", "api_key", "secret", "token", "auth"]
        sanitized = {}

        for key, value in arguments.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = value

        return sanitized

    def _sanitize_data(self, data: Any) -> Any:
        """Helper method to sanitize data recursively"""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                # Skip very large data arrays to prevent huge logs
                if key == "data" and isinstance(value, list) and len(value) > 10:
                    sanitized[key] = f"[{len(value)} items - truncated for logging]"
                # Redact sensitive information
                elif any(
                    sensitive in key.lower()
                    for sensitive in ["password", "api_key", "secret", "token", "auth"]
                ):
                    sanitized[key] = "***REDACTED***"
                # Truncate very long strings
                elif isinstance(value, str) and len(value) > 1000:
                    sanitized[key] = value[:1000] + "[... truncated]"
                # Recursively sanitize nested objects
                elif isinstance(value, (dict, list)):
                    sanitized[key] = self._sanitize_data(value)
                else:
                    sanitized[key] = value
            return sanitized
        elif isinstance(data, list):
            # Truncate large lists but keep first few items
            if len(data) > 10:
                return [self._sanitize_data(item) for item in data[:3]] + [
                    f"... and {len(data) - 3} more items"
                ]
            else:
                return [self._sanitize_data(item) for item in data]
        else:
            return data
