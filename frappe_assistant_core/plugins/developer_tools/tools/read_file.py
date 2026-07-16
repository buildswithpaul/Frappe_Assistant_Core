# Copyright (C) 2025 Promantia
# Developer Tools Plugin — read_file tool

import os
from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.plugins.developer_tools.tools import (
    assert_system_manager,
    resolve_and_validate_path,
)

ALLOWED_EXTENSIONS = {".py", ".js", ".json", ".html", ".css", ".txt", ".md"}
_MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


class ReadFile(BaseTool):
    """
    Reads a source file from any Frappe app on the bench.
    Use this to study existing code patterns before generating new code.
    """

    def __init__(self):
        super().__init__()
        self.name = "read_file"
        self.description = (
            "Read any source file from a Frappe app "
            "on the bench. Returns file content with "
            "line numbers, size, and truncation info. "
            "IMPORTANT: Always call describe_app first "
            "to get the exact file path from the tree. "
            "Never guess or construct paths manually. "
            "WORKFLOW: Call describe_app to see the "
            "app structure → identify the exact file "
            "path from the tree → call read_file with "
            "that exact path."
        )
        self.source_app = "frappe_assistant_core"

        self.inputSchema = {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": (
                        "Path to the file relative to bench/apps/. "
                        "Example: 'erpnext/erpnext/accounts/report/accounts_receivable/accounts_receivable.py'"
                    ),
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Maximum lines to return. Min 1, max 2000. Default 500.",
                    "default": 500,
                },
                "offset": {
                    "type": "integer",
                    "description": "Line offset for pagination. Default 0.",
                    "default": 0,
                },
            },
            "required": ["file_path"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        assert_system_manager()

        file_path = arguments.get("file_path", "").strip()
        if not file_path:
            frappe.throw(_("file_path is required."), frappe.ValidationError)

        # Coerce and validate max_lines
        raw_max_lines = arguments.get("max_lines", 500)
        try:
            max_lines = int(raw_max_lines)
        except (TypeError, ValueError):
            frappe.throw(_("max_lines must be an integer."), frappe.ValidationError)
        if max_lines < 1 or max_lines > 2000:
            frappe.throw(
                _("max_lines must be between 1 and 2000. Got: {0}").format(max_lines),
                frappe.ValidationError,
            )

        offset = int(arguments.get("offset", 0))
        if offset < 0:
            offset = 0

        abs_path = resolve_and_validate_path(file_path)

        ext = os.path.splitext(abs_path)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            frappe.throw(
                _("File type '{0}' is not allowed. Allowed: {1}").format(
                    ext or "(none)", " ".join(sorted(ALLOWED_EXTENSIONS))
                ),
                frappe.ValidationError,
            )

        if not os.path.isfile(abs_path):
            frappe.throw(
                _("File not found: '{0}'").format(file_path),
                frappe.ValidationError,
            )

        size_bytes = os.path.getsize(abs_path)
        if size_bytes > _MAX_FILE_SIZE_BYTES:
            frappe.throw(
                _("File too large ({0} MB). Maximum allowed size is 5 MB.").format(
                    round(size_bytes / (1024 * 1024), 1)
                ),
                frappe.ValidationError,
            )

        with open(  # nosemgrep: frappe-security-file-traversal — path validated by resolve_and_validate_path()
            abs_path, encoding="utf-8", errors="replace"
        ) as f:
            raw = f.read()

        all_lines = raw.splitlines()
        total_lines = len(all_lines)

        lines_to_return = all_lines[offset : offset + max_lines]
        truncated = (offset + len(lines_to_return)) < total_lines

        content = "\n".join(lines_to_return)
        if truncated:
            end = offset + len(lines_to_return)
            content += (
                f"\n[showing lines {offset + 1} to {end} of {total_lines}. Call with offset={end} for more]"
            )

        result = {
            "success": True,
            "file_path": file_path,
            "content": content,
            "lines": len(lines_to_return),
            "total_lines": total_lines,
            "truncated": truncated,
            "size_bytes": size_bytes,
        }

        if total_lines == 0:
            result["warning"] = "File is empty."

        return result


read_file = ReadFile
