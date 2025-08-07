# -*- coding: utf-8 -*-
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

import frappe
from frappe import _
import sys
import io
import traceback
from typing import Dict, Any
from contextlib import redirect_stdout, redirect_stderr
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
        self.description = self._get_dynamic_description()
        self.requires_permission = None  # Available to all users
        
        self.inputSchema = {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute. IMPORTANT: Do NOT use import statements - all libraries are pre-loaded and ready to use: pd (pandas), np (numpy), plt (matplotlib), sns (seaborn), frappe, math, datetime, json, re, random. Example: df = pd.DataFrame({'A': [1,2,3]}); plt.plot([1,2,3])"
                },
                "data_query": {
                    "type": "object",
                    "description": "Query to fetch data and make it available as 'data' variable",
                    "properties": {
                        "doctype": {"type": "string"},
                        "fields": {"type": "array", "items": {"type": "string"}},
                        "filters": {"type": "object"},
                        "limit": {"type": "integer", "default": 100}
                    }
                },
                "timeout": {
                    "type": "integer",
                    "description": "Execution timeout in seconds (default: 30)",
                    "default": 30,
                    "minimum": 1,
                    "maximum": 300
                },
                "capture_output": {
                    "type": "boolean",
                    "description": "Whether to capture print output (default: true)",
                    "default": True
                },
                "return_variables": {
                    "type": "array",
                    "description": "Variable names to return values for",
                    "items": {"type": "string"}
                }
            },
            "required": ["code"]
        }
    
    def _get_dynamic_description(self) -> str:
        """Generate description based on current streaming settings"""
        base_description = """🛡️ Execute Python code safely with SECURE database access and proper user context.

🔒 **ENTERPRISE SECURITY FEATURES**:
• ✅ **Read-Only Database**: Only SELECT queries allowed (no DELETE/UPDATE/DROP)
• ✅ **User Context Management**: All operations run under your user with proper permissions
• ✅ **Code Security Scanning**: Dangerous operations blocked before execution
• ✅ **Unicode Sanitization**: Surrogate characters cleaned to prevent encoding errors
• ✅ **Audit Trail**: All executions logged with user attribution
• ✅ **System Manager Required**: Role-based access control enforced

🚫 **NO IMPORTS NEEDED** - All libraries pre-loaded and ready:
• **pd** (pandas) - Data manipulation: `df = pd.DataFrame({'A': [1,2,3]})`
• **np** (numpy) - Numerical operations: `arr = np.array([1,2,3])`  
• **plt** (matplotlib) - Plotting: `plt.plot([1,2,3]); plt.show()`
• **sns** (seaborn) - Statistical visualization: `sns.scatterplot(data=df, x='A', y='B')`
• **db** - 🛡️ READ-ONLY database: `db.sql("SELECT name FROM tabUser LIMIT 5")`
• **frappe** - Frappe utilities: `frappe.get_all('Sales Invoice', limit=10)`
• **current_user** - Your username for context: `print(f"Running as: {current_user}")`
• **Standard libraries**: math, datetime, json, re, random, statistics

⚠️ **SECURITY NOTES**:
• Only SELECT/SHOW/DESCRIBE database queries allowed
• DELETE, UPDATE, INSERT, DROP operations are BLOCKED
• All database access respects your user permissions
• Code is scanned for security violations before execution
• Execution context is properly audited and logged

💡 **Example Safe Usage**:
```python
# ✅ Data analysis (ALLOWED)
sales = db.sql("SELECT grand_total, posting_date FROM `tabSales Invoice` WHERE docstatus = 1 LIMIT 100")
df = pd.DataFrame(sales)
print(f"Average sale: {df['grand_total'].mean()}")

# 🚫 Data modification (BLOCKED)
# db.sql("DELETE FROM tabUser")  # This will be blocked with security error
```

🎯 **Perfect for**: Data analysis, reporting, visualization, statistical calculations - all with enterprise-grade security."""
        
        try:
            from frappe_assistant_core.utils.streaming_manager import get_streaming_manager
            streaming_manager = get_streaming_manager()
            streaming_suffix = streaming_manager.get_tool_description_suffix(self.name)
            return base_description + streaming_suffix
            
        except Exception as e:
            frappe.logger("execute_python_code").warning(f"Failed to load streaming configuration: {str(e)}")
            return base_description
    
    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Python code safely with secure user context and read-only database"""
        code = arguments.get("code", "")
        data_query = arguments.get("data_query")
        timeout = arguments.get("timeout", 30)
        capture_output = arguments.get("capture_output", True)
        return_variables = arguments.get("return_variables", [])
        
        # Import security utilities
        from frappe_assistant_core.utils.user_context import secure_user_context, audit_code_execution
        
        if not code.strip():
            return {
                "success": False,
                "error": "No code provided",
                "output": "",
                "variables": {}
            }
        
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
                    
                    # Setup secure execution environment with read-only database
                    execution_globals = self._setup_secure_execution_environment(current_user)
                    
                    # Handle data query if provided
                    if data_query:
                        try:
                            data = self._fetch_data_from_query(data_query)
                            execution_globals['data'] = data
                        except Exception as e:
                            return {
                                "success": False,
                                "error": f"Error fetching data: {str(e)}",
                                "output": "",
                                "variables": {},
                                "user_context": current_user
                            }
                    
                    # Execute the code safely
                    return self._execute_code_with_timeout(
                        code, execution_globals, timeout, capture_output, 
                        return_variables, current_user, audit_info
                    )
                    
        except frappe.PermissionError as e:
            return {
                "success": False,
                "error": str(e),
                "output": "",
                "variables": {},
                "security_error": True
            }
        except Exception as e:
            frappe.logger().error(f"Code execution error: {str(e)}")
            return {
                "success": False,
                "error": f"Execution failed: {str(e)}",
                "output": "",
                "variables": {}
            }
    
    def _execute_code_with_timeout(self, code: str, execution_globals: Dict[str, Any], 
                                 timeout: int, capture_output: bool, return_variables: list,
                                 current_user: str, audit_info: Dict[str, Any]) -> Dict[str, Any]:
        """Execute code with timeout and proper error handling"""
        
        # Capture output
        output = ""
        error = ""
        variables = {}
        
        try:
            if capture_output:
                stdout_capture = io.StringIO()
                stderr_capture = io.StringIO()
                
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    # Execute code with user context preserved and Unicode handling
                    try:
                        exec(code, execution_globals)
                    except UnicodeEncodeError as unicode_error:
                        # Handle Unicode encoding errors during execution
                        raise UnicodeEncodeError(
                            unicode_error.encoding,
                            unicode_error.object, 
                            unicode_error.start,
                            unicode_error.end,
                            f"Unicode encoding error during code execution. "
                            f"Code contains characters that cannot be encoded. "
                            f"Original error: {unicode_error.reason}"
                        )
                
                output = stdout_capture.getvalue()
                error = stderr_capture.getvalue()
            else:
                # Execute without capturing output
                exec(code, execution_globals)
            
            # Extract all user-defined variables (not built-ins or system variables)
            excluded_vars = {
                'frappe', 'pd', 'np', 'plt', 'sns', 'data', 'current_user', 'db',
                'get_doc', 'get_list', 'get_all', 'get_single', 'math', 'datetime', 
                'json', 're', 'random', 'statistics', 'decimal', 'fractions',
                # Pre-loaded libraries that shouldn't appear in response
                'pandas', 'numpy', 'matplotlib', 'seaborn', 'plotly', 'scipy', 'stats',
                'go', 'px', '__builtins__', '__name__', '__doc__', '__package__',
                '__loader__', '__spec__', '__annotations__', '__cached__'
            }
            
            for var_name, var_value in execution_globals.items():
                if (not var_name.startswith('_') and 
                    var_name not in excluded_vars and 
                    var_name not in execution_globals.get('__builtins__', {})):
                    try:
                        # Try to serialize the variable
                        variables[var_name] = self._serialize_variable(var_value)
                    except Exception as e:
                        variables[var_name] = f"<Could not serialize: {str(e)}>"
            
            # Also extract specifically requested variables
            if return_variables:
                for var_name in return_variables:
                    if var_name in execution_globals and var_name not in variables:
                        try:
                            var_value = execution_globals[var_name]
                            variables[var_name] = self._serialize_variable(var_value)
                        except Exception as e:
                            variables[var_name] = f"<Could not serialize: {str(e)}>"
            
            result = {
                "success": True,
                "output": output,
                "error": error,
                "variables": variables,
                "user_context": current_user,
                "execution_info": {
                    "lines_executed": len(code.split('\n')),
                    "variables_returned": len(variables),
                    "execution_id": audit_info.get("execution_id"),
                    "executed_by": current_user
                }
            }
            
            return result
            
        except UnicodeEncodeError as unicode_error:
            error_msg = (f"🚫 Unicode Error: Code contains characters that cannot be encoded in UTF-8. "
                        f"Character '\\u{ord(unicode_error.object[unicode_error.start]):04x}' at position {unicode_error.start} "
                        f"cannot be processed. Please remove or replace non-standard Unicode characters.")
            
            self.logger.error(f"Unicode encoding error for user {current_user}: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg,
                "traceback": traceback.format_exc(),
                "output": output,
                "variables": {},
                "user_context": current_user,
                "unicode_error": True,
                "execution_info": {
                    "execution_id": audit_info.get("execution_id"),
                    "executed_by": current_user
                }
            }
            
        except Exception as e:
            error_msg = str(e)
            error_traceback = traceback.format_exc()
            
            self.logger.error(f"Python execution error for user {current_user}: {error_msg}")
            # Provide helpful error message for Unicode issues
            if "surrogates not allowed" in error_msg or "UnicodeEncodeError" in error_msg:
                error_msg = f"""Unicode encoding error: {error_msg}

