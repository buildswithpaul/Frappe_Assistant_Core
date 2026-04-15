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
Python Code Execution Tool for Data Science Plugin.
Executes Python code safely in a restricted environment.
"""

import sys
import traceback
from typing import Any, Dict

import frappe
from frappe import _
from frappe.query_builder import Order

from frappe_assistant_core.core.base_tool import BaseTool


class ExecutePythonCode(BaseTool):
    """
    Tool for executing Python code with data science libraries.

    Provides safe execution of Python code with access to:
    - pandas, numpy, matplotlib, seaborn, plotly
    - Frappe data access
    - Result capture and display
    """

    def __init__(self):
        super().__init__()
        self.name = "run_python_code"

        # Check library availability at initialization time
        self.library_status = self._check_library_availability()

        self.description = self._get_dynamic_description()
        self.requires_permission = None  # Available to all users

        self.inputSchema = {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute. IMPORTANT: Do NOT use import statements - all libraries are pre-loaded and ready to use: pd (pandas), np (numpy), plt (matplotlib), sns (seaborn), frappe, math, datetime, json, re, random. Example: df = pd.DataFrame({'A': [1,2,3]}); plt.plot([1,2,3])",
                },
                "data_query": {
                    "type": "object",
                    "description": "Query to fetch data and make it available as 'data' variable",
                    "properties": {
                        "doctype": {"type": "string"},
                        "fields": {"type": "array", "items": {"type": "string"}},
                        "filters": {"type": "object"},
                        "limit": {"type": "integer", "default": 100},
                    },
                },
                "timeout": {
                    "type": "integer",
                    "description": "Execution timeout in seconds (default: 30)",
                    "default": 30,
                    "minimum": 1,
                    "maximum": 300,
                },
                "capture_output": {
                    "type": "boolean",
                    "description": "Whether to capture print output (default: true)",
                    "default": True,
                },
                "return_variables": {
                    "type": "array",
                    "description": "Variable names to return values for",
                    "items": {"type": "string"},
                },
            },
            "required": ["code"],
        }

    def _check_library_availability(self) -> Dict[str, bool]:
        """Check which data science libraries are available at initialization"""
        libraries = {}

        try:
            import pandas

            libraries["pandas"] = True
        except ImportError:
            libraries["pandas"] = False

        try:
            import numpy

            libraries["numpy"] = True
        except ImportError:
            libraries["numpy"] = False

        try:
            import matplotlib

            libraries["matplotlib"] = True
        except ImportError:
            libraries["matplotlib"] = False

        try:
            import seaborn

            libraries["seaborn"] = True
        except ImportError:
            libraries["seaborn"] = False

        try:
            import plotly

            libraries["plotly"] = True
        except ImportError:
            libraries["plotly"] = False

        try:
            import scipy

            libraries["scipy"] = True
        except ImportError:
            libraries["scipy"] = False

        return libraries

    def _get_dynamic_description(self) -> str:
        """Generate description based on library availability"""
        base_description = """Execute Python code in a sandboxed environment with BUILT-IN data access.

PREFER THIS TOOL for analytics — it can fetch data AND analyze it in a single call via the `tools` API.
Do NOT call get_documents/generate_report separately then copy data into code. Instead, fetch inside code:

TOOLS API (available as `tools` variable — returns dicts, ready for pandas):
  tools.get_documents(doctype, filters={}, fields=["*"], limit=100) → {success, data, count}
  tools.get_document(doctype, name) → {success, data}
  tools.generate_report(report_name, filters={}, format="json") → {success, data, columns}
  tools.get_report_info(report_name) → {success, columns, filter_guidance}
  tools.list_reports(module=None, report_type=None) → {success, reports, count}
  tools.search(query, doctype=None, limit=20)
  tools.get_doctype_info(doctype) → {success, fields, links}

EXAMPLE — single call does fetch + analysis:
invoices = tools.get_documents("Sales Invoice",
    filters={"docstatus": 1, "posting_date": [">=", "2024-04-01"]},
    fields=["customer_name", "grand_total", "outstanding_amount"], limit=500)
customers = tools.get_documents("Customer", fields=["name", "customer_name", "territory"], limit=500)
if invoices["success"] and customers["success"]:
    df = pd.DataFrame(invoices["data"]).merge(
        pd.DataFrame(customers["data"]), left_on="customer_name", right_on="customer_name")
    print(df.groupby("territory")["grand_total"].sum().sort_values(ascending=False).to_string())

RULES:
- NO imports — all libraries are pre-loaded
- Read-only DB, permission-checked, audit-logged, no file/network access

