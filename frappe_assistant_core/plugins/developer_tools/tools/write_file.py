# Copyright (C) 2025 Promantia
# Developer Tools Plugin — write_file tool

import ast
import json
import os
from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.plugins.developer_tools.tools import (
    PROTECTED_APPS,
    assert_developer_mode,
    assert_system_manager,
    resolve_and_validate_path,
)

ALLOWED_EXTENSIONS = {".py", ".json", ".js", ".html", ".css", ".md", ".txt"}
_MAX_CONTENT_BYTES = 1_048_576  # 1 MB


def _validate_syntax(content: str, extension: str):
    if extension == ".py":
        try:
            ast.parse(content)
            return {"valid": True, "language": "python"}
        except SyntaxError as e:
            return {
                "valid": False,
                "language": "python",
                "error": f"SyntaxError: {e.msg}",
                "line": e.lineno,
                "col": e.offset,
            }
    elif extension == ".json":
        try:
            json.loads(content)
            return {"valid": True, "language": "json"}
        except json.JSONDecodeError as e:
            return {
                "valid": False,
                "language": "json",
                "error": f"JSONDecodeError: {e.msg}",
                "line": e.lineno,
                "col": e.colno,
            }
    return None


class WriteFile(BaseTool):
    """
    Writes content to a file inside a custom Frappe app on the bench.
    Creates missing parent directories automatically.
    """

    def __init__(self):
        super().__init__()
        self.name = "write_file"
        self.description = (
            "Write content to a file inside a custom Frappe app on the bench. "
            "Use when user asks to create or update any file in a Frappe app — "
            "Python files, JS, JSON, HTML, CSS. "
            "Creates missing parent directories automatically. "
            "Validates Python and JSON syntax after writing and returns the result so errors can be fixed. "
            "Only works on custom apps — cannot write to frappe, erpnext, or frappe_assistant_core. "
            "WORKFLOW: Call describe_app first to understand structure. "
            "For Script Reports also call read_file on a similar existing erpnext report "
            "to understand the correct pattern before writing — for example "
            "erpnext/erpnext/accounts/report/accounts_receivable/accounts_receivable.py. "
            "Call list_app_files to confirm the target path, "
            "call read_file before overwriting existing files, "
            "then write_file. Always ask user to confirm before writing. "
            "FOLDER RULE: Always call describe_app before writing any report files. "
            "Look at the tree carefully: the app has an inner folder with the same name as the app — "
            "this is the module folder. Reports go INSIDE this module folder. "
            "Example: if describe_app shows naruto_app/naruto_app/naruto_app/, "
            "then reports go at naruto_app/naruto_app/naruto_app/report/ "
            "NOT at naruto_app/naruto_app/report/. "
            "Files sit directly inside their named folder — "
            "report/my_report/my_report.py not report/my_report/my_report/my_report.py. "
            "SCRIPT REPORT MANDATORY: A Script Report is INCOMPLETE without all 4 files. "
            "You MUST create .js file even if there are no filters — use an empty filters array: "
            "frappe.query_reports['Report Name'] = {filters: []} "
            "Never skip the .js file for any reason. "
            "REPORT SQL RULE: For all Script Reports always use frappe.db.sql() only. "
            "Never use frappe.get_all(), frappe.get_list(), or frappe.qb in report Python files. "
            'REPORT JSON RULE: Always include "modified" and "creation" keys in report JSON files. '
            'Set them to any valid datetime string such as "2025-01-01 00:00:01" as a placeholder — '
            "write_file automatically overwrites them with the real current timestamp at write time. "
            'Never use empty string "" — empty string causes NoneType TypeError on Frappe v15 migrate. '
            "AFTER WRITING FILES: When you have finished all write_file calls for a task, always ask: "
            "'Files created successfully. Should I run bench migrate now to register the changes "
            "in Frappe UI? (Yes/No)' "
            "If user says yes, call bench_execute with action='migrate'. "
            "This applies to Script Reports, DocTypes, and any other Frappe files that need "
            "migration to take effect."
        )
        self.source_app = "frappe_assistant_core"

        self.inputSchema = {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": (
                        "Path relative to bench/apps/. Must be inside a custom app. "
                        "Example: 'fac_custom_code/fac_custom_code/hooks.py'"
                    ),
                },
                "content": {
                    "type": "string",
                    "description": "Complete file content to write. Max 1 MB.",
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Whether to overwrite if file already exists. Default True.",
                    "default": True,
                },
            },
            "required": ["file_path", "content"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        assert_system_manager()
        assert_developer_mode()

        file_path = arguments.get("file_path", "").strip()
        content = arguments.get("content", "")
        overwrite = arguments.get("overwrite", True)

        if not file_path:
            frappe.throw(_("file_path is required."), frappe.ValidationError)

        content_bytes = content.encode("utf-8")
        if len(content_bytes) > _MAX_CONTENT_BYTES:
            frappe.throw(
                _("Content exceeds maximum size of 1 MB ({0} bytes).").format(len(content_bytes)),
                frappe.ValidationError,
            )

        abs_path = resolve_and_validate_path(file_path)

        bench_apps = os.path.join(frappe.utils.get_bench_path(), "apps")
        rel = os.path.relpath(abs_path, bench_apps)
        app_name = rel.split(os.sep)[0]

        if app_name in PROTECTED_APPS:
            frappe.throw(
                _("Cannot write to protected app '{0}'. Only custom apps allowed.").format(app_name),
                frappe.ValidationError,
            )

        ext = os.path.splitext(abs_path)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            frappe.throw(
                _("File extension '{0}' is not allowed. Allowed: .py .json .js .html .css .md .txt").format(
                    ext
                ),
                frappe.ValidationError,
            )

        file_exists = os.path.isfile(abs_path)
        if not overwrite and file_exists:
            frappe.throw(
                _("File already exists. Use overwrite=True to replace."),
                frappe.ValidationError,
            )

        previous_size = None
        previous_lines = None
        if file_exists:
            try:
                previous_size = os.path.getsize(abs_path)
                with open(abs_path, encoding="utf-8", errors="replace") as f:  # nosemgrep: frappe-security-file-traversal — path validated by resolve_and_validate_path()  # fmt: skip
                    previous_lines = len(f.read().splitlines())
            except OSError:
                pass

        parent_dir = os.path.dirname(abs_path)
        dirs_created = []

        if not os.path.exists(parent_dir):
            new_dirs = []
            d = parent_dir
            while not os.path.exists(d) and len(d) > len(bench_apps):
                new_dirs.append(d)
                d = os.path.dirname(d)
            new_dirs.reverse()

            os.makedirs(parent_dir, exist_ok=True)

            for new_dir in new_dirs:
                try:
                    os.chmod(new_dir, 0o755)
                except OSError:
                    pass
                dirs_created.append(os.path.relpath(new_dir, bench_apps))

        with open(abs_path, "w", encoding="utf-8") as f:  # nosemgrep: frappe-security-file-traversal — path validated by resolve_and_validate_path()  # fmt: skip
            f.write(content)

        # For JSON files, inject the real current timestamp into modified/creation.
        # This prevents Frappe from storing a stale hardcoded date and showing
        # reports as "1-2 years old" in the UI.
        if ext == ".json":
            try:
                import json as _json

                doc = _json.loads(content)
                now_str = frappe.utils.now()
                changed = False
                if "modified" in doc:
                    doc["modified"] = now_str
                    changed = True
                if "creation" in doc:
                    doc["creation"] = now_str
                    changed = True
                if changed:
                    new_content = _json.dumps(doc, indent=1)
                    with open(abs_path, "w", encoding="utf-8") as f:  # nosemgrep: frappe-security-file-traversal — path validated by resolve_and_validate_path()  # fmt: skip
                        f.write(new_content)
                    content = new_content
            except Exception:
                pass  # invalid JSON — leave as-is; validation below will report the error

        try:
            os.chmod(abs_path, 0o644)
        except OSError:
            pass

        files_created = []

        if ext == ".json" and '"report_type": "Script Report"' in content:
            init_path = os.path.join(os.path.dirname(abs_path), "__init__.py")
            if not os.path.exists(init_path):
                open(init_path, "w").close()  # nosemgrep: frappe-security-file-traversal — path validated by resolve_and_validate_path()  # fmt: skip
                try:
                    os.chmod(init_path, 0o644)
                except OSError:
                    pass
                files_created.append(os.path.relpath(init_path, bench_apps))

        lines_written = len(content.splitlines())
        validation = _validate_syntax(content, ext)

        result = {
            "success": True,
            "file_path": file_path,
            "bytes_written": len(content_bytes),
            "lines_written": lines_written,
            "created_new": not file_exists,
            "dirs_created": dirs_created,
            "files_created": files_created,
            "validation": validation,
        }

        if previous_size is not None:
            result["previous_size"] = previous_size
        if previous_lines is not None:
            result["previous_lines"] = previous_lines

        return result


write_file = WriteFile
