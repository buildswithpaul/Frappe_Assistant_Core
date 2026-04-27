# Copyright (C) 2025 Promantia
# Developer Tools Plugin — ensure_app tool

import os
import re
import sys
from typing import Any, Dict

import frappe
import frappe.installer
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.plugins.developer_tools.tools import PROTECTED_APPS, assert_system_manager

_APP_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class EnsureApp(BaseTool):
    """
    Ensures a custom Frappe app exists in the bench.

    Idempotent: if the app directory already exists, returns immediately with
    already_existed=True. Otherwise scaffolds the app, registers it in
    sites/apps.txt, and installs it on the current site.
    """

    def __init__(self):
        super().__init__()
        self.name = "ensure_app"
        self.description = (
            "Creates and installs a new Frappe app. Automatically handles bench path detection "
            "and site installation — do NOT ask the user for bench paths, site names, or "
            "installation preferences. Just call this tool with app_name only. "
            "Idempotent — safe to call when the app may already exist."
        )
        self.category = "Developer Tools"
        self.source_app = "frappe_assistant_core"

        self.inputSchema = {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": (
                        "Snake-case app name (lowercase letters, digits, underscores; "
                        "must start with a letter). Defaults to 'fac_custom_code'."
                    ),
                    "default": "fac_custom_code",
                },
                "app_title": {
                    "type": "string",
                    "description": "Human-readable title. Defaults to title-cased app_name.",
                },
                "app_description": {
                    "type": "string",
                    "description": "Short description of the app.",
                },
            },
            "required": [],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        assert_system_manager()

        app_name = arguments.get("app_name") or "fac_custom_code"

        if not _APP_NAME_RE.match(app_name):
            frappe.throw(
                _(
                    "Invalid app_name '{0}'. Must match ^[a-z][a-z0-9_]*$ "
                    "(lowercase letters, digits, underscores; must start with a letter)."
                ).format(app_name),
                frappe.ValidationError,
            )

        if app_name in PROTECTED_APPS:
            frappe.throw(
                _("Cannot create or overwrite protected app '{0}'.").format(app_name),
                frappe.PermissionError,
            )

        bench_path = frappe.utils.get_bench_path()
        apps_path = os.path.join(bench_path, "apps")
        app_path = os.path.join(apps_path, app_name)

        # Idempotent check
        if os.path.isdir(app_path):
            return {
                "success": True,
                "already_existed": True,
                "installed": False,
                "apps_txt_updated": False,
                "app_name": app_name,
                "app_title": arguments.get("app_title") or app_name.replace("_", " ").title(),
                "message": f"App '{app_name}' already exists at {app_path}.",
            }

        app_title = arguments.get("app_title") or app_name.replace("_", " ").title()
        app_description = arguments.get("app_description") or ""

        hooks = frappe._dict(
            app_name=app_name,
            app_title=app_title,
            app_description=app_description,
            app_publisher="Promantia",
            app_email="dev@promantia.com",
            app_license="mit",
            create_github_workflow=False,
        )

        from frappe.utils.boilerplate import _create_app_boilerplate
        _create_app_boilerplate(apps_path, hooks, no_git=True)

        outer_init = os.path.join(apps_path, app_name, "__init__.py")
        if not os.path.exists(outer_init):
            open(outer_init, "w").close()

        # Create pyproject.toml so the package is pip-installable
        pyproject = os.path.join(apps_path, app_name, "pyproject.toml")
        if not os.path.exists(pyproject):
            with open(pyproject, "w") as f:
                f.write(f"""[project]
name = "{app_name}"
version = "0.0.1"

[build-system]
requires = ["flit_core >=3.2,<4"]
build-backend = "flit_core.buildapi"
""")

        # Register package using pip Python API — no subprocess, no bench CLI
        from pip._internal.cli.main import main as pip_main
        pip_main(["install", "--quiet", "-e", os.path.join(apps_path, app_name)])

        # Also add to sys.path for current process
        if app_path not in sys.path:
            sys.path.insert(0, app_path)

        # Register in sites/apps.txt
        apps_txt_path = os.path.join(bench_path, "sites", "apps.txt")
        apps_txt_updated = False
        if os.path.exists(apps_txt_path):
            with open(apps_txt_path) as f:
                existing = [line.strip() for line in f if line.strip()]
        else:
            existing = []

        if app_name not in existing:
            existing.append(app_name)
            with open(apps_txt_path, "w") as f:
                f.write("\n".join(existing) + "\n")
            apps_txt_updated = True

        frappe.db.delete("Module Def", {"app_name": app_name})
        frappe.db.commit()

        # Install using Frappe API only — no bench CLI or subprocess
        frappe.installer.install_app(app_name, set_as_patched=True)

        return {
            "success": True,
            "already_existed": False,
            "installed": True,
            "apps_txt_updated": apps_txt_updated,
            "app_name": app_name,
            "app_title": app_title,
            "message": f"App '{app_name}' created and installed successfully.",
        }


ensure_app = EnsureApp
