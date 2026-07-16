# Copyright (C) 2025 Promantia
# Developer Tools Plugin — describe_app tool

import ast
import importlib
import os
import re
from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.plugins.developer_tools.tools import (
    assert_system_manager,
)

_APP_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_MAX_TREE_FILES = 50


def _get_app_title(hooks_path: str) -> str:
    try:
        with open(hooks_path) as f:  # nosemgrep: frappe-security-file-traversal — path built from validated app_name under bench/apps/  # fmt: skip
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "app_title":
                        try:
                            return str(ast.literal_eval(node.value))
                        except Exception:
                            return ""
    except Exception:
        return ""
    return ""


def _get_modules(app_root: str, app_name: str) -> list:
    modules_path = os.path.join(app_root, app_name, "modules.txt")
    try:
        with open(modules_path) as f:  # nosemgrep: frappe-security-file-traversal — path built from validated app_name under bench/apps/  # fmt: skip
            return [line.strip() for line in f.read().splitlines() if line.strip()]
    except Exception:
        return []


def _should_skip_tree(name: str) -> bool:
    if name in {"__pycache__", ".git", "node_modules"}:
        return True
    if name.endswith(".egg-info"):
        return True
    if name.endswith(".pyc"):
        return True
    if name.startswith("."):
        return True
    return False


def _get_file_annotation(filename: str, parent_dir_name: str, grandparent_dir_name: str) -> str:
    gp = grandparent_dir_name
    ext = os.path.splitext(filename)[1]

    if gp == "doctype":
        if ext == ".json":
            return "[DocType]"
        if ext == ".py":
            return "[Controller]"
    elif gp == "report":
        if ext == ".json":
            return "[Report]"
        if ext == ".py":
            return "[Script Report Controller]"
        if ext == ".js":
            return "[Report Filters]"
    elif gp == "page":
        if ext == ".json":
            return "[Page]"
    elif gp == "print_format":
        if ext == ".html":
            return "[Print Format]"
    elif gp == "workspace":
        if ext == ".json":
            return "[Workspace]"
    return ""


def _build_tree(app_root: str, max_depth: int, include_metadata: bool, max_files: int, offset: int):
    lines = [os.path.basename(app_root) + "/"]
    counter = [0]  # global index across all entries (dirs + files)
    shown = [0]  # entries actually added to lines

    def _walk(dirpath, prefix, depth):
        if depth > max_depth:
            return
        try:
            entries = os.listdir(dirpath)
        except OSError:
            return
        dirs = sorted(
            [e for e in entries if os.path.isdir(os.path.join(dirpath, e)) and not _should_skip_tree(e)]
        )
        files = sorted(
            [e for e in entries if os.path.isfile(os.path.join(dirpath, e)) and not _should_skip_tree(e)]
        )
        all_items = dirs + files
        for idx, name in enumerate(all_items):
            full_path = os.path.join(dirpath, name)
            entry_num = counter[0]
            counter[0] += 1
            in_window = offset <= entry_num < offset + max_files
            is_last = idx == len(all_items) - 1
            connector = "`-- " if is_last else "|-- "
            child_prefix = prefix + ("    " if is_last else "|   ")
            if os.path.isdir(full_path):
                if in_window:
                    lines.append(f"{prefix}{connector}{name}/")
                    shown[0] += 1
                _walk(full_path, child_prefix, depth + 1)
            else:
                if in_window:
                    parent_dir_name = os.path.basename(dirpath)
                    grandparent_dir_name = os.path.basename(os.path.dirname(dirpath))
                    annotation = _get_file_annotation(name, parent_dir_name, grandparent_dir_name)
                    meta_str = ""
                    if include_metadata:
                        try:
                            size = os.path.getsize(full_path)
                            if size < 1024:
                                meta_str = f" ({size} B)"
                            else:
                                meta_str = f" ({size / 1024:.1f} KB)"
                        except OSError:
                            pass
                    annotation_str = f"  {annotation}" if annotation else ""
                    lines.append(f"{prefix}{connector}{name}{meta_str}{annotation_str}")
                    shown[0] += 1

    _walk(app_root, "", 1)

    total = counter[0]
    shown_count = shown[0]
    truncated = (offset + shown_count) < total

    if offset > 0 or truncated:
        end = offset + shown_count
        notice = f"[showing entries {offset + 1} to {end} of {total}."
        if truncated:
            notice += f" Call with offset={offset + max_files} for more]"
        else:
            notice += "]"
        lines.append(notice)

    summary = {"total_files": total, "files_shown": shown_count, "truncated": truncated}
    return "\n".join(lines), summary


