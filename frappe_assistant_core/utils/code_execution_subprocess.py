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

import datetime
import io
import json
import platform
import signal
import sys
import traceback
import types as _types
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


# A resource limit firing while a variable is being serialized ends the run; it
# is not a reason to drop that one variable and report success.
_LIMIT_ERRORS = (ExecutionTimeoutError, CPUTimeLimitError, MemoryError)


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


class _AttrSafeModule:
    """Expose only a stdlib helper module's public, non-module members.

    Used for the small helper modules (math, statistics, json, …) where it costs
    no capability. pandas and numpy are exposed as-is: wrapping them breaks
    everyday analysis (pd.offsets, pd.api.types, np.ma), and in-process
    wrapping cannot be the security boundary. That is planned as process
    isolation with a SELECT-only database user (follow-up).
    """

    __slots__ = ("_mod", "_label")

    def __init__(self, mod, label):
        object.__setattr__(self, "_mod", mod)
        object.__setattr__(self, "_label", label)

    def __getattr__(self, name):
        unavailable = AttributeError(f"{self._label}.{name} is not available in run_python_code")
        if name.startswith("_"):
            raise unavailable
        value = getattr(self._mod, name)
        if isinstance(value, _types.ModuleType):
            raise unavailable
        return value

    def __setattr__(self, name, value):
        raise AttributeError(f"{self._label} is read-only in run_python_code")

    def __dir__(self):
        return [n for n in dir(self._mod) if not n.startswith("_")]

    def __repr__(self):
        return f"<module {self._label!r} (run_python_code)>"