🚨 This error occurs when your code contains invalid Unicode characters (surrogates).
💡 Common causes:
   • Copy-pasting code from Word documents, PDFs, or certain web pages
   • Data with mixed encodings or corrupted text
   • Special characters that aren't valid UTF-8

✅ Solutions:
   • Re-type the code manually instead of copy-pasting
   • Check for unusual characters around position 1030 in your code
   • Use plain text editors when preparing code"""
            
            self.logger.error(f"Python execution error: {error_msg}")            
            result = {
                "success": False,
                "error": error_msg,
                "traceback": error_traceback,
                "output": output,
                "variables": {},
                "user_context": current_user,
                "execution_info": {
                    "execution_id": audit_info.get("execution_id"),
                    "executed_by": current_user
                }
            }
            
            return result
    
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
                        cleaned_chars.append(' ')
                        surrogate_count += 1
                    else:
                        cleaned_chars.append(char)
                
                cleaned_code = ''.join(cleaned_chars)
                
                # Provide a helpful warning
                warning_msg = f"⚠️  Code contained {surrogate_count} invalid Unicode surrogate character(s) that were replaced with spaces. This often happens when copying code from certain documents or web pages."
                
                return {
                    "success": True,
                    "code": cleaned_code,
                    "warning": warning_msg
                }
            
            # Try encoding to UTF-8 to catch other encoding issues
            try:
                code.encode('utf-8')
            except UnicodeEncodeError as e:
                # Handle other encoding errors
                cleaned_code = code.encode('utf-8', errors='replace').decode('utf-8')
                return {
                    "success": True,
                    "code": cleaned_code,
                    "warning": f"⚠️  Code contained invalid Unicode characters that were replaced. Original error: {str(e)}"
                }
            
            # Code is clean
            return {
                "success": True,
                "code": code
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error sanitizing Unicode in code: {str(e)}",
                "output": "",
                "variables": {}
            }
    
    def _check_and_handle_imports(self, code: str) -> Dict[str, Any]:
        """Check for import statements and provide helpful guidance"""
        import re
        
        lines = code.split('\n')
        import_lines = []
        processed_lines = []
        
        # Common import patterns that can be safely removed (exact matches)
        safe_replacements = {
            'import pandas as pd': '# pandas is pre-loaded as "pd"',
            'import numpy as np': '# numpy is pre-loaded as "np"', 
            'import matplotlib.pyplot as plt': '# matplotlib is pre-loaded as "plt"',
            'import seaborn as sns': '# seaborn is pre-loaded as "sns"',
            'import frappe': '# frappe is pre-loaded',
            'import math': '# math is pre-loaded',
            'import datetime': '# datetime is pre-loaded',
            'import json': '# json is pre-loaded',
            'import re': '# re is pre-loaded',
            'import random': '# random is pre-loaded'
        }
        
        # Safe import prefixes (for partial matches)
        safe_prefixes = {
            'from datetime import': '# datetime is pre-loaded',
            'from math import': '# math is pre-loaded'
        }
        
        for i, line in enumerate(lines):
            stripped_line = line.strip()
            
            # Check if this is an import statement
            if stripped_line.startswith('import ') or stripped_line.startswith('from '):
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
                    processed_lines.append(f'# REMOVED: {stripped_line} - library not available or not needed')
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
{chr(10).join(f'   Line {line_num}: {stmt}' for line_num, stmt in problematic_imports)}

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
                
                return {
                    "success": False,
                    "error": error_msg,
                    "output": "",
                    "variables": {}
                }
        
        return {
            "success": True,
            "code": '\n'.join(processed_lines)
        }
    
    def _remove_dangerous_imports(self, code: str) -> str:
        """Remove dangerous import statements for security, but allow safe ones"""
        import re
        
        # Define safe modules that are allowed
        safe_modules = {
            'math', 'statistics', 'decimal', 'fractions', 'datetime', 'json', 're', 'random',
            'pandas', 'numpy', 'matplotlib', 'seaborn', 'plotly', 'scipy',
            'pd', 'np', 'plt', 'sns', 'go', 'px', 'stats'
        }
        
        # Define dangerous modules to block
        dangerous_modules = {
            'os', 'sys', 'subprocess', 'socket', 'urllib', 'requests', 'http',
            'ftplib', 'smtplib', 'imaplib', 'poplib', 'telnetlib', 'socketserver',
            'threading', 'multiprocessing', 'asyncio', 'concurrent',
            'ctypes', 'imp', 'importlib', '__import__', 'exec', 'eval',
            'file', 'open', 'input', 'raw_input'
        }
        
        lines = code.split('\n')
        cleaned_lines = []
        
        for line in lines:
            stripped_line = line.strip()
            
            # Check for import statements
            if stripped_line.startswith('import ') or stripped_line.startswith('from '):
                # Extract module name
                if stripped_line.startswith('import '):
                    module = stripped_line[7:].split()[0].split('.')[0]
                elif stripped_line.startswith('from '):
                    module = stripped_line[5:].split()[0].split('.')[0]
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
        
        return '\n'.join(cleaned_lines)
    
    def _fetch_data_from_query(self, data_query: Dict[str, Any]) -> list:
        """Fetch data from Frappe based on query parameters"""
        doctype = data_query.get('doctype')
        fields = data_query.get('fields', ['name'])
        filters = data_query.get('filters', {})
        limit = data_query.get('limit', 100)
        
        if not doctype:
            raise ValueError("DocType is required for data query")
        
        # Check permission
        if not frappe.has_permission(doctype, "read"):
            raise frappe.PermissionError(f"No permission to read {doctype}")
        
        # Use raw SQL to avoid frappe._dict objects that cause __array_struct__ issues
        try:
            # Build SQL query manually to get clean data
            field_list = ", ".join([f"`{field}`" for field in fields])
            table_name = f"tab{doctype}"
            
            # Build WHERE clause from filters
            where_conditions = []
            values = []
            
            for key, value in filters.items():
                if isinstance(value, (list, tuple)):
                    placeholders = ", ".join(["%s"] * len(value))
                    where_conditions.append(f"`{key}` IN ({placeholders})")
                    values.extend(value)
                elif value is None:
                    where_conditions.append(f"`{key}` IS NULL")
                else:
                    where_conditions.append(f"`{key}` = %s")
                    values.append(value)
            
            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
            
            query = f"""
                SELECT {field_list}
                FROM `{table_name}`
                {where_clause}
                ORDER BY creation DESC
                LIMIT {limit}
            """
            
            # Execute raw SQL to get clean data without frappe._dict objects
            result = frappe.db.sql(query, values, as_dict=True)
            
            # Convert to plain Python dicts to avoid array interface issues
            return [dict(row) for row in result]
            
        except Exception as e:
            # Fallback to get_all with conversion if SQL approach fails
            frappe.log_error(f"SQL data query failed: {str(e)}")
            
            raw_data = frappe.get_all(
                doctype,
                fields=fields,
                filters=filters,
                limit=limit
            )
            
            # Convert frappe._dict objects to plain dicts
            return [dict(row) for row in raw_data]
    
    def _setup_execution_environment(self) -> Dict[str, Any]:
        """Legacy method - use _setup_secure_execution_environment instead"""
        frappe.logger().warning("Using legacy _setup_execution_environment - should use secure version")
        return self._setup_secure_execution_environment("legacy_user")
    
    def _setup_secure_execution_environment(self, current_user: str) -> Dict[str, Any]:
        """Setup secure execution environment with read-only database and user context"""
        from frappe_assistant_core.utils.read_only_db import ReadOnlyDatabase
        
        # Base environment with safe built-ins only
        env = {
            '__builtins__': {
                # Safe built-ins for data manipulation and analysis
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'set': set,
                'range': range,
                'enumerate': enumerate,
                'zip': zip,
                'map': map,
                'filter': filter,
                'sorted': sorted,
                'sum': sum,
                'min': min,
                'max': max,
                'abs': abs,
                'round': round,
                'print': print,
                'type': type,
                'isinstance': isinstance,
                'hasattr': hasattr,
                'getattr': getattr,
                # Note: setattr removed for security
                'Exception': Exception,
                'ValueError': ValueError,
                'TypeError': TypeError,
                'KeyError': KeyError,
                'IndexError': IndexError,
                'AttributeError': AttributeError,
                'NameError': NameError,
                'ZeroDivisionError': ZeroDivisionError,
                'StopIteration': StopIteration,
            }
        }
        
        # Add standard libraries (safe mathematical and utility libraries)
        import math
        import statistics
        import decimal
        import fractions
        import datetime
        import json
        import re
        import random
        
        env.update({
            'math': math,
            'statistics': statistics,
            'decimal': decimal,
            'fractions': fractions,
            'datetime': datetime,
            'json': json,
            're': re,
            'random': random
        })
        
        # Add data science libraries
        try:
            import pandas as pd
            import numpy as np
            import matplotlib.pyplot as plt
            import seaborn as sns
            
            env.update({
                'pd': pd,
                'pandas': pd,
                'np': np,
                'numpy': np,
                'plt': plt,
                'matplotlib': plt,
                'sns': sns,
                'seaborn': sns
            })
            
            # Try to add plotly if available
            try:
                import plotly.graph_objects as go
                import plotly.express as px
                env.update({
                    'go': go,
                    'px': px,
                    'plotly': {'graph_objects': go, 'express': px}
                })
            except ImportError:
                pass
            
            # Add scipy if available
            try:
                import scipy
                import scipy.stats as stats
                env.update({
                    'scipy': scipy,
                    'stats': stats
                })
            except ImportError:
                pass
                
        except ImportError as e:
            self.logger.warning(f"Some data science libraries not available: {str(e)}")
        
        # Add SECURE Frappe utilities with read-only database wrapper
        secure_db = ReadOnlyDatabase(frappe.db)
        
        env.update({
            'frappe': frappe,  # Keep frappe for utility functions
            'get_doc': frappe.get_doc,  # Permission-checked by default
            'get_list': frappe.get_list,  # Permission-checked by default
            'get_all': frappe.get_all,  # Permission-checked by default
            'get_single': frappe.get_single,  # Permission-checked by default
            'db': secure_db,  # 🛡️ READ-ONLY database wrapper instead of frappe.db
            'current_user': current_user,  # 👤 Current user context for reference
        })
        
        # Log security setup
        frappe.logger().info(
            f"Secure execution environment setup complete - User: {current_user}, "
            f"DB: Read-only wrapper, Libraries: {len(env)} variables available"
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
            (r'db\.sql\s*\(\s*[\'"](?:DELETE|DROP|INSERT|UPDATE|ALTER|CREATE|TRUNCATE|REPLACE)', 
             'Dangerous SQL operation detected in db.sql()'),
            (r'frappe\.db\.sql\s*\(\s*[\'"](?:DELETE|DROP|INSERT|UPDATE|ALTER|CREATE|TRUNCATE|REPLACE)', 
             'Dangerous SQL operation detected in frappe.db.sql()'),
             
            # Python security patterns
            (r'\bexec\s*\(', 'Code execution via exec() not allowed'),
            (r'\beval\s*\(', 'Code evaluation via eval() not allowed'),
            (r'__import__\s*\(', 'Dynamic imports via __import__() not allowed'),
            (r'compile\s*\(', 'Code compilation not allowed'),
            
            # Frappe framework modification patterns
            (r'setattr\s*\(\s*frappe', 'Frappe framework modification not allowed'),
            (r'delattr\s*\(\s*frappe', 'Frappe framework modification not allowed'),
            (r'frappe\.local\s*\.\s*\w+\s*=', 'Frappe local context modification not allowed'),
            (r'frappe\.session\s*\.\s*\w+\s*=', 'Frappe session modification not allowed'),
            
            # File system access patterns (additional security)
            (r'open\s*\(', 'File system access not allowed'),
            (r'file\s*\(', 'File system access not allowed'),
            (r'input\s*\(', 'User input not allowed in code execution'),
            (r'raw_input\s*\(', 'User input not allowed in code execution'),
            
            # Dangerous database method patterns
            (r'db\.set_value\s*\(', 'Database write operation db.set_value() not allowed'),
            (r'db\.delete\s*\(', 'Database delete operation not allowed'),
            (r'db\.insert\s*\(', 'Database insert operation not allowed'),
            (r'db\.truncate\s*\(', 'Database truncate operation not allowed'),
            
            # Network access patterns
            (r'urllib', 'Network access not allowed'),
            (r'requests', 'Network access not allowed'),
            (r'socket', 'Network access not allowed'),
            (r'http', 'Network access not allowed'),
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
                    "variables": {}
                }
        
        # Check for suspicious variable names that might indicate attempts to bypass security
        suspicious_vars = [
            r'\b_[a-zA-Z0-9_]*db[a-zA-Z0-9_]*\b',  # Variables like _db, _original_db
            r'\boriginal_[a-zA-Z0-9_]*\b',          # Variables like original_frappe
            r'\b__[a-zA-Z0-9_]+__\b'                # Dunder variables
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
                    cleaned_chars.append(' ')
                    frappe.logger().warning(
                        f"Surrogate character U+{char_code:04X} found at position {i}, replaced with space"
                    )
                else:
                    cleaned_chars.append(char)
            
            cleaned_code = ''.join(cleaned_chars)
            
            # Test if the cleaned code is valid UTF-8
            try:
                cleaned_code.encode('utf-8')
            except UnicodeEncodeError as e:
                frappe.logger().error(f"Unicode encoding still failed after cleaning: {str(e)}")
                return {
                    "success": False,
                    "error": f"🚫 Unicode Error: Code contains characters that cannot be encoded in UTF-8. "
                            f"Please remove or replace non-standard Unicode characters.",
                    "output": "",
                    "variables": {},
                    "unicode_error": True
                }
            
            result = {
                "success": True,
                "code": cleaned_code
            }
            
            # Add warning information if surrogates were found
            if surrogate_found:
                result["warning"] = f"Cleaned {surrogate_count} surrogate character(s) from code"
                frappe.logger().warning(f"Unicode sanitization: {surrogate_count} surrogate characters cleaned")
            
            return result
            
        except Exception as e:
            frappe.logger().error(f"Unicode sanitization failed: {str(e)}")
            return {
                "success": False,
                "error": f"🚫 Unicode Processing Error: {str(e)}",
                "output": "",
                "variables": {},
                "unicode_error": True
            }
    
    def _serialize_variable(self, value: Any) -> Any:
        """Serialize a variable for JSON return"""
        try:
            # Handle pandas objects
            if hasattr(value, 'to_dict'):
                return value.to_dict()
            elif hasattr(value, 'to_list'):
                return value.to_list()
            elif hasattr(value, 'tolist'):
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
    