PRE-LOADED: pd (pandas), np (numpy), plt (matplotlib), sns (seaborn), frappe, math, datetime, json, re, statistics, random, collections, itertools, functools, operator, copy"""

        # Add library availability warnings
        library_warnings = []
        if not self.library_status.get("pandas"):
            library_warnings.append(
                "⚠️  pandas NOT available - use tools.generate_report() or frappe.get_all() instead"
            )
        if not self.library_status.get("numpy"):
            library_warnings.append("⚠️  numpy NOT available - use math/statistics modules")
        if not self.library_status.get("matplotlib"):
            library_warnings.append("⚠️  matplotlib NOT available - visualization not supported")

        if library_warnings:
            base_description += "\n\n" + "\n".join(library_warnings)

        return base_description

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Python code safely with secure user context and read-only database"""
        code = arguments.get("code", "")
        data_query = arguments.get("data_query")
        timeout = arguments.get("timeout", 30)
        capture_output = arguments.get("capture_output", True)
        return_variables = arguments.get("return_variables", [])

        # Import security utilities
        from frappe_assistant_core.utils.user_context import audit_code_execution, secure_user_context

        if not code.strip():
            return {"success": False, "error": "No code provided", "output": "", "variables": {}}

        try:
            # Use secure user context manager with audit trail
            with secure_user_context(require_system_manager=True) as current_user:
                with audit_code_execution(code_snippet=code, user_context=current_user) as audit_info:
                    # Perform security scan before execution
                    security_check = self._scan_for_dangerous_operations(code)
                    if not security_check["success"]:
                        frappe.logger().warning(
                            f"Security violation in code execution - User: {current_user}, "
                            f"Pattern: {security_check.get('pattern_matched', 'unknown')}"
                        )
                        return security_check

                    # Check for import statements and provide helpful error
                    import_check_result = self._check_and_handle_imports(code)
                    if not import_check_result["success"]:
                        return import_check_result

                    # Remove dangerous imports for additional security
                    code = self._remove_dangerous_imports(import_check_result["code"])

                    # Sanitize Unicode characters to prevent encoding errors
                    unicode_check_result = self._sanitize_unicode(code)
                    if not unicode_check_result["success"]:
                        return unicode_check_result
                    code = unicode_check_result["code"]

                    # Auto-fix common pandas/numpy errors before execution
                    preprocess_result = self._preprocess_code_for_common_errors(code)
                    if not preprocess_result["success"]:
                        return preprocess_result
                    code = preprocess_result["code"]
                    fixes_applied = preprocess_result.get("fixes_applied", [])

                    # Execute the code in an isolated subprocess.
                    # The subprocess sets up its own execution environment
                    # (read-only DB, tools API, pre-loaded libraries).
                    return self._execute_code_with_timeout(
                        code,
                        data_query,
                        timeout,
                        capture_output,
                        return_variables,
                        current_user,
                        audit_info,
                    )

        except frappe.PermissionError as e:
            return {"success": False, "error": str(e), "output": "", "variables": {}, "security_error": True}
        except Exception as e:
            frappe.logger().error(f"Code execution error: {str(e)}")
            return {"success": False, "error": f"Execution failed: {str(e)}", "output": "", "variables": {}}

    def _execute_code_with_timeout(
        self,
        code: str,
        data_query: dict,
        timeout: int,
        capture_output: bool,
        return_variables: list,
        current_user: str,
        audit_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute code in an isolated subprocess with resource limits.

        Spawns a child process so that RLIMIT_CPU, RLIMIT_AS, and SIGALRM
        only affect the child — the gunicorn worker is never at risk.
        Communication is via JSON over stdin/stdout (same pattern as
        ``ocr_subprocess.py``).
        """
        import json as json_mod
        import subprocess

        from frappe_assistant_core.utils.execution_limits import get_execution_limits_from_settings

        # Get limits from settings
        limits = get_execution_limits_from_settings()
        effective_timeout = min(timeout, limits["timeout_seconds"]) if timeout else limits["timeout_seconds"]

        # Build the JSON request for the subprocess
        request_data = json_mod.dumps(
            {
                "code": code,
                "user": current_user,
                "site": frappe.local.site,
                "sites_path": str(frappe.local.sites_path),
                "limits": {
                    "timeout_seconds": effective_timeout,
                    "max_memory_mb": limits["max_memory_mb"],
                    "max_cpu_seconds": limits["max_cpu_seconds"],
                    "max_recursion_depth": limits["max_recursion_depth"],
                },
                "data_query": data_query,
                "return_variables": return_variables or [],
                "capture_output": capture_output,
            }
        )

        # Spawn isolated subprocess
        proc = subprocess.Popen(
            [sys.executable, "-m", "frappe_assistant_core.utils.code_execution_subprocess"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Give the child extra grace time beyond its own SIGALRM to report errors
        parent_timeout = effective_timeout + 10

        try:
            stdout, stderr = proc.communicate(
                input=request_data.encode("utf-8"),
                timeout=parent_timeout,
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            self.logger.warning(
                f"Code execution subprocess killed after {parent_timeout}s " f"(user: {current_user})"
            )
            return {
                "success": False,
                "error": (
                    f"Code execution timed out after {effective_timeout} seconds.\n\n"
                    f"The code took too long to execute and was terminated.\n\n"
                    f"Tips to fix this:\n"
                    f"   - Reduce the size of data being processed\n"
                    f"   - Add early termination conditions to loops\n"
                    f"   - Use more efficient algorithms\n"
                    f"   - Break complex operations into smaller steps"
                ),
                "output": "",
                "variables": {},
                "user_context": current_user,
                "timeout_error": True,
                "execution_info": {
                    "execution_id": audit_info.get("execution_id"),
                    "executed_by": current_user,
                    "timeout_seconds": effective_timeout,
                },
            }

        # Try to parse the subprocess JSON response
        try:
            result = json_mod.loads(stdout.decode("utf-8", errors="replace"))
        except (json_mod.JSONDecodeError, ValueError):
            # Subprocess crashed without writing valid JSON
            stderr_text = stderr.decode("utf-8", errors="replace").strip()
            exit_code = proc.returncode

            # Determine the likely cause from exit code and stderr
            if exit_code and exit_code < 0:
                # Killed by signal (e.g., SIGXCPU = -24, SIGKILL = -9)
                sig_num = -exit_code
                if sig_num == 24:  # SIGXCPU
                    error_msg = (
                        f"CPU time limit exceeded. The code used more than "
                        f"{limits['max_cpu_seconds']} seconds of CPU time.\n\n"
                        f"Tips: reduce computation, optimize algorithms, or process less data."
                    )
                elif sig_num == 9:  # SIGKILL (likely OOM killer)
                    error_msg = (
                        f"Code execution was killed (likely out of memory).\n\n"
                        f"Maximum allowed memory: {limits['max_memory_mb']} MB.\n\n"
                        f"Tips: process data in smaller batches, use generators."
                    )
                else:
                    error_msg = (
                        f"Code execution was terminated by signal {sig_num}.\n\n"
                        f"This usually indicates a resource limit was exceeded."
                    )
            else:
                error_msg = (
                    f"Code execution subprocess crashed (exit code {exit_code}).\n\n"
                    f"{stderr_text[:500] if stderr_text else 'No error details available.'}"
                )

            self.logger.error(
                f"Code execution subprocess crashed: exit={exit_code}, " f"stderr={stderr_text[:200]}"
            )

            return {
                "success": False,
                "error": error_msg,
                "output": "",
                "variables": {},
                "user_context": current_user,
                "execution_info": {
                    "execution_id": audit_info.get("execution_id"),
                    "executed_by": current_user,
                },
            }

        # Map subprocess error types to the expected result format
        if not result.get("success"):
            error_type = result.get("error_type", "runtime")
            error_msg = result.get("error", "Unknown error")

            if error_type == "timeout":
                result["timeout_error"] = True
                error_msg = (
                    f"Execution Timeout: {error_msg}\n\n"
                    f"The code exceeded the maximum allowed execution time of "
                    f"{effective_timeout} seconds.\n\n"
                    f"Tips to fix this:\n"
                    f"   - Reduce the size of data being processed\n"
                    f"   - Add early termination conditions to loops\n"
                    f"   - Use more efficient algorithms\n"
                    f"   - Break complex operations into smaller steps"
                )
            elif error_type == "cpu_limit":
                error_msg = (
                    f"CPU Time Limit Exceeded: {error_msg}\n\n"
                    f"Maximum CPU time: {limits['max_cpu_seconds']} seconds.\n\n"
                    f"Tips to fix this:\n"
                    f"   - Reduce computational complexity\n"
                    f"   - Use vectorized operations (pandas/numpy) instead of loops\n"
                    f"   - Process less data at once"
                )
            elif error_type == "memory":
                result["memory_error"] = True
                error_msg = (
                    f"Memory Limit Exceeded: {error_msg}\n\n"
                    f"Maximum allowed memory: {limits['max_memory_mb']} MB.\n\n"
                    f"Tips to fix this:\n"
                    f"   - Process data in smaller batches\n"
                    f"   - Use generators instead of loading all data into memory\n"
                    f"   - Delete intermediate variables when no longer needed"
                )
            elif error_type == "recursion":
                result["recursion_error"] = True
                error_msg = (
                    f"Recursion Limit Exceeded: {error_msg}\n\n"
                    f"Maximum recursion depth: {limits['max_recursion_depth']}.\n\n"
                    f"Tips to fix this:\n"
                    f"   - Convert recursive algorithms to iterative ones\n"
                    f"   - Add proper base cases to recursive functions"
                )

            result["error"] = error_msg

        # Enrich with execution context the caller expects
        result["user_context"] = current_user
        result.setdefault("execution_info", {})
        result["execution_info"]["execution_id"] = audit_info.get("execution_id")
        result["execution_info"]["executed_by"] = current_user

        return result

    def _preprocess_code_for_common_errors(self, code: str) -> Dict[str, Any]:
        """Auto-fix common pandas/numpy errors before execution"""
        import re

        fixes_applied = []
        original_code = code

        # Fix 1: Replace deprecated df.append() with pd.concat()
        # Pattern: df = df.append(...) -> df = pd.concat([df, ...], ignore_index=True)
        append_pattern = r"(\w+)\s*=\s*\1\.append\s*\(([^)]+)\)"
        if re.search(append_pattern, code):
            code = re.sub(append_pattern, r"\1 = pd.concat([\1, \2], ignore_index=True)", code)
            if code != original_code:
                fixes_applied.append("✓ Replaced deprecated df.append() with pd.concat()")
                original_code = code

        # Fix 2: Add ignore_index=True to pd.concat if missing
        concat_pattern = r"pd\.concat\s*\(\s*\[([^\]]+)\]\s*\)"
        concat_matches = re.finditer(concat_pattern, code)
        for match in concat_matches:
            full_match = match.group(0)
            if "ignore_index" not in full_match:
                # Add ignore_index=True
                new_match = full_match[:-1] + ", ignore_index=True)"
                code = code.replace(full_match, new_match)
                if code != original_code:
                    fixes_applied.append("✓ Added ignore_index=True to pd.concat()")
                    original_code = code
                    break  # Only fix first occurrence to avoid issues

        # Fix 3: Replace inplace=True with explicit assignment (safer)
        # Pattern: df.sort_values(..., inplace=True) -> df = df.sort_values(...)
        inplace_pattern = (
            r"(\w+)\.(sort_values|drop_duplicates|fillna|reset_index)\(([^)]*inplace\s*=\s*True[^)]*)\)"
        )
        if re.search(inplace_pattern, code):

            def replace_inplace(match):
                var_name = match.group(1)
                method_name = match.group(2)
                args = match.group(3)
                # Remove inplace=True from args
                args_clean = re.sub(r",?\s*inplace\s*=\s*True,?", "", args)
                args_clean = args_clean.strip(", ")
                return f"{var_name} = {var_name}.{method_name}({args_clean})"

            new_code = re.sub(inplace_pattern, replace_inplace, code)
            if new_code != code:
                code = new_code
                fixes_applied.append("✓ Replaced inplace=True with explicit assignment (safer)")
                original_code = code

        # Fix 4: Fix chained indexing df['col'][0] = value -> df.loc[0, 'col'] = value
        # This is complex and risky, so only warn in comments
        if re.search(r'\w+\[["\'][^"\']+["\']\]\[\d+\]\s*=', code):
            # Add a warning comment at the top
            warning = "# Warning: Chained indexing detected - consider using .loc[] instead\n"
            if not code.startswith(warning):
                code = warning + code
                fixes_applied.append("ℹ️  Added warning about chained indexing")

        # Fix 5: Auto-add .copy() when slicing DataFrames to avoid SettingWithCopyWarning
        # Pattern: df2 = df[...] -> df2 = df[...].copy()
        slice_pattern = r"(\w+)\s*=\s*(\w+)\[([^\]]+)\](?!\s*\.)"
        if re.search(slice_pattern, code):
            # Only apply if it looks like a DataFrame slice (not dict or list access)
            def add_copy(match):
                if "pd.DataFrame" in code or "data" in match.group(2):
                    return f"{match.group(1)} = {match.group(2)}[{match.group(3)}].copy()"
                return match.group(0)

            new_code = re.sub(slice_pattern, add_copy, code)
            if new_code != code:
                code = new_code
                fixes_applied.append("✓ Added .copy() to DataFrame slices to avoid SettingWithCopyWarning")

        return {"success": True, "code": code, "fixes_applied": fixes_applied}

    def _sanitize_unicode(self, code: str) -> Dict[str, Any]:
        """Sanitize Unicode characters to prevent encoding errors"""
        try:
            # Check if the string contains surrogate characters
            if any(0xD800 <= ord(char) <= 0xDFFF for char in code if isinstance(char, str)):
                # Found surrogate characters - clean them
                cleaned_chars = []
                surrogate_count = 0

                for char in code:
                    char_code = ord(char)
                    if 0xD800 <= char_code <= 0xDFFF:
                        # Replace surrogate with a space or remove it
                        cleaned_chars.append(" ")
                        surrogate_count += 1
                    else:
                        cleaned_chars.append(char)

                cleaned_code = "".join(cleaned_chars)

                # Provide a helpful warning
                warning_msg = f"⚠️  Code contained {surrogate_count} invalid Unicode surrogate character(s) that were replaced with spaces. This often happens when copying code from certain documents or web pages."

                return {"success": True, "code": cleaned_code, "warning": warning_msg}

            # Try encoding to UTF-8 to catch other encoding issues
            try:
                code.encode("utf-8")
            except UnicodeEncodeError as e:
                # Handle other encoding errors
                cleaned_code = code.encode("utf-8", errors="replace").decode("utf-8")
                return {
                    "success": True,
                    "code": cleaned_code,
                    "warning": f"⚠️  Code contained invalid Unicode characters that were replaced. Original error: {str(e)}",
                }

            # Code is clean
            return {"success": True, "code": code}

        except Exception as e:
            return {
                "success": False,
                "error": f"Error sanitizing Unicode in code: {str(e)}",
                "output": "",
                "variables": {},
            }

    def _check_and_handle_imports(self, code: str) -> Dict[str, Any]:
        """Check for import statements and provide helpful guidance"""
        import re

        lines = code.split("\n")
        import_lines = []
        processed_lines = []

        # Common import patterns that can be safely removed (exact matches)
        safe_replacements = {
            "import pandas as pd": '# pandas is pre-loaded as "pd"',
            "import numpy as np": '# numpy is pre-loaded as "np"',
            "import matplotlib.pyplot as plt": '# matplotlib is pre-loaded as "plt"',
            "import seaborn as sns": '# seaborn is pre-loaded as "sns"',
            "import frappe": "# frappe is pre-loaded",
            "import math": "# math is pre-loaded",
            "import datetime": "# datetime is pre-loaded",
            "import json": "# json is pre-loaded",
            "import re": "# re is pre-loaded",
            "import random": "# random is pre-loaded",
            "import statistics": "# statistics is pre-loaded",
            "import decimal": "# decimal is pre-loaded",
            "import fractions": "# fractions is pre-loaded",
            # Allow these common stdlib imports
            "import collections": "# collections allowed - Counter, defaultdict, etc.",
            "import itertools": "# itertools allowed - combinatoric iterators",
            "import functools": "# functools allowed - higher-order functions",
            "import operator": "# operator allowed - standard operators",
            "import copy": "# copy allowed - shallow and deep copy",
            "import string": "# string allowed - string operations",
        }

        # Safe import prefixes (for partial matches)
        safe_prefixes = {
            "from datetime import": "# datetime is pre-loaded",
            "from math import": "# math is pre-loaded",
            "from collections import": "# collections allowed",
            "from itertools import": "# itertools allowed",
            "from functools import": "# functools allowed",
            "from operator import": "# operator allowed",
        }

        for i, line in enumerate(lines):
            stripped_line = line.strip()

            # Check if this is an import statement
            if stripped_line.startswith("import ") or stripped_line.startswith("from "):
                import_lines.append((i + 1, stripped_line))

                # Try to replace with helpful comment
                replaced = False

                # Check exact matches first
                if stripped_line in safe_replacements:
                    processed_lines.append(line.replace(stripped_line, safe_replacements[stripped_line]))
                    replaced = True
                else:
                    # Check prefix matches
                    for prefix, replacement in safe_prefixes.items():
                        if stripped_line.startswith(prefix):
                            processed_lines.append(line.replace(stripped_line, replacement))
                            replaced = True
                            break

                if not replaced:
                    # Unknown import - provide helpful error
                    processed_lines.append(
                        f"# REMOVED: {stripped_line} - library not available or not needed"
                    )
            else:
                processed_lines.append(line)

        # If we found problematic imports, provide helpful guidance
        if import_lines:
            # Check if they're all safe imports that we can handle
            problematic_imports = []
            for line_num, import_stmt in import_lines:
                is_safe = False

                # Check exact matches
                if import_stmt in safe_replacements:
                    is_safe = True
                else:
                    # Check prefix matches
                    for prefix in safe_prefixes.keys():
                        if import_stmt.startswith(prefix):
                            is_safe = True
                            break

                if not is_safe:
                    problematic_imports.append((line_num, import_stmt))

            if problematic_imports:
                error_msg = f"""Import statements detected that are not available or needed:

❌ Problematic imports found:
{chr(10).join(f"   Line {line_num}: {stmt}" for line_num, stmt in problematic_imports)}

✅ Available pre-loaded libraries (use directly, no imports needed):
   • pd (pandas) - Data manipulation
   • np (numpy) - Numerical operations
   • plt (matplotlib) - Plotting
   • sns (seaborn) - Statistical visualization
   • frappe - Frappe API access
   • math, datetime, json, re, random - Standard libraries

💡 Example correct usage:
   df = pd.DataFrame({{'A': [1,2,3]}})
   arr = np.array([1,2,3])
   plt.plot(arr)
   plt.show()"""

                return {"success": False, "error": error_msg, "output": "", "variables": {}}

        return {"success": True, "code": "\n".join(processed_lines)}

    def _remove_dangerous_imports(self, code: str) -> str:
        """Remove dangerous import statements for security, but allow safe ones"""
        import re

        # Define safe modules that are allowed (expanded for more functionality)
        safe_modules = {
            # Mathematical and numeric modules
            "math",
            "statistics",
            "decimal",
            "fractions",
            "cmath",  # Complex math
            # Date/time modules
            "datetime",
            "time",
            "calendar",
            # Text and data processing
            "json",
            "re",
            "string",
            "textwrap",
            "unicodedata",
            # Data structures and algorithms
            "collections",  # Counter, defaultdict, OrderedDict, etc.
            "itertools",  # Combinatoric iterators
            "functools",  # Higher-order functions
            "operator",  # Standard operators as functions
            "heapq",  # Heap queue algorithm
            "bisect",  # Array bisection algorithm
            "array",  # Efficient arrays of numeric values
            "copy",  # Shallow and deep copy operations
            # Randomization
            "random",
            "secrets",  # Cryptographically strong random numbers
            # Data science libraries
            "pandas",
            "numpy",
            "matplotlib",
            "seaborn",
            "plotly",
            "scipy",
            # Short aliases
            "pd",
            "np",
            "plt",
            "sns",
            "go",
            "px",
            "stats",
        }

        # Define dangerous modules to block
        dangerous_modules = {
            "os",
            "sys",
            "subprocess",
            "socket",
            "urllib",
            "requests",
            "http",
            "ftplib",
            "smtplib",
            "imaplib",
            "poplib",
            "telnetlib",
            "socketserver",
            "threading",
            "multiprocessing",
            "asyncio",
            "concurrent",
            "ctypes",
            "imp",
            "importlib",
            "__import__",
            "exec",
            "eval",
            "file",
            "open",
            "input",
            "raw_input",
        }

        lines = code.split("\n")
        cleaned_lines = []

        for line in lines:
            stripped_line = line.strip()

            # Check for import statements
            if stripped_line.startswith("import ") or stripped_line.startswith("from "):
                # Extract module name
                if stripped_line.startswith("import "):
                    module = stripped_line[7:].split()[0].split(".")[0]
                elif stripped_line.startswith("from "):
                    module = stripped_line[5:].split()[0].split(".")[0]
                else:
                    module = ""

                # Allow safe modules, block dangerous ones
                if module in safe_modules:
                    cleaned_lines.append(line)  # Keep safe imports
                elif module in dangerous_modules:
                    continue  # Remove dangerous imports
                else:
                    # For unknown modules, be conservative and remove them
                    continue
            else:
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _fetch_data_from_query(self, data_query: Dict[str, Any]) -> list:
        """Fetch data from Frappe based on query parameters.

        Uses the Query Builder (`frappe.qb`) so that field names and filter
        keys — which can come from LLM-generated input — cannot be used to
        inject SQL. Unknown field names surface as a validation error via
        `frappe.get_meta`, not as a malformed query reaching the DB.
        """
        doctype = data_query.get("doctype")
        fields = data_query.get("fields", ["name"])
        filters = data_query.get("filters", {})
        limit = data_query.get("limit", 100)

        if not doctype:
            raise ValueError("DocType is required for data query")

        if not frappe.has_permission(doctype, "read"):
            raise frappe.PermissionError(f"No permission to read {doctype}")

        # Validate doctype up-front so a bad value triggers a clean error
        # instead of a SQL failure deeper down.
        meta = frappe.get_meta(doctype)

        # Validate every field name and filter key against the DocType meta.
        # `name`, `creation`, `modified`, `modified_by`, `owner`, `docstatus`,
        # `idx`, `parent`, `parentfield`, `parenttype` are always valid.
        standard_fields = {
            "name",
            "creation",
            "modified",
            "modified_by",
            "owner",
            "docstatus",
            "idx",
            "parent",
            "parentfield",
            "parenttype",
        }

        def _ensure_field(field_name: str) -> None:
            if field_name not in standard_fields and not meta.has_field(field_name):
                raise ValueError(f"Unknown field '{field_name}' on DocType '{doctype}'")

        for field in fields:
            _ensure_field(field)
        for key in filters:
            _ensure_field(key)

        table = frappe.qb.DocType(doctype)
        query = frappe.qb.from_(table).select(*[table[f] for f in fields])

        for key, value in filters.items():
            column = table[key]
            if isinstance(value, (list, tuple)):
                query = query.where(column.isin(list(value)))
            elif value is None:
                query = query.where(column.isnull())
            else:
                query = query.where(column == value)

        query = query.orderby(table.creation, order=Order.desc).limit(limit)

        rows = query.run(as_dict=True)

        # Strip frappe._dict wrappers so numpy/pandas interop downstream
        # doesn't trip on the __array_struct__ attribute.
        return [dict(row) for row in rows]

    def _setup_execution_environment(self) -> Dict[str, Any]:
        """Legacy method - use _setup_secure_execution_environment instead"""
        frappe.logger().warning("Using legacy _setup_execution_environment - should use secure version")
        return self._setup_secure_execution_environment("legacy_user")

    @staticmethod
    def _make_restricted_import():
        """Create a restricted __import__ that only allows submodules of known-safe packages.

        This is needed because libraries like numpy and pandas internally call
        __import__ for lazy submodule loading (e.g. np.array().mean() triggers
        numpy.core imports). User-level import statements are already blocked by
        _scan_for_dangerous_operations and _check_and_handle_imports, so this
        only serves internal library machinery.
        """
        real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        # Top-level packages whose submodules may be lazily imported
        allowed_roots = frozenset(
            {
                "numpy",
                "pandas",
                "matplotlib",
                "seaborn",
                "plotly",
                "scipy",
                "dateutil",
                "pytz",
                "six",
                "packaging",
                "pyparsing",
                "cycler",
                "kiwisolver",
                "PIL",
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
                # Internal / C-extension modules that libraries depend on
                "_thread",
                "threading",
                "concurrent",
                "queue",
            }
        )

        def restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
            # Relative imports (level > 0) are always internal to the calling package
            if level > 0:
                return real_import(name, globals, locals, fromlist, level)

            root = name.split(".")[0]
            # Allow stdlib and known-safe data-science package trees
            if root.startswith("_") or root in allowed_roots:
                return real_import(name, globals, locals, fromlist, level)

            raise ImportError(
                f"Import of '{name}' is not allowed in the sandbox. "
                f"All supported libraries are pre-loaded — do not use import statements."
            )

        return restricted_import

    def _setup_secure_execution_environment(self, current_user: str) -> Dict[str, Any]:
        """Setup secure execution environment with read-only database and user context"""
        from frappe_assistant_core.utils.read_only_db import ReadOnlyDatabase

        # Base environment with safe built-ins only
        env = {
            "__builtins__": {
                # Restricted import — allows internal library lazy-loading only
                "__import__": self._make_restricted_import(),
                # Safe built-ins for data manipulation and analysis
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
                # Note: setattr removed for security
                "Exception": Exception,
                "ValueError": ValueError,
                "TypeError": TypeError,
                "KeyError": KeyError,
                "IndexError": IndexError,
                "AttributeError": AttributeError,
                "NameError": NameError,
                "ZeroDivisionError": ZeroDivisionError,
                "StopIteration": StopIteration,
            }
        }

        # Add standard libraries (safe mathematical and utility libraries)
        import datetime
        import decimal
        import fractions
        import json
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
                "json": json,
                "re": re,
                "random": random,
            }
        )

        # Add data science libraries with clear availability tracking
        available_libraries = []
        missing_libraries = []

        # Helper class for unavailable libraries
        class LibraryNotInstalled:
            def __init__(self, library_name):
                self.library_name = library_name

            def __getattr__(self, name):
                raise ImportError(
                    f"❌ {self.library_name} is not installed in this environment.\n\n"
                    f"💡 Alternative solutions:\n"
                    f"   • Use frappe.get_all() for data queries and manipulation\n"
                    f"   • Use generate_report tool for business analytics and reporting\n"
                    f"   • Use Python's built-in modules (math, statistics) for calculations\n"
                    f"   • Contact your system administrator to install {self.library_name}\n\n"
                    f"📚 Available libraries: {', '.join(available_libraries) if available_libraries else 'None (data science libraries)'}"
                )

            def __call__(self, *args, **kwargs):
                return self.__getattr__("__call__")

        # Try to import pandas
        try:
            import pandas as pd

            env.update({"pd": pd, "pandas": pd})
            available_libraries.append("pandas (pd)")
        except ImportError:
            missing_libraries.append("pandas")
            env["pd"] = LibraryNotInstalled("pandas")
            env["pandas"] = env["pd"]

        # Try to import numpy
        try:
            import numpy as np

            env.update({"np": np, "numpy": np})
            available_libraries.append("numpy (np)")
        except ImportError:
            missing_libraries.append("numpy")
            env["np"] = LibraryNotInstalled("numpy")
            env["numpy"] = env["np"]

        # Try to import matplotlib
        try:
            import matplotlib.pyplot as plt

            env.update({"plt": plt, "matplotlib": plt})
            available_libraries.append("matplotlib (plt)")
        except ImportError:
            missing_libraries.append("matplotlib")
            env["plt"] = LibraryNotInstalled("matplotlib")
            env["matplotlib"] = env["plt"]

        # Try to import seaborn
        try:
            import seaborn as sns

            env.update({"sns": sns, "seaborn": sns})
            available_libraries.append("seaborn (sns)")
        except ImportError:
            missing_libraries.append("seaborn")
            env["sns"] = LibraryNotInstalled("seaborn")
            env["seaborn"] = env["sns"]

        # Try to add plotly if available
        try:
            import plotly.express as px
            import plotly.graph_objects as go

            env.update({"go": go, "px": px, "plotly": {"graph_objects": go, "express": px}})
            available_libraries.append("plotly (go, px)")
        except ImportError:
            missing_libraries.append("plotly")

        # Add scipy if available
        try:
            import scipy
            import scipy.stats as stats

            env.update({"scipy": scipy, "stats": stats})
            available_libraries.append("scipy (stats)")
        except ImportError:
            missing_libraries.append("scipy")

        # Add SECURE Frappe utilities with read-only database wrapper
        secure_db = ReadOnlyDatabase(frappe.db)

        # Add secure tool orchestration API (no internal paths exposed)
        from frappe_assistant_core.utils.tool_api import FrappeAssistantAPI

        tools_api = FrappeAssistantAPI(current_user)

        env.update(
            {
                "frappe": frappe,  # Keep frappe for utility functions
                "get_doc": frappe.get_doc,  # Permission-checked by default
                "get_list": frappe.get_list,  # Permission-checked by default
                "get_all": frappe.get_all,  # Permission-checked by default
                "get_single": frappe.get_single,  # Permission-checked by default
                "db": secure_db,  # 🛡️ READ-ONLY database wrapper instead of frappe.db
                "current_user": current_user,  # 👤 Current user context for reference
                # 🔧 TOOL ORCHESTRATION API - secure multi-tool access
                "tools": tools_api,  # Unified API for report/document/search operations
                # Store library availability for error messages
                "_available_libraries": available_libraries,
                "_missing_libraries": missing_libraries,
            }
        )

        # Log security setup with library availability
        frappe.logger().info(
            f"Secure execution environment setup complete - User: {current_user}, "
            f"DB: Read-only wrapper, Available libraries: {', '.join(available_libraries) if available_libraries else 'None'}, "
            f"Missing libraries: {', '.join(missing_libraries) if missing_libraries else 'None'}"
        )

        return env

    def _scan_for_dangerous_operations(self, code: str) -> Dict[str, Any]:
        """
        Scan code for potentially dangerous operations before execution

        This method performs static analysis of the code to detect:
        - Dangerous SQL operations (DELETE, UPDATE, DROP, etc.)
        - Unsafe Python operations (exec, eval, __import__)
        - Attempts to modify Frappe framework internals
        - Other security-sensitive patterns

        Args:
            code (str): Python code to analyze

        Returns:
            dict: Security scan results with success flag and error details
        """
        import re

        # Define dangerous patterns with descriptions
        dangerous_patterns = [
            # Database security patterns
            (
                r'db\.sql\s*\(\s*[\'"](?:DELETE|DROP|INSERT|UPDATE|ALTER|CREATE|TRUNCATE|REPLACE)',
                "Dangerous SQL operation detected in db.sql()",
            ),
            (
                r'frappe\.db\.sql\s*\(\s*[\'"](?:DELETE|DROP|INSERT|UPDATE|ALTER|CREATE|TRUNCATE|REPLACE)',
                "Dangerous SQL operation detected in frappe.db.sql()",
            ),
            # Python security patterns
            (r"\bexec\s*\(", "Code execution via exec() not allowed"),
            (r"\beval\s*\(", "Code evaluation via eval() not allowed"),
            (r"__import__\s*\(", "Dynamic imports via __import__() not allowed"),
            (r"compile\s*\(", "Code compilation not allowed"),
            # Frappe framework modification patterns
            (r"setattr\s*\(\s*frappe", "Frappe framework modification not allowed"),
            (r"delattr\s*\(\s*frappe", "Frappe framework modification not allowed"),
            (r"frappe\.local\s*\.\s*\w+\s*=", "Frappe local context modification not allowed"),
            (r"frappe\.session\s*\.\s*\w+\s*=", "Frappe session modification not allowed"),
            # File system access patterns (additional security)
            (r"open\s*\(", "File system access not allowed"),
            (r"file\s*\(", "File system access not allowed"),
            (r"input\s*\(", "User input not allowed in code execution"),
            (r"raw_input\s*\(", "User input not allowed in code execution"),
            # Dangerous database method patterns
            (r"db\.set_value\s*\(", "Database write operation db.set_value() not allowed"),
            (r"db\.delete\s*\(", "Database delete operation not allowed"),
            (r"db\.insert\s*\(", "Database insert operation not allowed"),
            (r"db\.truncate\s*\(", "Database truncate operation not allowed"),
            # Network access patterns
            (r"urllib", "Network access not allowed"),
            (r"requests", "Network access not allowed"),
            (r"socket", "Network access not allowed"),
            (r"http", "Network access not allowed"),
        ]

        # Scan for dangerous patterns
        for pattern, message in dangerous_patterns:
            if re.search(pattern, code, re.IGNORECASE | re.MULTILINE):
                return {
                    "success": False,
                    "error": f"🚫 Security: {message}",
                    "pattern_matched": pattern,
                    "security_violation": True,
                    "output": "",
                    "variables": {},
                }

        # Check for suspicious variable names that might indicate attempts to bypass security
        suspicious_vars = [
            r"\b_[a-zA-Z0-9_]*db[a-zA-Z0-9_]*\b",  # Variables like _db, _original_db
            r"\boriginal_[a-zA-Z0-9_]*\b",  # Variables like original_frappe
            r"\b__[a-zA-Z0-9_]+__\b",  # Dunder variables
        ]

        for pattern in suspicious_vars:
            if re.search(pattern, code, re.IGNORECASE):
                frappe.logger().warning(f"Suspicious variable pattern detected in code execution: {pattern}")

        # Additional check for SQL injection patterns in string literals
        sql_injection_patterns = [
            r'[\'"].*(?:union|select|insert|delete|update|drop).*[\'"]',
            r'[\'"].*;.*[\'"]',  # SQL statement terminators
        ]

        for pattern in sql_injection_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                frappe.logger().warning(f"Potential SQL injection pattern detected: {pattern}")

        return {"success": True}

    def _sanitize_unicode(self, code: str) -> Dict[str, Any]:
        """
        Sanitize Unicode characters in code to prevent encoding errors

        This method detects and cleans surrogate characters that can cause
        'utf-8' codec can't encode character errors during exec().

        Args:
            code (str): Python code to sanitize

        Returns:
            dict: Sanitization results with success flag and cleaned code
        """
        try:
            # Check for surrogate characters (Unicode code points 0xD800-0xDFFF)
            surrogate_found = False
            surrogate_count = 0
            cleaned_chars = []

            for i, char in enumerate(code):
                char_code = ord(char)

                # Check if this is a surrogate character
                if 0xD800 <= char_code <= 0xDFFF:
                    surrogate_found = True
                    surrogate_count += 1
                    # Replace with space to maintain code structure
                    cleaned_chars.append(" ")
                    frappe.logger().warning(
                        f"Surrogate character U+{char_code:04X} found at position {i}, replaced with space"
                    )
                else:
                    cleaned_chars.append(char)

            cleaned_code = "".join(cleaned_chars)

            # Test if the cleaned code is valid UTF-8
            try:
                cleaned_code.encode("utf-8")
            except UnicodeEncodeError as e:
                frappe.logger().error(f"Unicode encoding still failed after cleaning: {str(e)}")
                return {
                    "success": False,
                    "error": "🚫 Unicode Error: Code contains characters that cannot be encoded in UTF-8. "
                    "Please remove or replace non-standard Unicode characters.",
                    "output": "",
                    "variables": {},
                    "unicode_error": True,
                }

            result = {"success": True, "code": cleaned_code}

            # Add warning information if surrogates were found
            if surrogate_found:
                result["warning"] = f"Cleaned {surrogate_count} surrogate character(s) from code"
                frappe.logger().warning(
                    f"Unicode sanitization: {surrogate_count} surrogate characters cleaned"
                )

            return result

        except Exception as e:
            frappe.logger().error(f"Unicode sanitization failed: {str(e)}")
            return {
                "success": False,
                "error": f"🚫 Unicode Processing Error: {str(e)}",
                "output": "",
                "variables": {},
                "unicode_error": True,
            }

    def _serialize_variable(self, value: Any) -> Any:
        """Serialize a variable for JSON return"""
        try:
            # Handle pandas objects
            if hasattr(value, "to_dict"):
                return value.to_dict()
            elif hasattr(value, "to_list"):
                return value.to_list()
            elif hasattr(value, "tolist"):
                return value.tolist()

            # Handle numpy arrays
            import numpy as np

            if isinstance(value, np.ndarray):
                return value.tolist()

            # Handle basic types
            if isinstance(value, (str, int, float, bool, list, dict, tuple)):
                return value

            # Try to convert to string
            return str(value)

        except Exception:
            return f"<{type(value).__name__} object>"

    def _enhance_error_message(
        self, error_msg: str, error_traceback: str, env: Dict[str, Any], code: str
    ) -> Dict[str, Any]:
        """Provide context-aware error messages with helpful solutions"""

        # Common error patterns and their enhancements
        error_enhancements = {
            "name 'pd' is not defined": {
                "reason": "pandas library is not available in this environment",
                "solution": "Use Frappe's native data tools instead",
                "alternative_code": "# Instead of pandas, use:\ndata = frappe.get_all('DocType', fields=['*'], limit=100)\n# Or use the generate_report tool for analytics",
                "available_alternatives": ["frappe.get_all()", "frappe.get_list()", "generate_report tool"],
            },
            "name 'np' is not defined": {
                "reason": "numpy library is not available in this environment",
                "solution": "Use Python's math or statistics modules for calculations",
                "alternative_code": "# Instead of numpy, use:\nimport math\nimport statistics\n# Example: statistics.mean([1,2,3]) instead of np.mean([1,2,3])",
                "available_alternatives": ["math module", "statistics module"],
            },
            "name 'plt' is not defined": {
                "reason": "matplotlib library is not available in this environment",
                "solution": "Visualization is not supported without matplotlib",
                "alternative_code": "# Contact your administrator to install matplotlib for visualization support",
            },
            "KeyError": {
                "reason": "Column or key doesn't exist in the DataFrame/dict",
                "solution": "Check available columns/keys before accessing",
                "alternative_code": "# Check DataFrame columns:\nprint(df.columns.tolist())\n# Or check dict keys:\nprint(list(my_dict.keys()))",
                "debug_tip": f"Available variables: {', '.join([k for k in env.keys() if not k.startswith('_')])[:200]}...",
            },
            "'DataFrame' object has no attribute 'append'": {
                "reason": "df.append() was deprecated in pandas 2.0",
                "solution": "Use pd.concat() instead (this should have been auto-fixed)",
                "alternative_code": "# Instead of:\n# df = df.append(new_row, ignore_index=True)\n# Use:\ndf = pd.concat([df, new_row], ignore_index=True)",
            },
            "ValueError": {
                "reason": "Value error - often due to array length mismatch or invalid value",
                "solution": "Check array shapes and data types",
                "alternative_code": "# Check shapes:\nprint(f'Shape: {df.shape}')\nprint(f'Length: {len(my_list)}')",
            },
            "AttributeError": {
                "reason": "Attribute doesn't exist on the object",
                "solution": "Check object type and available methods",
                "alternative_code": "# Check object type and methods:\nprint(type(obj))\nprint(dir(obj))",
            },
            "IndexError": {
                "reason": "Index out of range",
                "solution": "Check list/array length before accessing by index",
                "alternative_code": "# Check length first:\nif len(my_list) > index:\n    value = my_list[index]",
            },
            "TypeError": {
                "reason": "Type error - operation not supported for these types",
                "solution": "Check data types and convert if needed",
                "alternative_code": "# Check and convert types:\nprint(type(value))\nvalue = int(value)  # or str(value), float(value), etc.",
            },
        }

        # Find matching error pattern
        enhanced_error = None
        for pattern, enhancement in error_enhancements.items():
            if pattern.lower() in error_msg.lower():
                enhanced_error = {
                    "success": False,
                    "error": error_msg,
                    "reason": enhancement.get("reason", ""),
                    "solution": enhancement.get("solution", ""),
                    "traceback": error_traceback,
                    "available_libraries": env.get("_available_libraries", []),
                    "missing_libraries": env.get("_missing_libraries", []),
                }

                if "alternative_code" in enhancement:
                    enhanced_error["alternative_code"] = enhancement["alternative_code"]

                if "available_alternatives" in enhancement:
                    enhanced_error["available_alternatives"] = enhancement["available_alternatives"]

                if "debug_tip" in enhancement:
                    enhanced_error["debug_tip"] = enhancement["debug_tip"]

                return enhanced_error

        # Return standard error with context
        return {
            "success": False,
            "error": error_msg,
            "traceback": error_traceback,
            "available_libraries": env.get("_available_libraries", []),
            "missing_libraries": env.get("_missing_libraries", []),
            "help": "Check that all required libraries are available and data types are correct. Use print() statements to debug variable values and types.",
        }