class DescribeApp(BaseTool):
    """
    Returns full directory tree and structural metadata for a Frappe app.
    Call this before creating or modifying any files in an app.
    """

    def __init__(self):
        super().__init__()
        self.name = "describe_app"
        self.description = "Get complete directory tree and structural metadata for a Frappe app. Returns app title, version, modules, annotated file tree, and artifact counts (DocTypes, Reports, Pages). IMPORTANT: Always display the tree field verbatim in a code block — do not summarize it. Display the tree field exactly as returned. Do not add any extra information, file names, or annotations next to folder names. Show only what is in the tree string. WORKFLOW: Call this tool first before creating or modifying any files in an app to understand existing structure. If app not found, suggest bench_execute with action='create_app'. If tree is truncated, ask user which subfolder to explore next. Never suggest GitHub or external sources for file browsing. Use list_app_files to explore specific folders in more detail after seeing the tree. After showing each page of files, STOP and ask the user if they want to see more before calling again with the next offset. Never auto-paginate multiple pages without user confirmation. After showing each page, end your response with a clear question on its own line: '--- Want to see the next page? (Yes/No) ---' Make it visible and easy to respond to. If tree is truncated (truncated=true), always call list_app_files with the specific subfolder path to explore further. Never ask user what they want — just explore the truncated folders."
        self.source_app = "frappe_assistant_core"

        self.inputSchema = {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": (
                        "Snake-case app name (e.g. fac_custom_code). "
                        "Lowercase letters, digits, underscores only. Must start with a letter."
                    ),
                },
                "max_depth": {
                    "type": "integer",
                    "description": "How many folder levels deep to walk. Min 1, max 6. Default 4.",
                },
                "include_metadata": {
                    "type": "boolean",
                    "description": "Show file sizes next to file names in tree. Default true.",
                },
                "offset": {
                    "type": "integer",
                    "description": "File offset for pagination. Default 0. Use multiples of 50.",
                    "default": 0,
                },
            },
            "required": ["app_name"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        assert_system_manager()

        app_name = arguments.get("app_name", "").strip()
        max_depth = arguments.get("max_depth", 4)
        include_metadata = arguments.get("include_metadata", True)
        offset = arguments.get("offset", 0)
        try:
            offset = int(offset)
        except (TypeError, ValueError):
            offset = 0
        if offset < 0:
            offset = 0

        if not app_name:
            frappe.throw(_("app_name is required."), frappe.ValidationError)

        if not _APP_NAME_RE.match(app_name):
            frappe.throw(
                _(
                    "Invalid app_name '{0}'. Must match ^[a-z][a-z0-9_]*$ "
                    "(lowercase letters, digits, underscores; must start with a letter)."
                ).format(app_name),
                frappe.ValidationError,
            )

        try:
            max_depth = int(max_depth)
        except (TypeError, ValueError):
            frappe.throw(_("max_depth must be an integer."), frappe.ValidationError)

        if not (1 <= max_depth <= 6):
            frappe.throw(_("max_depth must be between 1 and 6."), frappe.ValidationError)

        bench_path = frappe.utils.get_bench_path()
        app_root = os.path.join(bench_path, "apps", app_name)

        if not os.path.isdir(app_root):
            frappe.throw(
                _("App '{0}' not found on this bench.").format(app_name),
                frappe.ValidationError,
            )

        try:
            mod = importlib.import_module(app_name)
            v = getattr(mod, "__version__", "unknown")
            if isinstance(v, tuple):
                version = ".".join(str(x) for x in v)
            else:
                version = str(v)
        except Exception:
            version = "unknown"

        modules = _get_modules(app_root, app_name)

        hooks_path = os.path.join(app_root, app_name, "hooks.py")
        app_title = _get_app_title(hooks_path) or app_name.replace("_", " ").title()

        max_files = _MAX_TREE_FILES
        tree, summary = _build_tree(app_root, max_depth, include_metadata, max_files, offset)
        summary["modules"] = len(modules)

        return {
            "success": True,
            "app_name": app_name,
            "app_title": app_title,
            "version": version,
            "modules": modules,
            "tree": tree,
            "summary": summary,
        }


describe_app = DescribeApp