def _setup_execution_environment(user: str) -> dict:
    """Build the sandboxed globals dict for exec()."""
    import frappe

    from frappe_assistant_core.utils.sandbox_frappe import build_sandbox_frappe
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
            "math": _AttrSafeModule(math, "math"),
            "statistics": _AttrSafeModule(statistics, "statistics"),
            "decimal": _AttrSafeModule(decimal, "decimal"),
            "fractions": _AttrSafeModule(fractions, "fractions"),
            "datetime": _AttrSafeModule(datetime, "datetime"),
            "json": _AttrSafeModule(_json, "json"),
            "re": _AttrSafeModule(re, "re"),
            "random": _AttrSafeModule(random, "random"),
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

    # Frappe integration — permission-checked and read-only, never the real module
    sandbox_frappe = build_sandbox_frappe(user)
    tools_api = FrappeAssistantAPI(user)

    env.update(
        {
            "frappe": sandbox_frappe,
            "get_doc": sandbox_frappe.get_doc,
            "get_list": sandbox_frappe.get_list,
            "get_all": sandbox_frappe.get_all,
            "get_single": sandbox_frappe.get_single,
            "db": sandbox_frappe.db,
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


def _json_key(key):
    """JSON object keys must be strings. Pandas groupby keys are not."""
    return key if isinstance(key, str) else str(key)


# ``tolist()`` renders datetime64/timedelta64 as integer nanoseconds. At
# microsecond precision it yields datetime/timedelta objects instead.
_NUMPY_TIME_UNITS = {"M": "datetime64[us]", "m": "timedelta64[us]"}


def _serialize_variable(value):
    """Serialize a variable to a JSON-compatible representation.

    Dict keys are always coerced to strings: a pandas groupby on more than one
    column (or on a date) produces keys ``json.dumps`` cannot encode, and a
    failed encode used to abort the result halfway through stdout.
    """
    # Plain mappings first. frappe._dict (and any dict subclass) implements
    # __getattr__, so hasattr(row, "to_dict") is true for a reason that has
    # nothing to do with pandas.
    if isinstance(value, dict):
        return {_json_key(k): _serialize_variable(v) for k, v in value.items()}

    # Pandas objects. to_dict() keeps the original index as keys.
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _serialize_variable(value.to_dict())
    if hasattr(value, "to_list") and callable(value.to_list):
        return _serialize_variable(value.to_list())
    time_unit = _NUMPY_TIME_UNITS.get(getattr(getattr(value, "dtype", None), "kind", None))
    if time_unit and callable(getattr(value, "astype", None)):
        return _serialize_variable(value.astype(time_unit).tolist())
    if hasattr(value, "tolist") and callable(value.tolist):
        return _serialize_variable(value.tolist())

    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, (datetime.date, datetime.time, datetime.timedelta)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_serialize_variable(v) for v in value]
    if isinstance(value, set):
        return [_serialize_variable(v) for v in value]

    rendered = str(value)
    if rendered.startswith("<") and " object at " in rendered:
        raise TypeError(f"{type(value).__name__} has no JSON representation")
    return rendered


def _extract_variables(execution_globals: dict, return_variables: list) -> tuple:
    """Extract user-defined variables from execution globals.

    When ``return_variables`` is non-empty, only those names are serialized.
    Otherwise every non-internal user-defined global is returned (legacy behavior).

    A variable that cannot be serialized is dropped, not substituted: one bad
    value must not discard the whole result. Returns ``(variables, warnings)``.
    """
    variables = {}
    warnings = []
    builtins = execution_globals.get("__builtins__", {})

    def _is_excluded(var_name):
        return var_name.startswith("_") or var_name in _EXCLUDED_VARS or var_name in builtins

    def _take(var_name, var_value):
        try:
            variables[var_name] = _serialize_variable(var_value)
        except _LIMIT_ERRORS:
            raise
        except Exception as e:
            warnings.append(f"{var_name}: {e}")

    if return_variables:
        for var_name in return_variables:
            if var_name not in execution_globals or _is_excluded(var_name):
                continue
            _take(var_name, execution_globals[var_name])
    else:
        for var_name, var_value in execution_globals.items():
            if _is_excluded(var_name):
                continue
            _take(var_name, var_value)

    return variables, warnings


def _write_result(result: dict, stream) -> None:
    """Write exactly one JSON document, or one error document that keeps output.

    Building the whole document before writing means a value JSON cannot encode
    never leaves a half-written object on stdout for the parent to fail to parse.
    """
    try:
        stream.write(json.dumps(result, default=str))
        return
    except Exception:
        pass

    variables = result.get("variables") or {}
    kept = {}
    dropped = []
    for name, value in variables.items():
        try:
            json.dumps(value)
            kept[name] = value
        except Exception:
            dropped.append(name)

    names = ", ".join(dropped) or "result"
    # The parent appends the retry guidance to every failure it reports.
    fallback = {
        "success": False,
        "error": f"Could not serialize variables: {names}.",
        "error_type": "serialization",
        "output": result.get("output", ""),
        "variables": kept,
        "unserializable_variables": dropped,
    }
    stream.write(json.dumps(fallback, default=str))


# ---------------------------------------------------------------------------
# User code execution
# ---------------------------------------------------------------------------

_MAX_OUTPUT_CHARS = 1024 * 1024  # 1 MB


def _truncate_output(output: str) -> str:
    if len(output) <= _MAX_OUTPUT_CHARS:
        return output
    return (
        output[:_MAX_OUTPUT_CHARS]
        + f"\n\n... [OUTPUT TRUNCATED - exceeded {_MAX_OUTPUT_CHARS // 1024}KB limit. "
        f"Original size: {len(output) // 1024}KB]"
    )


def _failure(error_type: str, error: str, output: str, execution_info: dict | None = None, **extra) -> dict:
    return {
        "success": False,
        "error": error,
        "error_type": error_type,
        "output": output,
        "variables": {},
        "execution_info": execution_info or {},
        **extra,
    }


def _exec_user_code(code, execution_globals, capture_output, stdout_capture, stderr_capture) -> None:
    """Run the user's code, cancelling the wall-clock alarm however it ends.

    The alarm governs the user's code only. Left armed, it fired during
    serialization and was mistaken for a failure of one variable.
    """
    try:
        if capture_output:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(code, execution_globals)  # noqa: S102  # nosemgrep: frappe-codeinjection-eval
        else:
            exec(code, execution_globals)  # noqa: S102  # nosemgrep: frappe-codeinjection-eval
    finally:
        if platform.system() != "Windows":
            signal.alarm(0)


def _run_user_code(code, execution_globals, limits, capture_output, return_variables) -> dict:
    """Execute user code and build the result document.

    Printed output is returned on every path: the totals a script printed
    before it raised or hit a limit are exactly what the model must not retype.
    """
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    def printed() -> str:
        return _truncate_output(stdout_capture.getvalue())

    try:
        _exec_user_code(code, execution_globals, capture_output, stdout_capture, stderr_capture)

        error_output = stderr_capture.getvalue()
        variables, variable_warnings = _extract_variables(execution_globals, return_variables)
        if variable_warnings:
            error_output = (error_output + "\n" if error_output else "") + (
                "Some variables could not be returned: " + "; ".join(variable_warnings)
            )

        return {
            "success": True,
            "output": printed(),
            "error": error_output,
            "variables": variables,
            "execution_info": {
                "lines_executed": len(code.split("\n")),
                "variables_returned": len(variables),
            },
        }

    except ExecutionTimeoutError as e:
        return _failure("timeout", str(e), printed(), {"timeout_seconds": limits.get("timeout_seconds", 30)})

    except CPUTimeLimitError as e:
        return _failure(
            "cpu_limit", str(e), printed(), {"max_cpu_seconds": limits.get("max_cpu_seconds", 60)}
        )

    except MemoryError:
        max_memory_mb = limits.get("max_memory_mb", 512)
        return _failure(
            "memory",
            "Memory limit exceeded. The code attempted to use more memory than allowed. "
            f"Maximum allowed: {max_memory_mb} MB.",
            printed(),
            {"max_memory_mb": max_memory_mb},
        )

    except RecursionError:
        max_depth = limits.get("max_recursion_depth", 100)
        return _failure(
            "recursion",
            f"Recursion limit exceeded. The code exceeded the maximum recursion depth of {max_depth}.",
            printed(),
            {"max_recursion_depth": max_depth},
        )

    except Exception as e:
        return _failure("runtime", f"Execution failed: {e}", printed(), traceback=traceback.format_exc())


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
            # Static safety gate. The parent process runs this too; repeating it
            # here means the exec is never reached with unvalidated code, even if
            # this module is ever invoked directly.
            from frappe_assistant_core.utils.sandbox_ast import SandboxSecurityError, validate_code

            try:
                validate_code(code)
            except SandboxSecurityError as exc:
                result = {
                    "success": False,
                    "error": f"🚫 Security: {exc}",
                    "error_type": "security",
                    "output": "",
                    "variables": {},
                }
                json.dump(result, sys.stdout)
                return

            # Build execution environment and fetch data_query BEFORE applying
            # resource limits — the 512 MB memory budget should govern user code,
            # not interpreter/library setup that the user did not write.
            execution_globals = _setup_execution_environment(user)

            if data_query:
                try:
                    from frappe_assistant_core.utils.sandbox_frappe import fetch_data_query

                    execution_globals["data"] = fetch_data_query(data_query)
                except Exception as e:
                    result["error"] = f"Error fetching data: {e}"
                    _write_result(result, sys.stdout)
                    return

            # Apply resource limits immediately before exec (disposable process).
            _apply_limits(limits)
            result = _run_user_code(code, execution_globals, limits, capture_output, return_variables)

        except Exception as e:
            result = _failure("runtime", f"Execution failed: {e}", "", traceback=traceback.format_exc())

        finally:
            try:
                frappe.destroy()
            except Exception:
                pass

    except Exception as e:
        # Fatal error before frappe init (bad JSON, missing fields, etc.)
        result = _failure("init", f"Subprocess initialization failed: {e}", "")

    # Always write exactly one valid JSON document, keeping any printed output.
    _write_result(result, sys.stdout)


if __name__ == "__main__":
    main()
