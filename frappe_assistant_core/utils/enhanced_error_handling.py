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
Enhanced Error Handling and Resource Monitoring for Frappe Assistant Core
Provides comprehensive error management, resource monitoring, and operation limits
"""

import signal
import sys
import threading
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import frappe
import psutil

from frappe_assistant_core.utils.cache import get_cached_server_settings
from frappe_assistant_core.utils.logger import api_logger


class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ResourceType(Enum):
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    EXECUTION_TIME = "execution_time"


@dataclass
class ResourceLimit:
    """Defines resource limits for operations"""

    resource_type: ResourceType
    limit_value: float
    warning_threshold: float
    unit: str
    description: str


@dataclass
class ErrorContext:
    """Enhanced error context with Frappe-specific information"""

    error_id: str
    operation_id: str
    user: str
    tool_name: str
    error_type: str
    severity: ErrorSeverity
    message: str
    frappe_context: Dict[str, Any]
    stack_trace: str
    timestamp: datetime
    resolution_suggestions: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_id": self.error_id,
            "operation_id": self.operation_id,
            "user": self.user,
            "tool_name": self.tool_name,
            "error_type": self.error_type,
            "severity": self.severity.value,
            "message": self.message,
            "frappe_context": self.frappe_context,
            "stack_trace": self.stack_trace,
            "timestamp": self.timestamp.isoformat(),
            "resolution_suggestions": self.resolution_suggestions,
        }


class ResourceMonitor:
    """Monitors system resources during operation execution"""

    def __init__(self):
        self.limits: Dict[ResourceType, ResourceLimit] = self._get_default_limits()
        self.monitoring_active = False
        self.monitoring_data: Dict[str, Any] = {}
        self._monitor_thread = None
        self._stop_monitoring = threading.Event()

    def _get_default_limits(self) -> Dict[ResourceType, ResourceLimit]:
        """Get default resource limits from settings"""
        try:
            settings = get_cached_server_settings()

            return {
                ResourceType.CPU: ResourceLimit(
                    ResourceType.CPU,
                    limit_value=80.0,  # 80% CPU usage
                    warning_threshold=60.0,
                    unit="percentage",
                    description="CPU usage limit",
                ),
                ResourceType.MEMORY: ResourceLimit(
                    ResourceType.MEMORY,
                    limit_value=1024.0,  # 1GB memory
                    warning_threshold=768.0,  # 768MB
                    unit="MB",
                    description="Memory usage limit",
                ),
                ResourceType.EXECUTION_TIME: ResourceLimit(
                    ResourceType.EXECUTION_TIME,
                    limit_value=300.0,  # 5 minutes
                    warning_threshold=240.0,  # 4 minutes
                    unit="seconds",
                    description="Maximum execution time",
                ),
            }
        except Exception:
            # Fallback defaults
            return {
                ResourceType.CPU: ResourceLimit(
                    ResourceType.CPU, 80.0, 60.0, "percentage", "CPU usage limit"
                ),
                ResourceType.MEMORY: ResourceLimit(
                    ResourceType.MEMORY, 1024.0, 768.0, "MB", "Memory usage limit"
                ),
                ResourceType.EXECUTION_TIME: ResourceLimit(
                    ResourceType.EXECUTION_TIME, 300.0, 240.0, "seconds", "Maximum execution time"
                ),
            }

    def start_monitoring(self, operation_id: str):
        """Start resource monitoring for an operation"""
        if self.monitoring_active:
            return

        self.monitoring_active = True
        self.monitoring_data[operation_id] = {
            "start_time": time.time(),
            "peak_cpu": 0.0,
            "peak_memory": 0.0,
            "warnings": [],
            "limits_exceeded": [],
        }

        self._stop_monitoring.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_resources, args=(operation_id,), daemon=True
        )
        self._monitor_thread.start()

    def stop_monitoring(self, operation_id: str) -> Dict[str, Any]:
        """Stop monitoring and return resource usage summary"""
        self.monitoring_active = False
        self._stop_monitoring.set()

        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)

        summary = self.monitoring_data.get(operation_id, {})
        if operation_id in self.monitoring_data:
            summary["duration"] = time.time() - summary["start_time"]
            summary["end_time"] = time.time()

        return summary

    def _monitor_resources(self, operation_id: str):
        """Monitor resources in background thread"""
        try:
            process = psutil.Process()

            while not self._stop_monitoring.is_set():
                try:
                    # Get current resource usage
                    cpu_percent = process.cpu_percent()
                    memory_info = process.memory_info()
                    memory_mb = memory_info.rss / 1024 / 1024

                    # Update peaks
                    data = self.monitoring_data[operation_id]
                    data["peak_cpu"] = max(data["peak_cpu"], cpu_percent)
                    data["peak_memory"] = max(data["peak_memory"], memory_mb)

                    # Check limits
                    self._check_resource_limits(operation_id, cpu_percent, memory_mb)

                    # Check execution time
                    elapsed = time.time() - data["start_time"]
                    time_limit = self.limits[ResourceType.EXECUTION_TIME]

                    if elapsed > time_limit.warning_threshold:
                        warning = f"Execution time warning: {elapsed:.1f}s > {time_limit.warning_threshold}s"
                        if warning not in data["warnings"]:
                            data["warnings"].append(warning)

                    if elapsed > time_limit.limit_value:
                        limit_exceeded = (
                            f"Execution time limit exceeded: {elapsed:.1f}s > {time_limit.limit_value}s"
                        )
                        if limit_exceeded not in data["limits_exceeded"]:
                            data["limits_exceeded"].append(limit_exceeded)

                        # Force stop operation
                        self._force_stop_operation(operation_id)
                        break

                    time.sleep(1.0)  # Monitor every second

                except psutil.NoSuchProcess:
                    break
                except Exception as e:
                    api_logger.error(f"Resource monitoring error: {str(e)}")
                    break

        except Exception as e:
            api_logger.error(f"Resource monitor initialization failed: {str(e)}")

    def _check_resource_limits(self, operation_id: str, cpu_percent: float, memory_mb: float):
        """Check if resource limits are exceeded"""
        data = self.monitoring_data[operation_id]

        # Check CPU
        cpu_limit = self.limits[ResourceType.CPU]
        if cpu_percent > cpu_limit.warning_threshold:
            warning = f"CPU usage warning: {cpu_percent:.1f}% > {cpu_limit.warning_threshold}%"
            if warning not in data["warnings"]:
                data["warnings"].append(warning)

        if cpu_percent > cpu_limit.limit_value:
            limit_exceeded = f"CPU limit exceeded: {cpu_percent:.1f}% > {cpu_limit.limit_value}%"
            if limit_exceeded not in data["limits_exceeded"]:
                data["limits_exceeded"].append(limit_exceeded)

        # Check Memory
        memory_limit = self.limits[ResourceType.MEMORY]
        if memory_mb > memory_limit.warning_threshold:
            warning = f"Memory usage warning: {memory_mb:.1f}MB > {memory_limit.warning_threshold}MB"
            if warning not in data["warnings"]:
                data["warnings"].append(warning)

        if memory_mb > memory_limit.limit_value:
            limit_exceeded = f"Memory limit exceeded: {memory_mb:.1f}MB > {memory_limit.limit_value}MB"
            if limit_exceeded not in data["limits_exceeded"]:
                data["limits_exceeded"].append(limit_exceeded)

    def _force_stop_operation(self, operation_id: str):
        """Force stop an operation that exceeded limits"""
        try:
            api_logger.warning(f"Force stopping operation {operation_id} due to resource limit exceeded")
            # In a real implementation, this would signal the operation to stop
            # For now, we just log the event
        except Exception as e:
            api_logger.error(f"Failed to force stop operation: {str(e)}")


class EnhancedErrorHandler:
    """Enhanced error handler with Frappe-specific context"""

    def __init__(self):
        self.error_patterns = self._load_error_patterns()
        self.resolution_map = self._load_resolution_map()

    def _load_error_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Load common error patterns and their classifications"""
        return {
            "PermissionError": {
                "severity": ErrorSeverity.HIGH,
                "category": "security",
                "description": "User lacks required permissions",
            },
            "ValidationError": {
                "severity": ErrorSeverity.MEDIUM,
                "category": "validation",
                "description": "Data validation failed",
            },
            "DoesNotExistError": {
                "severity": ErrorSeverity.MEDIUM,
                "category": "data",
                "description": "Requested resource does not exist",
            },
            "DuplicateEntryError": {
                "severity": ErrorSeverity.MEDIUM,
                "category": "data",
                "description": "Duplicate entry detected",
            },
            "LinkValidationError": {
                "severity": ErrorSeverity.MEDIUM,
                "category": "validation",
                "description": "Link field validation failed",
            },
            "MandatoryError": {
                "severity": ErrorSeverity.MEDIUM,
                "category": "validation",
                "description": "Mandatory field missing",
            },
            "ImportError": {
                "severity": ErrorSeverity.HIGH,
                "category": "system",
                "description": "Python module import failed",
            },
            "MemoryError": {
                "severity": ErrorSeverity.CRITICAL,
                "category": "resources",
                "description": "System out of memory",
            },
            "TimeoutError": {
                "severity": ErrorSeverity.HIGH,
                "category": "performance",
                "description": "Operation timed out",
            },
        }

    def _load_resolution_map(self) -> Dict[str, List[str]]:
        """Load resolution suggestions for common errors"""
        return {
            "PermissionError": [
                "Check user roles and permissions",
                "Verify DocType permissions",
                "Contact system administrator",
                "Review role-based access controls",
            ],
            "ValidationError": [
                "Check field validation rules",
                "Verify data format and types",
                "Review mandatory field requirements",
                "Validate linked document references",
            ],
            "DoesNotExistError": [
                "Verify document exists and is not deleted",
                "Check spelling of document names",
                "Ensure user has read permissions",
                "Review filters and search criteria",
            ],
            "ImportError": [
                "Check if required module is installed",
                "Verify Python environment setup",
                "Review module dependencies",
                "Contact system administrator",
            ],
            "MemoryError": [
                "Reduce data set size",
                "Process data in smaller batches",
                "Optimize query parameters",
                "Contact system administrator for resources",
            ],
            "TimeoutError": [
                "Reduce operation complexity",
                "Process data in smaller chunks",
                "Optimize database queries",
                "Increase timeout limits if necessary",
            ],
        }

    def create_error_context(
        self,
        operation_id: str,
        tool_name: str,
        exception: Exception,
        additional_context: Dict[str, Any] = None,
    ) -> ErrorContext:
        """Create enhanced error context with Frappe information"""

        error_type = type(exception).__name__
        error_pattern = self.error_patterns.get(error_type, {})

        # Gather Frappe context
        frappe_context = {
            "user": frappe.session.user if hasattr(frappe, "session") else "Unknown",
            "site": frappe.local.site
            if hasattr(frappe, "local") and hasattr(frappe.local, "site")
            else "Unknown",
            "request_id": frappe.local.request_id
            if hasattr(frappe, "local") and hasattr(frappe.local, "request_id")
            else None,
            "form_dict": dict(frappe.form_dict) if hasattr(frappe, "form_dict") else {},
            "method": frappe.request.method
            if hasattr(frappe, "request") and hasattr(frappe.request, "method")
            else None,
            "url": frappe.request.url
            if hasattr(frappe, "request") and hasattr(frappe.request, "url")
            else None,
        }

        if additional_context:
            frappe_context.update(additional_context)

        return ErrorContext(
            error_id=frappe.generate_hash(length=8),
            operation_id=operation_id,
            user=frappe_context["user"],
            tool_name=tool_name,
            error_type=error_type,
            severity=error_pattern.get("severity", ErrorSeverity.MEDIUM),
            message=str(exception),
            frappe_context=frappe_context,
            stack_trace=traceback.format_exc(),
            timestamp=datetime.now(),
            resolution_suggestions=self.resolution_map.get(
                error_type, ["Review error details and try again"]
            ),
        )

    def log_error(self, error_context: ErrorContext):
        """Log error with enhanced context"""
        try:
            # Log to Frappe error log
            frappe.log_error(
                message=f"Enhanced Error: {error_context.message}",
                title=f"{error_context.tool_name} - {error_context.error_type}",
                context=error_context.to_dict(),
            )

            # Log to audit trail
            self._log_to_audit_trail(error_context)

            # Store in cache for real-time access
            cache_key = f"error_context_{error_context.error_id}"
            frappe.cache.set_value(cache_key, error_context.to_dict(), expires_in_sec=3600)

        except Exception as e:
            api_logger.error(f"Failed to log error context: {str(e)}")

    def _log_to_audit_trail(self, error_context: ErrorContext):
        """Log error to audit trail"""
        try:
            from frappe.utils import now

            # Severity + frappe context + resolution suggestions don't have
            # dedicated columns; fold them into output_data so auditors still
            # see them when opening the row.
            extra_payload = {
                "severity": error_context.severity.value,
                "operation_id": error_context.operation_id,
                "frappe_context": error_context.frappe_context,
                "resolution_suggestions": error_context.resolution_suggestions,
            }
            try:
                output_data_str = frappe.as_json(extra_payload)
            except Exception:
                output_data_str = str(extra_payload)

            audit_doc = frappe.get_doc(
                {
                    "doctype": "Assistant Audit Log",
                    "action": error_context.tool_name or "error",
                    "tool_name": error_context.tool_name,
                    "user": error_context.user,
                    "status": "Error",
                    "error_type": error_context.error_type,
                    "error_message": error_context.message,
                    "traceback": error_context.stack_trace,
                    "output_data": output_data_str,
                    "target_name": error_context.operation_id,
                    "client_id": getattr(frappe.local, "assistant_client_id", None),
                    "session_id": getattr(frappe.local, "assistant_session_id", None),
                    "ip_address": getattr(frappe.local, "request_ip", None),
                    "timestamp": now(),
                }
            )
            audit_doc.insert(ignore_permissions=True)
            # Error path runs while the surrounding request is unwinding; commit
            # explicitly so the audit row survives even if the outer transaction
            # is rolled back. nosemgrep: frappe-semgrep-rules.rules.frappe-manual-commit
            frappe.db.commit()  # nosemgrep: frappe-semgrep-rules.rules.frappe-manual-commit

        except Exception as e:
            api_logger.error(f"Failed to log to audit trail: {str(e)}")


