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
Isolated subprocess worker for safe Python code execution.

Runs user code in a disposable process so that resource limits (RLIMIT_CPU,
RLIMIT_AS, SIGALRM) only affect the child — never the Frappe/gunicorn worker.

Usage:
    python -m frappe_assistant_core.utils.code_execution_subprocess < request.json

Communication is via JSON over stdin/stdout, following the same pattern as
``ocr_subprocess.py``.
"""

import io
import json
import platform
import signal
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout

# ---------------------------------------------------------------------------
# Resource limit helpers (applied permanently — the process is disposable)
# ---------------------------------------------------------------------------


class ExecutionTimeoutError(Exception):
    """Raised when code execution exceeds the wall-clock timeout."""

    pass


class CPUTimeLimitError(Exception):
    """Raised when code execution exceeds the CPU time limit."""

    pass


def _timeout_handler(signum, frame):
    raise ExecutionTimeoutError(
        "Code execution timed out. The code took too long to execute and was "
        "terminated to prevent system resource exhaustion."
    )


def _cpu_limit_handler(signum, frame):
    raise CPUTimeLimitError("Code execution exceeded the CPU time limit and was terminated.")


def _apply_limits(limits: dict) -> None:
    """Apply resource limits permanently on the current (subprocess) process.

    Safe to call because the process is disposable — no need to save/restore.
    """
    timeout = limits.get("timeout_seconds", 30)
    max_memory_mb = limits.get("max_memory_mb", 512)
    max_cpu_seconds = limits.get("max_cpu_seconds", 60)
    max_recursion_depth = limits.get("max_recursion_depth", 100)

    # 1. Wall-clock timeout via SIGALRM (works: we ARE the main thread)
    if platform.system() != "Windows":
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout)

    # 2. CPU time limit — relative to current usage so we measure only
    #    the sandboxed code, not interpreter startup.
    if platform.system() != "Windows":
        try:
            import resource

            usage = resource.getrusage(resource.RUSAGE_SELF)
            current_cpu = int(usage.ru_utime + usage.ru_stime) + 1  # +1 rounding buffer
            new_soft = current_cpu + max_cpu_seconds
            _, hard = resource.getrlimit(resource.RLIMIT_CPU)
            if hard != resource.RLIM_INFINITY:
                new_soft = min(new_soft, hard)
            resource.setrlimit(resource.RLIMIT_CPU, (new_soft, hard))
            # Install SIGXCPU handler so we get a catchable exception
            # instead of a silent process kill.
            signal.signal(signal.SIGXCPU, _cpu_limit_handler)
        except (ImportError, ValueError, OSError):
            pass

    # 3. Memory limit (RLIMIT_AS) — additive on top of current VM footprint.
    #    Only effective on Linux; macOS does not enforce RLIMIT_AS.
    if platform.system() != "Windows":
        try:
            import resource

            # Try reading current VM from /proc (Linux only)
            current_vm = 0
            try:
                with open("/proc/self/status") as f:  # nosemgrep: frappe-security-file-traversal
                    for line in f:
                        if line.startswith("VmSize:"):
                            current_vm = int(line.split()[1]) * 1024
                            break
            except Exception:
                pass

            delta_bytes = max_memory_mb * 1024 * 1024
            new_limit = current_vm + delta_bytes if current_vm > 0 else delta_bytes

            soft, hard = resource.getrlimit(resource.RLIMIT_AS)
            if hard != resource.RLIM_INFINITY:
                new_limit = min(new_limit, hard)
            resource.setrlimit(resource.RLIMIT_AS, (new_limit, hard))
        except (ImportError, ValueError, OSError):
            pass

    # 4. Recursion depth
    sys.setrecursionlimit(max_recursion_depth + 50)


# ---------------------------------------------------------------------------
# Execution environment setup (mirrors run_python_code._setup_secure_execution_environment)
# ---------------------------------------------------------------------------


def _make_restricted_import():
    """Create a restricted __import__ allowing only known-safe package roots."""
    real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

    allowed_roots = frozenset(
        {
            "numpy",
            "pandas",
            "dateutil",
            "pytz",
            "six",
            "decimal",
            "fractions",
            "numbers",
            "encodings",
            "codecs",
            "unicodedata",
            "_decimal",
            "_strptime",
            "calendar",
            "locale",
            "warnings",
            "contextlib",
            "abc",
            "collections",
            "functools",
            "itertools",
            "operator",
            "copy",
            "math",
            "statistics",
            "json",
            "re",
            "random",
            "datetime",
            "string",
            "textwrap",
            "struct",
            "array",
            "bisect",
            "heapq",
            "_thread",
            "threading",
            "concurrent",
            "queue",
        }
    )

    def restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level > 0:
            return real_import(name, globals, locals, fromlist, level)
        root = name.split(".")[0]
        if root.startswith("_") or root in allowed_roots:
            return real_import(name, globals, locals, fromlist, level)
        raise ImportError(
            f"Import of '{name}' is not allowed in the sandbox. "
            f"All supported libraries are pre-loaded — do not use import statements."
        )

    return restricted_import


def _setup_execution_environment(user: str) -> dict:
    """Build the sandboxed globals dict for exec()."""
    import frappe

    from frappe_assistant_core.utils.read_only_db import ReadOnlyDatabase
    from frappe_assistant_core.utils.tool_api import FrappeAssistantAPI

    env = {
        "__builtins__": {
            "__import__": _make_restricted_import(),
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "range": range,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "sorted": sorted,
            "sum": sum,
            "min": min,
            "max": max,
            "abs": abs,
            "round": round,
            "print": print,
            "type": type,
            "isinstance": isinstance,
            "hasattr": hasattr,
            "getattr": getattr,
            "Exception": Exception,
            "ValueError": ValueError,
            "TypeError": TypeError,
            "KeyError": KeyError,
            "IndexError": IndexError,
            "AttributeError": AttributeError,
            "NameError": NameError,
            "ZeroDivisionError": ZeroDivisionError,
            "StopIteration": StopIteration,
        },
    }

    # Standard libraries
    import datetime
    import decimal
    import fractions
    import json as _json
    import math
    import random
    import re
    import statistics

    env.update(
        {
            "math": math,
            "statistics": statistics,
            "decimal": decimal,
            "fractions": fractions,
            "datetime": datetime,
            "json": _json,
            "re": re,
            "random": random,
        }
    )

    # Data-science libraries (best-effort)
    class _LibraryNotInstalled:
        def __init__(self, name):
            self._name = name

        def __getattr__(self, attr):
            raise ImportError(f"{self._name} is not installed in this environment.")

        def __call__(self, *a, **kw):
            return self.__getattr__("__call__")

    available, missing = [], []

    for alias, pkg in [("pd", "pandas"), ("np", "numpy")]:
        try:
            mod = __import__(pkg)
            env[alias] = mod
            env[pkg] = mod
            available.append(f"{pkg} ({alias})")
        except ImportError:
            missing.append(pkg)
            stub = _LibraryNotInstalled(pkg)
            env[alias] = stub
            env[pkg] = stub

    # Frappe integration — read-only
    secure_db = ReadOnlyDatabase(frappe.db)
    tools_api = FrappeAssistantAPI(user)

    env.update(
        {
            "frappe": frappe,
            "get_doc": frappe.get_doc,
            "get_list": frappe.get_list,
            "get_all": frappe.get_all,
            "get_single": frappe.get_single,
            "db": secure_db,
            "current_user": user,
            "tools": tools_api,
            "_available_libraries": available,
            "_missing_libraries": missing,
        }
    )

    return env


# ---------------------------------------------------------------------------
# Variable serialization (mirrors run_python_code._serialize_variable)
# ---------------------------------------------------------------------------

_EXCLUDED_VARS = frozenset(
    {
        "frappe",
        "pd",
        "np",
        "data",
        "current_user",
        "db",
        "get_doc",
        "get_list",
        "get_all",
        "get_single",
        "math",
        "datetime",
        "json",
        "re",
        "random",
        "statistics",
        "decimal",
        "fractions",
        "pandas",
        "numpy",
        "tools",
        "__builtins__",
        "__name__",
        "__doc__",
        "__package__",
        "__loader__",
        "__spec__",
        "__annotations__",
        "__cached__",
        "_available_libraries",
        "_missing_libraries",
    }
)


def _serialize_variable(value):
    """Serialize a variable to a JSON-compatible representation."""
    try:
        # Pandas objects
        if hasattr(value, "to_dict"):
            return value.to_dict()
        if hasattr(value, "to_list"):
            return value.to_list()
        if hasattr(value, "tolist"):
            return value.tolist()

        # Basic types
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        if isinstance(value, (list, tuple)):
            return [_serialize_variable(v) for v in value]
        if isinstance(value, dict):
            return {str(k): _serialize_variable(v) for k, v in value.items()}
        if isinstance(value, set):
            return list(value)

        return str(value)
    except Exception:
        return f"<{type(value).__name__} object>"


def _extract_variables(execution_globals: dict, return_variables: list) -> dict:
    """Extract user-defined variables from execution globals."""
    variables = {}
    builtins = execution_globals.get("__builtins__", {})

    for var_name, var_value in execution_globals.items():
        if var_name.startswith("_") or var_name in _EXCLUDED_VARS:
            continue
        if var_name in builtins:
            continue
        try:
            variables[var_name] = _serialize_variable(var_value)
        except Exception as e:
            variables[var_name] = f"<Could not serialize: {e}>"

    # Also extract explicitly requested variables
    for var_name in return_variables or []:
        if var_name in execution_globals and var_name not in variables:
            try:
                variables[var_name] = _serialize_variable(execution_globals[var_name])
            except Exception as e:
                variables[var_name] = f"<Could not serialize: {e}>"

    return variables


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main():
    """Read JSON request from stdin, execute code, write JSON result to stdout."""
    result = {"success": False, "output": "", "error": "", "variables": {}, "execution_info": {}}

    try:
        request = json.loads(sys.stdin.read())

        code = request["code"]
        user = request["user"]
        site = request["site"]
        sites_path = request["sites_path"]
        limits = request.get("limits", {})
        data_query = request.get("data_query")
        return_variables = request.get("return_variables", [])
        capture_output = request.get("capture_output", True)

        # Initialize Frappe context.
        # CWD must be the sites directory for Frappe's logger to find
        # the correct log file paths ({site}/logs/*.log).
        import os

        os.chdir(sites_path)

        import frappe

        frappe.init(site, sites_path=sites_path)
        frappe.connect(set_admin_as_user=False)
        frappe.set_user(user)  # nosemgrep: frappe-setuser

        try:
            # Build execution environment and fetch data_query BEFORE applying
            # resource limits — the 512 MB memory budget should govern user code,
            # not interpreter/library setup that the user did not write.
            execution_globals = _setup_execution_environment(user)

            if data_query:
                try:
                    doctype = data_query.get("doctype")
                    fields = data_query.get("fields", ["*"])
                    filters = data_query.get("filters", {})
                    limit = data_query.get("limit", 100)
                    execution_globals["data"] = frappe.get_all(
                        doctype, filters=filters, fields=fields, limit_page_length=limit
                    )
                except Exception as e:
                    result["error"] = f"Error fetching data: {e}"
                    json.dump(result, sys.stdout)
                    return

            # Apply resource limits immediately before exec (disposable process).
            _apply_limits(limits)

            # Execute user code
            output = ""
            error_output = ""

            if capture_output:
                stdout_capture = io.StringIO()
                stderr_capture = io.StringIO()
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    exec(code, execution_globals)  # noqa: S102  # nosemgrep: frappe-codeinjection-eval
                output = stdout_capture.getvalue()
                error_output = stderr_capture.getvalue()
            else:
                exec(code, execution_globals)  # noqa: S102  # nosemgrep: frappe-codeinjection-eval

            # Truncate output
            max_output = 1024 * 1024  # 1 MB
            if len(output) > max_output:
                output = (
                    output[:max_output]
                    + f"\n\n... [OUTPUT TRUNCATED - exceeded {max_output // 1024}KB limit. "
                    f"Original size: {len(output) // 1024}KB]"
                )

            variables = _extract_variables(execution_globals, return_variables)

            result = {
                "success": True,
                "output": output,
                "error": error_output,
                "variables": variables,
                "execution_info": {
                    "lines_executed": len(code.split("\n")),
                    "variables_returned": len(variables),
                },
            }

        except ExecutionTimeoutError as e:
            result = {
                "success": False,
                "error": str(e),
                "error_type": "timeout",
                "output": "",
                "variables": {},
                "execution_info": {"timeout_seconds": limits.get("timeout_seconds", 30)},
            }

        except CPUTimeLimitError as e:
            result = {
                "success": False,
                "error": str(e),
                "error_type": "cpu_limit",
                "output": "",
                "variables": {},
                "execution_info": {"max_cpu_seconds": limits.get("max_cpu_seconds", 60)},
            }

        except MemoryError:
            result = {
                "success": False,
                "error": (
                    "Memory limit exceeded. The code attempted to use more memory than allowed. "
                    f"Maximum allowed: {limits.get('max_memory_mb', 512)} MB."
                ),
                "error_type": "memory",
                "output": "",
                "variables": {},
                "execution_info": {"max_memory_mb": limits.get("max_memory_mb", 512)},
            }

        except RecursionError:
            result = {
                "success": False,
                "error": (
                    "Recursion limit exceeded. The code exceeded the maximum recursion depth of "
                    f"{limits.get('max_recursion_depth', 100)}."
                ),
                "error_type": "recursion",
                "output": "",
                "variables": {},
                "execution_info": {"max_recursion_depth": limits.get("max_recursion_depth", 100)},
            }

        except Exception as e:
            result = {
                "success": False,
                "error": f"Execution failed: {e}",
                "error_type": "runtime",
                "output": "",
                "variables": {},
                "traceback": traceback.format_exc(),
            }

        finally:
            try:
                frappe.destroy()
            except Exception:
                pass

    except Exception as e:
        # Fatal error before frappe init (bad JSON, missing fields, etc.)
        result = {
            "success": False,
            "error": f"Subprocess initialization failed: {e}",
            "error_type": "init",
            "output": "",
            "variables": {},
        }

    # Always write valid JSON to stdout
    try:
        json.dump(result, sys.stdout, default=str)
    except Exception:
        # Last resort — ensure the parent always gets parseable JSON
        sys.stdout.write(
            '{"success": false, "error": "Failed to serialize result", "output": "", "variables": {}}'
        )


if __name__ == "__main__":
    main()
