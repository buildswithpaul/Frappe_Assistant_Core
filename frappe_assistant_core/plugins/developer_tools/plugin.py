# Copyright (C) 2025 Promantia
# Developer Tools Plugin

from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _

from frappe_assistant_core.plugins.base_plugin import BasePlugin


class DeveloperToolsPlugin(BasePlugin):
    """
    Plugin providing filesystem tools for creating
    Frappe apps and writing code files.

    Tools:
    - ensure_app    : create a custom Frappe app
    - write_file    : write code files to a custom app
    - read_file     : read files from any app
    - list_app_files: browse app directory structure
    - describe_app  : get full app structure tree
    """

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": "developer_tools",
            "display_name": "Developer Tools",
            "description": (
                "Filesystem tools for creating Frappe apps, "
                "writing Script Reports, and reading existing code."
            ),
            "version": "1.0.0",
            "author": "Promantia",
            "dependencies": [],
            "requires_restart": False,
        }

    def get_tools(self) -> List[str]:
        return [
            "bench_help",
            "bench_execute",
            "get_logs",
            "write_file",
            "read_file",
            "list_app_files",
            "describe_app",
        ]

    def validate_environment(self) -> Tuple[bool, Optional[str]]:
        """
        Validate that the bench path is resolvable
        and the apps/ directory exists.
        """
        try:
            bench_path = frappe.utils.get_bench_path()
            import os
            apps_path = os.path.join(bench_path, "apps")
            if not os.path.exists(apps_path):
                return False, f"apps/ directory not found at {apps_path}"
            return True, None
        except Exception as e:
            return False, f"Cannot resolve bench path: {str(e)}"
