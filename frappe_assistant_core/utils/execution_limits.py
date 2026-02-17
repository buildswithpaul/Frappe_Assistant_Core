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
Execution Limits and Resource Controls for Safe Code Execution.

Provides timeout enforcement, memory limits, CPU limits, and recursion depth
controls to prevent runaway code from crashing the system.
"""

import platform
import signal
import sys
from contextlib import contextmanager
from typing import Any, Dict, Optional

import frappe


class ExecutionTimeoutError(Exception):
    """Raised when code execution exceeds the allowed time limit."""

    pass


class MemoryLimitError(Exception):
    """Raised when code execution exceeds the allowed memory limit."""

    pass


class ResourceLimitError(Exception):
    """Raised when any resource limit is exceeded."""

    pass


# Default limits
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_MEMORY_MB = 512  # 512 MB
DEFAULT_MAX_CPU_TIME_SECONDS = 60
DEFAULT_MAX_RECURSION_DEPTH = 100
DEFAULT_MAX_OUTPUT_SIZE = 1024 * 1024  # 1 MB output limit


def _timeout_handler(signum, frame):
    """Signal handler for timeout."""
    raise ExecutionTimeoutError(
        "Code execution timed out. The code took too long to execute and was terminated "
        "to prevent system resource exhaustion. Consider optimizing your code or breaking "
        "it into smaller chunks."
    )


@contextmanager
def timeout_limit(seconds: int = DEFAULT_TIMEOUT_SECONDS):
    """
    Context manager to enforce execution timeout using signals.

    Args:
        seconds: Maximum execution time in seconds.

    Raises:
        ExecutionTimeoutError: If execution exceeds the time limit.

    Note:
        This uses SIGALRM which only works on Unix-like systems.
        On Windows, this is a no-op (timeout not enforced).
    """
    if platform.system() == "Windows":
        # Windows doesn't support SIGALRM, skip timeout enforcement
        frappe.logger("execution_limits").warning("Timeout enforcement not available on Windows")
        yield
        return

    # Store old handler
    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(seconds)

    try:
        yield
    finally:
        # Cancel the alarm and restore old handler
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


@contextmanager
def memory_limit(max_memory_mb: int = DEFAULT_MAX_MEMORY_MB):
    """
    Context manager to enforce memory limits using resource module.

    Args:
        max_memory_mb: Maximum memory in megabytes.

    Note:
        This uses the resource module which only works on Unix-like systems.
        On Windows, this is a no-op (memory limit not enforced).
    """
    if platform.system() == "Windows":
        frappe.logger("execution_limits").warning("Memory limits not available on Windows")
        yield
        return

    try:
        import resource

        # Convert MB to bytes
        max_memory_bytes = max_memory_mb * 1024 * 1024

        # Get current limits
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)

        # Set new limits (soft limit is what matters for enforcement)
        # We don't want to exceed the existing hard limit
        new_soft = min(max_memory_bytes, hard) if hard != resource.RLIM_INFINITY else max_memory_bytes

        resource.setrlimit(resource.RLIMIT_AS, (new_soft, hard))

        try:
            yield
        finally:
            # Restore original limits
            resource.setrlimit(resource.RLIMIT_AS, (soft, hard))

    except (ImportError, ValueError, OSError) as e:
        # resource module not available or limits can't be set
        frappe.logger("execution_limits").warning(f"Could not set memory limits: {e}")
        yield


@contextmanager
def cpu_time_limit(max_cpu_seconds: int = DEFAULT_MAX_CPU_TIME_SECONDS):
    """
    Context manager to enforce CPU time limits.

    Args:
        max_cpu_seconds: Maximum CPU time in seconds.

    Note:
        This uses the resource module which only works on Unix-like systems.
        On Windows, this is a no-op.
    """
    if platform.system() == "Windows":
        frappe.logger("execution_limits").warning("CPU time limits not available on Windows")
        yield
        return

    try:
        import resource

        # Get current limits
        soft, hard = resource.getrlimit(resource.RLIMIT_CPU)

        # Set new limits
        new_soft = min(max_cpu_seconds, hard) if hard != resource.RLIM_INFINITY else max_cpu_seconds

        resource.setrlimit(resource.RLIMIT_CPU, (new_soft, hard))

        try:
            yield
        finally:
            # Restore original limits
            resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))

    except (ImportError, ValueError, OSError) as e:
        frappe.logger("execution_limits").warning(f"Could not set CPU time limits: {e}")
        yield


@contextmanager
def recursion_limit(max_depth: int = DEFAULT_MAX_RECURSION_DEPTH):
    """
    Context manager to enforce recursion depth limits.

    Args:
        max_depth: Maximum recursion depth.
    """
    old_limit = sys.getrecursionlimit()

    # Set a lower recursion limit for sandboxed code
    # Add some buffer for the framework overhead
    sys.setrecursionlimit(max_depth + 50)

    try:
        yield
    finally:
        # Restore original limit
        sys.setrecursionlimit(old_limit)


@contextmanager
def all_execution_limits(
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_memory_mb: int = DEFAULT_MAX_MEMORY_MB,
    max_cpu_seconds: int = DEFAULT_MAX_CPU_TIME_SECONDS,
    max_recursion_depth: int = DEFAULT_MAX_RECURSION_DEPTH,
):
    """
    Context manager that applies all execution limits.

    Args:
        timeout_seconds: Maximum wall-clock time.
        max_memory_mb: Maximum memory in MB.
        max_cpu_seconds: Maximum CPU time.
        max_recursion_depth: Maximum recursion depth.

    Example:
        with all_execution_limits(timeout_seconds=30, max_memory_mb=256):
            exec(user_code, sandbox_env)
    """
    with timeout_limit(timeout_seconds):
        with memory_limit(max_memory_mb):
            with cpu_time_limit(max_cpu_seconds):
                with recursion_limit(max_recursion_depth):
                    yield


def get_execution_limits_from_settings() -> Dict[str, int]:
    """
    Get execution limits from Assistant Core Settings.

    Returns:
        Dict with timeout_seconds, max_memory_mb, max_cpu_seconds, max_recursion_depth
    """
    try:
        settings = frappe.get_cached_doc("Assistant Core Settings")

        return {
            "timeout_seconds": getattr(settings, "code_execution_timeout", DEFAULT_TIMEOUT_SECONDS)
            or DEFAULT_TIMEOUT_SECONDS,
            "max_memory_mb": getattr(settings, "code_execution_max_memory_mb", DEFAULT_MAX_MEMORY_MB)
            or DEFAULT_MAX_MEMORY_MB,
            "max_cpu_seconds": getattr(
                settings, "code_execution_max_cpu_seconds", DEFAULT_MAX_CPU_TIME_SECONDS
            )
            or DEFAULT_MAX_CPU_TIME_SECONDS,
            "max_recursion_depth": getattr(
                settings, "code_execution_max_recursion", DEFAULT_MAX_RECURSION_DEPTH
            )
            or DEFAULT_MAX_RECURSION_DEPTH,
        }
    except Exception:
        # Return defaults if settings can't be loaded
        return {
            "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
            "max_memory_mb": DEFAULT_MAX_MEMORY_MB,
            "max_cpu_seconds": DEFAULT_MAX_CPU_TIME_SECONDS,
            "max_recursion_depth": DEFAULT_MAX_RECURSION_DEPTH,
        }


def truncate_output(output: str, max_size: int = DEFAULT_MAX_OUTPUT_SIZE) -> str:
    """
    Truncate output to prevent memory issues with large outputs.

    Args:
        output: The output string to truncate.
        max_size: Maximum size in bytes.

    Returns:
        Truncated output with indicator if truncation occurred.
    """
    if len(output) <= max_size:
        return output

    truncated = output[:max_size]
    return (
        f"{truncated}\n\n"
        f"... [OUTPUT TRUNCATED - exceeded {max_size // 1024}KB limit. "
        f"Original size: {len(output) // 1024}KB]"
    )


def check_system_resources() -> Dict[str, Any]:
    """
    Check current system resource usage.

    Returns:
        Dict with memory_usage_mb, cpu_percent, etc.
    """
    result = {
        "platform": platform.system(),
        "limits_available": platform.system() != "Windows",
    }

    try:
        import resource

        # Get current memory usage
        usage = resource.getrusage(resource.RUSAGE_SELF)
        result["memory_usage_mb"] = usage.ru_maxrss / 1024  # Convert KB to MB on Linux
        result["user_time_seconds"] = usage.ru_utime
        result["system_time_seconds"] = usage.ru_stime
    except ImportError:
        result["memory_usage_mb"] = "N/A (resource module not available)"

    return result
