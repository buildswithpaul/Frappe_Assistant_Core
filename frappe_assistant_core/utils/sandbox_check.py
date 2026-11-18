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

"""Checking Server Script code against Frappe's sandbox without running it.

Frappe's own save only warns when a script does not compile, and a name missing from the
sandbox or a blocked attribute such as ``format`` fails only when the script runs.
"""

import ast
from typing import Any, List, Optional, Tuple

import frappe
from frappe import _
from frappe.utils.safe_exec import UNSAFE_ATTRIBUTES, FrappeTransformer, get_safe_globals
from RestrictedPython import compile_restricted

# Per-request data: the name is real, the keys under it belong to the current request
REQUEST_DATA_NAMES = {"form_dict", "args", "response", "session", "request"}
# Containers whose keys are data, so a key missing now can exist when the script runs
DATA_CONTAINER_NAMES = REQUEST_DATA_NAMES | {"flags", "style"}

# The replacement to suggest for a name the hackathon scripts expected in the sandbox
MISSING_NAME_HINTS = {
    "frappe.get_roles": 'frappe.get_all("Has Role", filters={"parent": frappe.session.user, '
    '"parenttype": "User"}, pluck="role")',
}


def sandbox_globals() -> Any:
    """get_safe_globals(), leaving the live request's form_dict as it found it."""
    form_dict = getattr(frappe.local, "form_dict", None)
    snapshot = dict(form_dict) if form_dict is not None else None
    try:
        return get_safe_globals()
    finally:
        # Frappe deletes the "_" cache-buster key from the live form_dict while building globals
        if snapshot is not None:
            for key, value in snapshot.items():
                form_dict.setdefault(key, value)


def _compile_problems(script: str) -> List[str]:
    """RestrictedPython's compile errors, each already prefixed with its line."""
    try:
        compile_restricted(script, policy=FrappeTransformer)
    except SyntaxError as e:
        messages = e.args[0] if e.args and isinstance(e.args[0], tuple) else (str(e),)
        return [str(message) for message in messages]
    return []


def _dotted_chain(node: ast.Attribute) -> Optional[List[str]]:
    """["frappe", "db", "get_value"] for frappe.db.get_value; None unless it starts at a name."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return parts[::-1]


def _missing_name(chain: List[str], sandbox: Any) -> Optional[str]:
    """The dotted prefix of ``chain`` that the sandbox does not have, if any."""
    current = sandbox.get(chain[0])
    for depth, part in enumerate(chain[1:], start=1):
        if not isinstance(current, dict) or chain[depth - 1] in DATA_CONTAINER_NAMES:
            return None
        if part not in current:
            return ".".join(chain[: depth + 1])
        current = current[part]
    return None


def _missing_name_problem(line: int, name: str) -> str:
    hint = MISSING_NAME_HINTS.get(name)
    if hint:
        return _("Line {0}: {1} is not available in the Server Script sandbox. Use {2} instead.").format(
            line, name, hint
        )
    return _(
        "Line {0}: {1} is not available in the Server Script sandbox. Call sandbox_reference to see what is."
    ).format(line, name)


def _name_problems(tree: ast.AST, sandbox: Any) -> List[Tuple[int, str]]:
    """(line, problem) for blocked attributes such as format, and sandbox names that do not exist."""
    assigned = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }
    problems, reported = [], set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if node.attr in UNSAFE_ATTRIBUTES:
            message = _(
                "Line {0}: .{1}() is blocked in the Server Script sandbox. Use an f-string, "
                'such as f"{{name}} items", instead.'
            ).format(node.lineno, node.attr)
            problems.append((node.lineno, message))
            continue
        chain = _dotted_chain(node)
        if not chain or chain[0] in assigned or chain[0] not in sandbox:
            continue
        missing = _missing_name(chain, sandbox)
        if missing and missing not in reported:
            reported.add(missing)
            problems.append((node.lineno, _missing_name_problem(node.lineno, missing)))
    return problems


def sandbox_problems(script: str) -> List[str]:
    """Why ``script`` would fail in the Server Script sandbox, one line each; empty when it would not."""
    problems = _compile_problems(script)
    if problems:
        return problems
    # ast.walk goes breadth first, so sort back into line order
    return [message for _line, message in sorted(_name_problems(ast.parse(script), sandbox_globals()))]
