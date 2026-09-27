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
Static validation for run_python_code, run before the code is executed.

The regex scanner it replaces as primary gate could be worked around by
whitespace or string tricks. This parses the code and rejects the structural
building blocks that let sandboxed code walk back to the real interpreter:

  * import statements (libraries are pre-loaded)
  * access to any private/dunder attribute (``.__class__``, ``._os``, …), the
    root of the classic ``().__class__.__subclasses__()`` style escapes
  * references to dunder names (``__builtins__``, ``__import__``)
  * builtins that read/eval/exec or reach the interpreter (``eval``, ``exec``,
    ``getattr``, ``open``, …)

This is one layer. It is paired with a curated builtins dict and attribute-safe
module wrappers in the execution subprocess, and does not replace running the
code in an isolated process. It is defense in depth, not a hard boundary.
"""

import ast


class SandboxSecurityError(Exception):
    """User code was rejected before execution for a security reason."""


# Builtins that evaluate code or hand back the object graph. Only a *reference to
# the builtin* is rejected: a variable the code itself defines under one of these
# names (``help = df.describe()``) is fine. Other builtins that are simply absent
# from the sandbox (``input``, ``dir``, …) fail with a NameError and need no rule.
_FORBIDDEN_NAMES = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "open",
        "breakpoint",
        "getattr",
        "setattr",
        "delattr",
        "globals",
        "locals",
        "vars",
    }
)


def _bound_names(tree: ast.AST) -> set:
    """Names the code binds itself: assignments, arguments, defs, loop/except/match targets."""
    bound = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            bound.add(node.name)
    return bound


def _describe(node: ast.AST) -> SandboxSecurityError:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return SandboxSecurityError(
            "Import statements are not allowed — pandas (pd), numpy (np), frappe, math, "
            "statistics, datetime, json, re and random are already available."
        )
    if isinstance(node, ast.Attribute):
        return SandboxSecurityError(
            f"Access to private attribute '.{node.attr}' is not allowed in run_python_code. "
            "Use the documented public methods (e.g. frappe.get_list, df.groupby)."
        )
    if isinstance(node, ast.Name):
        return SandboxSecurityError(f"Use of '{node.id}' is not allowed in run_python_code.")
    return SandboxSecurityError("This code is not allowed in run_python_code.")


def validate_code(code: str) -> None:
    """Raise :class:`SandboxSecurityError` if ``code`` uses a forbidden construct."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise SandboxSecurityError(f"Could not parse code: {exc.msg} (line {exc.lineno})") from None

    bound = _bound_names(tree)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise _describe(node)

        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise _describe(node)

        if isinstance(node, ast.Name):
            if node.id.startswith("__") and node.id.endswith("__"):
                raise _describe(node)
            if node.id in _FORBIDDEN_NAMES and isinstance(node.ctx, ast.Load) and node.id not in bound:
                raise _describe(node)
