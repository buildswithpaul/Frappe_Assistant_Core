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
Server Script sandbox reference tool for the Core plugin.
Lists the names a Server Script can call, read from Frappe's own sandbox globals.
"""

from typing import Any, Dict, List, Set

import frappe
from frappe import _
from frappe.utils.safe_exec import get_safe_globals

from frappe_assistant_core.core.base_tool import BaseTool

DEFAULT_LIMIT = 200
MAX_LIMIT = 500
MAX_DEPTH = 8


def _sandbox_rules() -> List[str]:
    """Fixed notes on what a Server Script may and may not do."""
    return [
        _("frappe.db.sql runs SELECT statements only."),
        _("import statements are not allowed; use the names the sandbox provides."),
        _("commit and rollback are blocked in DocType Event scripts."),
        _("DocType Event scripts get the document as doc."),
        _("API scripts read frappe.form_dict and set frappe.response."),
        _("Permission Query scripts set conditions to a SQL condition string."),
        _("Server Scripts only run when server_script_enabled is set in common_site_config.json."),
        _("Build a script switched off (Disabled) and switch it on once it is ready."),
    ]


def _walk_names(node: Any, prefix: str, depth: int, ancestors: Set[int]) -> List[str]:
    """Dotted names under a sandbox mapping. Containers are only read, nothing is called."""
    names = []
    for key, value in list(node.items()):
        if not isinstance(key, str) or key.startswith("_"):
            continue
        name = f"{prefix}.{key}" if prefix else key
        is_container = isinstance(value, dict) and value
        if is_container and depth < MAX_DEPTH and id(value) not in ancestors:
            names.extend(_walk_names(value, name, depth + 1, ancestors | {id(value)}))
        else:
            names.append(name)
    return names


def _matches_prefix(name: str, prefix: str) -> bool:
    return not prefix or name == prefix or name.startswith(prefix + ".")


class SandboxReference(BaseTool):
    """
    Tool for listing the names available inside a Server Script.

    Read-only: it walks Frappe's sandbox globals without calling anything.
    """

    def __init__(self):
        super().__init__()
        self.name = "sandbox_reference"
        self.description = (
            "List the names a Server Script can use, such as frappe.db.get_value, read from the "
            "sandbox of this site's Frappe version, plus the rules scripts run under. Use this "
            "before writing a Server Script instead of guessing what the sandbox allows. Pass a "
            "prefix such as frappe.db to narrow the list."
        )
        self.category = "Customization"
        self.requires_permission = None
        self.required_roles = ["System Manager"]

        self.inputSchema = {
            "type": "object",
            "properties": {
                "prefix": {
                    "type": "string",
                    "description": "Only names under this dotted prefix, for example frappe.db.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_LIMIT,
                    "default": DEFAULT_LIMIT,
                    "description": "Most names to return, up to 500.",
                },
            },
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Return the sorted sandbox names under the prefix."""
        prefix = (arguments.get("prefix") or "").strip().strip(".")
        limit = max(1, min(int(arguments.get("limit") or DEFAULT_LIMIT), MAX_LIMIT))

        sandbox = get_safe_globals()
        names = sorted(
            n for n in set(_walk_names(sandbox, "", 0, {id(sandbox)})) if _matches_prefix(n, prefix)
        )

        return {
            "success": True,
            "names": names[:limit],
            "truncated": len(names) > limit,
            "rules": _sandbox_rules(),
        }


sandbox_reference = SandboxReference