@contextmanager
def enhanced_execution_context(operation_id: str, tool_name: str, monitor_resources: bool = True):
    """Context manager for enhanced execution with error handling and resource monitoring"""

    resource_monitor = ResourceMonitor() if monitor_resources else None
    error_handler = EnhancedErrorHandler()

    try:
        # Start resource monitoring
        if resource_monitor:
            resource_monitor.start_monitoring(operation_id)

        yield {
            "operation_id": operation_id,
            "resource_monitor": resource_monitor,
            "error_handler": error_handler,
        }

    except Exception as e:
        # Handle error with enhanced context
        error_context = error_handler.create_error_context(
            operation_id=operation_id, tool_name=tool_name, exception=e
        )
        error_handler.log_error(error_context)

        # Re-raise the exception with enhanced context
        raise Exception(f"Enhanced Error [{error_context.error_id}]: {str(e)}") from e

    finally:
        # Stop resource monitoring and get summary
        if resource_monitor:
            monitoring_summary = resource_monitor.stop_monitoring(operation_id)

            # Log resource usage if significant
            if (
                monitoring_summary.get("peak_cpu", 0) > 50
                or monitoring_summary.get("peak_memory", 0) > 500
                or monitoring_summary.get("duration", 0) > 60
            ):
                api_logger.info(f"Resource usage for {operation_id}: {monitoring_summary}")


# API endpoints for error and resource monitoring


@frappe.whitelist()
def get_error_context(error_id: str) -> Dict[str, Any]:
    """Get detailed error context by error ID"""
    try:
        cache_key = f"error_context_{error_id}"
        error_data = frappe.cache.get_value(cache_key)

        if not error_data:
            return {"success": False, "message": "Error context not found"}

        return {"success": True, "error_context": error_data}

    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_resource_usage_stats() -> Dict[str, Any]:
    """Get current system resource usage statistics"""
    try:
        if not frappe.has_permission("System Manager"):
            return {"success": False, "message": "Insufficient permissions"}

        # Get current system stats
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        stats = {
            "cpu": {"usage_percent": cpu_percent, "cores": psutil.cpu_count()},
            "memory": {
                "total_mb": memory.total / 1024 / 1024,
                "used_mb": memory.used / 1024 / 1024,
                "available_mb": memory.available / 1024 / 1024,
                "usage_percent": memory.percent,
            },
            "disk": {
                "total_gb": disk.total / 1024 / 1024 / 1024,
                "used_gb": disk.used / 1024 / 1024 / 1024,
                "free_gb": disk.free / 1024 / 1024 / 1024,
                "usage_percent": (disk.used / disk.total) * 100,
            },
            "timestamp": datetime.now().isoformat(),
        }

        return {"success": True, "resource_stats": stats}

    except Exception as e:
        return {"success": False, "error": str(e)}
